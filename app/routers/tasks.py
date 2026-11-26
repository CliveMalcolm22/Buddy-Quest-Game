from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.deadline_extension import DeadlineExtension
from app.models.help import HelpRequest
from app.models.notification import Notification
from app.models.point_event import PointEvent
from app.models.task import Task, TaskHistory
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.task import (
    DeadlineExtensionRequest,
    TaskCreate,
    TaskHistoryResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services.scoring import HELP_FRIEND_POINTS, task_completion_points

router = APIRouter(prefix="/tasks", tags=["tasks"])

GRACE_PERIOD = timedelta(minutes=5)


def _as_utc(value: datetime) -> datetime:
    """Treat naive database datetimes as UTC before comparing."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/", response_model=list[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(Task.created_at.desc())
    ).all()


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = Task(
        user_id=current_user.id,
        title=payload.title,
        notes=payload.notes,
        start_time=payload.start_time,
        deadline=payload.deadline,
        status="pending",
        completion_points=0,
    )

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/extend", response_model=TaskResponse)
def extend_task_deadline(
    task_id: int,
    payload: DeadlineExtensionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == current_user.id,
        )
    )

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Only pending tasks can have their deadlines extended",
        )

    if task.deadline is None:
        raise HTTPException(
            status_code=400,
            detail="This task does not have a deadline to extend",
        )

    now = datetime.now(timezone.utc)
    original_deadline = _as_utc(task.deadline)
    new_deadline = _as_utc(payload.new_deadline)

    if now >= original_deadline:
        raise HTTPException(
            status_code=409,
            detail="A deadline can only be extended before it expires",
        )

    if new_deadline <= original_deadline:
        raise HTTPException(
            status_code=400,
            detail="The new deadline must be later than the current deadline",
        )

    existing_extension = db.scalar(
        select(DeadlineExtension).where(
            DeadlineExtension.task_id == task.id
        )
    )

    if existing_extension is not None:
        raise HTTPException(
            status_code=409,
            detail="This task has already used its one deadline extension",
        )

    db.add(
        DeadlineExtension(
            task_id=task.id,
            extended_by_user_id=current_user.id,
            original_deadline=task.deadline,
            new_deadline=payload.new_deadline,
            extended_at=now,
        )
    )
    task.deadline = payload.new_deadline

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This task has already used its one deadline extension",
        )

    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == current_user.id,
        )
    )

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == current_user.id,
        )
    )

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="This task is no longer pending",
        )

    if task.deadline is None:
        raise HTTPException(
            status_code=400,
            detail="A task needs a deadline before it can be completed",
        )

    now = datetime.now(timezone.utc)
    deadline = _as_utc(task.deadline)

    # A task becomes missed after its five-minute grace period.
    if now > deadline + GRACE_PERIOD:
        task.status = "missed"
        task.completion_points = 0

        db.add(
            PointEvent(
                user_id=current_user.id,
                task_id=task.id,
                source="task_missed",
                points=0,
                description=f"Missed task: {task.title}",
            )
        )

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="This task has already been recorded",
            )

        raise HTTPException(
            status_code=409,
            detail="The task's grace period has expired; it was recorded as missed",
        )

    completion_type = "on_time" if now <= deadline else "late"
    points = task_completion_points(completion_type)

    task.status = "completed"
    task.completed_at = now
    task.completion_points = points

    db.add(
        PointEvent(
            user_id=current_user.id,
            task_id=task.id,
            source=f"task_completion_{completion_type}",
            points=points,
            description=f"{completion_type.replace('_', ' ').title()} completion: {task.title}",
        )
    )

    help_request = db.scalar(
        select(HelpRequest).where(
            HelpRequest.task_id == task.id,
            HelpRequest.status == "accepted",
        )
    )

    if help_request is not None and help_request.helper_id is not None:
        helper = db.get(User, help_request.helper_id)

        if helper is not None:
            db.add(
                PointEvent(
                    user_id=helper.id,
                    task_id=None,
                    source="help_friend",
                    points=HELP_FRIEND_POINTS,
                    description=f"Helped {current_user.username} complete: {task.title}",
                )
            )
            db.add(
                Notification(
                    user_id=helper.id,
                    message=f"You earned {HELP_FRIEND_POINTS} points for helping with {task.title}!",
                    type="help_completed",
                )
            )

        help_request.status = "completed"

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This task has already been recorded",
        )

    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == current_user.id,
        )
    )

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "pending":
        raise HTTPException(
            status_code=409,
            detail="Completed or missed tasks cannot be edited",
        )

    if task.deadline is not None:
        now = datetime.now(timezone.utc)
        if now >= _as_utc(task.deadline):
            raise HTTPException(
                status_code=409,
                detail="Tasks cannot be edited after their deadline",
            )

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == current_user.id,
        )
    )

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

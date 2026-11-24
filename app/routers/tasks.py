from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.point_event import PointEvent
from app.models.task import Task
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.scoring import task_completion_points

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

    for field, value in payload.model_dump().items():
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

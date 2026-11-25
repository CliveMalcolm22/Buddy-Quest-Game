from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task, TaskHistory
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.task import TaskCreate, TaskHistoryResponse, TaskResponse, TaskUpdate
from app.services.scheduler import get_task_scheduler

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=list[TaskResponse])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Task).where(Task.user_id == current_user.id, Task.deleted_at.is_(None)).order_by(Task.start_time, Task.id)
    ).all()


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    start_time = _as_utc(payload.start_time)
    if start_time <= now:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A task must be created before its start time.")
    task = Task(user_id=current_user.id, **payload.model_dump())
    task.start_time = start_time
    task.deadline = _as_utc(payload.deadline)
    db.add(task)
    db.flush()
    _record_history(db, task, "created")
    db.commit()
    db.refresh(task)
    get_task_scheduler().schedule_task(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _find_task(db, task_id, current_user.id)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _find_task(db, task_id, current_user.id)
    now = datetime.now(timezone.utc)
    if _as_utc(task.start_time) <= now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tasks can only be edited before their start time.")
    start_time = _as_utc(payload.start_time)
    if start_time <= now:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Start time must be in the future.")
    task.title = payload.title
    task.notes = payload.notes
    task.start_time = start_time
    task.deadline = _as_utc(payload.deadline)
    task.updated_at = now
    _record_history(db, task, "updated")
    db.commit()
    db.refresh(task)
    get_task_scheduler().schedule_task(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _find_task(db, task_id, current_user.id)
    if _as_utc(task.start_time) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tasks can only be deleted before their start time.")
    task.deleted_at = datetime.now(timezone.utc)
    _record_history(db, task, "deleted")
    db.commit()
    get_task_scheduler().unschedule_task(task.id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/{task_id}/history", response_model=list[TaskHistoryResponse])
def get_task_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _find_task(db, task_id, current_user.id, include_deleted=True)
    return db.scalars(
        select(TaskHistory).where(TaskHistory.task_id == task_id).order_by(TaskHistory.recorded_at, TaskHistory.id)
    ).all()


def _find_task(db: Session, task_id: int, user_id: int, *, include_deleted: bool = False) -> Task:
    statement = select(Task).where(Task.id == task_id, Task.user_id == user_id)
    if not include_deleted:
        statement = statement.where(Task.deleted_at.is_(None))
    task = db.scalar(statement)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _record_history(db: Session, task: Task, action: str) -> None:
    db.add(
        TaskHistory(
            task_id=task.id,
            action=action,
            title=task.title,
            notes=task.notes,
            status=task.status,
            start_time=task.start_time,
            deadline=task.deadline,
        )
    )

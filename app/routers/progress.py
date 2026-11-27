from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.point_event import PointEvent
from app.models.streak import Streak
from app.models.task import Task
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.progress import ProgressSummary, StreakResponse

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/summary", response_model=ProgressSummary)
def get_progress_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_points = db.scalar(
        select(func.coalesce(func.sum(PointEvent.points), 0)).where(
            PointEvent.user_id == current_user.id
        )
    ) or 0

    tasks_completed = db.scalar(
        select(func.count(Task.id)).where(
            Task.user_id == current_user.id,
            Task.status == "completed",
        )
    ) or 0

    tasks_pending = db.scalar(
        select(func.count(Task.id)).where(
            Task.user_id == current_user.id,
            Task.status == "pending",
        )
    ) or 0

    streak = db.scalar(
        select(Streak).where(Streak.user_id == current_user.id)
    )

    return ProgressSummary(
        total_points=total_points,
        tasks_completed=tasks_completed,
        tasks_pending=tasks_pending,
        streak=StreakResponse(
            current_streak=streak.current_streak if streak else 0,
            longest_streak=streak.longest_streak if streak else 0,
            last_active_date=streak.last_active_date if streak else None,
        ),
    )


@router.get("/weekly")
def get_weekly_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    next_monday = monday + timedelta(days=7)

    days = {
        (monday + timedelta(days=i)).date(): {
            "date": (monday + timedelta(days=i)).date().isoformat(),
            "planned_tasks": 0,
            "completed_tasks": 0,
            "points": 0,
        }
        for i in range(7)
    }

    tasks = db.scalars(
        select(Task).where(
            Task.user_id == current_user.id,
            (Task.start_time >= monday) & (Task.start_time < next_monday)
            | (Task.completed_at >= monday) & (Task.completed_at < next_monday),
        )
    ).all()

    for task in tasks:
        if task.start_time and task.start_time.date() in days:
            days[task.start_time.date()]["planned_tasks"] += 1

        if task.status == "completed" and task.completed_at:
            completed_date = task.completed_at.date()
            if completed_date in days:
                days[completed_date]["completed_tasks"] += 1

    events = db.scalars(
        select(PointEvent).where(
            PointEvent.user_id == current_user.id,
            PointEvent.created_at >= monday,
            PointEvent.created_at < next_monday,
        )
    ).all()

    for event in events:
        event_date = event.created_at.date()
        if event_date in days:
            days[event_date]["points"] += event.points

    daily_progress = []
    for day in days.values():
        planned = day["planned_tasks"]
        completed = day["completed_tasks"]
        rate = round(completed / planned * 100) if planned else 0

        daily_progress.append({
            **day,
            "completion_rate": rate,
            "qualifying_day": planned > 0 and rate >= 80,
        })

    return {
        "week_start": monday.date().isoformat(),
        "week_end": (next_monday - timedelta(days=1)).date().isoformat(),
        "days": daily_progress,
    }

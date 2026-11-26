from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Habit, HabitCompletion, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/habits", tags=["habits"])


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    frequency: str = "daily"


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_habit(
    data: HabitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.frequency not in {"daily", "weekly"}:
        raise HTTPException(status_code=400, detail="Frequency must be daily or weekly")

    habit = Habit(
        user_id=current_user.id,
        name=data.name.strip(),
        description=data.description,
        frequency=data.frequency,
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)

    return {
        "id": habit.id,
        "name": habit.name,
        "description": habit.description,
        "frequency": habit.frequency,
        "active": habit.active,
    }


@router.get("/")
def list_habits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    habits = db.scalars(
        select(Habit)
        .where(Habit.user_id == current_user.id)
        .order_by(Habit.created_at.desc())
    ).all()

    results = []
    for habit in habits:
        completions = db.scalars(
            select(HabitCompletion.completion_date)
            .where(HabitCompletion.habit_id == habit.id)
            .order_by(HabitCompletion.completion_date.desc())
        ).all()

        results.append({
            "id": habit.id,
            "name": habit.name,
            "description": habit.description,
            "frequency": habit.frequency,
            "active": habit.active,
            "total_completions": len(completions),
            "last_completed": completions[0].isoformat() if completions else None,
        })

    return results


@router.post("/{habit_id}/complete")
def complete_habit(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    habit = db.scalar(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    )
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    if not habit.active:
        raise HTTPException(status_code=400, detail="Habit is inactive")

    today = date.today()
    existing = db.scalar(
        select(HabitCompletion).where(
            HabitCompletion.habit_id == habit.id,
            HabitCompletion.completion_date == today,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Habit already completed today")

    completion = HabitCompletion(
        habit_id=habit.id,
        completion_date=today,
    )
    db.add(completion)
    db.commit()

    return {
        "message": "Habit completed",
        "habit_id": habit.id,
        "completion_date": today.isoformat(),
    }


@router.get("/{habit_id}/progress")
def habit_progress(
    habit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    habit = db.scalar(
        select(Habit).where(
            Habit.id == habit_id,
            Habit.user_id == current_user.id,
        )
    )
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    dates = db.scalars(
        select(HabitCompletion.completion_date)
        .where(HabitCompletion.habit_id == habit.id)
        .order_by(HabitCompletion.completion_date.desc())
    ).all()

    completed_dates = set(dates)
    streak = 0
    check_date = date.today()

    if check_date not in completed_dates:
        check_date -= timedelta(days=1)

    while check_date in completed_dates:
        streak += 1
        check_date -= timedelta(days=1)

    return {
        "habit_id": habit.id,
        "habit_name": habit.name,
        "total_completions": len(dates),
        "current_streak": streak,
        "completion_dates": [day.isoformat() for day in dates],
    }

from datetime import datetime

from pydantic import BaseModel


class StreakResponse(BaseModel):
    current_streak: int = 0
    longest_streak: int = 0
    last_active_date: datetime | None = None


class ProgressSummary(BaseModel):
    total_points: int = 0
    tasks_completed: int = 0
    tasks_pending: int = 0
    streak: StreakResponse

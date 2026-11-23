from fastapi import APIRouter

from app.schemas.progress import ProgressSummary, StreakResponse

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/summary", response_model=ProgressSummary)
async def get_progress_summary():
    return {
        "total_points": 1200,
        "tasks_completed": 8,
        "tasks_pending": 2,
        "streak": {
            "current_streak": 5,
            "longest_streak": 12,
            "last_active_date": None,
        },
    }

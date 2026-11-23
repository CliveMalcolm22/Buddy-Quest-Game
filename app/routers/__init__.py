from .auth import router as auth_router
from .friends import router as friends_router
from .leaderboard import router as leaderboard_router
from .progress import router as progress_router
from .tasks import router as tasks_router

__all__ = [
    "auth_router",
    "tasks_router",
    "friends_router",
    "leaderboard_router",
    "progress_router",
]

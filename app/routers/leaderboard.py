from fastapi import APIRouter

from app.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/", response_model=LeaderboardResponse)
async def get_leaderboard():
    return {
        "leaderboard": [
            LeaderboardEntry(rank=1, username="Sarah", points=15420, is_you=False),
            LeaderboardEntry(rank=2, username="Marcus", points=14830, is_you=False),
            LeaderboardEntry(rank=3, username="You", points=12750, is_you=True),
        ]
    }

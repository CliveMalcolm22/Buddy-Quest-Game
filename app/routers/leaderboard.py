from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.friendship import Friendship
from app.models.point_event import PointEvent
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/", response_model=LeaderboardResponse)
def get_leaderboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    friendships = db.scalars(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(
                Friendship.user_id == current_user.id,
                Friendship.friend_id == current_user.id,
            ),
        )
    ).all()

    participant_ids = {current_user.id}
    for friendship in friendships:
        participant_ids.add(friendship.user_id)
        participant_ids.add(friendship.friend_id)

    weekly_points = func.coalesce(func.sum(PointEvent.points), 0).label("points")

    rows = db.execute(
        select(User.id, User.username, weekly_points)
        .outerjoin(
            PointEvent,
            and_(
                PointEvent.user_id == User.id,
                PointEvent.created_at >= monday,
            ),
        )
        .where(
            User.id.in_(participant_ids),
            User.is_active.is_(True),
        )
        .group_by(User.id, User.username)
        .order_by(desc("points"), User.username.asc())
    ).all()

    entries = [
        LeaderboardEntry(
            rank=index,
            username=row.username,
            points=int(row.points),
            is_you=row.id == current_user.id,
        )
        for index, row in enumerate(rows, start=1)
    ]

    return LeaderboardResponse(leaderboard=entries)

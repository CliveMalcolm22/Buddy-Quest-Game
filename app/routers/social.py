from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.friendship import Friendship
from app.models.help import HelpRequest
from app.models.notification import Notification
from app.models.point_event import PointEvent
from app.models.task import Task
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.scoring import (
    CHEER_POINTS,
    DAILY_CHEER_LIMIT,
    HELP_FRIEND_POINTS,
    cheer_points,
)

router = APIRouter(prefix="/social", tags=["social"])


class HelpRequestCreate(BaseModel):
    friend_id: int = Field(..., gt=0)
    task_id: int = Field(..., gt=0)
    message: str = Field(default="", max_length=1000)


class HelpRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int
    helper_id: int | None
    task_id: int | None
    message: str
    status: str
    created_at: datetime
    updated_at: datetime


def _require_friend(db: Session, user_id: int, friend_id: int) -> User:
    if user_id == friend_id:
        raise HTTPException(status_code=400, detail="You cannot interact with yourself")

    friend = db.get(User, friend_id)
    if friend is None or not friend.is_active:
        raise HTTPException(status_code=404, detail="Friend not found")

    friendship = db.scalar(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(
                (Friendship.user_id == user_id)
                & (Friendship.friend_id == friend_id),
                (Friendship.user_id == friend_id)
                & (Friendship.friend_id == user_id),
            ),
        )
    )
    if friendship is None:
        raise HTTPException(status_code=403, detail="You can only interact with accepted friends")

    return friend


@router.post("/users/{friend_id}/cheer", status_code=status.HTTP_201_CREATED)
def send_cheer(
    friend_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friend = _require_friend(db, current_user.id, friend_id)

    now = datetime.now(timezone.utc)
    midnight = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)

    cheers_today = db.scalar(
        select(func.count(PointEvent.id)).where(
            PointEvent.user_id == current_user.id,
            PointEvent.source == "cheer",
            PointEvent.created_at >= midnight,
        )
    ) or 0

    points = cheer_points(cheers_today)
    if points == 0:
        raise HTTPException(
            status_code=429,
            detail=f"You can send a maximum of {DAILY_CHEER_LIMIT} cheers per day",
        )

    db.add(
        PointEvent(
            user_id=current_user.id,
            task_id=None,
            source="cheer",
            points=CHEER_POINTS,
            description=f"Cheered for {friend.username}",
        )
    )
    db.add(
        Notification(
            user_id=friend.id,
            message=f"{current_user.username} cheered you on!",
            type="cheer",
        )
    )
    db.commit()

    return {
        "message": f"You cheered {friend.username}!",
        "points_awarded": CHEER_POINTS,
        "cheers_remaining": DAILY_CHEER_LIMIT - cheers_today - 1,
    }


@router.post(
    "/help-requests",
    response_model=HelpRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_help_request(
    payload: HelpRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friend = _require_friend(db, current_user.id, payload.friend_id)

    task = db.scalar(
        select(Task).where(
            Task.id == payload.task_id,
            Task.user_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Your task was not found")

    if task.status != "pending":
        raise HTTPException(status_code=409, detail="Help can only be requested for pending tasks")

    existing = db.scalar(
        select(HelpRequest).where(
            HelpRequest.task_id == task.id,
            HelpRequest.status.in_(["open", "accepted"]),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="This task already has an active help request",
        )

    request = HelpRequest(
        requester_id=current_user.id,
        helper_id=friend.id,
        task_id=task.id,
        message=payload.message,
        status="open",
    )
    db.add(request)
    db.add(
        Notification(
            user_id=friend.id,
            message=f"{current_user.username} requested your help with: {task.title}",
            type="help_request",
        )
    )
    db.commit()
    db.refresh(request)
    return request


@router.get(
    "/help-requests/incoming",
    response_model=list[HelpRequestResponse],
)
def incoming_help_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(HelpRequest)
        .where(
            HelpRequest.helper_id == current_user.id,
            HelpRequest.status == "open",
        )
        .order_by(HelpRequest.created_at.desc())
    ).all()


@router.post(
    "/help-requests/{request_id}/accept",
    response_model=HelpRequestResponse,
)
def accept_help_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = db.scalar(
        select(HelpRequest).where(
            HelpRequest.id == request_id,
            HelpRequest.helper_id == current_user.id,
            HelpRequest.status == "open",
        )
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Open help request not found")

    request.status = "accepted"
    db.add(
        Notification(
            user_id=request.requester_id,
            message=f"{current_user.username} accepted your help request.",
            type="help_accepted",
        )
    )
    db.commit()
    db.refresh(request)
    return request


@router.get(
    "/help-requests/outgoing",
    response_model=list[HelpRequestResponse],
)
def outgoing_help_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(HelpRequest)
        .where(HelpRequest.requester_id == current_user.id)
        .order_by(HelpRequest.created_at.desc())
    ).all()


@router.post(
    "/help-requests/{request_id}/decline",
    response_model=HelpRequestResponse,
)
def decline_help_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = db.scalar(
        select(HelpRequest).where(
            HelpRequest.id == request_id,
            HelpRequest.helper_id == current_user.id,
            HelpRequest.status == "open",
        )
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Open help request not found")

    request.status = "declined"
    db.add(
        Notification(
            user_id=request.requester_id,
            message=f"{current_user.username} declined your help request.",
            type="help_declined",
        )
    )
    db.commit()
    db.refresh(request)
    return request


@router.delete(
    "/help-requests/{request_id}",
    response_model=HelpRequestResponse,
)
def cancel_help_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = db.scalar(
        select(HelpRequest).where(
            HelpRequest.id == request_id,
            HelpRequest.requester_id == current_user.id,
            HelpRequest.status == "open",
        )
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Open help request not found")

    request.status = "cancelled"
    db.commit()
    db.refresh(request)
    return request

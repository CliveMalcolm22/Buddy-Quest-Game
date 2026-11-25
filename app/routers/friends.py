
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.friendship import Friendship
from app.models.notification import Notification
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.friendship import (
    FriendProfileResponse,
    FriendshipCreate,
    FriendshipResponse,
    FriendSearchResponse,
)
router = APIRouter(prefix="/friends", tags=["friends"])


@router.get("/", response_model=list[FriendProfileResponse])
def list_friends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendships = db.scalars(
        select(Friendship)
        .where(
            Friendship.status == "accepted",
            or_(
                Friendship.user_id == current_user.id,
                Friendship.friend_id == current_user.id,
            ),
        )
        .order_by(Friendship.created_at.desc())
    ).all()

    profiles = []

    for friendship in friendships:
        friend_id = (
            friendship.friend_id
            if friendship.user_id == current_user.id
            else friendship.user_id
        )
        friend = db.get(User, friend_id)

        if friend is None or not friend.is_active:
            continue

        profiles.append(
            FriendProfileResponse(
                friendship_id=friendship.id,
                friend_id=friend.id,
                username=friend.username,
                display_name=friend.display_name,
                avatar_url=friend.avatar_url,
                friends_since=friendship.created_at,
            )
        )

    return profiles


@router.get("/search", response_model=list[FriendSearchResponse])
def search_users(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = q.strip().lower()

    if len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query must contain at least 2 characters.",
        )

    users = db.scalars(
        select(User)
        .where(
            User.id != current_user.id,
            User.is_active.is_(True),
            User.username.ilike(f"%{query}%"),
        )
        .order_by(User.username)
        .limit(20)
    ).all()

    return [
        FriendSearchResponse(
            friend_id=user.id,
            username=user.username,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
        )
        for user in users
    ]


@router.post(
    "/request",
    response_model=FriendshipResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_friend_request(
    payload: FriendshipCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.friend_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot send a friend request to yourself.",
        )

    recipient = db.get(User, payload.friend_id)
    if recipient is None or not recipient.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    existing = db.scalar(
        select(Friendship).where(
            or_(
                (
                    (Friendship.user_id == current_user.id)
                    & (Friendship.friend_id == payload.friend_id)
                ),
                (
                    (Friendship.user_id == payload.friend_id)
                    & (Friendship.friend_id == current_user.id)
                ),
            )
        )
    )

    if existing is not None:
        if existing.status == "declined":
            now = datetime.now(timezone.utc)
            existing.user_id = current_user.id
            existing.friend_id = payload.friend_id
            existing.status = "pending"
            existing.created_at = now
            existing.updated_at = now

            db.add(
                Notification(
                    user_id=recipient.id,
                    message=f"{current_user.username} sent you a friend request.",
                    type="friend_request",
                )
            )
            db.commit()
            db.refresh(existing)
            return existing

        if existing.status == "accepted":
            detail = "You are already friends."
        elif existing.status == "pending":
            detail = "A friend request already exists."
        else:
            detail = "A previous friend request exists."

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

    friendship = Friendship(
        user_id=current_user.id,
        friend_id=payload.friend_id,
        status="pending",
    )
    db.add(friendship)
    db.add(
        Notification(
            user_id=recipient.id,
            message=f"{current_user.username} sent you a friend request.",
            type="friend_request",
        )
    )
    db.commit()
    db.refresh(friendship)
    return friendship


@router.get("/requests/incoming", response_model=list[FriendshipResponse])
def list_incoming_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(Friendship).where(
        Friendship.friend_id == current_user.id,
        Friendship.status == "pending",
    )
    return db.scalars(statement).all()


@router.get("/requests/outgoing", response_model=list[FriendshipResponse])
def list_outgoing_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(Friendship).where(
        Friendship.user_id == current_user.id,
        Friendship.status == "pending",
    )
    return db.scalars(statement).all()


@router.post(
    "/requests/{request_id}/accept",
    response_model=FriendshipResponse,
)
def accept_friend_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = db.scalar(
        select(Friendship).where(
            Friendship.id == request_id,
            Friendship.friend_id == current_user.id,
            Friendship.status == "pending",
        )
    )

    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending friend request not found.",
        )

    friendship.status = "accepted"
    db.add(
        Notification(
            user_id=friendship.user_id,
            message=f"{current_user.username} accepted your friend request.",
            type="friend_request_accepted",
        )
    )
    db.commit()
    db.refresh(friendship)
    return friendship


@router.post(
    "/requests/{request_id}/decline",
    response_model=FriendshipResponse,
)
def decline_friend_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = db.scalar(
        select(Friendship).where(
            Friendship.id == request_id,
            Friendship.friend_id == current_user.id,
            Friendship.status == "pending",
        )
    )

    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending friend request not found.",
        )

    friendship.status = "declined"
    db.commit()
    db.refresh(friendship)
    return friendship

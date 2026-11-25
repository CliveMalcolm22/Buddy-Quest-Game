from fastapi import APIRouter, HTTPException, status

from app.schemas.friendship import FriendshipCreate, FriendshipResponse

router = APIRouter(prefix="/friends", tags=["friends"])


@router.get("/", response_model=list[FriendshipResponse])
async def list_friends():
    return []


@router.post("/request", response_model=FriendshipResponse, status_code=status.HTTP_201_CREATED)
async def send_friend_request(payload: FriendshipCreate):
    return {
        "id": 1,
        "user_id": 1,
        "friend_id": payload.friend_id,
        "status": "pending",
    }


@router.post("/{friend_id}/accept", response_model=FriendshipResponse)
async def accept_friend_request(friend_id: int):
    return {
        "id": 1,
        "user_id": 1,
        "friend_id": friend_id,
        "status": "accepted",
    }

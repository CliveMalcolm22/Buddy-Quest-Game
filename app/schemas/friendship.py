from pydantic import BaseModel, Field


class FriendshipCreate(BaseModel):
    friend_id: int = Field(..., gt=0)


class FriendshipResponse(BaseModel):
    id: int
    user_id: int
    friend_id: int
    status: str


from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FriendshipCreate(BaseModel):
    friend_id: int = Field(..., gt=0)


class FriendshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    friend_id: int
    status: str
    created_at: datetime
    updated_at: datetime

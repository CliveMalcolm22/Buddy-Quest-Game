from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notes: str = ""
    start_time: datetime | None = None
    deadline: datetime | None = None


class TaskUpdate(TaskCreate):
    pass


class TaskResponse(TaskCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    completion_points: int
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notes: str = ""
    start_time: datetime | None = None
    deadline: datetime | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = None
    start_time: datetime | None = None


class DeadlineExtensionRequest(BaseModel):
    new_deadline: datetime


class TaskResponse(TaskCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    completion_points: int
    completed_at: datetime | None = None

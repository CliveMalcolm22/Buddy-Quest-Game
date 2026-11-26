from datetime import datetime, timezone

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notes: str = ""
    start_time: datetime
    deadline: datetime

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task title cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_time_window(self):
        start = _as_utc(self.start_time)
        deadline = _as_utc(self.deadline)
        if deadline <= start:
            raise ValueError("Deadline must be later than the start time.")
        return self


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
    deleted_at: datetime | None = None


class TaskHistoryResponse(BaseModel):
    id: int
    task_id: int
    action: str
    title: str
    notes: str
    status: str
    start_time: datetime
    deadline: datetime
    recorded_at: datetime

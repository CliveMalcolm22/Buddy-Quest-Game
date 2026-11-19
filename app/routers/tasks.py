from fastapi import APIRouter, HTTPException, status

from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=list[TaskResponse])
async def list_tasks():
    return []


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate):
    return {
        "id": 1,
        "user_id": 1,
        "status": "pending",
        "completion_points": 10,
        **payload.model_dump(),
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int):
    if task_id != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {
        "id": 1,
        "user_id": 1,
        "title": "Design review",
        "notes": "Prepare mockups for sprint planning",
        "start_time": None,
        "deadline": None,
        "status": "pending",
        "completion_points": 10,
    }


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, payload: TaskUpdate):
    return {
        "id": task_id,
        "user_id": 1,
        "status": "pending",
        "completion_points": 10,
        **payload.model_dump(),
    }


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int):
    return None

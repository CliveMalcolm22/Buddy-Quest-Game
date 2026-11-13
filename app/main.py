from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.database import initialize_database
from app.services.tasks import (
    TaskLockedError,
    TaskNotFoundError,
    TaskValidationError,
    complete_task,
    create_task,
    delete_task,
    get_task,
    list_today_tasks,
    update_task,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Buddy Quest", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_dashboard_context():
    tasks = list_today_tasks()
    completed = [task for task in tasks if task["status"] == "done"]
    done_count = len(completed)
    task_count = len(tasks)
    score = sum(task["completion_points"] for task in completed)
    percent = round(done_count / task_count * 100) if task_count else 0
    return {
        "summary_cards": [
            {"label": "Daily score", "value": f"{score:,}", "trend": "earned today", "trend_class": "positive", "meta": "task completion points"},
            {"label": "Tasks today", "value": str(task_count), "trend": f"{done_count} done", "trend_class": "neutral", "meta": "planned for today"},
            {"label": "Done today", "value": f"{done_count} / {task_count}", "trend": f"{percent}%", "trend_class": "neutral", "meta": "tasks completed"},
            {"label": "Rank", "value": "#4", "trend": "+1", "trend_class": "positive", "meta": "friends ahead"},
        ],
        "tasks": tasks,
        "leaderboard": [
            {"rank": 1, "name": "Sarah Chen", "points": 15420, "initials": "SC", "avatar": "images/avatars/sarah.svg", "is_you": False},
            {"rank": 2, "name": "Marcus Lee", "points": 14830, "initials": "ML", "avatar": "images/avatars/marcus.svg", "is_you": False},
            {"rank": 3, "name": "Priya Sharma", "points": 13990, "initials": "PS", "avatar": "images/avatars/priya.svg", "is_you": False},
            {"rank": 4, "name": "You", "points": 12750, "initials": "YO", "avatar": "images/avatars/you.svg", "is_you": True},
            {"rank": 5, "name": "Diego Alvarez", "points": 11200, "initials": "DA", "avatar": "images/avatars/diego.svg", "is_you": False},
        ],
        "notifications": [
            {"message": "Amélie commented to your post", "date": "Friday 3:12 PM", "time_ago": "2 hours ago", "initials": "A", "avatar": "images/avatars/amelie.svg", "cta": None},
            {"message": "Sienna followed you", "date": "Friday 3:04 PM", "time_ago": "2 hours ago", "initials": "S", "avatar": "images/avatars/sienna.svg", "cta": None},
            {"message": "Ammar invited you to Blog design", "date": "Friday 2:22 PM", "time_ago": "3 hours ago", "initials": "A", "avatar": "images/avatars/ammar.svg", "cta": "Accept"},
        ],
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "pages/dashboard.html",
        get_dashboard_context(),
    )


@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard(request: Request):
    return templates.TemplateResponse(
        request,
        "pages/leaderboard.html",
        {"leaderboard": get_dashboard_context()["leaderboard"]},
    )


@app.get("/summary", response_class=HTMLResponse)
def summary(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/summary-cards.html",
        {"summary_cards": get_dashboard_context()["summary_cards"]},
    )


@app.get("/tasks/empty", response_class=HTMLResponse)
def empty_task_state(request: Request):
    return templates.TemplateResponse(request, "partials/empty-tasks.html", {})


def task_error_response(message: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(
        f'<p class="form-error" role="alert">{message}</p>',
        status_code=status_code,
        headers={"HX-Retarget": "#task-form-feedback", "HX-Reswap": "innerHTML"},
    )


@app.get("/tasks/new", response_class=HTMLResponse)
def task_form_modal(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/task-form.html",
        {"task": None, "form_action": "/tasks", "form_title": "Add task"},
    )


@app.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
def edit_task_modal(request: Request, task_id: int):
    try:
        task = get_task(task_id)
        if not task["can_edit"]:
            return task_error_response("Tasks can only be edited before their start time.", 409)
    except TaskNotFoundError as exc:
        return task_error_response(str(exc), 404)
    return templates.TemplateResponse(
        request,
        "partials/task-form.html",
        {"task": task, "form_action": f"/tasks/{task_id}/edit", "form_title": "Edit task"},
    )


def task_write_response(request: Request, task: dict, *, created: bool) -> HTMLResponse:
    template = "partials/task-create-response.html" if created else "partials/task-update-response.html"
    response = templates.TemplateResponse(request, template, {"task": task})
    response.headers["HX-Trigger"] = '{"taskSaved": null}'
    response.headers["HX-Trigger-After-Swap"] = '{"taskChanged": null}'
    return response


@app.post("/tasks", response_class=HTMLResponse)
def add_task(
    request: Request,
    title: str = Form(""),
    start_time: str = Form(""),
    deadline: str = Form(""),
    notes: str = Form(""),
):
    try:
        task = create_task(title, start_time, deadline, notes)
    except TaskValidationError as exc:
        return task_error_response(str(exc), 422)
    return task_write_response(request, task, created=True)


@app.post("/tasks/{task_id}/edit", response_class=HTMLResponse)
def save_task(
    request: Request,
    task_id: int,
    title: str = Form(""),
    start_time: str = Form(""),
    deadline: str = Form(""),
    notes: str = Form(""),
):
    try:
        task = update_task(task_id, title, start_time, deadline, notes)
    except TaskValidationError as exc:
        return task_error_response(str(exc), 422)
    except TaskNotFoundError as exc:
        return task_error_response(str(exc), 404)
    except TaskLockedError as exc:
        return task_error_response(str(exc), 409)
    return task_write_response(request, task, created=False)


@app.post("/tasks/{task_id}/complete", response_class=HTMLResponse)
def mark_task_complete(request: Request, task_id: int):
    try:
        task = complete_task(task_id)
    except TaskNotFoundError as exc:
        return task_error_response(str(exc), 404)
    except TaskLockedError as exc:
        return task_error_response(str(exc), 409)
    response = templates.TemplateResponse(request, "partials/task-update-response.html", {"task": task})
    response.headers["HX-Trigger-After-Swap"] = '{"taskChanged": null}'
    return response


@app.post("/tasks/{task_id}/delete", response_class=HTMLResponse)
def remove_task(task_id: int):
    try:
        delete_task(task_id)
    except TaskNotFoundError as exc:
        return task_error_response(str(exc), 404)
    except TaskLockedError as exc:
        return task_error_response(str(exc), 409)
    return HTMLResponse("", headers={"HX-Trigger-After-Swap": '{"taskChanged": null}'})


@app.get("/health")
async def health_check():
    return {"status": "ok"}

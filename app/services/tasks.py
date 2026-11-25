from datetime import date, datetime, time, timedelta
import sqlite3

from app.database import DATABASE_PATH, connect


class TaskError(Exception):
    """Base error for task operations."""


class TaskValidationError(TaskError):
    def __init__(self, message: str, field: str = "form"):
        super().__init__(message)
        self.field = field


class TaskNotFoundError(TaskError):
    pass


class TaskLockedError(TaskError):
    pass


def _parse_time(value: str, field: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise TaskValidationError("Enter a valid time.", field) from exc


def _validate_task(
    title: str,
    start_time: str,
    deadline: str,
    notes: str,
    now: datetime,
    *,
    creating: bool,
) -> tuple[str, time, time, str]:
    title = title.strip()
    if not title:
        raise TaskValidationError("Enter a task name.", "title")
    if len(title) > 160:
        raise TaskValidationError("Task names must be 160 characters or fewer.", "title")
    if len(notes) > 1000:
        raise TaskValidationError("Notes must be 1,000 characters or fewer.", "notes")

    start = _parse_time(start_time, "start_time")
    due = _parse_time(deadline, "deadline")
    if start >= due:
        raise TaskValidationError("Deadline must be later than the start time.", "deadline")
    if datetime.combine(now.date(), start) <= now:
        message = "A task must be created before its start time." if creating else "Start time must be in the future."
        raise TaskValidationError(message, "start_time")
    return title, start, due, notes.strip()


def _row_to_task(row: sqlite3.Row, now: datetime) -> dict:
    task = dict(row)
    start = datetime.combine(date.fromisoformat(task["task_date"]), time.fromisoformat(task["start_time"]))
    due = datetime.combine(date.fromisoformat(task["task_date"]), time.fromisoformat(task["deadline"]))

    if task["completed_at"]:
        status, label, progress = "done", "Done", 100
    elif now > due + timedelta(minutes=5):
        status, label, progress = "missed", "Missed", 100
    elif now > due:
        status, label, progress = "late", "Late", 100
    elif now >= start and due - now <= timedelta(minutes=10):
        status, label, progress = "warning", "Due soon", 0
    elif now >= start:
        status, label, progress = "ontrack", "In progress", 0
    else:
        status, label, progress = "scheduled", "Upcoming", 0

    task.update(
        status=status,
        status_label=label,
        progress=progress,
        points=task["completion_points"] if task["completed_at"] else (3 if status == "late" else 0 if status == "missed" else 10),
        can_edit=now < start and task["completed_at"] is None,
        can_complete=task["completed_at"] is None and status != "missed",
    )
    return task


def list_today_tasks(database_path=DATABASE_PATH, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM tasks WHERE task_date = ? ORDER BY start_time, id",
            (now.date().isoformat(),),
        ).fetchall()
    return [_row_to_task(row, now) for row in rows]


def get_task(task_id: int, database_path=DATABASE_PATH, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskNotFoundError("Task not found.")
    return _row_to_task(row, now)


def create_task(
    title: str,
    start_time: str,
    deadline: str,
    notes: str = "",
    database_path=DATABASE_PATH,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now()
    title, start, due, notes = _validate_task(
        title, start_time, deadline, notes, now, creating=True
    )
    with connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO tasks (title, start_time, deadline, notes, task_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, start.isoformat(timespec="minutes"), due.isoformat(timespec="minutes"), notes, now.date().isoformat()),
        )
        task_id = cursor.lastrowid
    return get_task(task_id, database_path, now)


def update_task(
    task_id: int,
    title: str,
    start_time: str,
    deadline: str,
    notes: str = "",
    database_path=DATABASE_PATH,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now()
    existing = get_task(task_id, database_path, now)
    if not existing["can_edit"]:
        raise TaskLockedError("Tasks can only be edited before their start time.")
    title, start, due, notes = _validate_task(
        title, start_time, deadline, notes, now, creating=False
    )
    with connect(database_path) as connection:
        connection.execute(
            """
            UPDATE tasks
            SET title = ?, start_time = ?, deadline = ?, notes = ?
            WHERE id = ?
            """,
            (title, start.isoformat(timespec="minutes"), due.isoformat(timespec="minutes"), notes, task_id),
        )
    return get_task(task_id, database_path, now)


def delete_task(task_id: int, database_path=DATABASE_PATH, now: datetime | None = None) -> None:
    now = now or datetime.now()
    existing = get_task(task_id, database_path, now)
    if not existing["can_edit"]:
        raise TaskLockedError("Tasks can only be deleted before their start time.")
    with connect(database_path) as connection:
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def complete_task(task_id: int, database_path=DATABASE_PATH, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    task = get_task(task_id, database_path, now)
    if not task["can_complete"]:
        raise TaskLockedError("This task can no longer be completed.")
    due = datetime.combine(date.fromisoformat(task["task_date"]), time.fromisoformat(task["deadline"]))
    points = 10 if now <= due else 3
    with connect(database_path) as connection:
        connection.execute(
            """
            UPDATE tasks
            SET completed_at = ?, completion_points = ?
            WHERE id = ? AND completed_at IS NULL
            """,
            (now.isoformat(timespec="seconds"), points, task_id),
        )
    return get_task(task_id, database_path, now)

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.models.notification import Notification
from app.models.scheduler_event import SchedulerEvent
from app.models.task import Task


class TaskScheduler:
    def __init__(self, session_factory: sessionmaker = SessionLocal):
        self.session_factory = session_factory
        self.scheduler = BackgroundScheduler(timezone=timezone.utc)

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def reschedule_all(self) -> None:
        with self.session_factory() as db:
            tasks = db.scalars(
                select(Task).where(
                    Task.deleted_at.is_(None),
                    Task.status.not_in(("completed", "missed")),
                )
            ).all()
        for task in tasks:
            self.schedule_task(task)

    def schedule_task(self, task: Task) -> None:
        task_id = task.id
        if task.deleted_at is not None or task.status in ("completed", "missed"):
            self.unschedule_task(task_id)
            return

        self._remove_jobs(task_id)
        now = datetime.now(timezone.utc)

        if task.start_time:
            start_time = self._as_utc(task.start_time)
            if start_time > now:
                self._add_job(
                    f"task-{task_id}-start",
                    start_time,
                    self.process_start,
                    task_id,
                )

        if task.deadline:
            deadline = self._as_utc(task.deadline)
            countdown = deadline - timedelta(minutes=10)
            if countdown > now:
                self._add_job(
                    f"task-{task_id}-countdown",
                    countdown,
                    self.process_countdown,
                    task_id,
                )
            if deadline > now:
                self._add_job(
                    f"task-{task_id}-due",
                    deadline,
                    self.process_due,
                    task_id,
                )

    def unschedule_task(self, task_id: int) -> None:
        self._remove_jobs(task_id)

    def process_start(self, task_id: int) -> bool:
        return self._process_event(task_id, "start", self._apply_start)

    def process_countdown(self, task_id: int) -> bool:
        return self._process_event(task_id, "countdown", self._apply_countdown)

    def process_due(self, task_id: int) -> bool:
        return self._process_event(task_id, "due", self._apply_due)

    def _process_event(self, task_id: int, event_type: str, apply) -> bool:
        with self.session_factory() as db:
            task = db.scalar(select(Task).where(Task.id == task_id))
            if task is None or task.deleted_at is not None:
                return False

            db.add(SchedulerEvent(task_id=task_id, event_type=event_type))
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                return False

            apply(db, task)
            db.commit()
            return True

    def _apply_start(self, db: Session, task: Task) -> None:
        if task.status == "pending":
            task.status = "in_progress"
        db.add(Notification(
            user_id=task.user_id,
            message=f"Task started: {task.title}",
            type="task_start",
        ))

    def _apply_countdown(self, db: Session, task: Task) -> None:
        if task.status not in ("completed", "missed"):
            db.add(Notification(
                user_id=task.user_id,
                message=f"Deadline approaching: {task.title}",
                type="task_deadline",
            ))

    def _apply_due(self, db: Session, task: Task) -> None:
        if task.status not in ("completed", "missed"):
            task.status = "missed"
            db.add(Notification(
                user_id=task.user_id,
                message=f"Task overdue: {task.title}",
                type="task_due",
            ))

    def _add_job(self, job_id: str, run_at: datetime, function, task_id: int) -> None:
        self.scheduler.add_job(
            function,
            trigger="date",
            run_date=run_at,
            args=[task_id],
            id=job_id,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
        )

    def _remove_jobs(self, task_id: int) -> None:
        for event_type in ("start", "countdown", "due"):
            job_id = f"task-{task_id}-{event_type}"
            if self.scheduler.get_job(job_id) is not None:
                self.scheduler.remove_job(job_id)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


task_scheduler = TaskScheduler()


def get_task_scheduler() -> TaskScheduler:
    return task_scheduler

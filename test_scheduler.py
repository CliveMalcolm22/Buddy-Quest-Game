from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.notification import Notification
from app.models.scheduler_event import SchedulerEvent
from app.models.task import Task
from app.models.user import User
from app.services.scheduler import TaskScheduler


def test_scheduler_uses_stable_jobs_and_replaces_duplicates():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with Session(engine) as db:
        user = User(username="scheduler", email="scheduler@example.com", password_hash="hashed")
        db.add(user)
        db.flush()
        now = datetime.now(timezone.utc)
        task = Task(
            user_id=user.id,
            title="Scheduled task",
            status="pending",
            start_time=now + timedelta(minutes=30),
            deadline=now + timedelta(minutes=60),
        )
        db.add(task)
        db.commit()

        scheduler = TaskScheduler(sessions)
        scheduler.schedule_task(task)
        scheduler.schedule_task(task)

        jobs = scheduler.scheduler.get_jobs()
        assert {job.id for job in jobs} == {
            f"task-{task.id}-start",
            f"task-{task.id}-countdown",
            f"task-{task.id}-due",
        }
        assert len(jobs) == 3
        scheduler.shutdown()


def test_task_events_are_processed_only_once():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with Session(engine) as db:
        user = User(username="events", email="events@example.com", password_hash="hashed")
        db.add(user)
        db.flush()
        user_id = user.id
        now = datetime.now(timezone.utc)
        task = Task(
            user_id=user.id,
            title="Due task",
            status="pending",
            start_time=now - timedelta(minutes=5),
            deadline=now - timedelta(minutes=1),
        )
        db.add(task)
        db.commit()
        task_id = task.id

        scheduler = TaskScheduler(sessions)
        assert scheduler.process_start(task_id) is True
        assert scheduler.process_start(task_id) is False
        assert scheduler.process_countdown(task_id) is True
        assert scheduler.process_countdown(task_id) is False
        assert scheduler.process_due(task_id) is True
        assert scheduler.process_due(task_id) is False

    with Session(engine) as db:
        stored_task = db.scalar(select(Task).where(Task.id == task_id))
        assert stored_task.status == "missed"
        assert len(db.scalars(select(SchedulerEvent).where(SchedulerEvent.task_id == task_id)).all()) == 3
        assert len(db.scalars(select(Notification).where(Notification.user_id == user_id)).all()) == 3

# app/services/scoring.py

"""Scoring rules for BuddyQuest.

These functions calculate points only. They do not save points
to the database or modify task records.
"""

# Points awarded for different activities
ON_TIME_TASK_POINTS = 10
LATE_TASK_POINTS = 3
MISSED_TASK_POINTS = 0

DAILY_COMPLETION_BONUS = 20
HELP_FRIEND_POINTS = 5
CHEER_POINTS = 1

# A user can cheer friends at most five times per day.
DAILY_CHEER_LIMIT = 5


def task_completion_points(status: str) -> int:
    """Return points based on how a task was completed."""
    points_by_status = {
        "on_time": ON_TIME_TASK_POINTS,
        "late": LATE_TASK_POINTS,
        "missed": MISSED_TASK_POINTS,
    }

    if status not in points_by_status:
        raise ValueError(
            "Status must be 'on_time', 'late', or 'missed'."
        )

    return points_by_status[status]


def daily_completion_bonus(
    total_tasks: int,
    completed_tasks: int,
) -> int:
    """Award a bonus when every task for the day is completed."""
    if total_tasks < 0 or completed_tasks < 0:
        raise ValueError("Task counts cannot be negative.")

    if completed_tasks > total_tasks:
        raise ValueError("Completed tasks cannot exceed total tasks.")

    if total_tasks > 0 and completed_tasks == total_tasks:
        return DAILY_COMPLETION_BONUS

    return 0


def cheer_points(cheers_today: int) -> int:
    """Return cheer points if the user has not reached the daily limit."""
    if cheers_today < 0:
        raise ValueError("Cheer count cannot be negative.")

    if cheers_today < DAILY_CHEER_LIMIT:
        return CHEER_POINTS

    return 0

"""Streak rules for BuddyQuest.

These functions determine whether a user qualifies
for a streak day.
"""

STREAK_COMPLETION_THRESHOLD = 0.80


def is_streak_day(total_tasks: int, completed_tasks: int) -> bool:
    """Return True when at least 80% of daily tasks are completed."""
    if total_tasks < 0 or completed_tasks < 0:
        raise ValueError("Task counts cannot be negative.")

    if completed_tasks > total_tasks:
        raise ValueError("Completed tasks cannot exceed total tasks.")

    if total_tasks == 0:
        return False

    completion_rate = completed_tasks / total_tasks

    return completion_rate >= STREAK_COMPLETION_THRESHOLD

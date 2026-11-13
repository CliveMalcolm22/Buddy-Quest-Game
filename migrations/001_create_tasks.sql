CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    deadline TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    task_date TEXT NOT NULL,
    completed_at TEXT,
    completion_points INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_task_date_start_time
    ON tasks (task_date, start_time);

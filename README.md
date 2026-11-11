# Buddy-Quest-Game
# Buddy Quest Game

A Python web app that turns a daily to-do list into a game you play with friends. Every task gets a time limit, alerts fire as deadlines approach, missed tasks are recorded honestly, and friends can cheer, help and compete on a weekly leaderboard.

---

## Table of contents

1. [What the app does](#1-what-the-app-does)
2. [Tech stack](#2-tech-stack)
3. [Step 1: Prerequisites](#3-step-1-prerequisites)
4. [Step 2: Get the code](#4-step-2-get-the-code)
5. [Step 3: Create a virtual environment](#5-step-3-create-a-virtual-environment)
6. [Step 4: Install dependencies](#6-step-4-install-dependencies)
7. [Step 5: Configure environment variables](#7-step-5-configure-environment-variables)
8. [Step 6: Set up the database](#8-step-6-set-up-the-database)
9. [Step 7: Run the app](#9-step-7-run-the-app)
10. [Step 8: Run the tests](#10-step-8-run-the-tests)
11. [Step 9: Try a full day in the app](#11-step-9-try-a-full-day-in-the-app)
12. [Project folder structure](#12-project-folder-structure)
13. [How the app works](#13-how-the-app-works)
14. [Game rules and business rules](#14-game-rules-and-business-rules)
15. [Functional requirements](#15-functional-requirements)
16. [Non-functional requirements](#16-non-functional-requirements)
17. [Working conventions](#17-working-conventions)
18. [Team roles](#18-team-roles)
19. [Delivery plan by phase](#19-delivery-plan-by-phase)
20. [Gates and definition of done](#20-gates-and-definition-of-done)
21. [Risks](#21-risks)
22. [Troubleshooting](#22-troubleshooting)

---

## 1. What the app does

**The problem:** people write daily task lists but rarely finish them, because nothing happens when a task slips. Ordinary to-do apps allow tasks with no deadline, hide missed tasks, offer no accountability, and show no visible progress.

**The answer:** one app that combines mandatory time limits, an honest record of missed tasks, friend accountability and habit tracking.

### A day in the app

1. **Morning.** The user types or pastes the day's tasks and sets a start time and a deadline for each.
2. **During the day.** The Today screen shows a live countdown per task. Alerts fire at the start, shortly before the deadline, and at the deadline.
3. **Finishing.** The user ticks a task as done. On time earns full points, late earns fewer.
4. **Missing.** A task not done after its deadline plus a short grace period is marked *missed* and kept in the history.
5. **With friends.** Friends see each other's progress, cheer or help, and the weekly leaderboard updates.
6. **Night.** A nightly job updates each user's streak and progress charts.

### Key terms

| Term | Meaning |
|---|---|
| Task | One thing the user plans to do today, with a start time and a deadline |
| Time limit | The window between a task's start time and its deadline |
| Grace period | A short wait after the deadline before a task is marked missed |
| Missed task | A task not completed by its deadline plus the grace period |
| Points | Score earned for completing, helping and cheering |
| Streak | Number of consecutive days the user met the daily completion target |
| Leaderboard | Weekly ranking of a user and their friends by points |
| Help | A friend's action on a task: cheer, share or take over |

### Scope of the first release

Included: a web app that installs to a phone's home screen, built entirely in Python, covering one person's daily planning plus a friends-only social layer.

Not included: team or company project management, calendar sync, payments, native mobile apps.

---

## 2. Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Web framework | FastAPI |
| Database | SQLite in development, PostgreSQL in production, via SQLAlchemy and Alembic |
| Scheduler | APScheduler (alert checks and nightly jobs) |
| Frontend | Jinja2 templates with HTMX, installable as a web app (PWA) |
| Notifications | Web push through pywebpush, with email as a backup |
| Testing | pytest |

---

## 3. Step 1: Prerequisites

Install these before you start:

- **Python 3.12** (check with `python --version`)
- **Git** (check with `git --version`)
- A code editor such as VS Code
- Optional for production: a PostgreSQL server

---

## 4. Step 2: Get the code

```bash
git clone <your-repository-url> task-tracker-game
cd task-tracker-game
```

Create your own branch before changing anything (one branch per feature):

```bash
git checkout -b feature/<short-feature-name>
```

---

## 5. Step 3: Create a virtual environment

A virtual environment keeps the project's packages separate from the rest of your computer.

**macOS / Linux**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of your terminal prompt.

---

## 6. Step 4: Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The starting list for `requirements.txt` is:

```
fastapi
uvicorn
sqlalchemy
alembic
apscheduler
jinja2
pywebpush
passlib
pytest
```

Add packages here as the project grows (for example `python-dotenv` or `pydantic-settings` for reading `.env`, and `httpx` for testing endpoints). Always commit the updated `requirements.txt`.

---

## 7. Step 5: Configure environment variables

Secrets live in a `.env` file that is **never committed**. `.env.example` lists the names only.

1. Copy the template:

   ```bash
   cp .env.example .env        # Windows: copy .env.example .env
   ```

2. Open `.env` and fill in the values. Typical entries:

   | Name | What it is | Example |
   |---|---|---|
   | `DATABASE_URL` | Where the database lives | `sqlite:///./app.db` (dev) |
   | `SECRET_KEY` | Signs login sessions | a long random string |
   | `VAPID_PUBLIC_KEY` | Public key for web push | generated key |
   | `VAPID_PRIVATE_KEY` | Private key for web push | generated key |
   | `VAPID_CLAIM_EMAIL` | Contact address sent with push messages | `mailto:you@example.com` |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Email backup settings | from your email provider |

3. Generate a secret key:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Generate web push (VAPID) keys with the `vapid` tool that comes with pywebpush's dependencies:

   ```bash
   vapid --gen
   ```

   Copy the keys it produces into `.env`. Never share the private key.

5. Confirm `.env` is listed in `.gitignore`.

---

## 8. Step 6: Set up the database

Database settings are read from `app/config.py` and the engine and sessions are created in `app/database.py`. All schema changes go through Alembic migrations.

Apply all existing migrations:

```bash
alembic upgrade head
```

When you change a table in `app/models/`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Review the generated file in `migrations/` before committing it. **Every change that touches the database must come with a migration.**

Tables the app uses: `user`, `task`, `friendship`, `help`, `point_event`, `streak`, `notification`.

To roll back the last migration:

```bash
alembic downgrade -1
```

---

## 9. Step 7: Run the app

```bash
uvicorn app.main:app --reload
```

- App: http://127.0.0.1:8000
- Interactive API docs (FastAPI built in): http://127.0.0.1:8000/docs

`app/main.py` creates the FastAPI app, connects the routers and starts the scheduler, so alerts and the missed-task job run while the server is up.

**Testing on a phone:** web push and installing to the home screen require HTTPS. For local testing, use a secure tunnel tool to expose your dev server over HTTPS, then open that address on your phone and choose "Add to Home Screen".

---

## 10. Step 8: Run the tests

```bash
pytest
```

Useful variations:

```bash
pytest tests/test_scoring.py      # one file
pytest -k deadline                # tests matching a name
pytest -x                         # stop at first failure
```

Rules for tests:

- Every scoring and deadline rule has at least one automated test.
- Everyone writes tests for their own area in `tests/` (scoring, deadlines, alerts, friends).
- A change is not done until its tests pass.

---

## 11. Step 9: Try a full day in the app

Use this walkthrough to check that the whole app works end to end.

1. **Sign up** and log in (FR-16). Set your timezone and alert preferences.
2. **Add tasks** (FR-1): type one, or paste a list, and each line becomes a task.
3. **Set a start time and deadline** on every task (FR-3). Confirm a task cannot be saved without both.
4. **Open the Today screen** and check the live countdown (FR-4).
5. **Wait for alerts** (FR-5, FR-6): at the start time, 10 minutes before the deadline (default), and at the deadline.
6. **Complete one task on time** and check you earn +10 points.
7. **Let one task pass its deadline** and wait 5 minutes (the grace period). Check it is marked missed (FR-7), then open the history and add a reason (FR-8).
8. **Try to edit or create a task after its time** and confirm it is blocked (FR-13).
9. **Add a friend** by username with a second test account (FR-9). Accept the request.
10. **View each other's tasks** (FR-10). Mark one task private and confirm the friend cannot see it.
11. **Cheer, share or take over** a task (FR-11) and check the notification and points.
12. **Check the leaderboard** shows both users (FR-12).
13. **Check progress** shows daily, weekly and monthly completion rate and the streak (FR-14, FR-15).

---

## 12. Project folder structure

The code is split by job so each team member can work in their own folders without stepping on the others.

```
task-tracker-game/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # settings: database URL, keys
│   ├── database.py      # engine and session setup
│   ├── models/          # tables: user, task, friendship, help, point_event, streak, notification
│   ├── schemas/         # request and response shapes
│   ├── routers/         # auth.py, tasks.py, friends.py, leaderboard.py, progress.py
│   ├── services/        # scoring.py, streaks.py, deadlines.py
│   ├── scheduler/       # jobs.py: alert checks, missed-task and nightly jobs
│   ├── notifications/   # push.py, email.py
│   ├── templates/       # Jinja2 pages: today, friends, progress, history
│   └── static/          # css, HTMX, icons, service worker, manifest
├── migrations/          # Alembic database migrations
├── tests/               # pytest: scoring, deadlines, alerts, friends
├── docs/                # project documentation
├── requirements.txt
├── .env.example
└── README.md
```

| Folder or file | Purpose |
|---|---|
| `app/main.py` | Creates the FastAPI app, connects the routers and starts the scheduler |
| `app/models/` | Database tables, one file per table |
| `app/schemas/` | Shapes of the data that goes in and out of the API |
| `app/routers/` | The web endpoints, grouped by feature |
| `app/services/` | Business logic kept apart from endpoints, such as scoring and deadline checks |
| `app/scheduler/` | Timed jobs that check deadlines, mark missed tasks and run the nightly update |
| `app/notifications/` | Sending web push and email |
| `app/templates/` | The HTML pages |
| `app/static/` | Styles, scripts, icons, the service worker and the install manifest |
| `migrations/` | Versioned database changes |
| `tests/` | Automated tests |
| `docs/` | Project documentation |

---

## 13. How the app works

### Adding a new feature (the recommended flow)

1. Create a branch: `git checkout -b feature/<name>`.
2. Add or change the **model** in `app/models/` and create a **migration**.
3. Define the **schemas** in `app/schemas/`.
4. Put the **business logic** in `app/services/` so it can be tested without the web layer.
5. Add a short **router** endpoint in `app/routers/` that calls the service.
6. Add or update the **template** in `app/templates/`.
7. Write **pytest tests** in `tests/`.
8. Run `pytest`, then open a pull request for Clive to review.

### The scheduler

`app/scheduler/jobs.py` holds the timed jobs, run by APScheduler:

- **Alert check:** sends alerts at the start time, before the deadline (lead time is a user setting), and at the deadline.
- **Missed-task job:** marks tasks missed once deadline plus grace period has passed. It must be **safe to run twice** (NFR-2), so it only touches tasks not already marked.
- **Nightly job:** updates streaks and progress data, and resets the weekly leaderboard on Mondays.

### Alerts

Alerts go by **web push** (`notifications/push.py`) with **email** as a backup (`notifications/email.py`). They respect each user's quiet hours and must still arrive when the app is closed, which is why the service worker in `app/static/` handles push.

### Time zones

Store all times in **UTC**. Convert to the user's own timezone only when displaying (NFR-3).

---

## 14. Game rules and business rules

### Points (starting proposals, to tune after testing)

| Action | Points |
|---|---|
| Complete a task before its deadline | +10 |
| Complete a task after its deadline | +3 |
| Miss a task | 0, and it is logged |
| Finish every task in a day | +20 bonus |
| Help a friend finish a shared or taken-over task | +5 |
| Cheer a friend (up to 5 a day) | +1 |

### Business rules

- **Grace period:** 5 minutes after the deadline before a task is marked missed.
- **Default alert lead time:** 10 minutes before the deadline; each user can change it.
- **Streak:** a day counts when at least 80% of its tasks are completed.
- **Leaderboard:** resets every Monday; an all-time view is kept separately.
- **Privacy:** private tasks are never shown to friends and never appear in the friend feed.
- **Fair play:** tasks must be created before their start time and cannot be edited after their deadline. A task can be extended once before its deadline, and the extension is recorded. Friends can flag a suspicious completion.

### Design principles

1. The time limit is mandatory.
2. Misses are recorded, never hidden (with an optional reason).
3. Friends help, not only compete.
4. Fair play is built in.
5. Start simple: a solo tracker first, then the social and game layers.

---

## 15. Functional requirements

| ID | Feature | Requirement |
|---|---|---|
| FR-1 | Daily task entry | Add tasks one at a time or paste a list; each line becomes a task |
| FR-2 | Daily task entry | Edit or delete a task until its start time |
| FR-3 | Time limits | Every task must have a start time and a deadline before it can be saved |
| FR-4 | Time limits | Today screen shows a live countdown for each active task |
| FR-5 | Alerts | Alert at start time, before the deadline (lead time is a user setting), and at the deadline |
| FR-6 | Alerts | Web push with email backup, respecting quiet hours |
| FR-7 | Missed-task record | A task not completed by deadline plus grace period is marked missed |
| FR-8 | Missed-task record | View missed tasks in a history and add a reason |
| FR-9 | Friends | Send, accept and decline friend requests by username |
| FR-10 | Friends | Friends can view each other's tasks, except private ones |
| FR-11 | Helping | A friend can cheer, share or take over a task, and the user is notified |
| FR-12 | Competition | Points for completed tasks and a weekly leaderboard |
| FR-13 | Competition | No creating tasks after their start time or editing after their deadline |
| FR-14 | Progress | Completion rate by day, week and month |
| FR-15 | Habits | Streaks, and repeating tasks tracked as habits over time |
| FR-16 | Accounts | Sign up, log in, set timezone and alert preferences |

---

## 16. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Security | Passwords hashed, secure-cookie sessions, site runs over HTTPS |
| NFR-2 | Reliability | Alerts arrive when the app is closed; the missed-task job is safe to run twice |
| NFR-3 | Time zones | Stored in UTC, shown in the user's timezone |
| NFR-4 | Privacy | Visible only to accepted friends, with a private option per task |
| NFR-5 | Usability | Works at phone width; a full day's tasks can be entered in under 60 seconds |
| NFR-6 | Performance | Today screen loads quickly on a mobile connection |
| NFR-7 | Maintainability | Database changes use migrations; scoring and deadline logic is tested |

### Success measures (targets are proposals for the team to confirm)

| Objective | How to check | Target |
|---|---|---|
| Time limits | Share of saved tasks with a start time and deadline | 100% |
| Alerts | Delay between scheduled time and alert sent | Within 1 minute |
| Missed record | Share of overdue tasks (past grace) marked missed | 100% |
| Friends and leaderboard | Two test users become friends, see tasks, cheer, and appear on one leaderboard | Passes an end-to-end test |
| Progress and habits | Dashboard shows daily, weekly, monthly rate and current streak | All four shown |
| Phased delivery | Phase 1 usable on a real phone before friend features start | Gate 1 passed |
| Tests | Every scoring and deadline rule has an automated test | All tests pass |

---

## 17. Working conventions

- One shared Git repository. **One branch per feature**, merged by pull request after review. Clive reviews every change.
- Secrets live in `.env`, which is never committed. `.env.example` lists the names.
- Business logic goes in `services/`, so endpoints stay short and logic can be tested without the web layer.
- Each change that touches the database comes with a migration.
- A short team check-in each week: what is done, what is blocked, what is next.
- Anyone who finishes early helps the member whose area is furthest behind.

### Pull request checklist

- [ ] Branch is up to date with `main`
- [ ] `pytest` passes
- [ ] Migration included if the database changed
- [ ] No secrets or `.env` committed
- [ ] The requirement (FR/NFR) can be shown working
- [ ] Clive has been asked to review

---

## 18. Team roles

These assignments are a proposal; swap them if someone prefers a different area.

| Member | Role | Owns | Requirements |
|---|---|---|---|
| Clive | Backend core: plans phases, reviews code, sets up the database, builds accounts, tasks and time limits, keeps README and docs current | `app/main.py`, `config.py`, `database.py`, `models/`, `routers/auth.py`, `routers/tasks.py`, `migrations/`, `docs/` | FR-1, FR-2, FR-3, FR-16 |
| Peter | Alerts and scheduler: scheduler, alert rules, web push and email, missed-task marking, nightly job | `scheduler/`, `notifications/`, `services/deadlines.py` | FR-5, FR-6, FR-7, FR-8 |
| Martin | Frontend and UX: screens, countdown timers, mobile layout, installable web app | `templates/`, `static/` | FR-4, FR-14 (charts and display) |
| Lakhisha | Friends, game and progress: friend requests, shared views, helping, scoring, leaderboard, streaks, progress data | `routers/friends.py`, `routers/leaderboard.py`, `routers/progress.py`, `services/scoring.py`, `services/streaks.py` | FR-9 to FR-13, FR-14 (data), FR-15 |

Everyone writes pytest tests for their own area in `tests/`.

---

## 19. Delivery plan by phase

Each person has a job in every phase, so nobody waits on another member.

| Phase | Clive | Peter | Martin | Lakhisha |
|---|---|---|---|---|
| **1. Solo tracker** | Database setup, accounts, task model and time-limit checks | Scheduler, alert rules, missed-task job | Plan-the-day and Today screens, countdown timers | Designs friend, point and streak tables with Clive; drafts scoring rules |
| **2. Friends** | Permission checks and private-task option | Alerts for friend requests and cheers | Friends feed and add-friend screens | Friend requests, shared task view, cheering, helping |
| **3. The game** | Rules that block late creation and late edits | Nightly streak update and weekly leaderboard reset | Leaderboard, level and badge screens | Points, levels, badges, leaderboard, streaks |
| **4. Habits** | Repeating-task model | Daily summary alert | Progress charts and monthly view | Progress data and habit history |

### Step-by-step build order

**Phase 1: Solo tracker**
1. Set up the repo, folder structure, `requirements.txt`, `.env.example` (Clive).
2. Create `config.py`, `database.py` and the first migration with the user and task tables (Clive).
3. Build sign up and log in (`routers/auth.py`) and the task endpoints with time-limit validation (`routers/tasks.py`).
4. Agree the alert and screen formats (Peter and Martin, early).
5. Build the Today and plan-the-day screens with countdowns (Martin).
6. Build the scheduler, alert rules and push/email sending (Peter).
7. Build the missed-task job and history with reasons (Peter).
8. Pass **Gate 1**: alerts reach a real phone on time.

**Phase 2: Friends**
1. Add friendship and help tables with a migration (Lakhisha and Clive).
2. Build friend requests, shared task view, private option and permission checks.
3. Build cheering, sharing and taking over, with notifications.
4. Build the friends feed and add-friend screens.
5. Pass **Gate 2**: two friends use the app together.

**Phase 3: The game**
1. Implement `services/scoring.py` using the points table, with tests.
2. Block late task creation and late edits.
3. Build streaks (`services/streaks.py`) and the nightly update.
4. Build the weekly leaderboard, its Monday reset, levels and badges.
5. Add the anti-cheat flag for suspicious completions.
6. Pass **Gate 3**: scoring tests pass and cheats are blocked.

**Phase 4: Habits**
1. Add the repeating-task model and habit history.
2. Build progress data for daily, weekly and monthly completion rate.
3. Build charts and the monthly view.
4. Add the daily summary alert.

---

## 20. Gates and definition of done

| Gate | Passed when |
|---|---|
| Gate 1 | Alerts reach a phone on time |
| Gate 2 | Two friends use the app together |
| Gate 3 | Scoring tests pass and cheats are blocked |

A task counts as **done** when its code is merged, its tests pass, and the requirement can be shown working.

---

## 21. Risks

| Risk | What the team does |
|---|---|
| Alerts and screens depend on each other | Peter and Martin agree alert and screen formats early in Phase 1 |
| One member falls behind | The weekly check-in spots it, and others help |
| Scoring rules change after testing | Lakhisha keeps scoring in `services/scoring.py`, so changes stay in one place |

---

## 22. Troubleshooting

| Problem | Likely fix |
|---|---|
| `ModuleNotFoundError` | The virtual environment is not active, or run `pip install -r requirements.txt` again |
| `alembic` cannot find the database | Check `DATABASE_URL` in `.env` and that you run commands from the project root |
| Alerts not arriving | Check the scheduler started in `main.py`, VAPID keys are set, the site is on HTTPS and the user allowed notifications |
| Alerts arrive twice | Confirm only one server process is running the scheduler |
| Times look wrong | Check times are stored in UTC and converted using the user's timezone |
| Cannot install to home screen | The app must be served over HTTPS with a valid manifest and service worker |

---

## Documentation

Further project documentation lives in the `docs/` folder.

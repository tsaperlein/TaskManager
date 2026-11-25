# Task Manager

A standalone web app for Reza Tabriz’s two-week technical challenge. You can create, view, edit, complete, and delete tasks on one page. PostgreSQL saves your tasks across browser refreshes and service restarts.

**GitHub submission deadline** — Tuesday, 1 December 2026.

**Individual demonstration period** — 1–7 December 2026. Reza will confirm the time.

## Prerequisites

- Git and Homebrew on macOS
- Node.js 20.9 or later and npm
- Python 3.11 with `venv` and pip
- Homebrew PostgreSQL 14 with an initialized local cluster and a PostgreSQL role matching your macOS username

This project was verified with Node.js 20.19, npm 10.8, Python 3.11, and PostgreSQL 14. The frontend uses Next.js, TypeScript, HTML, and plain CSS. The backend uses FastAPI and Psycopg with parameterised SQL.

## Install from a fresh checkout

```sh
git clone https://github.com/tsaperlein/TaskManager.git
cd TaskManager

npm ci --prefix frontend
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt

cp frontend/.env.local.example frontend/.env.local
cp backend/.env.example backend/.env
```

`npm ci` installs the exact frontend dependency tree in [package-lock.json](frontend/package-lock.json). The Python direct and transitive dependencies are pinned in [requirements.txt](backend/requirements.txt) for the verified setup.

| Variable | File | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | Base URL the browser uses to reach FastAPI. Leave it at `http://127.0.0.1:8000` for this setup. |
| `FRONTEND_ORIGIN` | `backend/.env` | Exact browser origin FastAPI allows. The default is `http://127.0.0.1:3000`. |
| `DATABASE_URL` | `backend/.env` | Psycopg connection URL. The example connects to `task_manager` on local PostgreSQL using the current user's database role. Adjust it if your installation requires another role or password. |

The frontend URL is public and is bundled into the production frontend at build time. Keep database credentials in the ignored backend environment file. Run the app on the loopback address for the local exercise.

## Set up PostgreSQL

Run these from the repository root. The first command makes this Homebrew PostgreSQL version's client tools available in the current shell. If PostgreSQL is already running on the expected local port, skip the `pg_ctl start` command. Create the database once.

```sh
export PATH="$(brew --prefix postgresql@14)/bin:$PATH"
pg_ctl -D "$(brew --prefix)/var/postgresql@14" \
  -l "$(brew --prefix)/var/postgresql@14/server.log" -w start
createdb -h 127.0.0.1 task_manager
psql -X -h 127.0.0.1 -d task_manager -v ON_ERROR_STOP=1 -f backend/schema.sql
```

[The schema](backend/schema.sql) defines one table. PostgreSQL assigns each task an integer `id`, which identifies it when you edit or delete it. The `title` is required, `description` is optional and defaults to an empty string, and `completed` starts as `false`.

## Run the application

In one terminal, start FastAPI from the repository root.

```sh
cd backend
set -a
source .env
set +a
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal, start Next.js from the repository root.

```sh
npm run dev --prefix frontend
```

Open [Task Manager](http://127.0.0.1:3000). Use this exact address so it matches `FRONTEND_ORIGIN`. If the database is temporarily unavailable, the page shows an error and lets you retry loading tasks once PostgreSQL is back.

To stop the app, press **Ctrl+C** in each app terminal. Then stop PostgreSQL if you started it for this project and nothing else is using the instance.

```sh
"$(brew --prefix postgresql@14)/bin/pg_ctl" \
  -D "$(brew --prefix)/var/postgresql@14" -m fast -w stop
```

To run a production frontend build, stop the development frontend first. Leave FastAPI and PostgreSQL running if you want to use the built page.

```sh
npm run build --prefix frontend
npm run start --prefix frontend
```

## REST API

| Method and path | JSON request | Success response |
| --- | --- | --- |
| `GET /tasks` | No body | `200` with the task list, ordered by ID |
| `POST /tasks` | `title` and optional `description` | `201` with the created task |
| `PUT /tasks/{id}` | `title`, `description`, and Boolean `completed` | `200` with the updated task |
| `DELETE /tasks/{id}` | No body | `204` with an empty response |

FastAPI trims the title and rejects blank titles. Titles and descriptions are limited to 200 and 2,000 characters. The API returns `422` for invalid input, `404` when the task to edit or delete is missing, and `503` when the database connection fails.

### Try the API in Swagger UI

Start PostgreSQL and FastAPI, then open [FastAPI Swagger UI](http://127.0.0.1:8000/docs). This works without starting Next.js.

1. Expand **POST /tasks**, select **Try it out**, and enter `{"title":"Swagger demo","description":"A sample task"}`. Select **Execute**. Look for `201` and copy the `id` from the JSON response.
2. Expand **GET /tasks**, select **Try it out**, and execute it. Look for the new task in the list.
3. Expand **PUT /tasks/{task_id}**, enter that ID and `{"title":"Swagger demo updated","description":"A sample task","completed":true}`, and execute it. The response should show the new title and `completed: true`.
4. Expand **DELETE /tasks/{task_id}** and execute it with the ID of your sample task. Expect `204`. Run **GET /tasks** again to check the sample is gone.

### Inspect records directly with psql

Open a terminal while PostgreSQL is running.

```sh
"$(brew --prefix postgresql@14)/bin/psql" -X -h 127.0.0.1 -d task_manager
```

At the `psql` prompt, run these read-only commands. Try the `SELECT` after creating or completing a sample task in the page or Swagger UI.

```sql
\conninfo
\dt
\d tasks
SELECT id, title, description, completed FROM tasks ORDER BY id;
\q
```

## Run the integration tests

With PostgreSQL running on the default local port, create the test database once. The suite applies the schema to it automatically.

```sh
"$(brew --prefix postgresql@14)/bin/createdb" -h 127.0.0.1 task_manager_test
backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

[The suite](backend/tests/test_tasks_api.py) always uses the local `task_manager_test` database. It checks the database name before applying the schema, supplies its own connection URL, and starts its own FastAPI process on a free port. It ignores the development `DATABASE_URL`, does not use the development API process, and cleans up only records it creates. Coverage includes the full create, list, edit, complete, and delete flow, invalid input, missing IDs, browser CORS, and Swagger availability.

## How it works

1. [The Next.js page](frontend/app/page.tsx) uses HTML form controls and CSS. Its TypeScript code handles user actions and calls `fetch`. It updates the displayed list from successful API responses.
2. [FastAPI](backend/main.py) exposes the REST API. A REST API gives clients HTTP methods for working with resources like tasks. Here, `GET` reads them, `POST` creates one, `PUT` replaces a task's editable state, and `DELETE` removes one. JSON represents task fields in requests and responses.
3. [The database schema](backend/schema.sql) defines how PostgreSQL stores each task. Psycopg passes user values separately from the SQL text. FastAPI commits successful writes through the connection context, then sends the saved result back to the browser.

When you add a task, the page serializes the title and description to JSON. FastAPI validates those values and runs an `INSERT`. For an edit or completion, the page sends the full task state and FastAPI runs an `UPDATE` using the task ID. For deletion, FastAPI runs a `DELETE` using that same ID. On refresh, the browser starts with fresh UI state and asks FastAPI for the current rows. Those rows still exist because PostgreSQL committed them to storage.

Git records the implementation in stages. GitHub hosts the pushed `main` branch and its history. Run `git log --oneline` to see the separate scaffolding, API, frontend, and documentation commits.

## Demonstration walkthrough

1. Open the task page and the browser’s Network panel. Create a task and show the `POST /tasks` request body and `201` response, including the database-generated ID.
2. Open `psql`, select from `tasks`, and point to the same row. Refresh the page and show how `GET /tasks` loads it again.
3. Edit the title, then mark the task complete. Compare the two `PUT` payloads and show the updated row. If asked about persistence, restart the app processes before refreshing.
4. Delete the demo task and show the `204` response. Use Swagger UI to explain how you can test the API independently of the page.

| Question Reza might ask | What to explain |
| --- | --- |
| Where is the source of truth? | PostgreSQL stores the task rows. The page keeps a temporary copy for rendering. |
| Why validate in FastAPI if the page already validates? | Swagger, scripts, and other clients can call the API directly. Backend validation applies to all requests. |
| Why use SQL parameters? | Psycopg sends field values separately so PostgreSQL treats user input as data. |
| Why does completion use the edit route? | Completion changes the `completed` field of the same task. The page sends the full state through `PUT`. |
| Why configure a frontend origin? | The browser treats different ports as different origins. FastAPI allows requests from the configured page origin. |

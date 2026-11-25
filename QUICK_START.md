# Task Manager quick start

These commands assume the local checkout is already set up. For a fresh clone, follow the [installation and database setup in the README](README.md#install-from-a-fresh-checkout).

## 1. Start PostgreSQL and FastAPI

In **Terminal 1**, run the following from the directory containing your TaskManager checkout. Skip the `pg_ctl` command if PostgreSQL is already running.

```sh
cd TaskManager

"$(brew --prefix postgresql@14)/bin/pg_ctl" \
  -D "$(brew --prefix)/var/postgresql@14" \
  -l "$(brew --prefix)/var/postgresql@14/server.log" -w start

cd backend
set -a
source .env
set +a
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Leave this terminal open.

## 2. Start and use the app

In **Terminal 2**, start from the same parent directory and run:

```sh
cd TaskManager
npm run dev --prefix frontend
```

Open [Task Manager](http://127.0.0.1:3000). Enter a title and an optional description, then select **Add task**. Use **Edit**, **Mark complete**, or **Delete** on an existing task. Refresh the page to see that saved tasks are still there.

## 3. Test the API

Open [Swagger UI](http://127.0.0.1:8000/docs). Only PostgreSQL and FastAPI need to be running. For each request, select **Try it out**, enter the input if required, then select **Execute**.

| Request | What to try |
| --- | --- |
| `POST /tasks` | Send `{"title":"Demo task"}`. Expect `201` and copy the returned `id`. |
| `GET /tasks` | Expect `200` and find the demo task in the list. |
| `PUT /tasks/{task_id}` | Enter the same ID and send `{"title":"Updated demo","description":"","completed":true}`. Expect `200`. |
| `DELETE /tasks/{task_id}` | Enter your demo task’s ID. Expect `204`. Run `GET` again to confirm it’s gone. |

For automated API tests, keep PostgreSQL running and run the command below from the repository root. The suite starts its own API process and uses the separate `task_manager_test` database. On a fresh setup, [create that database first](README.md#run-the-integration-tests).

```sh
backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

## 4. What to show in the demo

Create a task in Swagger, refresh the app, and show that the same task appears. The browser sends HTTP requests and reads JSON. FastAPI validates the input and runs SQL through Psycopg. PostgreSQL stores the task, so a fresh `GET /tasks` can retrieve it. You can also [inspect the row directly with psql](README.md#inspect-records-directly-with-psql).

## Stop the app

Press **Ctrl+C** in both app terminals. If you started PostgreSQL for this project and nothing else is using it, stop it with:

```sh
"$(brew --prefix postgresql@14)/bin/pg_ctl" \
  -D "$(brew --prefix)/var/postgresql@14" -m fast -w stop
```

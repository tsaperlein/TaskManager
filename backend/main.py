import os
from typing import Annotated

import psycopg
from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from pydantic import BaseModel, StrictBool, StringConstraints

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI(title="Task Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ["FRONTEND_ORIGIN"]],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

# PostgreSQL text fields cannot store a NUL character.
NO_NUL = r"^[^\x00]*$"
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=NO_NUL)
]
Description = Annotated[str, StringConstraints(max_length=2000, pattern=NO_NUL)]
TaskId = Annotated[int, Path(ge=1, le=2_147_483_647)]


class TaskCreate(BaseModel):
    title: Title
    description: Description = ""


class TaskUpdate(BaseModel):
    title: Title
    description: Description
    completed: StrictBool


class Task(TaskUpdate):
    id: int


def connect():
    # The connection context commits on success, rolls back on failure, and closes.
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=3)


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(_request: Request, _error: psycopg.OperationalError):
    return JSONResponse(status_code=503, content={"detail": "Database unavailable. Try again."})


@app.get("/tasks", response_model=list[Task])
def list_tasks():
    with connect() as connection:
        return connection.execute(
            "SELECT id, title, description, completed FROM tasks ORDER BY id"
        ).fetchall()


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: TaskCreate):
    with connect() as connection:
        return connection.execute(
            """
            INSERT INTO tasks (title, description) VALUES (%s, %s)
            RETURNING id, title, description, completed
            """,
            (task.title, task.description),
        ).fetchone()


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: TaskId, task: TaskUpdate):
    with connect() as connection:
        updated = connection.execute(
            """
            UPDATE tasks SET title = %s, description = %s, completed = %s
            WHERE id = %s
            RETURNING id, title, description, completed
            """,
            (task.title, task.description, task.completed, task_id),
        ).fetchone()
        if updated is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return updated


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: TaskId):
    with connect() as connection:
        deleted = connection.execute(
            "DELETE FROM tasks WHERE id = %s RETURNING id",
            (task_id,),
        ).fetchone()
        if deleted is None:
            raise HTTPException(status_code=404, detail="Task not found.")

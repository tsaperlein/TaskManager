'use client';

import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

type TaskDetails = {
  title: string;
  description: string;
};

type Task = TaskDetails & {
  id: number;
  completed: boolean;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const emptyDraft: TaskDetails = { title: '', description: '' };

async function requestTasks(path: string, options?: RequestInit) {
  if (!apiUrl) {
    throw new Error('Set NEXT_PUBLIC_API_URL to connect to the task API.');
  }

  let response: Response;
  try {
    response = await fetch(`${apiUrl}/tasks${path}`, options);
  } catch (error) {
    if (options?.signal?.aborted) throw error;
    throw new Error('Could not reach the task API. Check that FastAPI is running.');
  }

  if (response.ok) return response;

  if (response.status === 422) {
    throw new Error('Check the task details and try again.');
  }

  const body: { detail?: unknown } | null = await response.json().catch(() => null);
  throw new Error(
    typeof body?.detail === 'string' ? body.detail : 'The request failed. Try again.',
  );
}

export default function Home() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [newTask, setNewTask] = useState(emptyDraft);
  const [edit, setEdit] = useState<{ id: number; draft: TaskDetails } | null>(null);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState('');
  const [status, setStatus] = useState('');
  const titleInput = useRef<HTMLInputElement>(null);
  const listHeading = useRef<HTMLHeadingElement>(null);
  const editingTask = tasks.find((task) => task.id === edit?.id);
  const draft = edit?.draft ?? newTask;

  useEffect(() => {
    const controller = new AbortController();

    async function loadTasks() {
      try {
        const response = await requestTasks('', { signal: controller.signal });
        const savedTasks: Task[] = await response.json();
        if (!controller.signal.aborted) setTasks(savedTasks);
      } catch (error) {
        if (!controller.signal.aborted) setLoadError((error as Error).message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadTasks();
    return () => controller.abort();
  }, [loadAttempt]);

  function retryLoad() {
    setLoadError('');
    setLoading(true);
    setLoadAttempt((attempt) => attempt + 1);
  }

  function updateDraft(field: keyof TaskDetails, value: string) {
    if (edit) {
      setEdit({ ...edit, draft: { ...edit.draft, [field]: value } });
    } else {
      setNewTask({ ...newTask, [field]: value });
    }
    setActionError('');
  }

  function startEditing(task: Task) {
    setEdit({ id: task.id, draft: { title: task.title, description: task.description } });
    setActionError('');
    setStatus('');
    titleInput.current?.focus();
  }

  function cancelEditing() {
    if (edit) document.getElementById(`edit-task-${edit.id}`)?.focus();
    setEdit(null);
    setActionError('');
  }

  async function runAction(action: () => Promise<void>) {
    setPending(true);
    setActionError('');
    setStatus('');
    try {
      await action();
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setPending(false);
    }
  }

  async function saveTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = draft.title.trim();
    if (!title) {
      setActionError('Enter a task title.');
      titleInput.current?.focus();
      return;
    }

    if (editingTask) {
      await updateTask(
        { ...editingTask, title, description: draft.description },
        'Task updated.',
        true,
      );
      return;
    }

    await runAction(async () => {
      const response = await requestTasks('', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description: draft.description }),
      });
      const task: Task = await response.json();
      setTasks((current) => [...current, task]);
      setNewTask(emptyDraft);
      titleInput.current?.focus();
      setStatus('Task added.');
    });
  }

  async function updateTask(task: Task, message: string, finishEditing = false) {
    await runAction(async () => {
      const { id, title, description, completed } = task;
      const response = await requestTasks(`/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description, completed }),
      });
      const saved: Task = await response.json();
      setTasks((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      if (finishEditing) setEdit(null);
      document.getElementById(`task-title-${id}`)?.focus();
      setStatus(message);
    });
  }

  async function deleteTask(task: Task) {
    await runAction(async () => {
      await requestTasks(`/${task.id}`, { method: 'DELETE' });
      listHeading.current?.focus();
      setTasks((current) => current.filter((item) => item.id !== task.id));
      if (edit?.id === task.id) setEdit(null);
      setStatus('Task deleted.');
    });
  }

  const formDisabled = loading || Boolean(loadError) || pending;

  return (
    <main>
      <h1>Task Manager</h1>

      <section className="panel" aria-labelledby="form-heading">
        <h2 id="form-heading">{editingTask ? 'Edit task' : 'Add a task'}</h2>
        <form onSubmit={saveTask} aria-labelledby="form-heading">
          <div className="field">
            <label htmlFor="title">Title</label>
            <input
              id="title"
              ref={titleInput}
              required
              maxLength={200}
              value={draft.title}
              onChange={(event) => updateDraft('title', event.target.value)}
              readOnly={formDisabled}
            />
          </div>
          <div className="field">
            <label htmlFor="description">Description <span>(optional)</span></label>
            <textarea
              id="description"
              rows={3}
              maxLength={2000}
              value={draft.description}
              onChange={(event) => updateDraft('description', event.target.value)}
              readOnly={formDisabled}
            />
          </div>
          <div className="actions">
            <button className="primary" disabled={formDisabled} type="submit">
              {editingTask ? 'Save changes' : 'Add task'}
            </button>
            {editingTask && (
              <button disabled={pending} type="button" onClick={cancelEditing}>Cancel</button>
            )}
          </div>
        </form>
      </section>

      {actionError && <p className="feedback error" role="alert">{actionError}</p>}
      <div className="feedback" role="status">{pending ? 'Saving…' : status}</div>

      <section className="task-section" aria-labelledby="tasks-heading">
        <h2 id="tasks-heading" tabIndex={-1} ref={listHeading}>Tasks</h2>
        {loading && <p role="status">Loading tasks…</p>}
        {loadError && (
          <div className="panel">
            <p className="error" role="alert">{loadError}</p>
            <button type="button" onClick={retryLoad}>Retry</button>
          </div>
        )}
        {!loading && !loadError && tasks.length === 0 && (
          <p className="panel">No tasks yet.</p>
        )}
        {tasks.length > 0 && (
          <ul className="task-list">
            {tasks.map((task) => (
              <li className="panel task" key={task.id}>
                <div className="task-details">
                  <h3 id={`task-title-${task.id}`} tabIndex={-1}>{task.title}</h3>
                  {task.description && <p className="description">{task.description}</p>}
                  {task.completed && <p className="completed">Completed</p>}
                </div>
                <div className="actions" role="group" aria-label={`Actions for ${task.title}`}>
                  {!task.completed && (
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => updateTask({ ...task, completed: true }, 'Task completed.')}
                    >
                      Mark complete
                    </button>
                  )}
                  <button
                    type="button"
                    id={`edit-task-${task.id}`}
                    disabled={pending}
                    onClick={() => startEditing(task)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="danger"
                    disabled={pending}
                    onClick={() => deleteTask(task)}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

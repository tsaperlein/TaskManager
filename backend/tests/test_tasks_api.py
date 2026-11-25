import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg

BACKEND = Path(__file__).resolve().parents[1]
TEST_DATABASE = "task_manager_test"
TEST_DATABASE_URL = f"postgresql://127.0.0.1:5432/{TEST_DATABASE}"
FRONTEND_ORIGIN = "http://127.0.0.1:3000"


class TasksAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The suite never uses the development DSN or a pre-existing HTTP server.
        with psycopg.connect(TEST_DATABASE_URL, connect_timeout=3) as connection:
            database, = connection.execute("SELECT current_database()").fetchone()
            if database != TEST_DATABASE:
                raise RuntimeError(f"Expected the test database, got {database!r}.")
            connection.execute((BACKEND / "schema.sql").read_text())

        # Reserve the port and pass the same socket to Uvicorn to avoid port races.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            cls.base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
            socket_fd = listener.fileno()
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "main:app", "--fd", str(socket_fd)],
                cwd=BACKEND,
                env=os.environ | {
                    "DATABASE_URL": TEST_DATABASE_URL,
                    "FRONTEND_ORIGIN": FRONTEND_ORIGIN,
                },
                pass_fds=(socket_fd,),
            )
        cls.addClassCleanup(cls.stop_server, server)

        deadline = time.monotonic() + 10
        while server.poll() is None and time.monotonic() < deadline:
            try:
                with urlopen(f"{cls.base_url}/openapi.json", timeout=0.5):
                    return
            except (URLError, TimeoutError):
                time.sleep(0.05)
        raise RuntimeError("The isolated test API did not start.")

    @staticmethod
    def stop_server(server):
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()

    def request(self, method, path, payload=None, headers=None):
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"} | (headers or {}),
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as response:
            with response:
                return response.code, response.read(), response.headers

    def task_list(self):
        status, body, _ = self.request("GET", "/tasks")
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_create_list_edit_complete_delete(self):
        status, body, _ = self.request("POST", "/tasks", {"title": "  Reza's demo  "})
        self.assertEqual(status, 201)
        task = json.loads(body)
        path = f"/tasks/{task['id']}"
        self.addCleanup(self.request, "DELETE", path)
        self.assertEqual(
            task,
            {"id": task["id"], "title": "Reza's demo", "description": "", "completed": False},
        )
        self.assertIn(task, self.task_list())

        for title, description, completed in (
            ("Updated demo", "Explain how SQL parameters work.", False),
            ("Updated demo", "Explain how SQL parameters work.", True),
        ):
            with self.subTest(completed=completed):
                fields = {"title": title, "description": description, "completed": completed}
                status, body, _ = self.request("PUT", path, fields)
                self.assertEqual(status, 200)
                expected = {"id": task["id"], **fields}
                self.assertEqual(json.loads(body), expected)
                self.assertIn(expected, self.task_list())

        status, body, _ = self.request("DELETE", path)
        self.assertEqual((status, body), (204, b""))
        self.assertFalse(any(item["id"] == task["id"] for item in self.task_list()))

        fields = {"title": "Missing", "description": "", "completed": False}
        self.assertEqual(self.request("PUT", path, fields)[0], 404)
        self.assertEqual(self.request("DELETE", path)[0], 404)

    def test_invalid_input_does_not_change_tasks(self):
        tasks_before = self.task_list()
        for payload in (
            {},
            {"title": ""},
            {"title": " \t "},
            {"title": "x" * 201},
            {"title": "Valid", "description": "x" * 2001},
            {"title": "Valid", "description": None},
            {"title": "Invalid\x00title"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("POST", "/tasks", payload)[0], 422)

        fields = {"title": "Valid", "description": "", "completed": "true"}
        self.assertEqual(self.request("PUT", "/tasks/1", fields)[0], 422)
        self.assertEqual(self.request("DELETE", "/tasks/0")[0], 422)
        self.assertEqual(self.task_list(), tasks_before)

    def test_browser_preflight_and_docs(self):
        status, _, headers = self.request(
            "OPTIONS",
            "/tasks/1",
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], FRONTEND_ORIGIN)
        status, body, _ = self.request("GET", "/docs")
        self.assertEqual(status, 200)
        self.assertIn(b"Swagger UI", body)

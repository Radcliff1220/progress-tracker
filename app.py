from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from openpyxl import Workbook


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("DB_PATH", DATA_DIR / "progress.db"))
STATIC_DIR = BASE_DIR / "static"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows(cur: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cur.fetchall()]


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                workload REAL NOT NULL DEFAULT 1,
                confirmed_progress REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, name)
            );

            CREATE TABLE IF NOT EXISTS project_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                progress REAL NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS research_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                stage TEXT NOT NULL,
                progress REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS task_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                confirmed_progress REAL NOT NULL,
                admin_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('admin_password', ?)",
            (DEFAULT_ADMIN_PASSWORD,),
        )
        for name in ["张三", "李四", "王五"]:
            conn.execute(
                "INSERT OR IGNORE INTO users(name, active, created_at) VALUES(?, 1, ?)",
                (name, now_text()),
            )
        for project in ["A", "B", "C"]:
            conn.execute(
                "INSERT OR IGNORE INTO projects(name, active, created_at) VALUES(?, 1, ?)",
                (project, now_text()),
            )
        project_ids = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM projects").fetchall()
        }
        for project, project_id in project_ids.items():
            for task_no in range(1, 10):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO tasks(project_id, name, workload, confirmed_progress, active, created_at)
                    VALUES(?, ?, 10, 0, 1, ?)
                    """,
                    (project_id, f"任务{task_no}", now_text()),
                )


def get_payload(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length == 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw or "{}")


def check_admin(handler: BaseHTTPRequestHandler) -> bool:
    password = handler.headers.get("X-Admin-Password", "")
    with connect() as conn:
        expected = conn.execute(
            "SELECT value FROM settings WHERE key = 'admin_password'"
        ).fetchone()["value"]
    return password == expected


def get_bootstrap() -> dict:
    with connect() as conn:
        users = rows(conn.execute("SELECT * FROM users ORDER BY active DESC, name"))
        projects = rows(conn.execute("SELECT * FROM projects ORDER BY active DESC, name"))
        tasks = rows(
            conn.execute(
                """
                SELECT t.*, p.name AS project_name
                FROM tasks t
                JOIN projects p ON p.id = t.project_id
                ORDER BY p.name, t.name
                """
            )
        )
    return {"users": users, "projects": projects, "tasks": tasks}


def get_stats() -> dict:
    with connect() as conn:
        project_progress = rows(
            conn.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    COALESCE(SUM(t.workload), 0) AS total_workload,
                    COALESCE(SUM(t.workload * t.confirmed_progress / 100.0), 0) AS done_workload,
                    CASE
                        WHEN COALESCE(SUM(t.workload), 0) = 0 THEN 0
                        ELSE ROUND(SUM(t.workload * t.confirmed_progress) / SUM(t.workload), 2)
                    END AS progress
                FROM projects p
                LEFT JOIN tasks t ON t.project_id = p.id AND t.active = 1
                GROUP BY p.id, p.name
                ORDER BY p.name
                """
            )
        )
        task_rollup = rows(
            conn.execute(
                """
                SELECT
                    t.id,
                    t.active,
                    t.project_id,
                    p.name AS project_name,
                    t.name AS task_name,
                    t.workload,
                    t.confirmed_progress,
                    COALESCE(SUM(ps.progress), 0) AS submitted_progress,
                    COUNT(ps.id) AS submission_count
                FROM tasks t
                JOIN projects p ON p.id = t.project_id
                LEFT JOIN project_submissions ps ON ps.task_id = t.id
                GROUP BY t.id
                ORDER BY p.name, t.name
                """
            )
        )
        contributions = rows(
            conn.execute(
                """
                SELECT
                    u.name AS user_name,
                    p.name AS project_name,
                    ROUND(SUM(t.workload * ps.progress / 100.0), 2) AS contribution_workload,
                    ROUND(
                        CASE WHEN totals.total_workload = 0 THEN 0
                        ELSE SUM(t.workload * ps.progress / 100.0) * 100.0 / totals.total_workload
                        END,
                        2
                    ) AS contribution_percent
                FROM project_submissions ps
                JOIN users u ON u.id = ps.user_id
                JOIN projects p ON p.id = ps.project_id
                JOIN tasks t ON t.id = ps.task_id
                JOIN (
                    SELECT project_id, SUM(workload) AS total_workload
                    FROM tasks
                    WHERE active = 1
                    GROUP BY project_id
                ) totals ON totals.project_id = p.id
                GROUP BY u.id, p.id
                ORDER BY p.name, contribution_percent DESC, u.name
                """
            )
        )
        research_latest = rows(
            conn.execute(
                """
                SELECT u.name AS user_name, rs.title, rs.stage, rs.progress, rs.created_at
                FROM research_submissions rs
                JOIN users u ON u.id = rs.user_id
                JOIN (
                    SELECT user_id, MAX(created_at) AS created_at
                    FROM research_submissions
                    GROUP BY user_id
                ) latest ON latest.user_id = rs.user_id AND latest.created_at = rs.created_at
                ORDER BY u.name
                """
            )
        )
        project_history = rows(
            conn.execute(
                """
                SELECT ps.id, u.name AS user_name, p.name AS project_name, t.name AS task_name,
                       ps.progress, ps.note, ps.created_at
                FROM project_submissions ps
                JOIN users u ON u.id = ps.user_id
                JOIN projects p ON p.id = ps.project_id
                JOIN tasks t ON t.id = ps.task_id
                ORDER BY ps.created_at DESC, ps.id DESC
                LIMIT 500
                """
            )
        )
        research_history = rows(
            conn.execute(
                """
                SELECT rs.id, u.name AS user_name, rs.title, rs.stage, rs.progress, rs.created_at
                FROM research_submissions rs
                JOIN users u ON u.id = rs.user_id
                ORDER BY rs.created_at DESC, rs.id DESC
                LIMIT 500
                """
            )
        )
    return {
        "project_progress": project_progress,
        "task_rollup": task_rollup,
        "contributions": contributions,
        "research_latest": research_latest,
        "project_history": project_history,
        "research_history": research_history,
    }


def make_export() -> Path:
    data = get_stats()
    bootstrap = get_bootstrap()
    wb = Workbook()
    sheets = [
        ("项目整体进度", data["project_progress"]),
        ("任务汇总", data["task_rollup"]),
        ("个人项目贡献", data["contributions"]),
        ("科研最新进展", data["research_latest"]),
        ("项目历史记录", data["project_history"]),
        ("科研历史记录", data["research_history"]),
        ("人员", bootstrap["users"]),
        ("项目", bootstrap["projects"]),
        ("任务", bootstrap["tasks"]),
    ]
    for idx, (title, records) in enumerate(sheets):
        ws = wb.active if idx == 0 else wb.create_sheet()
        ws.title = title
        if not records:
            ws.append(["暂无数据"])
            continue
        headers = list(records[0].keys())
        ws.append(headers)
        for record in records:
            ws.append([record.get(key, "") for key in headers])
        for column_cells in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(max_len + 2, 35)
    export_path = BASE_DIR / f"进展统计导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(export_path)
    return export_path


class Handler(BaseHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Password")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def write_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def write_error(self, message: str, status: int = 400) -> None:
        self.write_json({"error": message}, status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            return self.serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/api/bootstrap":
            return self.write_json(get_bootstrap())
        if path == "/api/stats":
            return self.write_json(get_stats())
        if path == "/api/export":
            if not check_admin(self):
                return self.write_error("管理员密码错误", 401)
            export_path = make_export()
            raw = export_path.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header("Content-Disposition", "attachment; filename=progress_export.xlsx")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path.startswith("/static/"):
            target = STATIC_DIR / path.replace("/static/", "", 1)
            ctype = "text/plain"
            if target.suffix == ".css":
                ctype = "text/css; charset=utf-8"
            elif target.suffix == ".js":
                ctype = "application/javascript; charset=utf-8"
            return self.serve_file(target, ctype)
        return self.write_error("未找到页面", 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = get_payload(self)
        try:
            if path == "/api/project-submissions":
                return self.add_project_submission(payload)
            if path == "/api/research-submissions":
                return self.add_research_submission(payload)
            if path == "/api/admin/login":
                ok = check_admin(self) or payload.get("password") == self.get_admin_password()
                return self.write_json({"ok": ok}, 200 if ok else 401)
            if not check_admin(self):
                return self.write_error("管理员密码错误", 401)
            if path == "/api/admin/users":
                return self.create_user(payload)
            if path == "/api/admin/projects":
                return self.create_project(payload)
            if path == "/api/admin/tasks":
                return self.create_task(payload)
            if path == "/api/admin/confirm-task":
                return self.confirm_task(payload)
            if path == "/api/admin/password":
                return self.change_password(payload)
        except sqlite3.IntegrityError as exc:
            return self.write_error(f"数据重复或引用错误：{exc}", 400)
        except (KeyError, ValueError, TypeError) as exc:
            return self.write_error(f"参数错误：{exc}", 400)
        return self.write_error("未找到接口", 404)

    def do_PUT(self) -> None:
        if not check_admin(self):
            return self.write_error("管理员密码错误", 401)
        payload = get_payload(self)
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/admin/users/"):
                return self.update_user(int(path.rsplit("/", 1)[1]), payload)
            if path.startswith("/api/admin/projects/"):
                return self.update_project(int(path.rsplit("/", 1)[1]), payload)
            if path.startswith("/api/admin/tasks/"):
                return self.update_task(int(path.rsplit("/", 1)[1]), payload)
        except sqlite3.IntegrityError as exc:
            return self.write_error(f"数据重复或引用错误：{exc}", 400)
        except (KeyError, ValueError, TypeError) as exc:
            return self.write_error(f"参数错误：{exc}", 400)
        return self.write_error("未找到接口", 404)

    def serve_file(self, path: Path, ctype: str) -> None:
        if not path.exists() or not path.is_file():
            return self.write_error("文件不存在", 404)
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def get_admin_password(self) -> str:
        with connect() as conn:
            return conn.execute("SELECT value FROM settings WHERE key='admin_password'").fetchone()["value"]

    def add_project_submission(self, payload: dict) -> None:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO project_submissions(user_id, project_id, task_id, progress, note, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    int(payload["user_id"]),
                    int(payload["project_id"]),
                    int(payload["task_id"]),
                    float(payload["progress"]),
                    payload.get("note", ""),
                    now_text(),
                ),
            )
        self.write_json({"ok": True})

    def add_research_submission(self, payload: dict) -> None:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO research_submissions(user_id, title, stage, progress, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    int(payload["user_id"]),
                    payload["title"].strip(),
                    payload["stage"],
                    float(payload["progress"]),
                    now_text(),
                ),
            )
        self.write_json({"ok": True})

    def create_user(self, payload: dict) -> None:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO users(name, active, created_at) VALUES(?, 1, ?)",
                (payload["name"].strip(), now_text()),
            )
        self.write_json({"ok": True, "id": cur.lastrowid})

    def create_project(self, payload: dict) -> None:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects(name, active, created_at) VALUES(?, 1, ?)",
                (payload["name"].strip(), now_text()),
            )
        self.write_json({"ok": True, "id": cur.lastrowid})

    def create_task(self, payload: dict) -> None:
        with connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks(project_id, name, workload, confirmed_progress, active, created_at)
                VALUES(?, ?, ?, 0, 1, ?)
                """,
                (
                    int(payload["project_id"]),
                    payload["name"].strip(),
                    float(payload["workload"]),
                    now_text(),
                ),
            )
        self.write_json({"ok": True, "id": cur.lastrowid})

    def update_user(self, item_id: int, payload: dict) -> None:
        with connect() as conn:
            conn.execute(
                "UPDATE users SET name = ?, active = ? WHERE id = ?",
                (payload["name"].strip(), int(payload.get("active", 1)), item_id),
            )
        self.write_json({"ok": True})

    def update_project(self, item_id: int, payload: dict) -> None:
        with connect() as conn:
            conn.execute(
                "UPDATE projects SET name = ?, active = ? WHERE id = ?",
                (payload["name"].strip(), int(payload.get("active", 1)), item_id),
            )
        self.write_json({"ok": True})

    def update_task(self, item_id: int, payload: dict) -> None:
        with connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET name = ?, workload = ?, active = ?, confirmed_progress = ?
                WHERE id = ?
                """,
                (
                    payload["name"].strip(),
                    float(payload["workload"]),
                    int(payload.get("active", 1)),
                    float(payload.get("confirmed_progress", 0)),
                    item_id,
                ),
            )
        self.write_json({"ok": True})

    def confirm_task(self, payload: dict) -> None:
        progress = max(0, min(100, float(payload["confirmed_progress"])))
        with connect() as conn:
            conn.execute(
                "UPDATE tasks SET confirmed_progress = ? WHERE id = ?",
                (progress, int(payload["task_id"])),
            )
            conn.execute(
                """
                INSERT INTO task_confirmations(task_id, confirmed_progress, admin_note, created_at)
                VALUES(?, ?, ?, ?)
                """,
                (int(payload["task_id"]), progress, payload.get("admin_note", ""), now_text()),
            )
        self.write_json({"ok": True})

    def change_password(self, payload: dict) -> None:
        password = payload["new_password"].strip()
        if len(password) < 4:
            raise ValueError("密码至少 4 位")
        with connect() as conn:
            conn.execute("UPDATE settings SET value = ? WHERE key = 'admin_password'", (password,))
        self.write_json({"ok": True})


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"进展填报系统已启动：http://{HOST}:{PORT}")
    print(f"管理员初始密码：{DEFAULT_ADMIN_PASSWORD}")
    server.serve_forever()

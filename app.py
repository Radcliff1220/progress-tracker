from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from openpyxl import Workbook


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("DB_PATH", DATA_DIR / "progress.db"))
STATIC_DIR = BASE_DIR / "static"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
CATALOG_VERSION = "2026-07-10-catalog-v4"

DEFAULT_USERS = [
    "乔舒", "余欣然", "刘倩竹", "刘康", "刘自豪", "叶栩彤", "吕志锦", "孙榕",
    "崔永平", "张明威", "张润莹", "张骁", "徐浩阳", "房孟君", "朱浩楠", "李浩月",
    "李鹏飞", "毛文涛", "焉城菡", "王彩霞", "秦钰叶", "董一凡", "胡恺元", "胡添欢",
    "蒋竺宴", "蔡年杰", "邵梓效", "陈宜建", "陈海龙", "高兴", "高林越", "黄梦娇",
]

DEFAULT_PROJECTS = [
    "南通配微", "双碳", "多主体虚拟电厂", "海风", "盐城配微",
    "端侧感知", "虚拟电厂面包", "车网互动", "零碳城市",
]

DEFAULT_TASKS = ["任务1", "任务2", "任务3"]

DEFAULT_PROJECT_TASKS = {
    "南通配微": [
        ("研究内容1", 10), ("研究内容2", 10), ("研究内容3", 10), ("研究内容4", 10),
        ("论文", 20), ("专利1", 10), ("专利2", 10), ("标准", 10), ("材料整理", 10),
    ],
    "双碳": [
        ("研究内容2.4-1", 10), ("研究内容2.4-2", 10), ("软著", 10),
    ],
    "多主体虚拟电厂": [
        ("研究内容1", 10), ("研究内容2", 10), ("研究内容3", 10), ("研究内容4", 10),
        ("论文1", 20), ("论文2", 10), ("专利1", 10), ("专利2", 10), ("专利3", 10),
        ("专利4", 10), ("软著+测试", 20), ("材料整理", 10),
    ],
    "海风": [
        ("研究内容1", 10), ("研究内容2", 10), ("研究内容3", 10), ("论文1", 20),
        ("论文2", 20), ("论文3", 10), ("专利1", 10), ("专利2", 10), ("专利3", 20),
        ("材料整理", 10),
    ],
    "盐城配微": [
        ("研究内容1", 10), ("研究内容2", 10), ("研究内容3", 10), ("研究内容4", 10),
        ("论文", 10), ("专利1", 10), ("专利2", 10), ("专利3", 10), ("专利4", 10),
        ("软著+测试", 20), ("标准", 10), ("材料整理", 10),
    ],
    "端侧感知": [
        ("研究内容1-1", 5), ("研究内容1-2", 5), ("研究内容1-3", 5),
    ],
    "虚拟电厂面包": [
        ("研究内容1", 10), ("研究内容2", 10), ("研究内容3", 10), ("研究内容4", 5),
        ("专利1", 5), ("专利2", 5), ("材料整理", 5),
    ],
    "车网互动": [
        ("任务1", 10), ("任务2", 10), ("任务3", 10), ("材料整理", 10),
    ],
    "零碳城市": [
        ("研究内容1", 10), ("研究内容2", 10), ("材料整理", 10),
    ],
}


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
                status TEXT NOT NULL DEFAULT 'active',
                admin_reply TEXT NOT NULL DEFAULT '',
                admin_replied_at TEXT NOT NULL DEFAULT '',
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
                note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                admin_reply TEXT NOT NULL DEFAULT '',
                admin_replied_at TEXT NOT NULL DEFAULT '',
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
        migrate_db(conn)
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('admin_password', ?)",
            (DEFAULT_ADMIN_PASSWORD,),
        )
        reset_catalog_if_needed(conn)
        seed_defaults(conn)


def migrate_db(conn: sqlite3.Connection) -> None:
    ensure_columns(conn, "project_submissions", {
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "admin_reply": "TEXT NOT NULL DEFAULT ''",
        "admin_replied_at": "TEXT NOT NULL DEFAULT ''",
    })
    ensure_columns(conn, "research_submissions", {
        "note": "TEXT NOT NULL DEFAULT ''",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "admin_reply": "TEXT NOT NULL DEFAULT ''",
        "admin_replied_at": "TEXT NOT NULL DEFAULT ''",
    })


def ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def reset_catalog_if_needed(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM settings WHERE key = 'catalog_version'").fetchone()
    if row and row["value"] == CATALOG_VERSION:
        return
    conn.executescript(
        """
        DELETE FROM project_submissions;
        DELETE FROM research_submissions;
        DELETE FROM task_confirmations;
        DELETE FROM tasks;
        DELETE FROM projects;
        DELETE FROM users;
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES('catalog_version', ?)",
        (CATALOG_VERSION,),
    )


def seed_defaults(conn: sqlite3.Connection) -> None:
    for name in DEFAULT_USERS:
        conn.execute(
            "INSERT OR IGNORE INTO users(name, active, created_at) VALUES(?, 1, ?)",
            (name, now_text()),
        )

    for project in DEFAULT_PROJECTS:
        conn.execute(
            "INSERT OR IGNORE INTO projects(name, active, created_at) VALUES(?, 1, ?)",
            (project, now_text()),
        )

    project_ids = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM projects").fetchall()
    }
    for project in DEFAULT_PROJECTS:
        for task_name, workload in DEFAULT_PROJECT_TASKS.get(
            project, [(task, 10) for task in DEFAULT_TASKS]
        ):
            conn.execute(
                """
                INSERT OR IGNORE INTO tasks(project_id, name, workload, confirmed_progress, active, created_at)
                VALUES(?, ?, ?, 0, 1, ?)
                """,
                (project_ids[project], task_name, workload, now_text()),
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
        projects = rows(conn.execute("SELECT * FROM projects ORDER BY active DESC, id"))
        tasks = rows(
            conn.execute(
                """
                SELECT t.*, p.name AS project_name
                FROM tasks t
                JOIN projects p ON p.id = t.project_id
                ORDER BY p.id, t.id
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
                    COALESCE(SUM(CASE WHEN t.active = 1 THEN t.workload ELSE 0 END), 0) AS total_workload,
                    COALESCE(SUM(CASE WHEN t.active = 1 THEN t.workload * t.confirmed_progress / 100.0 ELSE 0 END), 0) AS done_workload,
                    CASE
                        WHEN COALESCE(SUM(CASE WHEN t.active = 1 THEN t.workload ELSE 0 END), 0) = 0 THEN 0
                        ELSE ROUND(
                            SUM(CASE WHEN t.active = 1 THEN t.workload * t.confirmed_progress ELSE 0 END) /
                            SUM(CASE WHEN t.active = 1 THEN t.workload ELSE 0 END),
                            2
                        )
                    END AS progress
                FROM projects p
                LEFT JOIN tasks t ON t.project_id = p.id
                GROUP BY p.id, p.name
                ORDER BY p.id
                """
            )
        )
        task_rollup = rows(
            conn.execute(
                """
                WITH latest AS (
                    SELECT ps.*
                    FROM project_submissions ps
                    JOIN (
                        SELECT user_id, task_id, MAX(id) AS id
                        FROM project_submissions
                        WHERE status != 'revoked'
                        GROUP BY user_id, task_id
                    ) latest_ids ON latest_ids.id = ps.id
                )
                SELECT
                    t.id,
                    t.active,
                    t.project_id,
                    p.name AS project_name,
                    t.name AS task_name,
                    t.workload,
                    t.confirmed_progress,
                    COALESCE(SUM(latest.progress), 0) AS submitted_progress,
                    COUNT(latest.id) AS submission_count
                FROM tasks t
                JOIN projects p ON p.id = t.project_id
                LEFT JOIN latest ON latest.task_id = t.id
                GROUP BY t.id
                ORDER BY p.id, t.id
                """
            )
        )
        contributions = rows(
            conn.execute(
                """
                WITH latest AS (
                    SELECT ps.*
                    FROM project_submissions ps
                    JOIN (
                        SELECT user_id, task_id, MAX(id) AS id
                        FROM project_submissions
                        WHERE status != 'revoked'
                        GROUP BY user_id, task_id
                    ) latest_ids ON latest_ids.id = ps.id
                ),
                task_totals AS (
                    SELECT task_id, SUM(progress) AS total_progress
                    FROM latest
                    GROUP BY task_id
                )
                SELECT
                    u.id AS user_id,
                    u.name AS user_name,
                    p.id AS project_id,
                    p.name AS project_name,
                    ROUND(SUM(
                        CASE
                            WHEN COALESCE(task_totals.total_progress, 0) = 0 THEN 0
                            ELSE t.workload * t.confirmed_progress / 100.0 * latest.progress / task_totals.total_progress
                        END
                    ), 2) AS contribution_workload,
                    ROUND(
                        CASE WHEN totals.total_workload = 0 THEN 0
                        ELSE SUM(
                            CASE
                                WHEN COALESCE(task_totals.total_progress, 0) = 0 THEN 0
                                ELSE t.workload * t.confirmed_progress / 100.0 * latest.progress / task_totals.total_progress
                            END
                        ) * 100.0 / totals.total_workload
                        END,
                        2
                    ) AS contribution_percent
                FROM latest
                JOIN users u ON u.id = latest.user_id
                JOIN projects p ON p.id = latest.project_id
                JOIN tasks t ON t.id = latest.task_id
                LEFT JOIN task_totals ON task_totals.task_id = latest.task_id
                JOIN (
                    SELECT project_id, SUM(workload) AS total_workload
                    FROM tasks
                    WHERE active = 1
                    GROUP BY project_id
                ) totals ON totals.project_id = p.id
                GROUP BY u.id, p.id
                ORDER BY p.id, contribution_workload DESC, u.name
                """
            )
        )
        project_latest_submissions = rows(
            conn.execute(
                """
                WITH latest AS (
                    SELECT ps.*
                    FROM project_submissions ps
                    JOIN (
                        SELECT user_id, task_id, MAX(id) AS id
                        FROM project_submissions
                        WHERE status != 'revoked'
                        GROUP BY user_id, task_id
                    ) latest_ids ON latest_ids.id = ps.id
                ),
                task_totals AS (
                    SELECT task_id, SUM(progress) AS total_progress
                    FROM latest
                    GROUP BY task_id
                )
                SELECT latest.id, u.id AS user_id, u.name AS user_name, p.id AS project_id,
                       p.name AS project_name, t.id AS task_id, t.name AS task_name,
                       t.workload,
                       ROUND(
                           CASE
                               WHEN COALESCE(task_totals.total_progress, 0) = 0 THEN 0
                               ELSE t.workload * t.confirmed_progress / 100.0 * latest.progress / task_totals.total_progress
                           END,
                           2
                       ) AS contribution_workload,
                       latest.progress, latest.note, latest.status, latest.admin_reply,
                       latest.admin_replied_at, latest.created_at
                FROM latest
                JOIN users u ON u.id = latest.user_id
                JOIN projects p ON p.id = latest.project_id
                JOIN tasks t ON t.id = latest.task_id
                LEFT JOIN task_totals ON task_totals.task_id = latest.task_id
                ORDER BY latest.created_at DESC, latest.id DESC
                LIMIT 1000
                """
            )
        )
        research_latest = rows(
            conn.execute(
                """
                SELECT u.id AS user_id, u.name AS user_name, rs.id, rs.title, rs.stage, rs.progress,
                       rs.note, rs.status, rs.admin_reply, rs.admin_replied_at, rs.created_at
                FROM research_submissions rs
                JOIN users u ON u.id = rs.user_id
                JOIN (
                    SELECT user_id, MAX(id) AS id
                    FROM research_submissions
                    WHERE status != 'revoked'
                    GROUP BY user_id
                ) latest ON latest.id = rs.id
                ORDER BY u.name
                """
            )
        )
        project_history = rows(
            conn.execute(
                """
                SELECT ps.id, u.id AS user_id, u.name AS user_name, p.id AS project_id,
                       p.name AS project_name, t.id AS task_id, t.name AS task_name,
                       t.workload, ROUND(t.workload * ps.progress / 100.0, 2) AS contribution_workload,
                       ps.progress, ps.note, ps.status, ps.admin_reply, ps.admin_replied_at, ps.created_at
                FROM project_submissions ps
                JOIN users u ON u.id = ps.user_id
                JOIN projects p ON p.id = ps.project_id
                JOIN tasks t ON t.id = ps.task_id
                ORDER BY ps.created_at DESC, ps.id DESC
                LIMIT 1000
                """
            )
        )
        research_history = rows(
            conn.execute(
                """
                SELECT rs.id, u.id AS user_id, u.name AS user_name, rs.title, rs.stage, rs.progress,
                       rs.note, rs.status, rs.admin_reply, rs.admin_replied_at, rs.created_at
                FROM research_submissions rs
                JOIN users u ON u.id = rs.user_id
                ORDER BY rs.created_at DESC, rs.id DESC
                LIMIT 1000
                """
            )
        )
        confirmations = rows(
            conn.execute(
                """
                SELECT tc.id, t.id AS task_id, p.id AS project_id, p.name AS project_name,
                       t.name AS task_name, tc.confirmed_progress, tc.admin_note, tc.created_at
                FROM task_confirmations tc
                JOIN tasks t ON t.id = tc.task_id
                JOIN projects p ON p.id = t.project_id
                ORDER BY tc.created_at DESC, tc.id DESC
                LIMIT 500
                """
            )
        )
    return {
        "project_progress": project_progress,
        "task_rollup": task_rollup,
        "contributions": contributions,
        "project_latest_submissions": project_latest_submissions,
        "research_latest": research_latest,
        "project_history": project_history,
        "research_history": research_history,
        "confirmations": confirmations,
    }


def make_export() -> Path:
    data = get_stats()
    bootstrap = get_bootstrap()
    wb = Workbook()
    sheets = [
        ("项目整体进度", data["project_progress"]),
        ("任务汇总", data["task_rollup"]),
        ("个人项目贡献", data["contributions"]),
        ("个人任务最新填报", data["project_latest_submissions"]),
        ("科研最新进展", data["research_latest"]),
        ("项目历史记录", data["project_history"]),
        ("科研历史记录", data["research_history"]),
        ("确认修正记录", data["confirmations"]),
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
        path = urlparse(self.path).path
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
            if path == "/api/admin/review-submission":
                return self.review_submission(payload)
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
                INSERT INTO research_submissions(user_id, title, stage, progress, note, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    int(payload["user_id"]),
                    payload["title"].strip(),
                    payload["stage"],
                    float(payload["progress"]),
                    payload.get("note", ""),
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
            for task in DEFAULT_TASKS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO tasks(project_id, name, workload, confirmed_progress, active, created_at)
                    VALUES(?, ?, 10, 0, 1, ?)
                    """,
                    (cur.lastrowid, task, now_text()),
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
                    max(0, min(100, float(payload.get("confirmed_progress", 0)))),
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

    def review_submission(self, payload: dict) -> None:
        submission_type = payload["type"]
        table = {
            "project": "project_submissions",
            "research": "research_submissions",
        }.get(submission_type)
        if not table:
            raise ValueError("type 必须是 project 或 research")
        status = payload.get("status", "active")
        if status not in {"active", "revoked"}:
            raise ValueError("status 必须是 active 或 revoked")
        with connect() as conn:
            conn.execute(
                f"""
                UPDATE {table}
                SET status = ?, admin_reply = ?, admin_replied_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    payload.get("admin_reply", "").strip(),
                    now_text(),
                    int(payload["id"]),
                ),
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

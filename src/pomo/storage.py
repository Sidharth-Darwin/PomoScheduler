import sqlite3
import datetime
from typing import List, Dict, Any, Optional, cast
from pomo.utils import get_db_path, ensure_dirs


def get_connection() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_blueprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                max_pomodoros INTEGER DEFAULT 5,
                work_mins INTEGER DEFAULT 25,
                break_mins INTEGER DEFAULT 5,
                repeat_days TEXT, 
                scheduled_time TEXT,
                auto_start BOOLEAN DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                blueprint_id INTEGER,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                pomodoros_completed INTEGER DEFAULT 0,
                max_pomodoros INTEGER DEFAULT 5,
                work_mins INTEGER DEFAULT 25,
                break_mins INTEGER DEFAULT 5,
                scheduled_time TEXT,
                auto_start BOOLEAN DEFAULT 0,
                date_added DATE DEFAULT (DATE('now', 'localtime')),
                FOREIGN KEY(blueprint_id) REFERENCES task_blueprints(id)
            )
        """)
        conn.commit()


def spawn_daily_tasks():
    """Spawns tasks based on the specific day of the week."""
    today_str = str(datetime.datetime.today().weekday())  # 0=Mon, 6=Sun
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM task_blueprints")
        blueprints = cursor.fetchall()

        for bp in blueprints:
            # Check if today is one of the assigned repeating days
            if bp["repeat_days"] and today_str in bp["repeat_days"].split(","):
                cursor.execute(
                    """
                    SELECT id FROM daily_tasks 
                    WHERE blueprint_id = ? AND date_added = DATE('now', 'localtime')
                """,
                    (bp["id"],),
                )
                if not cursor.fetchone():
                    cursor.execute(
                        """
                        INSERT INTO daily_tasks (blueprint_id, name, max_pomodoros, work_mins, break_mins, scheduled_time, auto_start)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            bp["id"],
                            bp["name"],
                            bp["max_pomodoros"],
                            bp["work_mins"],
                            bp["break_mins"],
                            bp["scheduled_time"],
                            bp["auto_start"],
                        ),
                    )
        conn.commit()


def create_daily_task(
    name: str,
    pomos: int,
    work: int,
    break_m: int,
    scheduled_time: Optional[str] = None,
    auto_start: bool = False,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO daily_tasks (name, max_pomodoros, work_mins, break_mins, scheduled_time, auto_start)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (name, pomos, work, break_m, scheduled_time, auto_start),
        )
        conn.commit()
        return cast(int, cursor.lastrowid)


def create_repeating_task(
    name: str,
    pomos: int,
    work: int,
    break_m: int,
    repeat_days: str,
    scheduled_time: Optional[str] = None,
    auto_start: bool = False,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        blueprint_id = None
        if repeat_days:
            cursor.execute(
                """
                INSERT INTO task_blueprints (name, max_pomodoros, work_mins, break_mins, repeat_days, scheduled_time, auto_start)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (name, pomos, work, break_m, repeat_days, scheduled_time, auto_start),
            )
            blueprint_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO daily_tasks (blueprint_id, name, max_pomodoros, work_mins, break_mins, scheduled_time, auto_start)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (blueprint_id, name, pomos, work, break_m, scheduled_time, auto_start),
        )
        conn.commit()
        return cast(int, cursor.lastrowid)


def get_pending_tasks() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_tasks WHERE status != 'completed'")
        return [dict(row) for row in cursor.fetchall()]


def get_completed_tasks() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM daily_tasks WHERE status = 'completed' AND date_added = DATE('now', 'localtime')"
        )
        return [dict(row) for row in cursor.fetchall()]


def get_blueprints() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM task_blueprints")
        return [dict(row) for row in cursor.fetchall()]


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_task(task_id: int, delete_blueprint: bool = False):
    with get_connection() as conn:
        cursor = conn.cursor()
        if delete_blueprint:
            cursor.execute(
                "SELECT blueprint_id FROM daily_tasks WHERE id = ?", (task_id,)
            )
            row = cursor.fetchone()
            if row and row["blueprint_id"]:
                cursor.execute(
                    "DELETE FROM task_blueprints WHERE id = ?", (row["blueprint_id"],)
                )
        cursor.execute("DELETE FROM daily_tasks WHERE id = ?", (task_id,))
        conn.commit()


def update_daily_task(
    task_id: int,
    name: str,
    pomos: int,
    work: int,
    break_m: int,
    scheduled_time: Optional[str],
    auto_start: bool,
):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE daily_tasks
            SET name=?, max_pomodoros=?, work_mins=?, break_mins=?, scheduled_time=?, auto_start=?
            WHERE id=?
        """,
            (name, pomos, work, break_m, scheduled_time, auto_start, task_id),
        )
        conn.commit()


def update_blueprint(
    bp_id: int,
    name: str,
    pomos: int,
    work: int,
    break_m: int,
    repeat_days: str,
    scheduled_time: Optional[str],
    auto_start: bool,
):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE task_blueprints
            SET name=?, max_pomodoros=?, work_mins=?, break_mins=?, repeat_days=?, scheduled_time=?, auto_start=?
            WHERE id=?
        """,
            (
                name,
                pomos,
                work,
                break_m,
                repeat_days,
                scheduled_time,
                auto_start,
                bp_id,
            ),
        )
        conn.commit()

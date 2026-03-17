import sqlite3
from typing import List, Dict, Any, Optional, cast
from pomo.utils import get_db_path, ensure_dirs
import datetime


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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                daily_task_id INTEGER,
                blueprint_id INTEGER,
                start_time DATETIME,
                end_time DATETIME,
                work_mins INTEGER,
                FOREIGN KEY(daily_task_id) REFERENCES daily_tasks(id)
            )
        """)
        conn.commit()


def log_session(
    daily_task_id: int,
    blueprint_id: Optional[int],
    start_time: str,
    end_time: str,
    work_mins: int,
):
    """Ensure this function exists in your storage.py so the engine can call it!"""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pomodoro_sessions (daily_task_id, blueprint_id, start_time, end_time, work_mins)
            VALUES (?, ?, ?, ?, ?)
            """,
            (daily_task_id, blueprint_id, start_time, end_time, work_mins),
        )
        conn.commit()


def get_stats(task_name: Optional[str] = None, all_time: bool = False) -> dict:
    """Fetch advanced focus metrics, streaks, and heatmaps, filtering by task name."""
    with get_connection() as conn:
        cursor = conn.cursor()

        date_filter = (
            "1=1" if all_time else "DATE(ps.start_time) = DATE('now', 'localtime')"
        )

        # Filter by name string instead of task_id
        if task_name:
            task_filter = "dt.name = ?"
            params = (task_name,)
        else:
            task_filter = "1=1"
            params = ()

        where_clause = f"WHERE {date_filter} AND {task_filter}"
        where_clause_heatmap = f"WHERE {task_filter} AND DATE(ps.start_time) >= DATE('now', 'localtime', '-6 days')"

        stats = {
            "total_sessions": 0,
            "total_focus_minutes": 0,
            "best_hour": None,
            "heatmap": [],
            "streak": 0,
        }

        # 1. Total sessions and minutes
        cursor.execute(
            f"""
            SELECT COUNT(ps.id), SUM(ps.work_mins) 
            FROM pomodoro_sessions ps
            LEFT JOIN daily_tasks dt ON ps.daily_task_id = dt.id
            {where_clause}
        """,
            params,
        )
        row = cursor.fetchone()
        if row and row[0]:
            stats["total_sessions"] = row[0]
            stats["total_focus_minutes"] = row[1] or 0

        # 2. Most Productive Hour
        cursor.execute(
            f"""
            SELECT strftime('%H', ps.start_time) as hour, SUM(ps.work_mins) as mins
            FROM pomodoro_sessions ps
            LEFT JOIN daily_tasks dt ON ps.daily_task_id = dt.id
            {where_clause}
            GROUP BY hour
            ORDER BY mins DESC
            LIMIT 1
        """,
            params,
        )
        row = cursor.fetchone()
        if row:
            stats["best_hour"] = f"{row['hour']}:00"

        # 3. Last 7 Days Heatmap
        cursor.execute(
            f"""
            SELECT DATE(ps.start_time) as focus_date, SUM(ps.work_mins) as daily_mins
            FROM pomodoro_sessions ps
            LEFT JOIN daily_tasks dt ON ps.daily_task_id = dt.id
            {where_clause_heatmap}
            GROUP BY DATE(ps.start_time)
            ORDER BY focus_date ASC
        """,
            params,
        )
        stats["heatmap"] = [dict(r) for r in cursor.fetchall()]

        # 4. Calculate Current Streak
        cursor.execute(
            f"""
            SELECT DISTINCT DATE(ps.start_time) as focus_date
            FROM pomodoro_sessions ps
            LEFT JOIN daily_tasks dt ON ps.daily_task_id = dt.id
            WHERE {task_filter}
            ORDER BY focus_date DESC
        """,
            params,
        )
        dates = [r["focus_date"] for r in cursor.fetchall()]

        streak = 0
        today_date = datetime.datetime.now().date()
        current_check = today_date

        if str(today_date) in dates:
            streak += 1
            current_check -= datetime.timedelta(days=1)
        elif str(today_date - datetime.timedelta(days=1)) in dates:
            current_check -= datetime.timedelta(days=1)

        while str(current_check) in dates:
            streak += 1
            current_check -= datetime.timedelta(days=1)

        stats["streak"] = streak

        return stats


def spawn_daily_tasks():
    today_str = str(datetime.datetime.today().weekday())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM task_blueprints")
        blueprints = cursor.fetchall()

        for bp in blueprints:
            if bp["repeat_days"] and today_str in bp["repeat_days"].split(","):
                cursor.execute(
                    "SELECT id FROM daily_tasks WHERE blueprint_id = ? AND date_added = DATE('now', 'localtime')",
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

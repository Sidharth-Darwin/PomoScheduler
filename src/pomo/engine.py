import time
from typing import Optional, Dict, Any
from pomo.models import Phase, DaemonStatus, ActiveTaskState
from pomo.storage import get_connection, log_session


class PomoEngine:
    def __init__(self):
        self.is_running: bool = False
        self.current_phase: Phase = Phase.IDLE
        self.active_task: Optional[Dict[str, Any]] = None
        self.ends_at: float = 0.0

        self.paused_remaining: float = 0.0
        self.pre_pause_phase: Phase = Phase.IDLE

        self.last_checked_minute = ""
        self.triggered_schedules = set()

    def _log_current_phase(self):
        """Calculates exact elapsed time for both WORK and BREAK phases and logs it."""
        if not self.active_task:
            return

        is_work = self.current_phase == Phase.WORK
        was_work = (
            self.current_phase == Phase.PAUSED and self.pre_pause_phase == Phase.WORK
        )

        is_break = self.current_phase in (Phase.SHORT_BREAK, Phase.LONG_BREAK)
        was_break = self.current_phase == Phase.PAUSED and self.pre_pause_phase in (
            Phase.SHORT_BREAK,
            Phase.LONG_BREAK,
        )

        if not (is_work or was_work or is_break or was_break):
            return

        # Reference duration
        total_seconds = (
            self.active_task["work_mins"] * 60
            if (is_work or was_work)
            else self.active_task["break_mins"] * 60
        )

        if self.is_running:
            remaining = max(0.0, self.ends_at - time.time())
        else:
            remaining = self.paused_remaining

        elapsed_seconds = total_seconds - remaining
        elapsed_mins = int(round(elapsed_seconds / 60.0))

        if elapsed_mins > 0:
            end_time = time.time()
            start_time = end_time - elapsed_seconds
            str_start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
            str_end = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))

            session_type = "work" if (is_work or was_work) else "break"

            log_session(
                self.active_task["id"],
                self.active_task.get("blueprint_id"),
                str_start,
                str_end,
                elapsed_mins,
                session_type,
            )

    def get_status(self) -> dict:
        if self.current_phase == Phase.PAUSED:
            rem = int(self.paused_remaining)
        else:
            rem = int(self.ends_at - time.time()) if self.is_running else 0
        if rem < 0:
            rem = 0

        task_state = None
        if self.active_task:
            current_pomo = min(
                self.active_task.get("pomodoros_completed", 0) + 1,
                self.active_task["max_pomodoros"],
            )
            task_state = ActiveTaskState(
                task_id=self.active_task["id"],
                name=self.active_task["name"],
                pomodoro_current=current_pomo,
                pomodoro_total=self.active_task["max_pomodoros"],
            )

        return DaemonStatus(
            status="success",
            is_running=self.is_running,
            current_phase=self.current_phase,
            active_task=task_state,
            time_remaining_seconds=rem,
            ends_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.ends_at))
            if self.is_running
            else None,
        ).model_dump()

    def process_action(self, payload: dict) -> dict:
        action = payload.get("action")
        if action == "status":
            return self.get_status()
        elif action == "start":
            return self.start_task(payload.get("task_id"))
        elif action == "pause":
            return self.pause()
        elif action == "resume":
            return self.resume()
        elif action == "skip":
            return self.skip()
        elif action == "stop":
            return self.stop()
        return {"status": "error", "message": f"Unknown action: {action}"}

    def start_task(self, task_id: Optional[int]) -> dict:
        if not task_id:
            return {"status": "error", "message": "Task ID required."}
        if self.active_task and self.active_task["id"] != task_id:
            self.stop()

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM daily_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return {"status": "error", "message": f"Task {task_id} not found."}

            self.active_task = dict(row)
            if self.active_task.get("status") == "completed":
                self.active_task["pomodoros_completed"] = 0

            conn.execute(
                "UPDATE daily_tasks SET status = 'active', pomodoros_completed = ? WHERE id = ?",
                (self.active_task["pomodoros_completed"], task_id),
            )
            conn.commit()

        self.current_phase = Phase.WORK
        self.is_running = True
        self.ends_at = time.time() + (self.active_task["work_mins"] * 60)
        return {
            "status": "success",
            "message": f"Started task '{self.active_task['name']}'",
        }

    def pause(self) -> dict:
        if not self.is_running:
            return {"status": "error", "message": "Timer is not currently running."}
        self.is_running = False
        self.paused_remaining = self.ends_at - time.time()
        self.pre_pause_phase = self.current_phase
        self.current_phase = Phase.PAUSED
        return {"status": "success", "message": "Timer paused."}

    def resume(self) -> dict:
        if self.current_phase != Phase.PAUSED:
            return {"status": "error", "message": "Timer is not paused."}
        self.is_running = True
        self.current_phase = self.pre_pause_phase
        self.ends_at = time.time() + self.paused_remaining
        self.paused_remaining = 0.0
        return {"status": "success", "message": "Timer resumed."}

    def skip(self) -> dict:
        if not self.active_task:
            return {"status": "error", "message": "No active task to skip."}
        self.handle_transition()
        return {
            "status": "success",
            "message": f"Skipped to {self.current_phase.value}.",
        }

    def stop(self) -> dict:
        if not self.active_task:
            return {"status": "error", "message": "No active task to stop."}
        self._log_current_phase()
        with get_connection() as conn:
            conn.execute(
                "UPDATE daily_tasks SET status = 'pending' WHERE id = ?",
                (self.active_task["id"],),
            )
            conn.commit()
        self.is_running = False
        self.current_phase = Phase.IDLE
        self.active_task = None
        return {"status": "success", "message": "Task stopped and reset to pending."}

    def tick(self):
        current_minute = time.strftime("%H:%M")
        if current_minute != self.last_checked_minute:
            self.last_checked_minute = current_minute
            self.check_schedules(current_minute)

        if not self.is_running:
            return
        if time.time() >= self.ends_at:
            self.handle_transition()

    def check_schedules(self, current_minute: str):
        from pomo.storage import get_pending_tasks
        from pomo.notify import notify

        tasks = get_pending_tasks()
        try:
            now_h, now_m = map(int, current_minute.split(":"))
            now_total = now_h * 60 + now_m
        except ValueError:
            return

        for t in tasks:
            sched = t.get("scheduled_time")
            if not sched:
                continue
            try:
                sched_h, sched_m = map(int, sched.split(":"))
                sched_total = sched_h * 60 + sched_m
            except ValueError:
                continue

            diff = now_total - sched_total
            if 0 <= diff <= 10 and t["id"] not in self.triggered_schedules:
                self.triggered_schedules.add(t["id"])
                if t.get("auto_start"):
                    self.start_task(t["id"])
                    notify(
                        "Task Auto-Started!", f"Scheduled task has begun: {t['name']}"
                    )
                else:
                    notify("Scheduled Reminder", f"It's time to start: {t['name']}")

    def handle_transition(self):
        if not self.active_task:
            self.is_running = False
            return

        if self.current_phase == Phase.WORK:
            current_completed = self.active_task.get("pomodoros_completed", 0) + 1
            self.active_task["pomodoros_completed"] = current_completed

            self._log_current_phase()

            with get_connection() as conn:
                conn.execute(
                    "UPDATE daily_tasks SET pomodoros_completed = ? WHERE id = ?",
                    (current_completed, self.active_task["id"]),
                )
                conn.commit()

            if current_completed >= self.active_task["max_pomodoros"]:
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE daily_tasks SET status = 'completed' WHERE id = ?",
                        (self.active_task["id"],),
                    )
                    conn.commit()

                self.current_phase = Phase.IDLE
                self.is_running = False
                from pomo.notify import notify

                notify(
                    "Task Completed!",
                    f"You finished: {self.active_task['name']}",
                    fallback_sound="achievement.wav",
                )
                self.active_task = None
            else:
                self.current_phase = Phase.SHORT_BREAK
                self.ends_at = time.time() + (self.active_task["break_mins"] * 60)
                from pomo.notify import notify

                notify(
                    "Work Finished!",
                    f"Time for a break ({self.active_task['break_mins']}m)",
                )

        elif self.current_phase in (Phase.SHORT_BREAK, Phase.LONG_BREAK):
            self._log_current_phase()
            self.current_phase = Phase.WORK
            self.ends_at = time.time() + (self.active_task["work_mins"] * 60)
            from pomo.notify import notify

            notify("Break Over!", f"Back to work: {self.active_task['name']}")

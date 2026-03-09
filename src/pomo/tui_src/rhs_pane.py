from typing import cast, TYPE_CHECKING
from textual.app import ComposeResult
from textual.widgets import Static, Label, Button
from textual.containers import Vertical, Grid, Center

from pomo.tui_src.utils import async_send_to_daemon, render_clock

if TYPE_CHECKING:
    from pomo.tui_src.tui import PomoApp


class RHSWorkPane(Vertical):
    def compose(self) -> ComposeResult:
        with Vertical(id="engine_container"):
            yield Label("IDLE", id="phase", classes="engine_text")

            with Center():
                yield Static("", id="clock", classes="engine_text")

            yield Static(
                "Ready to start a task.", id="current_task", classes="engine_text"
            )
            yield Static("", id="pomo_count", classes="engine_text")

            with Grid(id="controls"):
                yield Button("Pause", id="btn_toggle_pause", variant="warning")
                yield Button("Skip", id="btn_skip", variant="primary")
                yield Button("Stop", id="btn_stop", variant="error")

    def update_display(self, response: dict) -> None:
        task_widget = self.query_one("#current_task", Static)
        pomo_widget = self.query_one("#pomo_count", Static)
        phase_widget = self.query_one("#phase", Label)
        time_widget = self.query_one("#clock", Static)
        btn_toggle = self.query_one("#btn_toggle_pause", Button)

        if response.get("status") == "error":
            task_widget.update("Daemon Auto-Starting...")
            return

        is_running = response.get("is_running")
        phase = response.get("current_phase", "idle").upper()
        task = response.get("active_task") or {}
        current_p = task.get("pomodoro_current", 0)

        if phase == "WORK":
            self.styles.background, phase_text = "#5c1b1b", "FOCUS"
        elif phase == "SHORT_BREAK":
            self.styles.background, phase_text = "#1b5c2a", "BREAK"
        elif phase == "PAUSED":
            self.styles.background, phase_text = "#6b5814", "PAUSED"
        else:
            self.styles.background, phase_text = "transparent", "IDLE"

        phase_widget.update(phase_text)

        if phase == "PAUSED":
            btn_toggle.label = "Resume"
            btn_toggle.variant = "success"
        else:
            btn_toggle.label = "Pause"
            btn_toggle.variant = "warning"

        if not is_running and phase != "PAUSED":
            task_widget.update("Ready to start a task.")
            pomo_widget.update("")
            time_widget.update(render_clock("00:00:00"))
            return

        rem = response.get("time_remaining_seconds", 0)
        hours, remainder = divmod(rem, 3600)
        mins, secs = divmod(remainder, 60)
        time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

        task_widget.update(f"{task.get('name', 'Unknown Task')}")
        pomo_widget.update(f"Block {current_p} of {task.get('pomodoro_total', 0)}")
        time_widget.update(render_clock(time_str))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn_toggle_pause":
            if event.button.label == "Resume":
                await async_send_to_daemon({"action": "resume"})
            else:
                await async_send_to_daemon({"action": "pause"})
        elif btn_id == "btn_skip":
            await async_send_to_daemon({"action": "skip"})
        elif btn_id == "btn_stop":
            await async_send_to_daemon({"action": "stop"})

        cast("PomoApp", self.app).action_refresh_table()

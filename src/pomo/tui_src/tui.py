from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, TabbedContent
from textual.containers import Horizontal

from .lhs_pane import LHSProjectPane
from .rhs_pane import RHSWorkPane

from pomo.tui_src.utils import format_days, async_send_to_daemon
from pomo.tui_src.edit_modal import EditTaskModal
from pomo.storage import (
    get_pending_tasks,
    get_task,
    get_completed_tasks,
    get_blueprints,
)


class PomoApp(App):
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("q", "quit", "Quit TUI"),
        ("r", "refresh_table", "Refresh Queue"),
    ]

    def __init__(self):
        super().__init__()
        self.last_phase = None
        self.last_pomo_count = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield LHSProjectPane(id="left_pane")
            yield RHSWorkPane(id="right_pane")
        yield Footer(compact=True)

    def on_mount(self) -> None:
        for t_id in ["table_today", "table_completed"]:
            self.query_one(f"#{t_id}", DataTable).add_columns(
                "ID", "Time", "Task", "Pomos"
            )
        self.query_one("#table_repeats", DataTable).add_columns(
            "ID", "Time", "Rule Name", "Days"
        )
        self.action_refresh_table()
        self.set_interval(1.0, self.update_status)

    def action_refresh_table(self) -> None:
        tbl_today = self.query_one("#table_today", DataTable)
        tbl_today.clear()
        for t in get_pending_tasks():
            name = f"∞ {t['name']}" if t.get("blueprint_id") else t["name"]
            auto = "⊛ " if t.get("auto_start") else ""
            time_str = (
                f"{auto}{t.get('scheduled_time')}" if t.get("scheduled_time") else "---"
            )
            tbl_today.add_row(
                str(t["id"]),
                time_str,
                name,
                f"{t.get('pomodoros_completed', 0)}/{t['max_pomodoros']}",
            )

        tbl_comp = self.query_one("#table_completed", DataTable)
        tbl_comp.clear()
        for t in get_completed_tasks():
            tbl_comp.add_row(
                str(t["id"]),
                t.get("scheduled_time") or "---",
                t["name"],
                f"{t['max_pomodoros']}/{t['max_pomodoros']}",
            )

        tbl_rep = self.query_one("#table_repeats", DataTable)
        tbl_rep.clear()
        for bp in get_blueprints():
            time_str = (
                f"{'⊛ ' if bp.get('auto_start') else ''}{bp.get('scheduled_time')}"
                if bp.get("scheduled_time")
                else "---"
            )
            tbl_rep.add_row(
                str(bp["id"]),
                time_str,
                bp["name"],
                format_days(bp.get("repeat_days") or ""),
            )

    async def update_status(self) -> None:
        response = await async_send_to_daemon({"action": "status"})

        right_pane = self.query_one("#right_pane", RHSWorkPane)
        right_pane.update_display(response)

        if response.get("status") != "error":
            phase = response.get("current_phase", "idle").upper()
            task = response.get("active_task") or {}
            current_p = task.get("pomodoro_current", 0)

            if (self.last_phase is not None and self.last_phase != phase) or (
                self.last_pomo_count is not None and self.last_pomo_count != current_p
            ):
                self.action_refresh_table()

            self.last_phase, self.last_pomo_count = phase, current_p

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        tabs = self.query_one("#tabs", TabbedContent)
        target_id = int(str(event.control.get_row(event.row_key)[0]))

        def handle_save(s):
            if s:
                self.action_refresh_table()

        if tabs.active == "tab_repeats":
            bp = next((bp for bp in get_blueprints() if bp["id"] == target_id), None)
            if bp:
                self.push_screen(
                    EditTaskModal(default_data=bp, mode="edit_bp"), handle_save
                )
        else:
            data = get_task(target_id)
            if data:
                self.push_screen(
                    EditTaskModal(default_data=data, mode="edit_task"), handle_save
                )

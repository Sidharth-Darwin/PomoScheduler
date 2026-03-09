from typing import Optional, cast, TYPE_CHECKING
from textual.app import ComposeResult
from textual.widgets import DataTable, TabbedContent, TabPane, Button
from textual.containers import Vertical, Horizontal

from pomo.storage import get_task, get_blueprints, delete_task, get_connection
from pomo.tui_src.edit_modal import EditTaskModal
from pomo.tui_src.delete_modal import DeleteTaskModal
from pomo.tui_src.settings_modal import SettingsModal
from pomo.tui_src.utils import async_send_to_daemon

if TYPE_CHECKING:
    from pomo.tui_src.tui import PomoApp


class LHSProjectPane(Vertical):
    def compose(self) -> ComposeResult:
        with TabbedContent(id="tabs"):
            with TabPane("Today", id="tab_today"):
                yield DataTable(id="table_today", cursor_type="row")
            with TabPane("Completed", id="tab_completed"):
                yield DataTable(id="table_completed", cursor_type="row")
            with TabPane("Repeating", id="tab_repeats"):
                yield DataTable(id="table_repeats", cursor_type="row")

        with Vertical(id="left_btn_area", classes="left_controls_container"):
            with Horizontal():
                yield Button("New Task", id="btn_new", variant="primary")
                yield Button("Start", id="btn_start", variant="success")
                yield Button("Copy", id="btn_copy", variant="warning")
            with Horizontal():
                yield Button("Settings", id="btn_settings", variant="default")
                yield Button("Delete", id="btn_del", variant="error")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        def trigger_refresh(saved: bool | None) -> None:
            if saved:
                cast("PomoApp", self.app).action_refresh_table()

        if btn_id == "btn_new":
            self.app.push_screen(EditTaskModal(mode="create"), trigger_refresh)

        elif btn_id == "btn_start":
            table = self.query_one("#table_today", DataTable)
            try:
                coord = table.coordinate_to_cell_key(table.cursor_coordinate)
                target_id = int(str(table.get_row(coord.row_key)[0]))
                await async_send_to_daemon({"action": "start", "task_id": target_id})
                cast("PomoApp", self.app).action_refresh_table()
            except Exception:
                pass

        elif btn_id == "btn_settings":
            self.app.push_screen(SettingsModal())

        elif btn_id == "btn_copy":
            tabs = self.query_one("#tabs", TabbedContent)
            suffix = tabs.active.split("_")[1]
            table = self.query_one(f"#table_{suffix}", DataTable)
            try:
                coord = table.coordinate_to_cell_key(table.cursor_coordinate)
                target_id = int(str(table.get_row(coord.row_key)[0]))
                data = (
                    next((bp for bp in get_blueprints() if bp["id"] == target_id), None)
                    if tabs.active == "tab_repeats"
                    else get_task(target_id)
                )
                if data:
                    self.app.push_screen(
                        EditTaskModal(default_data=data, mode="copy"), trigger_refresh
                    )
            except Exception:
                pass

        elif btn_id == "btn_del":
            tabs = self.query_one("#tabs", TabbedContent)
            suffix = tabs.active.split("_")[1]
            table = self.query_one(f"#table_{suffix}", DataTable)
            try:
                coord = table.coordinate_to_cell_key(table.cursor_coordinate)
                target_id = int(str(table.get_row(coord.row_key)[0]))
                if tabs.active == "tab_repeats":
                    with get_connection() as conn:
                        conn.execute(
                            "DELETE FROM task_blueprints WHERE id = ?", (target_id,)
                        )
                        conn.commit()
                    cast("PomoApp", self.app).action_refresh_table()
                else:
                    task_data = get_task(target_id)
                    if task_data:

                        def handle_del(res: Optional[tuple[bool, bool]]) -> None:
                            if res and res[0]:
                                delete_task(target_id, res[1])
                                cast("PomoApp", self.app).action_refresh_table()

                        self.app.push_screen(
                            DeleteTaskModal(
                                task_data["name"], bool(task_data.get("blueprint_id"))
                            ),
                            handle_del,
                        )
            except Exception:
                pass

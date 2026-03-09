import time
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import (
    Button,
    Input,
    Label,
    Checkbox,
)
from textual.screen import ModalScreen
from pomo.storage import (
    create_repeating_task,
    create_daily_task,
    update_daily_task,
    update_blueprint,
)


class EditTaskModal(ModalScreen[bool]):
    CSS = """
    EditTaskModal { align: center middle; }
    #dialog { padding: 1 2; width: 65; height: auto; border: thick $accent; background: $surface; }
    .input_grid { layout: grid; grid-size: 3; grid-gutter: 1; height: auto; margin-bottom: 1; }
    .row { layout: grid; grid-size: 2; grid-gutter: 1; height: auto; margin-bottom: 1; }
    .btn_row { layout: horizontal; align: right middle; height: auto; margin-top: 1; }
    .day_grid { layout: grid; grid-size: 4; grid-gutter: 1; height: auto; margin-bottom: 1; border: solid $primary; padding: 1; }
    Button { margin-left: 1; }
    """

    def __init__(self, default_data: dict | None = None, mode: str = "create"):
        super().__init__()
        self.default_data = default_data or {}
        self.mode = mode

    def compose(self) -> ComposeResult:
        from pomo.settings import get_config

        config = get_config().get(
            "defaults", {"pomos": 4, "work_mins": 25, "break_mins": 5}
        )

        if self.mode.startswith("edit"):
            title = "Edit Task"
        elif self.mode == "copy":
            title = "Copy Task"
        else:
            title = "Create Task"

        default_time = self.default_data.get("scheduled_time")
        if not default_time and self.mode == "create":
            default_time = time.strftime("%H:%M")

        with Vertical(id="dialog"):
            yield Label(title, id="modal_title")
            yield Input(
                self.default_data.get("name", ""),
                placeholder="Task Name",
                id="inp_name",
            )
            with Grid(classes="row"):
                yield Input(default_time, placeholder="Time (HH:MM)", id="inp_time")
                yield Checkbox(
                    "Auto-Start at Time",
                    value=bool(self.default_data.get("auto_start")),
                    id="chk_auto",
                )
            with Grid(classes="input_grid"):
                yield Input(
                    str(self.default_data.get("max_pomodoros", config["pomos"])),
                    placeholder="Pomos",
                    id="inp_pomos",
                    type="integer",
                )
                yield Input(
                    str(self.default_data.get("work_mins", config["work_mins"])),
                    placeholder="Work Mins",
                    id="inp_work",
                    type="integer",
                )
                yield Input(
                    str(self.default_data.get("break_mins", config["break_mins"])),
                    placeholder="Break Mins",
                    id="inp_break",
                    type="integer",
                )
            yield Label("Repeat Days (Leave empty for One-Time Task):")
            with Grid(classes="day_grid"):
                for i, day in enumerate(
                    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                ):
                    yield Checkbox(day, id=f"chk_day_{i}")
            with Horizontal(classes="btn_row"):
                yield Button("Save", variant="success", id="btn_save")
                yield Button("Cancel", variant="error", id="btn_cancel")

    def on_mount(self) -> None:
        repeat_days = self.default_data.get("repeat_days")
        if repeat_days:
            for day_idx in repeat_days.split(","):
                try:
                    self.query_one(f"#chk_day_{day_idx}", Checkbox).value = True
                except Exception:
                    pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss(False)
        elif event.button.id == "btn_save":
            name = self.query_one("#inp_name", Input).value
            pomos = max(1, min(int(self.query_one("#inp_pomos", Input).value or 2), 20))
            work = max(
                1, min(int(self.query_one("#inp_work", Input).value or 25), 1000)
            )
            break_m = max(
                1, min(int(self.query_one("#inp_break", Input).value or 5), 1000)
            )
            time_val = self.query_one("#inp_time", Input).value.strip() or None
            auto = self.query_one("#chk_auto", Checkbox).value
            days = [
                str(i)
                for i in range(7)
                if self.query_one(f"#chk_day_{i}", Checkbox).value
            ]
            repeat_days = ",".join(days) if days else None

            if not name.strip():
                return

            if self.mode == "edit_task":
                update_daily_task(
                    self.default_data["id"], name, pomos, work, break_m, time_val, auto
                )
            elif self.mode == "edit_bp":
                update_blueprint(
                    self.default_data["id"],
                    name,
                    pomos,
                    work,
                    break_m,
                    repeat_days or "",
                    time_val,
                    auto,
                )
            else:
                if repeat_days:
                    create_repeating_task(
                        name, pomos, work, break_m, repeat_days, time_val, auto
                    )
                else:
                    create_daily_task(name, pomos, work, break_m, time_val, auto)
            self.dismiss(True)

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import (
    Button,
    Input,
    Label,
)
from textual.screen import ModalScreen


class SettingsModal(ModalScreen[bool]):
    CSS = """
    SettingsModal { align: center middle; }
    #set_dialog { padding: 1 2; width: 70; height: auto; border: thick $primary; background: $surface; }
    .set_grid { layout: grid; grid-size: 3; grid-gutter: 1; height: auto; margin-bottom: 1; }
    .audio_grid { layout: grid; grid-size: 2; grid-gutter: 1; height: auto; margin-bottom: 1; }
    .btn_row { layout: horizontal; align: right middle; height: auto; margin-top: 1; }
    Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        from pomo.settings import get_config

        config = get_config()
        defaults = config.get("defaults", {})
        sounds = config.get("sounds", {})

        with Vertical(id="set_dialog"):
            label = Label("App Settings", id="modal_title")
            label.styles.text_style = "bold"
            label.styles.margin = (0, 0, 1, 0)
            yield label

            yield Label("Default Task Values:")
            with Grid(classes="set_grid"):
                yield Input(
                    str(defaults.get("pomos", 4)),
                    placeholder="Pomos",
                    id="set_pomos",
                    type="integer",
                )
                yield Input(
                    str(defaults.get("work_mins", 25)),
                    placeholder="Work Mins",
                    id="set_work",
                    type="integer",
                )
                yield Input(
                    str(defaults.get("break_mins", 5)),
                    placeholder="Break Mins",
                    id="set_break",
                    type="integer",
                )

            yield Label("Custom Audio Paths (Leave blank for defaults):")
            with Grid(classes="audio_grid"):
                yield Input(
                    sounds.get("work_done", ""),
                    placeholder="Path: Work Done (.wav)",
                    id="set_aud_work",
                )
                yield Input(
                    sounds.get("break_done", ""),
                    placeholder="Path: Break Done (.wav)",
                    id="set_aud_break",
                )
                yield Input(
                    sounds.get("task_done", ""),
                    placeholder="Path: Task Done (.wav)",
                    id="set_aud_task",
                )
                yield Input(
                    sounds.get("reminder", ""),
                    placeholder="Path: Reminder (.wav)",
                    id="set_aud_remind",
                )

            with Horizontal(classes="btn_row"):
                yield Button("Save Settings", variant="success", id="btn_save_settings")
                yield Button("Cancel", variant="error", id="btn_cancel_settings")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel_settings":
            self.dismiss(False)
        elif event.button.id == "btn_save_settings":
            from pomo.settings import get_config, save_config

            config = get_config()
            config["defaults"]["pomos"] = int(
                self.query_one("#set_pomos", Input).value or 4
            )
            config["defaults"]["work_mins"] = int(
                self.query_one("#set_work", Input).value or 25
            )
            config["defaults"]["break_mins"] = int(
                self.query_one("#set_break", Input).value or 5
            )
            config["sounds"]["work_done"] = self.query_one(
                "#set_aud_work", Input
            ).value.strip()
            config["sounds"]["break_done"] = self.query_one(
                "#set_aud_break", Input
            ).value.strip()
            config["sounds"]["task_done"] = self.query_one(
                "#set_aud_task", Input
            ).value.strip()
            config["sounds"]["reminder"] = self.query_one(
                "#set_aud_remind", Input
            ).value.strip()
            save_config(config)
            self.dismiss(True)

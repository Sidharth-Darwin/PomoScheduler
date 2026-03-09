from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Label,
    Checkbox,
)
from textual.screen import ModalScreen


class DeleteTaskModal(ModalScreen[tuple[bool, bool]]):
    CSS = """
    DeleteTaskModal { align: center middle; }
    #del_dialog { padding: 1 2; width: 50; height: auto; border: thick $error; background: $surface; }
    .btn_row { layout: horizontal; align: center middle; margin-top: 1; height: auto; }
    Button { margin: 1; }
    """

    def __init__(self, task_name: str, has_blueprint: bool):
        super().__init__()
        self.task_name = task_name
        self.has_blueprint = has_blueprint

    def compose(self) -> ComposeResult:
        with Vertical(id="del_dialog"):
            yield Label(f"Delete '{self.task_name}'?", id="modal_title")
            if self.has_blueprint:
                yield Checkbox("Delete the repeating rule too", id="chk_blueprint")
            with Horizontal(classes="btn_row"):
                yield Button("Cancel", variant="primary", id="btn_cancel")
                yield Button("Delete", variant="error", id="btn_delete_confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss((False, False))
        elif event.button.id == "btn_delete_confirm":
            del_bp = (
                self.query_one("#chk_blueprint", Checkbox).value
                if self.has_blueprint
                else False
            )
            self.dismiss((True, del_bp))

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import Button, Label, DataTable, TabbedContent, TabPane
from textual.screen import ModalScreen
from pomo.storage import get_stats


class StatsModal(ModalScreen[None]):
    CSS = """
    StatsModal { align: center middle; }
    #stats_dialog { padding: 1 2; width: 85; height: 90%; border: thick $accent; background: $surface; }
    .modal_title { text-style: bold; margin-bottom: 1; }
    
    TabbedContent { height: 1fr; margin-bottom: 1; }
    
    .stats_header { layout: grid; grid-size: 2; grid-gutter: 1; height: 6; margin-bottom: 1; }
    .stats_box { padding: 1; border: solid $primary; height: 100%; }
    .section_title { text-style: bold; color: $accent; margin-top: 1; margin-bottom: 1; }
    
    #dt_breakdown { height: 1fr; }
    #dt_heatmap { height: 1fr; }
    
    .close_row { layout: horizontal; align: right middle; height: auto; margin-top: 1; }
    .close_row Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="stats_dialog"):
            yield Label("", id="lbl_title", classes="modal_title")

            with TabbedContent():
                with TabPane("Overview", id="tab_overview"):
                    with Grid(classes="stats_header"):
                        with Vertical(classes="stats_box"):
                            yield Label("", id="lbl_streak")
                            yield Label("", id="lbl_sessions")
                            yield Label("", id="lbl_best")
                        with Vertical(classes="stats_box"):
                            yield Label("", id="lbl_focus")
                            yield Label("", id="lbl_break")

                    yield Label("Task Breakdown (Focus):", classes="section_title")
                    yield DataTable(id="dt_breakdown", cursor_type="none")

                with TabPane("Heatmap", id="tab_heatmap"):
                    yield DataTable(
                        id="dt_heatmap", cursor_type="none", show_header=False
                    )

            with Horizontal(classes="close_row"):
                yield Button("7 Days", id="btn_7", variant="primary")
                yield Button("30 Days", id="btn_30", variant="default")
                yield Button("All Time", id="btn_0", variant="default")
                yield Button("Close", variant="error", id="btn_close")

    def on_mount(self) -> None:
        self.query_one("#dt_breakdown", DataTable).add_columns(
            "Task", "Sessions", "Time"
        )
        self.query_one("#dt_heatmap", DataTable).add_columns("Date", "Bar", "Time")
        self.load_data(7)

    def load_data(self, days: int) -> None:
        data = get_stats(days=days)
        time_scope = "ALL TIME" if days <= 0 else f"LAST {days} DAYS"

        total_h, total_m = divmod(data["total_focus_minutes"], 60)
        break_h, break_m = divmod(data["total_break_minutes"], 60)

        self.query_one("#lbl_title", Label).update(f"Pomo Planner Stats [{time_scope}]")
        self.query_one("#lbl_streak", Label).update(
            f"Current Streak: {data['streak']} days"
        )
        self.query_one("#lbl_sessions", Label).update(
            f"Total Sessions: {data['total_sessions']}"
        )
        self.query_one("#lbl_best", Label).update(
            f"Most Productive: {data['best_hour'] or '--:--'}"
        )
        self.query_one("#lbl_focus", Label).update(
            f"Total Focus Time: {total_h}h {total_m}m"
        )
        self.query_one("#lbl_break", Label).update(
            f"Total Break Time: {break_h}h {break_m}m"
        )

        dt = self.query_one("#dt_breakdown", DataTable)
        dt.clear()
        for task in data["task_breakdown"]:
            th, tm = divmod(task["mins"], 60)
            t_name = task["name"] or "Unknown Task"
            dt.add_row(t_name, str(task["sessions"]), f"{th}h {tm}m")

        dt_heat = self.query_one("#dt_heatmap", DataTable)
        dt_heat.clear()

        if data["heatmap"]:
            max_mins = max([day["daily_mins"] for day in data["heatmap"]])
            scale_max = max(60, max_mins)

            for day in data["heatmap"]:
                dh, dm = divmod(day["daily_mins"], 60)
                blocks = min(20, max(1, int((day["daily_mins"] / scale_max) * 20)))
                bar = "█" * blocks
                dt_heat.add_row(f" {day['focus_date']}", bar, f"{dh}h {dm}m")
        else:
            dt_heat.add_row(" No session data found.", "", "")

        self.query_one("#btn_7", Button).variant = "primary" if days == 7 else "default"
        self.query_one("#btn_30", Button).variant = (
            "primary" if days == 30 else "default"
        )
        self.query_one("#btn_0", Button).variant = "primary" if days == 0 else "default"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_close":
            self.dismiss()
        elif event.button.id == "btn_7":
            self.load_data(7)
        elif event.button.id == "btn_30":
            self.load_data(30)
        elif event.button.id == "btn_0":
            self.load_data(0)

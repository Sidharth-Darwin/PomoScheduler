import typer
import json
import socket
from typing import Optional
from pomo.utils import get_socket_path, spawn_daemon_in_background
from pomo.storage import (
    init_db,
    create_daily_task,
    get_pending_tasks,
    get_completed_tasks,
    delete_task,
    get_stats,
)
from rich import print

app = typer.Typer(help="Pomo Planner - FOSS CLI/TUI Pomodoro Tracker")


def send_to_daemon(payload: dict, retries: int = 1) -> dict:
    sock_path = get_socket_path()
    try:
        if not sock_path.exists():
            raise FileNotFoundError("Socket missing")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(sock_path))
            client.sendall(json.dumps(payload).encode("utf-8"))
            response_data = client.recv(4096)
            return json.loads(response_data.decode("utf-8"))
    except (FileNotFoundError, ConnectionRefusedError):
        if retries > 0:
            spawn_daemon_in_background()
            import time

            time.sleep(0.5)
            return send_to_daemon(payload, retries=0)
        else:
            return {"status": "error", "message": "Daemon failed to start."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.command()
def status(
    as_json: bool = typer.Option(False, "--json"),
    short: bool = typer.Option(False, "--short"),
):
    response = send_to_daemon({"action": "status"})
    if as_json:
        typer.echo(json.dumps(response, indent=2))
        return

    if short:
        if response.get("status") == "error":
            typer.echo("OFFLINE")
            return
        phase = response.get("current_phase", "idle").upper()
        rem = response.get("time_remaining_seconds", 0)
        task = response.get("active_task", {})
        mins, secs = divmod(rem, 60)

        if phase == "WORK":
            print(
                f"FOCUS {mins:02d}:{secs:02d} ({task.get('pomodoro_current', 0)}/{task.get('pomodoro_total', 0)})"
            )
        elif phase == "SHORT_BREAK":
            print(f"BREAK {mins:02d}:{secs:02d}")
        elif phase == "PAUSED":
            print(f"PAUSED {mins:02d}:{secs:02d}")
        else:
            print("IDLE")
        return

    if response.get("status") == "error":
        typer.secho(f"Error: {response.get('message')}", fg=typer.colors.RED)
        return

    if not response.get("is_running") and response.get("current_phase") != "paused":
        typer.secho("No active timer running.", fg=typer.colors.YELLOW)
        return

    task = response.get("active_task", {})
    typer.secho(f"Active Task: {task.get('name')}", fg=typer.colors.CYAN, bold=True)
    phase = response.get("current_phase", "unknown").upper()

    if phase == "PAUSED":
        typer.secho(f"Phase: {phase}", fg=typer.colors.YELLOW, bold=True)
    else:
        typer.echo(f"Phase: {phase}")

    typer.echo(f"Pomodoro: {task.get('pomodoro_current')}/{task.get('pomodoro_total')}")
    rem = response.get("time_remaining_seconds", 0)
    mins, secs = divmod(rem, 60)
    typer.secho(f"Time Left: {mins:02d}:{secs:02d}", fg=typer.colors.GREEN, bold=True)


@app.command()
def list(as_json: bool = typer.Option(False, "--json")):
    init_db()
    tasks = get_pending_tasks()
    if as_json:
        typer.echo(json.dumps({"status": "success", "tasks": tasks}, indent=2))
        return
    if not tasks:
        typer.echo("No pending tasks for today.")
        return
    for t in tasks:
        typer.echo(
            f"[{t['id']}] {t['name']} ({t['pomodoros_completed']}/{t['max_pomodoros']} pomos)"
        )


@app.command()
def stats(
    name: Optional[str] = typer.Option(
        None, "-n", "--name", help="Filter by a specific task name"
    ),
    all_time: bool = typer.Option(
        False, "--all", help="Show all-time statistics instead of just today"
    ),
    as_json: bool = typer.Option(False, "--json"),
):
    """View advanced focus statistics, streaks, and a 7-day heatmap."""

    init_db()
    data = get_stats(name, all_time)

    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return

    time_scope = "ALL TIME" if all_time else "TODAY"
    task_scope = f"Task: {name}" if name else "All Tasks"

    typer.secho(
        f"\nPomo Planner Stats [{time_scope} | {task_scope}]",
        fg=typer.colors.MAGENTA,
        bold=True,
    )

    total_h, total_m = divmod(data["total_focus_minutes"], 60)

    typer.echo(f"Current Streak:      {data['streak']} days")
    typer.echo(f"Total Focus Time:    {total_h}h {total_m}m")
    typer.echo(f"Total Sessions:      {data['total_sessions']}")

    if data["best_hour"]:
        typer.echo(f"Most Productive:     {data['best_hour']}")

    if data["heatmap"]:
        typer.secho("\nLast 7 Days Heatmap:", fg=typer.colors.CYAN, bold=True)
        max_mins = max([day["daily_mins"] for day in data["heatmap"]])

        for day in data["heatmap"]:
            dh, dm = divmod(day["daily_mins"], 60)
            blocks = int((day["daily_mins"] / max_mins) * 20) if max_mins > 0 else 0
            bar = "█" * blocks

            typer.echo(f"  {day['focus_date']} │ {bar:<20} {dh}h {dm}m")
    else:
        typer.secho(
            "\nNo session data in the last 7 days to build a heatmap.",
            fg=typer.colors.BRIGHT_BLACK,
        )
    print("\n")


@app.command()
def create(
    name: Optional[str] = typer.Option(None, "-n", "--name", help="Name of the task"),
    pomos: int = typer.Option(5, "-p", "--pomos", help="Max pomodoros"),
    work: int = typer.Option(25, "-w", "--work", help="Work minutes"),
    break_m: int = typer.Option(5, "-b", "--break", help="Break minutes"),
    as_json: bool = typer.Option(False, "--json"),
):
    """Create a new daily task. Leave arguments empty for an interactive prompt."""
    init_db()

    # Interactive mode if name is omitted
    if name is None:
        typer.secho("Create a New Task", fg=typer.colors.CYAN, bold=True)
        name = typer.prompt("Task name", type=str)
        pomos = int(typer.prompt("Number of pomodoros", default=5))
        work = int(typer.prompt("Work duration (mins)", default=25))
        break_m = int(typer.prompt("Break duration (mins)", default=5))

    # Type assertion to satisfy the linter
    assert name is not None

    pomos = max(1, min(pomos, 20))
    work = max(1, min(work, 1000))
    break_m = max(1, min(break_m, 1000))

    task_id = create_daily_task(name, pomos, work, break_m)

    if as_json:
        typer.echo(json.dumps({"status": "success", "task_id": task_id}))
    else:
        typer.secho(f"Created task '{name}' (ID: {task_id})", fg=typer.colors.GREEN)


@app.command()
def delete(
    task_id: Optional[int] = typer.Argument(None, help="The ID of the task to delete"),
    blueprint: bool = typer.Option(False, "--all"),
):
    """Delete a task. Leave the ID empty to pick from a list."""
    init_db()

    if task_id is None:
        tasks = get_pending_tasks() + get_completed_tasks()

        if not tasks:
            typer.secho("No tasks available to delete.", fg=typer.colors.YELLOW)
            raise typer.Exit()

        typer.secho("Select a Task to Delete:", fg=typer.colors.CYAN, bold=True)
        for t in tasks:
            status_icon = "[DONE]" if t["status"] == "completed" else "[PENDING]"
            typer.echo(
                f"[{t['id']}] {status_icon} {t['name']} ({t['pomodoros_completed']}/{t['max_pomodoros']} pomos)"
            )

        task_id = int(typer.prompt("Enter the ID of the task to delete"))

    # Type assertion to satisfy the linter
    assert task_id is not None

    delete_task(task_id, delete_blueprint=blueprint)
    typer.secho(f"Task {task_id} deleted.", fg=typer.colors.YELLOW)


@app.command()
def daemon():
    init_db()
    typer.secho("Checking background daemon...", fg=typer.colors.MAGENTA)
    from pomo.daemon import run_server

    run_server()


@app.command()
def start(task_id: Optional[int] = typer.Argument(default=None)):
    if task_id is None:
        init_db()
        tasks = get_pending_tasks()
        if not tasks:
            typer.secho("No pending tasks available to start.", fg=typer.colors.YELLOW)
            raise typer.Exit()

        typer.secho("Pending Tasks:", fg=typer.colors.CYAN, bold=True)
        for t in tasks:
            typer.echo(
                f"[{t['id']}] {t['name']} ({t['pomodoros_completed']}/{t['max_pomodoros']} pomos)"
            )

        task_id = int(typer.prompt("Enter the ID of the task to start"))

    # Type assertion to satisfy the linter
    assert task_id is not None

    response = send_to_daemon({"action": "start", "task_id": task_id})
    color = (
        typer.colors.GREEN if response.get("status") == "success" else typer.colors.RED
    )
    typer.secho(response.get("message"), fg=color)


@app.command()
def pause():
    response = send_to_daemon({"action": "pause"})
    color = (
        typer.colors.GREEN if response.get("status") == "success" else typer.colors.RED
    )
    typer.secho(response.get("message"), fg=color)


@app.command()
def resume():
    response = send_to_daemon({"action": "resume"})
    color = (
        typer.colors.GREEN if response.get("status") == "success" else typer.colors.RED
    )
    typer.secho(response.get("message"), fg=color)


@app.command()
def skip():
    response = send_to_daemon({"action": "skip"})
    color = (
        typer.colors.GREEN if response.get("status") == "success" else typer.colors.RED
    )
    typer.secho(response.get("message"), fg=color)


@app.command()
def stop():
    response = send_to_daemon({"action": "stop"})
    color = (
        typer.colors.GREEN if response.get("status") == "success" else typer.colors.RED
    )
    typer.secho(response.get("message"), fg=color)


@app.command()
def tui():
    init_db()
    from pomo.tui_src.tui import PomoApp

    app = PomoApp()
    app.run()

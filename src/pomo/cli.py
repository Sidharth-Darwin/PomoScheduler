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
    days: int = typer.Option(
        7, "-d", "--days", help="Number of days to analyze (use 0 for all-time)"
    ),
    as_json: bool = typer.Option(False, "--json"),
):
    """View advanced focus statistics, streaks, and a dynamic heatmap."""
    from pomo.storage import get_stats

    init_db()
    data = get_stats(name, days)

    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return

    time_scope = "ALL TIME" if days <= 0 else f"LAST {days} DAYS"
    task_scope = f"Task: {name}" if name else "All Tasks"

    typer.secho(
        f"\nPomo Planner Stats [{time_scope} | {task_scope}]",
        fg=typer.colors.MAGENTA,
        bold=True,
    )

    total_h, total_m = divmod(data["total_focus_minutes"], 60)
    break_h, break_m = divmod(data["total_break_minutes"], 60)

    typer.echo(f"Current Streak:      {data['streak']} days")
    typer.echo(f"Total Focus Time:    {total_h}h {total_m}m")
    typer.echo(f"Total Break Time:    {break_h}h {break_m}m")
    typer.echo(f"Total Sessions:      {data['total_sessions']}")

    if data["best_hour"]:
        typer.echo(f"Most Productive:     {data['best_hour']}")

    if data["task_breakdown"]:
        typer.secho("\nTask Breakdown (Focus):", fg=typer.colors.CYAN, bold=True)
        for task in data["task_breakdown"]:
            th, tm = divmod(task["mins"], 60)
            t_name = task["name"] or "Unknown Task"
            typer.echo(f"  {t_name:<20} {th}h {tm}m ({task['sessions']} sessions)")

    if data["heatmap"]:
        max_mins = max([day["daily_mins"] for day in data["heatmap"]])
        scale_max = max(60, max_mins)
        block_value = scale_max / 20.0

        typer.secho(
            f"\nHeatmap ({time_scope}) | Scale: █ = ~{block_value:.1f} mins:",
            fg=typer.colors.CYAN,
            bold=True,
        )

        for day in data["heatmap"]:
            dh, dm = divmod(day["daily_mins"], 60)
            # Ensure at least 1 block if they did anything, capped at 20 blocks
            blocks = min(20, max(1, int((day["daily_mins"] / scale_max) * 20)))
            bar = "█" * blocks

            typer.echo(f"  {day['focus_date']} │ {bar:<20} {dh}h {dm}m")
    else:
        typer.secho(
            "\nNo session data found to build a heatmap for this timeframe.",
            fg=typer.colors.BRIGHT_BLACK,
        )
    print("\n")


@app.command()
def create(
    name: Optional[str] = typer.Option(None, "-n", "--name", help="Name of the task"),
    pomos: int = typer.Option(5, "-p", "--pomos", help="Max pomodoros"),
    work: int = typer.Option(25, "-w", "--work", help="Work minutes"),
    break_m: int = typer.Option(5, "-b", "--break", help="Break minutes"),
    time_val: Optional[str] = typer.Option(
        None, "-t", "--time", help="Scheduled time (HH:MM)"
    ),
    auto: bool = typer.Option(False, "--auto", help="Auto start at scheduled time"),
    repeat: Optional[str] = typer.Option(
        None, "-r", "--repeat", help="Repeat days (0=Mon, 6=Sun) e.g., '0,1,2'"
    ),
    as_json: bool = typer.Option(False, "--json"),
):
    """Create a new daily task. Leave arguments empty for an interactive prompt."""
    from pomo.storage import create_repeating_task

    init_db()

    if name is None:
        typer.secho("Create a New Task", fg=typer.colors.CYAN, bold=True)
        name = typer.prompt("Task name", type=str)
        pomos = int(typer.prompt("Number of pomodoros", default=5))
        work = int(typer.prompt("Work duration (mins)", default=25))
        break_m = int(typer.prompt("Break duration (mins)", default=5))

        time_prompt = typer.prompt(
            "Scheduled Time (HH:MM) [Leave empty to skip]", default=""
        )
        time_val = time_prompt.strip() or None

        if time_val:
            auto = typer.confirm("Auto-start task at this time?")

        is_repeat = typer.confirm("Does this task repeat on specific days?")
        if is_repeat:
            typer.echo("0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun")
            repeat = typer.prompt(
                "Enter days separated by comma (e.g. 0,1,2,3,4)", default="0,1,2,3,4"
            )

    assert name is not None

    pomos = max(1, min(pomos, 20))
    work = max(1, min(work, 1000))
    break_m = max(1, min(break_m, 1000))

    if repeat:
        task_id = create_repeating_task(
            name, pomos, work, break_m, repeat, time_val, auto
        )
    else:
        task_id = create_daily_task(name, pomos, work, break_m, time_val, auto)

    if as_json:
        typer.echo(json.dumps({"status": "success", "task_id": task_id}))
    else:
        typer.secho(f"Created task '{name}' (ID: {task_id})", fg=typer.colors.GREEN)


@app.command()
def clear():
    """Wipe ALL tasks, blueprints, and focus history permanently."""
    typer.secho(
        "WARNING: You are about to delete ALL your Pomodoro data.",
        fg=typer.colors.RED,
        bold=True,
    )

    confirm1 = typer.confirm("Are you absolutely sure you want to do this?")
    if not confirm1:
        raise typer.Exit()

    typer.secho(
        "This will wipe all your stats, streaks, tasks, and history.",
        fg=typer.colors.YELLOW,
    )
    confirm2 = typer.confirm(
        "This action CANNOT be undone. Final confirmation to proceed?"
    )

    if not confirm2:
        raise typer.Exit()

    init_db()
    from pomo.storage import clear_all_data

    clear_all_data()
    typer.secho("All data has been wiped clean.", fg=typer.colors.GREEN)


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

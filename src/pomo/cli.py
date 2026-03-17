import typer
import json
import socket
from typing import Optional
from pomo.utils import get_socket_path, spawn_daemon_in_background
from pomo.storage import (
    init_db,
    create_daily_task,
    get_pending_tasks,
    delete_task,
    get_gamification_stats,
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
def stats(as_json: bool = typer.Option(False, "--json")):
    """View your focus statistics and heatmap."""
    init_db()
    data = get_gamification_stats()

    if as_json:
        typer.echo(json.dumps(data, indent=2))
        return

    typer.secho("Pomo Planner Stats", fg=typer.colors.MAGENTA, bold=True)
    typer.echo(f"Total Focus Sessions: {data['total_sessions']}")

    total_h, total_m = divmod(data["total_focus_minutes"], 60)
    today_h, today_m = divmod(data["today_focus_minutes"], 60)

    typer.echo(f"All-Time Focus: {total_h}h {total_m}m")
    typer.secho(f"Focus Today: {today_h}h {today_m}m", fg=typer.colors.GREEN, bold=True)

    if data["heatmap"]:
        typer.echo("\nLast 7 Days Heatmap:")
        for day in data["heatmap"]:
            dh, dm = divmod(day["daily_mins"], 60)
            typer.echo(f"  {day['focus_date']}: {dh}h {dm}m")


@app.command()
def create(
    name: str = typer.Option(..., "-n", "--name"),
    pomos: int = typer.Option(5, "-p", "--pomos"),
    work: int = typer.Option(25, "-w", "--work"),
    break_m: int = typer.Option(5, "-b", "--break"),
    as_json: bool = typer.Option(False, "--json"),
):
    init_db()
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
    task_id: int = typer.Argument(...), blueprint: bool = typer.Option(False, "--all")
):
    init_db()
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

        task_id = typer.prompt("Enter the ID of the task to start", type=int)

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

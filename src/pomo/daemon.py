import json
import select
import socket
import sys
from pomo.utils import get_socket_path
from pomo.engine import PomoEngine
from pomo.storage import spawn_daily_tasks


def check_if_running(sock_path) -> bool:
    """Returns True if a live daemon is already responding on the socket."""
    if not sock_path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(sock_path))
            client.sendall(json.dumps({"action": "status"}).encode("utf-8"))
            client.recv(4096)
            return True
    except Exception:
        return False  # Socket exists but is dead


def run_server():
    sock_path = get_socket_path()

    # Idempotency check
    if check_if_running(sock_path):
        sys.exit(0)

    # Clean up dead socket file from a previous crash
    if sock_path.exists():
        sock_path.unlink()

    spawn_daily_tasks()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(5)
    server.setblocking(False)

    engine = PomoEngine()

    try:
        while True:
            readable, _, _ = select.select([server], [], [], 1.0)
            if readable:
                conn, _ = server.accept()
                with conn:
                    data = conn.recv(4096)
                    if data:
                        try:
                            payload = json.loads(data.decode("utf-8"))
                            response = engine.process_action(payload)
                            conn.sendall(json.dumps(response).encode("utf-8"))
                        except Exception as e:
                            err = {"status": "error", "message": str(e)}
                            conn.sendall(json.dumps(err).encode("utf-8"))

            engine.tick()

    except KeyboardInterrupt:
        pass
    finally:
        if sock_path.exists():
            sock_path.unlink()

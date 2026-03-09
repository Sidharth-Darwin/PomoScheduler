import json
import asyncio

from pomo.utils import get_socket_path, spawn_daemon_in_background


CUSTOM_FONT = {
    "0": [
        "████████",
        "████████",
        "██    ██",
        "██    ██",
        "██    ██",
        "██    ██",
        "██    ██",
        "██    ██",
        "████████",
        "████████",
    ],
    "1": [
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
    ],
    "2": [
        "████████",
        "████████",
        "      ██",
        "      ██",
        "████████",
        "████████",
        "██      ",
        "██      ",
        "████████",
        "████████",
    ],
    "3": [
        "████████",
        "████████",
        "      ██",
        "      ██",
        "████████",
        "████████",
        "      ██",
        "      ██",
        "████████",
        "████████",
    ],
    "4": [
        "██    ██",
        "██    ██",
        "██    ██",
        "██    ██",
        "████████",
        "████████",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
    ],
    "5": [
        "████████",
        "████████",
        "██      ",
        "██      ",
        "████████",
        "████████",
        "      ██",
        "      ██",
        "████████",
        "████████",
    ],
    "6": [
        "████████",
        "████████",
        "██      ",
        "██      ",
        "████████",
        "████████",
        "██    ██",
        "██    ██",
        "████████",
        "████████",
    ],
    "7": [
        "████████",
        "████████",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
        "      ██",
    ],
    "8": [
        "████████",
        "████████",
        "██    ██",
        "██    ██",
        "████████",
        "████████",
        "██    ██",
        "██    ██",
        "████████",
        "████████",
    ],
    "9": [
        "████████",
        "████████",
        "██    ██",
        "██    ██",
        "████████",
        "████████",
        "      ██",
        "      ██",
        "████████",
        "████████",
    ],
    ":": ["   ", "   ", " ██", " ██", "   ", "   ", " ██", " ██", "   ", "   "],
}


def render_clock(time_str: str) -> str:
    height = len(CUSTOM_FONT["0"])
    lines = ["" for _ in range(height)]
    for char in time_str:
        if char in CUSTOM_FONT:
            for i in range(height):
                lines[i] += CUSTOM_FONT[char][i] + "  "
    return "\n".join(lines)


def format_days(days_str: str) -> str:
    if not days_str or days_str == "None":
        return "None"
    day_map = {
        "0": "Mon",
        "1": "Tue",
        "2": "Wed",
        "3": "Thu",
        "4": "Fri",
        "5": "Sat",
        "6": "Sun",
    }
    return ", ".join([day_map.get(d, d) for d in days_str.split(",")])


async def async_send_to_daemon(payload: dict, retries: int = 1) -> dict:
    """Async wrapper to talk to the Unix socket and auto-spawn daemon if dead."""
    sock_path = get_socket_path()
    try:
        if not sock_path.exists():
            raise FileNotFoundError("Socket missing")
        reader, writer = await asyncio.open_unix_connection(str(sock_path))
        writer.write(json.dumps(payload).encode("utf-8"))
        await writer.drain()
        data = await reader.read(4096)
        writer.close()
        await writer.wait_closed()
        return json.loads(data.decode("utf-8"))
    except (FileNotFoundError, ConnectionRefusedError):
        if retries > 0:
            spawn_daemon_in_background()
            await asyncio.sleep(0.5)
            return await async_send_to_daemon(payload, retries=0)
        return {"status": "error", "message": "Daemon failed to start."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel


class Phase(str, Enum):
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    IDLE = "idle"
    PAUSED = "paused"


class ActiveTaskState(BaseModel):
    task_id: int
    name: str
    pomodoro_current: int
    pomodoro_total: int


class DaemonStatus(BaseModel):
    """The JSON payload returned by `pomo status --json`"""

    status: str = "success"
    is_running: bool
    current_phase: Phase
    active_task: Optional[ActiveTaskState] = None
    time_remaining_seconds: Optional[int] = None
    ends_at: Optional[str] = None


class SocketAction(BaseModel):
    """The JSON payload the CLI sends TO the daemon"""

    action: Literal["status", "start", "pause", "skip", "stop", "list"]
    task_id: Optional[int] = None

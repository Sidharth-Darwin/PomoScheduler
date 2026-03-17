from enum import Enum
from typing import Optional
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
    status: str = "success"
    is_running: bool
    current_phase: Phase
    active_task: Optional[ActiveTaskState] = None
    time_remaining_seconds: Optional[int] = None
    ends_at: Optional[str] = None

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class JobResult:
    name: str
    success: bool
    message: str = ""


class JobManager:
    """Starter synchronous manager. Replace with QThreadPool workers next."""

    def run(self, name: str, fn: Callable[[], None]) -> JobResult:
        try:
            fn()
            return JobResult(name=name, success=True)
        except Exception as exc:
            return JobResult(name=name, success=False, message=str(exc))

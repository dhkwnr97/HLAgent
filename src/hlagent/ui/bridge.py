"""Run async agent code from Streamlit's script thread on one long-lived event loop.

Provider HTTP clients are bound to the loop that created them; a single background loop keeps them
valid across Streamlit reruns (asyncio.run per message would close the loop under them).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class AsyncBridge:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="hlagent-async", daemon=True)
        self.thread.start()

    def run(self, coro: Coroutine[Any, Any, T], timeout: float = 900) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

"""Tiny async helper shared by store, models, and commands."""

from __future__ import annotations

from typing import Any


def run(coro: Any) -> Any:
    """Run ``coro`` on a loop, or in a worker thread if one is already running."""
    import asyncio
    import inspect

    if not inspect.isawaitable(coro):
        return coro
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _in_thread() -> Any:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    return _in_thread()

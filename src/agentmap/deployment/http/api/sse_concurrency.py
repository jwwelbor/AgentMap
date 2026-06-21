"""Process-wide stream-admission concurrency limiter (DEC-6; CR BLOCKER-1).

Split out of ``sse.py`` so both modules stay within the 350-line file limit
(CLAUDE.md ``max_file_lines``; spec.md E06-F05 §A.1 — the same "split out only if
the module would exceed the limit" precedent that produced ``sse.py`` from
``routes/stream.py``).  The concurrency limiter is a cohesive, separable concern:
the global ``asyncio.Semaphore`` that admits at most ``max_concurrent_streams``
simultaneous streams, sized from the ONE canonical config source.

The admission limit is ``get_sse_config()["max_concurrent_streams"]`` (§A.4) — the
single canonical source.  A module-level ``Semaphore(100)`` built at import is
wrong twice over: (1) the DI container has not started at import so live config is
unreadable, and (2) a hardcoded literal silently ignores the config knob (the
inert-config defect this fix removes).  Instead the semaphore is a lazily-
initialised singleton: the first request resolves ``max_concurrent_streams`` from
live config and builds the process-wide semaphore from it (coerced to ``int``);
every later request reuses that same object (one semaphore shared across all
requests — a per-request semaphore would limit nothing).  ``config wins once``:
the first resolved value sizes the pool for the process lifetime, mirroring how a
module-level semaphore would have been fixed at import.  Tests reset the singleton
via ``reset_stream_semaphore()`` so each starts from a clean, config-sized pool.
"""

import asyncio
from typing import Optional

_stream_semaphore_singleton: Optional[asyncio.Semaphore] = None


def get_stream_semaphore(max_concurrent_streams: int) -> asyncio.Semaphore:
    """Return the process-wide stream-admission semaphore, sized from config.

    On the first call the semaphore is built from ``max_concurrent_streams``
    (coerced to ``int``) and cached; subsequent calls return that same instance,
    ignoring the argument — the configured limit is fixed for the process lifetime
    (as a module-level semaphore would have been), so there is exactly ONE
    semaphore shared across every request.  The route obtains the limit from
    ``get_sse_config()["max_concurrent_streams"]`` and passes it here, keeping the
    config the single canonical source of the limit (REQ-F-004 / §A.4 / DEC-6).

    Args:
        max_concurrent_streams: The configured concurrency cap (from
            ``get_sse_config()``); used only on the first call to size the pool.

    Returns:
        The shared ``asyncio.Semaphore`` admitting at most ``max_concurrent_streams``
        concurrent streams.
    """
    global _stream_semaphore_singleton
    if _stream_semaphore_singleton is None:
        _stream_semaphore_singleton = asyncio.Semaphore(int(max_concurrent_streams))
    return _stream_semaphore_singleton


def reset_stream_semaphore() -> None:
    """Clear the cached stream-admission semaphore (test isolation seam).

    The semaphore is a process-wide singleton sized from config on first use, so a
    test that injects a particular ``max_concurrent_streams`` must reset it both
    before (to discard any pool an earlier test built) and after (so its small pool
    does not leak into later tests).  Production never calls this.
    """
    global _stream_semaphore_singleton
    _stream_semaphore_singleton = None


async def try_acquire_stream_slot(
    max_concurrent_streams: int,
) -> Optional[asyncio.Semaphore]:
    """Non-blocking pre-open admission against the config-sized semaphore (AC-6).

    Resolves the process-wide semaphore (sized from ``max_concurrent_streams`` on
    first use — see ``get_stream_semaphore``) and attempts to take a slot WITHOUT
    blocking: a full pool must yield a pre-open 503, never a queue behind a held
    slot (a blocking ``acquire()`` is forbidden — spec §A.7).  ``locked()`` is
    checked first; in asyncio ``acquire()`` never suspends while a slot is free, so
    there is no race between the ``locked()`` check and the ``acquire()``.

    Args:
        max_concurrent_streams: The configured concurrency cap (from
            ``get_sse_config()``); sizes the pool on first use.

    Returns:
        The shared semaphore with a slot HELD (the caller MUST release it on every
        exit path) when admission succeeds, or ``None`` when the pool is full (the
        caller returns 503; no slot was consumed).
    """
    semaphore = get_stream_semaphore(max_concurrent_streams)
    if semaphore.locked():
        return None
    await semaphore.acquire()
    return semaphore

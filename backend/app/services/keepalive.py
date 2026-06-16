"""CPU keep-alive to prevent CloudWatch low-CPU alarms from stopping the instance.

GPU-intensive mBER jobs produce minimal CPU load, which can trigger CloudWatch
alarms configured to stop instances when CPU utilization drops below a threshold
(e.g., <5-10% for 15 minutes). This module generates ~10-15% CPU utilization on
a single core using lightweight hash computations whenever jobs are active.
"""

import hashlib
import logging
import threading
import time

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_active = False  # Whether keep-alive CPU work is running
_shutdown = False  # Whether the module is shutting down entirely


def _cpu_work_loop() -> None:
    """Run CPU-bound hashing in a loop with brief sleeps to target ~10-15% utilization."""
    while True:
        with _lock:
            if _shutdown:
                return
            if not _active:
                # Wait until activated or shutdown
                pass

        if not _active:
            time.sleep(0.5)
            continue

        # Do a burst of SHA-256 hashing, then sleep to regulate CPU usage.
        # ~50ms work + ~200ms sleep ≈ 20% of one core, which translates to
        # roughly 10-15% overall on a 2-core instance or similar.
        end_time = time.monotonic() + 0.05
        data = b"keepalive"
        while time.monotonic() < end_time:
            data = hashlib.sha256(data).digest()

        time.sleep(0.2)


def start_keepalive() -> None:
    """Activate CPU keep-alive work. Safe to call multiple times."""
    global _active, _worker_thread, _shutdown

    with _lock:
        if _shutdown:
            return
        if _active:
            return
        _active = True
        logger.info("CPU keep-alive STARTED (preventing CloudWatch low-CPU alarm)")

        # Ensure the background thread is running
        if _worker_thread is None or not _worker_thread.is_alive():
            _shutdown = False
            _worker_thread = threading.Thread(
                target=_cpu_work_loop, name="cpu-keepalive", daemon=True
            )
            _worker_thread.start()


def stop_keepalive() -> None:
    """Deactivate CPU keep-alive work (thread stays alive but idles). Safe to call multiple times."""
    global _active

    with _lock:
        if not _active:
            return
        _active = False
        logger.info("CPU keep-alive STOPPED (no active jobs)")


def shutdown_keepalive() -> None:
    """Fully shut down the keep-alive thread. Call during app shutdown."""
    global _active, _shutdown, _worker_thread

    with _lock:
        _active = False
        _shutdown = True

    if _worker_thread is not None and _worker_thread.is_alive():
        _worker_thread.join(timeout=2.0)
        _worker_thread = None

    logger.info("CPU keep-alive shutdown complete")

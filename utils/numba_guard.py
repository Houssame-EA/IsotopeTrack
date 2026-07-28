"""Process-wide serialisation of Numba parallel regions.

The application pins Numba's ``workqueue`` threading layer (see ``Run.py``).
That layer is fast and dependency-free but **not** thread-safe: if two Python
threads enter a Numba parallel region at the same time it does not raise — it
prints

    Numba workqueue threading layer is terminating: Concurrent access has been
    detected.

and calls ``abort()``, killing the whole process with no traceback and no
chance to save the user's work.

UMAP (via ``pynndescent``) is built almost entirely from ``parallel=True`` /
``prange`` kernels, and the app can legitimately have several UMAP runs in
flight at once — the ④ *How it works* projection worker, the ② Cluster
worker, the sweep worker and the evaluate-K worker are all ``QThread`` s that
may be started from the same dialog.

Rather than change the threading layer (``tbb``/``omp`` are not always
available in the packaged builds), every Numba-heavy entry point takes this
lock, so at most one parallel region is ever live. The lock is re-entrant, so
nested calls from a single thread are fine.

Usage::

    from utils.numba_guard import numba_serial

    with numba_serial():
        embedding = UMAP(...).fit_transform(X)

The cost is that concurrent UMAP runs queue up instead of overlapping. In
practice they were already competing for the same cores, and a few seconds of
waiting is preferable to an ``abort()``.

Module attributes:
    NUMBA_LOCK (threading.RLock): Guards every Numba parallel region in the
        process. Re-entrant, so a guarded function may call another guarded
        function on the same thread.
    ACQUIRE_TIMEOUT (float): Seconds to wait for the lock before giving up and
        running anyway. A very long fit should not freeze a worker forever;
        running unguarded is a risk, a permanent deadlock is a certainty.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

_log = logging.getLogger("IsotopeTrack.utils.numba_guard")

NUMBA_LOCK = threading.RLock()

ACQUIRE_TIMEOUT = 600.0


@contextmanager
def numba_serial(what="numba parallel region"):
    """Serialise a Numba parallel region against every other thread.

    :param what: Short description used in the timeout warning.
    :yields: None, with :data:`NUMBA_LOCK` held (unless acquisition timed out).
    """
    got = NUMBA_LOCK.acquire(timeout=ACQUIRE_TIMEOUT)
    if not got:
        _log.warning("numba_serial: timed out waiting for the lock before %s; "
                     "proceeding unguarded", what)
    try:
        yield
    finally:
        if got:
            NUMBA_LOCK.release()

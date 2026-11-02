"""Background task registry (NDWI generation runs in a worker thread)."""

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from .utils import now_iso


class TaskStore:
    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()

    def create(self, kind, pid, extra=None):
        tid = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[tid] = {"id": tid, "kind": kind, "project": pid, "status": "queued",
                                "done": 0, "total": 0, "log": [], "error": None,
                                "result": None, "started": now_iso(), **(extra or {})}
        return tid

    def update(self, tid, **kw):
        with self._lock:
            self._tasks[tid].update(kw)

    def log(self, tid, msg):
        print(msg, flush=True)
        with self._lock:
            lg = self._tasks[tid]["log"]
            lg.append(msg)
            del lg[:-400]

    def get(self, tid):
        with self._lock:
            t = self._tasks.get(tid)
            return json.loads(json.dumps(t)) if t else None

    def any_active(self, kind):
        with self._lock:
            return any(t["kind"] == kind and t["status"] in ("queued", "running") for t in self._tasks.values())

    def active(self, pid, kind):
        with self._lock:
            for t in self._tasks.values():
                if t["project"] == pid and t["kind"] == kind and t["status"] in ("queued", "running"):
                    return dict(t)
        return None


TASKS = TaskStore()


EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rr-task")

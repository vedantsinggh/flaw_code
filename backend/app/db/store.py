import os
import json
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.config import settings

class JSONStore:
    def __init__(self, filename: str):
        self.filepath = os.path.join(settings.DATA_DIR, filename)
        self.lock = threading.Lock()
        self._initialize_store()

    def _initialize_store(self):
        with self.lock:
            if not os.path.exists(self.filepath):
                with open(self.filepath, "w") as f:
                    json.dump({}, f, indent=4)

    def read_all(self) -> Dict[str, Any]:
        with self.lock:
            try:
                if os.path.exists(self.filepath):
                    with open(self.filepath, "r") as f:
                        return json.load(f)
            except Exception:
                return {}
            return {}

    def write_all(self, data: Dict[str, Any]):
        with self.lock:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=4)

    def get(self, key: str) -> Optional[Any]:
        data = self.read_all()
        return data.get(key)

    def set(self, key: str, value: Any):
        data = self.read_all()
        data[key] = value
        self.write_all(data)

    def delete(self, key: str):
        data = self.read_all()
        if key in data:
            del data[key]
            self.write_all(data)


class EventLogStore:
    """
    Append-only, list-backed JSON store for structured pipeline events.
    Events are ordered chronologically; the list is capped at MAX_EVENTS entries.
    """
    MAX_EVENTS = 500

    def __init__(self, filename: str):
        self.filepath = os.path.join(settings.DATA_DIR, filename)
        self.lock = threading.Lock()
        self._initialize_store()

    def _initialize_store(self):
        with self.lock:
            if not os.path.exists(self.filepath):
                with open(self.filepath, "w") as f:
                    json.dump([], f, indent=2)

    def read_all(self) -> List[Dict[str, Any]]:
        with self.lock:
            try:
                if os.path.exists(self.filepath):
                    with open(self.filepath, "r") as f:
                        data = json.load(f)
                        return data if isinstance(data, list) else []
            except Exception:
                return []
            return []

    def append_event(self, source: str, event_type: str, payload: str, task_id: str = "") -> Dict[str, Any]:
        """
        Appends a new structured event and returns it.
        Trims the log to MAX_EVENTS to bound disk use.
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": source,
            "event_type": event_type,
            "payload": payload,
            "task_id": task_id,
        }
        with self.lock:
            try:
                events: List[Dict] = []
                if os.path.exists(self.filepath):
                    with open(self.filepath, "r") as f:
                        raw = json.load(f)
                        events = raw if isinstance(raw, list) else []
                events.append(event)
                # Trim to cap
                if len(events) > self.MAX_EVENTS:
                    events = events[-self.MAX_EVENTS:]
                with open(self.filepath, "w") as f:
                    json.dump(events, f, indent=2)
            except Exception:
                pass
        return event

    def clear(self):
        with self.lock:
            with open(self.filepath, "w") as f:
                json.dump([], f, indent=2)


# Global store instances
tasks_store = JSONStore("tasks.json")
analytics_store = JSONStore("analytics.json")
decisions_store = JSONStore("decisions.json")
memory_store = JSONStore("memory.json")
health_store = JSONStore("health.json")
event_log_store = EventLogStore("event_log.json")

# Helpers to initialize default data
def initialize_database():
    """
    Ensures every JSON store file exists on disk.
    No seed / mock data is written — every store starts empty so the
    dashboard only ever shows real data produced by live agent runs.
    """
    # Tasks, analytics, decisions, memory — all start empty
    if not tasks_store.read_all():
        tasks_store.write_all({})

    if not analytics_store.read_all():
        analytics_store.write_all({})

    if not decisions_store.read_all():
        decisions_store.write_all({})

    if not memory_store.read_all():
        memory_store.write_all({})

    # Health store — real service list, status set on first health-check run
    if not health_store.read_all():
        health_store.write_all({
            "Hermes":         {"status": "Starting", "last_checked": datetime.utcnow().isoformat(), "message": "Not yet checked"},
            "OpenClaw":       {"status": "Starting", "last_checked": datetime.utcnow().isoformat(), "message": "Not yet checked"},
            "Slack":          {"status": "Starting", "last_checked": datetime.utcnow().isoformat(), "message": "Not yet checked"},
            "GitHub":         {"status": "Starting", "last_checked": datetime.utcnow().isoformat(), "message": "Not yet checked"},
            "GitHub Actions": {"status": "Starting", "last_checked": datetime.utcnow().isoformat(), "message": "Not yet checked"},
            "EastRouter":     {"status": "Starting", "last_checked": datetime.utcnow().isoformat(), "message": "Not yet checked"},
            "Database":       {"status": "Healthy",  "last_checked": datetime.utcnow().isoformat(), "message": "JSONStore active"},
        })




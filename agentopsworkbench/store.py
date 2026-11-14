"""Fake customer store. In-memory by default; optionally persisted to JSON.

With no path, every run starts from the seed, as before: golden
runs, stress runs, the adversarial set, and replays all stay
isolated and deterministic. With a path, the store loads that JSON
file when it exists (seeding and saving it on first use), and the
executor saves it after a run whose verification passed. A
refused, denied, failed, or verification-failed run never writes
the file, so only verified state persists.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

SEED = {
    "C1001": {
        "id": "C1001",
        "name": "Asha Verma",
        "email": "asha@example.com",
        "address": "12 Oak St, Sunnyvale, CA",
        "status": "active",
    },
    "C1002": {
        "id": "C1002",
        "name": "Ben Ortiz",
        "email": "ben@example.com",
        "address": "48 Pine Ave, Sunnyvale, CA",
        "status": "active",
    },
    "C1003": {
        "id": "C1003",
        "name": "Cara Lin",
        "email": "cara@example.com",
        "address": "9 Cedar Rd, Mountain View, CA",
        "status": "active",
    },
}


def default_store_path():
    return Path(__file__).resolve().parents[1] / "store.json"


class CustomerStore:
    """A tiny customer record store for the v1 demo."""

    def __init__(self, seed=None, path=None):
        self._path = Path(path) if path is not None else None
        if self._path is not None and self._path.exists():
            self._data = json.loads(self._path.read_text())
        else:
            self._data = copy.deepcopy(seed or SEED)
            self.save()

    @property
    def path(self):
        return self._path

    def save(self):
        """Write the current state to disk. A no-op for in-memory stores."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))

    def reset(self, seed=None):
        """Restore the seed data and save it. Returns the seed snapshot."""
        self._data = copy.deepcopy(seed or SEED)
        self.save()
        return copy.deepcopy(self._data)

    def get(self, customer_id):
        record = self._data.get(customer_id)
        return copy.deepcopy(record) if record is not None else None

    def search(self, query):
        q = query.lower()
        return [
            copy.deepcopy(c)
            for c in self._data.values()
            if q in c["name"].lower() or q in c["email"].lower()
        ]

    def update(self, customer_id, **fields):
        if customer_id not in self._data:
            raise KeyError(customer_id)
        self._data[customer_id].update(fields)
        return copy.deepcopy(self._data[customer_id])

    def delete(self, customer_id):
        if customer_id not in self._data:
            raise KeyError(customer_id)
        del self._data[customer_id]

    def snapshot(self):
        return copy.deepcopy(self._data)


def load_store(path=None):
    """Load the persistent store (project-root store.json by default)."""
    return CustomerStore(path=path or default_store_path())

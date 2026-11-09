"""Fake customer store. In-memory only; nothing real is ever at risk."""
from __future__ import annotations

import copy

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


class CustomerStore:
    """A tiny in-memory customer record store for the v1 demo."""

    def __init__(self, seed=None):
        self._data = copy.deepcopy(seed or SEED)

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

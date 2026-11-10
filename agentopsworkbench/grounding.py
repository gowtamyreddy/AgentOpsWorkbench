"""Grounding check: a brain-proposed plan must be traceable to the
request text. The customer it names and any new value it writes must
appear in the request. Anything the request never supplied is a
guess, and a guess is refused before it runs, before approval is
even asked.

Two checks, both plain string matching, no model involved:

1. The customer is grounded: their ID, full name, first name, or
   last name appears in the request. And a different last name
   attached to the first name means the request is about someone
   else: "Asha Sharma" is not "Asha Verma".
2. Every new value in the plan (new_email, new_address) appears
   verbatim in the request, case-insensitive, trailing punctuation
   tolerated. And a new value must not be another customer's current
   value: "Change Asha's email to ben@example.com" states the value,
   but it is Ben's email, not a new one for Asha.

A refused plan is never executed, so a grounding failure costs a
refusal, never a wrong mutation.
"""
from __future__ import annotations

import re

_VALUE_FIELDS = ("new_email", "new_address")
_STORE_FIELD = {"new_email": "email", "new_address": "address"}


def _word_appears(word, request):
    return re.search(rf"\b{re.escape(word)}\b", request, re.I) is not None


def _value_appears(value, request):
    value = value.strip().rstrip(".,;:")
    return value.lower() in request.lower()


def _same_value(left, right):
    return " ".join(str(left).split()).lower() == " ".join(
        str(right).split()
    ).lower()


def grounding_problems(proposal, request, store):
    """Problems with a proposed plan; empty when it is grounded."""
    if not proposal.ok or proposal.task is None:
        return []
    customer_id = proposal.inputs.get("customer_id")
    customer = store.get(customer_id) if customer_id else None
    if customer is None:
        return [f"customer {customer_id} is not in the store"]
    first, _, last = customer["name"].partition(" ")
    problems = []
    named = (
        _word_appears(customer_id, request)
        or _word_appears(customer["name"], request)
        or _word_appears(first, request)
        or (last and _word_appears(last, request))
    )
    if not named:
        problems.append(
            f"customer {customer['name']} is not named in the request"
        )
    else:
        match = re.search(
            rf"\b{re.escape(first)}\s+([A-Za-z]+)", request, re.I
        )
        if match:
            other = match.group(1)
            if last and other.lower() != last.lower():
                problems.append(
                    f"request names {first} {other}, not "
                    f"{customer['name']}"
                )
    for field in _VALUE_FIELDS:
        value = proposal.inputs.get(field)
        if value and not _value_appears(value, request):
            problems.append(f"{field} {value!r} is not stated in the request")
        if value:
            store_field = _STORE_FIELD[field]
            for other_id, other in store.snapshot().items():
                if other_id == customer_id:
                    continue
                if _same_value(value, other.get(store_field, "")):
                    problems.append(
                        f"{field} {value!r} is {other['name']}'s "
                        f"current {store_field}"
                    )
    return problems

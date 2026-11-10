"""Grounding check: the customer and any new value in a plan must
come from the request text. No model involved, so these run fast.
"""
from agentopsworkbench.brain import PlanProposal
from agentopsworkbench.grounding import grounding_problems
from agentopsworkbench.store import CustomerStore


def _proposal(task, **inputs):
    return PlanProposal(task=task, inputs=inputs, ok=True,
                        raw="test proposal")


def test_grounded_full_name_and_value():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1001",
                  new_email="asha.new@example.com"),
        "Change Asha Verma's email to asha.new@example.com", store)
    assert problems == []


def test_grounded_first_name_only():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1003",
                  new_email="cara.new@example.com"),
        "Update Cara's email to cara.new@example.com", store)
    assert problems == []


def test_grounded_lookup_by_id():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("lookup_customer", customer_id="C1002"),
        "Can you look up C1002 for me?", store)
    assert problems == []


def test_grounded_value_with_trailing_period():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1001",
                  new_email="asha.new@example.com"),
        "Change Asha Verma's email to asha.new@example.com.", store)
    assert problems == []


def test_unknown_person_not_grounded():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1001",
                  new_email="zoe@example.com"),
        "Update the email for Zoe to zoe@example.com", store)
    assert any("not named" in p for p in problems)


def test_similar_name_not_grounded():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1001",
                  new_email="asha.sharma@example.com"),
        "Change Asha Sharma's email to asha.sharma@example.com",
        store)
    assert any("Asha Sharma" in p for p in problems)


def test_value_not_in_request_not_grounded():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1001",
                  new_email="asha@example.com"),
        "Update Asha's info", store)
    assert any("not stated" in p for p in problems)


def test_show_me_lookup_turned_update_not_grounded():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1003",
                  new_email="cara.new@example.com"),
        "Show me Cara Lin", store)
    assert any("not stated" in p for p in problems)


def test_gibberish_not_grounded():
    store = CustomerStore()
    problems = grounding_problems(
        _proposal("update_customer_email", customer_id="C1001",
                  new_email="asdf.qwer.zxcv"),
        "asdf qwer zxcv", store)
    assert problems


def test_declined_proposal_has_no_grounding_problems():
    store = CustomerStore()
    declined = PlanProposal(task=None, inputs={}, ok=False,
                            error="brain declined")
    assert grounding_problems(declined, "Delete Ben Ortiz", store) == []

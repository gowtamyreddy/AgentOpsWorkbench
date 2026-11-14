import json

from agentopsworkbench.approval import always_approve, always_deny
from agentopsworkbench.executor import run_plan
from agentopsworkbench.policy import build_plan
from agentopsworkbench.store import SEED, CustomerStore, load_store


def test_first_use_seeds_and_saves(tmp_path):
    path = tmp_path / "store.json"
    store = CustomerStore(path=path)
    assert path.exists()
    assert json.loads(path.read_text()) == SEED


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "store.json"
    store = CustomerStore(path=path)
    store.update("C1001", email="asha.new@example.com")
    store.save()
    reloaded = CustomerStore(path=path)
    assert reloaded.get("C1001")["email"] == "asha.new@example.com"


def test_reset_restores_seed(tmp_path):
    path = tmp_path / "store.json"
    store = CustomerStore(path=path)
    store.update("C1001", email="asha.new@example.com")
    store.save()
    store.reset()
    assert json.loads(path.read_text()) == SEED


def test_in_memory_store_never_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = CustomerStore()
    assert store.path is None
    store.update("C1001", email="asha.new@example.com")
    store.save()
    assert list(tmp_path.iterdir()) == []


def test_verified_write_persists_denied_does_not(tmp_path):
    path = tmp_path / "store.json"
    store = CustomerStore(path=path)
    steps, allow_list, verify_spec = build_plan(
        "update_customer_email",
        {"customer_id": "C1001", "new_email": "asha.new@example.com"},
    )
    result = run_plan(steps, allow_list, store, always_deny,
                      verify_spec=verify_spec)
    assert result.status == "denied"
    assert json.loads(path.read_text())["C1001"]["email"] == "asha@example.com"
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify_spec)
    assert result.status == "succeeded"
    assert json.loads(path.read_text())["C1001"]["email"] == "asha.new@example.com"


def test_verification_failed_write_does_not_persist(tmp_path):
    path = tmp_path / "store.json"
    store = CustomerStore(path=path)
    steps, allow_list, verify_spec = build_plan(
        "update_customer_email",
        {"customer_id": "C1001", "new_email": "asha.new@example.com"},
    )
    faults = {"update_customer_email": {"write_wrong": "wrong@example.com"}}
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify_spec, faults=faults)
    assert result.status == "verification_failed"
    assert json.loads(path.read_text())["C1001"]["email"] == "asha@example.com"


def test_cli_persists_and_fresh_resets(tmp_path, monkeypatch):
    import agentopsworkbench.cli as cli
    monkeypatch.setattr(
        cli, "save_run",
        lambda record, base=None: tmp_path / "run.json")
    store_path = tmp_path / "store.json"
    code = cli.main(["update_customer_email", "--customer", "C1001",
                     "--email", "asha.new@example.com", "--yes",
                     "--store", str(store_path)])
    assert code == 0
    assert json.loads(store_path.read_text())["C1001"]["email"] == \
        "asha.new@example.com"
    code = cli.main(["lookup_customer", "--customer", "C1001",
                     "--fresh", "--store", str(store_path)])
    assert code == 0
    assert json.loads(store_path.read_text())["C1001"]["email"] == \
        "asha@example.com"


def test_load_store_uses_given_path(tmp_path):
    path = tmp_path / "custom.json"
    store = load_store(path)
    assert store.path == path
    assert path.exists()

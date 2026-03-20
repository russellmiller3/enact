"""Tests for the @action decorator and generic action system."""
import pytest
from enact.action import action, execute_action, get_action_registry, clear_action_registry
from enact.client import EnactClient
from enact.models import PolicyResult, ActionResult


@pytest.fixture(autouse=True)
def clean_registry():
    """Prevent test pollution — clear the global action registry before each test."""
    clear_action_registry()
    yield
    clear_action_registry()


# --- Cycle 1: @action decorator basics ---

def test_decorator_sets_attribute():
    @action("math.add")
    def add(x, y):
        return {"sum": x + y}
    assert hasattr(add, "_enact_action")
    assert add._enact_action.name == "math.add"
    assert add._enact_action.system == "math"
    assert callable(add._enact_action.fn)


def test_decorator_registers():
    @action("test_reg.foo")
    def foo():
        return {}
    registry = get_action_registry()
    assert "test_reg.foo" in registry


def test_name_must_have_dot():
    with pytest.raises(ValueError, match="system.action_name"):
        @action("nodot")
        def bad():
            return {}


def test_explicit_system_overrides():
    @action("x.y", system="custom")
    def fn():
        return {}
    assert fn._enact_action.system == "custom"


def test_decorator_preserves_callable():
    """Decorated function is still directly callable — decorator just adds attributes."""
    @action("preserve.call")
    def add(x, y):
        return {"sum": x + y}
    assert add(1, 2) == {"sum": 3}


# --- Cycle 2: Return normalization ---

def test_dict_return():
    @action("norm.dict_ret")
    def fn(x):
        return {"val": x}
    result = execute_action(fn._enact_action, {"x": 5})
    assert result.success is True
    assert result.output == {"val": 5, "already_done": False}
    assert result.rollback_data == {}


def test_tuple_return():
    @action("norm.tuple_ret")
    def fn(x):
        return {"val": x}, {"original": x}
    result = execute_action(fn._enact_action, {"x": 5})
    assert result.success is True
    assert result.output == {"val": 5, "already_done": False}
    assert result.rollback_data == {"original": 5}


def test_action_result_passthrough():
    @action("norm.ar_ret")
    def fn():
        return ActionResult(action="norm.ar_ret", system="norm", success=True, output={"direct": True})
    result = execute_action(fn._enact_action, {})
    assert result.output == {"direct": True}


def test_exception_caught():
    @action("norm.raises")
    def fn():
        raise RuntimeError("boom")
    result = execute_action(fn._enact_action, {})
    assert result.success is False
    assert "boom" in result.output["error"]


def test_none_return_treated_as_empty():
    @action("norm.none_ret")
    def fn():
        return None
    result = execute_action(fn._enact_action, {})
    assert result.success is True
    assert result.output == {"already_done": False}


def test_bad_return_type():
    @action("norm.bad")
    def fn():
        return 42
    with pytest.raises(TypeError, match="must return"):
        execute_action(fn._enact_action, {})


# --- Cycle 3: rollback_with() pairing ---

def test_rollback_with():
    @action("rb.create")
    def create():
        return {"id": 1}, {"id": 1}

    @action("rb.delete")
    def delete(id):
        return {"deleted": True}

    create.rollback_with(delete)
    assert create._enact_action.rollback_fn is delete._enact_action


def test_rollback_with_non_decorated_raises():
    @action("rb.create2")
    def create():
        return {"id": 1}, {"id": 1}

    def plain_fn():
        pass

    with pytest.raises(TypeError, match="must be decorated with @action"):
        create.rollback_with(plain_fn)


# --- Cycle 4: EnactClient accepts actions= ---

def test_client_accepts_actions():
    @action("cli.test")
    def test_fn():
        return {"ok": True}
    client = EnactClient(actions=[test_fn], secret="x" * 32)
    assert "cli.test" in client._action_registry


def test_client_rejects_non_decorated():
    def plain_fn():
        pass
    with pytest.raises(TypeError, match="not decorated"):
        EnactClient(actions=[plain_fn], secret="x" * 32)


def test_client_rejects_duplicates():
    @action("dup.test")
    def fn1():
        return {}
    @action("dup.test")
    def fn2():
        return {}
    with pytest.raises(ValueError, match="Duplicate"):
        EnactClient(actions=[fn1, fn2], secret="x" * 32)


# --- Cycle 5: run_action() ---

def test_run_action_pass(tmp_path):
    @action("ra.greet")
    def greet(name):
        return {"msg": f"hello {name}"}

    client = EnactClient(
        actions=[greet], secret="x" * 32, receipt_dir=str(tmp_path)
    )
    result, receipt = client.run_action(
        action="ra.greet", user_email="test@test.com", payload={"name": "world"}
    )
    assert result.success is True
    assert result.output == {"ra.greet": {"msg": "hello world", "already_done": False}}
    assert receipt.decision == "PASS"
    assert receipt.workflow == "ra.greet"
    assert len(receipt.actions_taken) == 1


def test_run_action_blocked_by_policy(tmp_path):
    @action("ra.blocked")
    def do_thing():
        return {"done": True}

    def block_everything(context):
        return PolicyResult(policy="block_all", passed=False, reason="nope")

    client = EnactClient(
        actions=[do_thing], policies=[block_everything],
        secret="x" * 32, receipt_dir=str(tmp_path)
    )
    result, receipt = client.run_action(
        action="ra.blocked", user_email="test@test.com", payload={}
    )
    assert result.success is False
    assert receipt.decision == "BLOCK"
    assert receipt.actions_taken == []


def test_run_action_unknown_raises():
    client = EnactClient(secret="x" * 32)
    with pytest.raises(ValueError, match="Unknown action"):
        client.run_action(action="nope.nada", user_email="x", payload={})


def test_run_action_passes_user_attributes(tmp_path):
    captured = {}

    @action("ra.attr_test")
    def fn():
        return {"ok": True}

    def capture_policy(context):
        captured["attrs"] = context.user_attributes
        return PolicyResult(policy="capture", passed=True, reason="ok")

    client = EnactClient(
        actions=[fn], policies=[capture_policy],
        secret="x" * 32, receipt_dir=str(tmp_path)
    )
    client.run_action(
        action="ra.attr_test", user_email="t@t.com", payload={},
        user_attributes={"role": "admin"},
    )
    assert captured["attrs"] == {"role": "admin"}


def test_run_action_fn_exception_produces_receipt(tmp_path):
    """Action that raises still gets a PASS receipt with success=False action."""
    @action("ra.boom")
    def boom():
        raise RuntimeError("kaboom")

    client = EnactClient(
        actions=[boom], secret="x" * 32, receipt_dir=str(tmp_path)
    )
    result, receipt = client.run_action(
        action="ra.boom", user_email="t@t.com", payload={}
    )
    assert receipt.decision == "PASS"
    assert receipt.actions_taken[0].success is False
    assert "kaboom" in receipt.actions_taken[0].output["error"]
    assert result.success is False


# --- Cycle 6: Pluggable rollback ---

def test_rollback_with_registered_fn(tmp_path):
    calls = []

    @action("prb.create")
    def create(name):
        return {"id": 1}, {"id": 1, "name": name}

    @action("prb.undo_create")
    def undo_create(id, name):
        calls.append(("undo", id, name))
        return {"undone": True}

    create.rollback_with(undo_create)

    client = EnactClient(
        actions=[create, undo_create],
        secret="x" * 32,
        receipt_dir=str(tmp_path),
        rollback_enabled=True,
    )
    result, receipt = client.run_action(
        action="prb.create", user_email="t@t.com", payload={"name": "test"}
    )
    assert result.success is True

    rb_result, rb_receipt = client.rollback(receipt.run_id)
    assert rb_result.success is True
    assert calls == [("undo", 1, "test")]


def test_rollback_no_fn_returns_failure(tmp_path):
    @action("prb.no_rb")
    def no_rollback():
        return {"done": True}

    client = EnactClient(
        actions=[no_rollback],
        secret="x" * 32,
        receipt_dir=str(tmp_path),
        rollback_enabled=True,
    )
    result, receipt = client.run_action(
        action="prb.no_rb", user_email="t@t.com", payload={}
    )
    rb_result, rb_receipt = client.rollback(receipt.run_id)
    assert rb_receipt.decision == "PARTIAL"


def test_rollback_fn_exception_caught(tmp_path):
    @action("prb.explode")
    def explode():
        return {"id": 1}, {"id": 1}

    @action("prb.bad_undo")
    def bad_undo(id):
        raise RuntimeError("undo failed")

    explode.rollback_with(bad_undo)

    client = EnactClient(
        actions=[explode, bad_undo],
        secret="x" * 32,
        receipt_dir=str(tmp_path),
        rollback_enabled=True,
    )
    result, receipt = client.run_action(
        action="prb.explode", user_email="t@t.com", payload={}
    )
    rb_result, rb_receipt = client.rollback(receipt.run_id)
    assert rb_result.success is False
    assert rb_receipt.decision == "PARTIAL"
    assert "undo failed" in rb_receipt.actions_taken[0].output["error"]


# --- Cycle 8: End-to-end integration test ---

def test_e2e_action_lifecycle(tmp_path):
    """Full lifecycle: register actions, run with policies, verify receipt, rollback."""
    from enact import EnactClient, action
    from enact.receipt import load_receipt, verify_signature

    db = {}  # fake datastore

    @action("crm.create_contact")
    def create_contact(name, email):
        contact_id = len(db) + 1
        db[contact_id] = {"name": name, "email": email}
        return {"contact_id": contact_id}, {"contact_id": contact_id}

    @action("crm.delete_contact")
    def delete_contact(contact_id):
        removed = db.pop(contact_id, None)
        return {"deleted": True, "was": removed}

    create_contact.rollback_with(delete_contact)

    def no_evil_emails(context):
        email = context.payload.get("email", "")
        is_safe = not email.endswith("@evil.com")
        return PolicyResult(
            policy="no_evil_emails",
            passed=is_safe,
            reason="safe" if is_safe else "blocked evil domain",
        )

    secret = "a" * 32
    client = EnactClient(
        actions=[create_contact, delete_contact],
        policies=[no_evil_emails],
        secret=secret,
        receipt_dir=str(tmp_path),
        rollback_enabled=True,
    )

    # 1. Blocked action produces BLOCK receipt
    result, receipt = client.run_action(
        action="crm.create_contact",
        user_email="agent@co.com",
        payload={"name": "Bad", "email": "hacker@evil.com"},
    )
    assert result.success is False
    assert receipt.decision == "BLOCK"
    assert len(db) == 0

    # 2. Allowed action produces PASS receipt
    result, receipt = client.run_action(
        action="crm.create_contact",
        user_email="agent@co.com",
        payload={"name": "Good", "email": "good@company.com"},
    )
    assert result.success is True
    assert receipt.decision == "PASS"
    assert len(db) == 1
    assert db[1] == {"name": "Good", "email": "good@company.com"}

    # 3. Receipt is on disk and signed
    loaded = load_receipt(receipt.run_id, str(tmp_path))
    assert loaded.run_id == receipt.run_id
    assert verify_signature(loaded, secret)

    # 4. Rollback undoes the action
    rb_result, rb_receipt = client.rollback(receipt.run_id)
    assert rb_result.success is True
    assert len(db) == 0

    # 5. Rollback receipt is also signed
    rb_loaded = load_receipt(rb_receipt.run_id, str(tmp_path))
    assert rb_loaded.decision in ("PASS", "PARTIAL")

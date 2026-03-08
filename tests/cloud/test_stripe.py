"""
Tests for Stripe integration endpoints.

Mocking strategy:
- stripe.checkout.Session.create() → mock returning fake session object
- stripe.Webhook.construct_event() → mock returning fake event dict
- No real Stripe API calls in tests.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from cloud.main import app
from cloud.db import db, init_db

client = TestClient(app)

STRIPE_SK = "sk_test_fake"
STRIPE_WH = "whsec_fake"
STRIPE_PRICE = "price_fake123"


@pytest.fixture(autouse=True)
def stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", STRIPE_SK)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", STRIPE_WH)
    monkeypatch.setenv("STRIPE_PRICE_ID", STRIPE_PRICE)


# ── Cycle 1: Schema ───────────────────────────────────────────────────────────

class TestSchema:
    def test_subscriptions_table_exists(self, isolated_db):
        with db() as conn:
            conn.execute("SELECT team_id FROM subscriptions LIMIT 1")

    def test_checkout_sessions_table_exists(self, isolated_db):
        with db() as conn:
            conn.execute("SELECT session_id FROM checkout_sessions LIMIT 1")


# ── Cycle 2: Checkout session creation ───────────────────────────────────────

class TestCreateCheckoutSession:
    def _mock_session(self, url="https://checkout.stripe.com/pay/cs_test_fake"):
        mock = MagicMock()
        mock.url = url
        return mock

    def test_returns_checkout_url(self, isolated_db):
        with patch("stripe.checkout.Session.create", return_value=self._mock_session()):
            resp = client.post("/stripe/create-checkout-session", json={})
        assert resp.status_code == 200
        assert resp.json()["checkout_url"].startswith("https://checkout.stripe.com")

    def test_passes_customer_email(self, isolated_db):
        with patch("stripe.checkout.Session.create", return_value=self._mock_session()) as mock_create:
            client.post("/stripe/create-checkout-session", json={"customer_email": "test@example.com"})
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["customer_email"] == "test@example.com"

    def test_no_customer_email_omits_field(self, isolated_db):
        with patch("stripe.checkout.Session.create", return_value=self._mock_session()) as mock_create:
            client.post("/stripe/create-checkout-session", json={})
        call_kwargs = mock_create.call_args[1]
        assert "customer_email" not in call_kwargs

    def test_503_when_stripe_not_configured(self, isolated_db, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY")
        resp = client.post("/stripe/create-checkout-session", json={})
        assert resp.status_code == 503

    def test_503_when_price_id_missing(self, isolated_db, monkeypatch):
        monkeypatch.delenv("STRIPE_PRICE_ID")
        resp = client.post("/stripe/create-checkout-session", json={})
        assert resp.status_code == 503


# ── Cycle 3: Webhook — checkout.session.completed ─────────────────────────────

def _make_checkout_event(session_id="cs_test_1", customer_id="cus_test_1",
                          subscription_id="sub_test_1", email="buyer@example.com"):
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "customer": customer_id,
                "subscription": subscription_id,
                "customer_details": {"email": email},
                "customer_email": email,
            }
        },
    }


def _post_webhook(event_dict):
    with patch("stripe.Webhook.construct_event", return_value=event_dict):
        return client.post(
            "/stripe/webhook",
            content=json.dumps(event_dict),
            headers={"stripe-signature": "t=1,v1=fakesig"},
        )


class TestWebhookCheckoutCompleted:
    def test_provisions_team(self, isolated_db):
        _post_webhook(_make_checkout_event())
        with db() as conn:
            teams = conn.execute("SELECT * FROM teams").fetchall()
        assert len(teams) == 1
        assert teams[0]["plan"] == "cloud"

    def test_provisions_api_key(self, isolated_db):
        _post_webhook(_make_checkout_event())
        with db() as conn:
            keys = conn.execute("SELECT * FROM api_keys").fetchall()
        assert len(keys) == 1

    def test_provisions_subscription(self, isolated_db):
        _post_webhook(_make_checkout_event(
            customer_id="cus_abc", subscription_id="sub_abc"
        ))
        with db() as conn:
            sub = conn.execute("SELECT * FROM subscriptions").fetchone()
        assert sub["stripe_customer_id"] == "cus_abc"
        assert sub["stripe_subscription_id"] == "sub_abc"
        assert sub["status"] == "active"

    def test_stores_raw_key_in_checkout_sessions(self, isolated_db):
        _post_webhook(_make_checkout_event(session_id="cs_test_xyz"))
        with db() as conn:
            row = conn.execute(
                "SELECT * FROM checkout_sessions WHERE session_id = %s", ("cs_test_xyz",)
            ).fetchone()
        assert row is not None
        assert row["status"] == "completed"
        assert row["raw_api_key"].startswith("enact_live_")

    def test_idempotent_duplicate_webhook(self, isolated_db):
        event = _make_checkout_event()
        _post_webhook(event)
        resp = _post_webhook(event)
        assert resp.status_code == 200
        with db() as conn:
            count = conn.execute("SELECT COUNT(*) as cnt FROM teams").fetchone()["cnt"]
        assert count == 1  # not doubled

    def test_invalid_signature_returns_400(self, isolated_db):
        with patch("stripe.Webhook.construct_event", side_effect=Exception("Bad sig")):
            resp = client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "bad"},
            )
        assert resp.status_code == 400

    def test_503_when_webhook_secret_missing(self, isolated_db, monkeypatch):
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
        resp = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "x"})
        assert resp.status_code == 503


# ── Cycle 4: Success page + status polling ────────────────────────────────────

class TestSuccessPage:
    def test_returns_html(self, isolated_db):
        resp = client.get("/stripe/success?session_id=cs_test_1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "ENACT" in resp.text


class TestStripeStatus:
    def _seed_session(self, conn, session_id, status="completed", raw_api_key="enact_live_testkey123"):
        conn.execute(
            """INSERT INTO checkout_sessions (session_id, team_id, raw_api_key, customer_email, status)
               VALUES (%s, %s, %s, %s, %s)""",
            (session_id, "team-x", raw_api_key, "test@example.com", status),
        )

    def test_pending_returns_pending(self, isolated_db):
        with db() as conn:
            self._seed_session(conn, "cs_pending", status="pending", raw_api_key=None)
        resp = client.get("/stripe/status/cs_pending")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_ready_returns_key(self, isolated_db):
        with db() as conn:
            self._seed_session(conn, "cs_ready")
        resp = client.get("/stripe/status/cs_ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["api_key"] == "enact_live_testkey123"

    def test_key_nulled_after_first_read(self, isolated_db):
        with db() as conn:
            self._seed_session(conn, "cs_once")
        client.get("/stripe/status/cs_once")  # first read
        with db() as conn:
            row = conn.execute(
                "SELECT raw_api_key FROM checkout_sessions WHERE session_id = %s", ("cs_once",)
            ).fetchone()
        assert row["raw_api_key"] is None

    def test_already_retrieved_on_second_read(self, isolated_db):
        with db() as conn:
            self._seed_session(conn, "cs_twice")
        client.get("/stripe/status/cs_twice")  # first read
        resp = client.get("/stripe/status/cs_twice")  # second read
        assert resp.json()["status"] == "already_retrieved"

    def test_404_for_unknown_session(self, isolated_db):
        resp = client.get("/stripe/status/cs_nonexistent")
        assert resp.status_code == 404


# ── Cycle 5: Subscription lifecycle events ────────────────────────────────────

def _seed_subscription(conn, sub_id="sub_lifecycle", customer_id="cus_lifecycle"):
    team_id = "team-lifecycle"
    conn.execute("INSERT INTO teams (team_id, name) VALUES (%s, %s)", (team_id, "Test"))
    conn.execute(
        """INSERT INTO subscriptions (team_id, stripe_customer_id, stripe_subscription_id, status)
           VALUES (%s, %s, %s, %s)""",
        (team_id, customer_id, sub_id, "active"),
    )


class TestSubscriptionLifecycle:
    def test_subscription_deleted_marks_canceled(self, isolated_db):
        with db() as conn:
            _seed_subscription(conn)
        event = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_lifecycle"}},
        }
        _post_webhook(event)
        with db() as conn:
            row = conn.execute(
                "SELECT status FROM subscriptions WHERE stripe_subscription_id = %s",
                ("sub_lifecycle",),
            ).fetchone()
        assert row["status"] == "canceled"

    def test_payment_failed_marks_past_due(self, isolated_db):
        with db() as conn:
            _seed_subscription(conn)
        event = {
            "type": "invoice.payment_failed",
            "data": {"object": {"subscription": "sub_lifecycle"}},
        }
        _post_webhook(event)
        with db() as conn:
            row = conn.execute(
                "SELECT status FROM subscriptions WHERE stripe_subscription_id = %s",
                ("sub_lifecycle",),
            ).fetchone()
        assert row["status"] == "past_due"

    def test_unknown_event_type_returns_200(self, isolated_db):
        event = {"type": "some.unknown.event", "data": {"object": {}}}
        resp = _post_webhook(event)
        assert resp.status_code == 200

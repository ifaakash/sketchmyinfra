"""Tests for the growth-funnel endpoints: inline rating, first download, claiming
a pre-sign-in diagram, and the Pro trial new signups get.

Same approach as test_open_in_editor.py: no database harness, so handlers are
called directly with scripted sessions.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import settings
from app.routers import auth, generate_v2
from app.schemas import GenerationRating


class _ScriptedSession:
    """Returns queued scalar results from execute(), one per call, and keeps
    the statements so tests can check what was written."""

    def __init__(self, *scalars):
        self._scalars = list(scalars)
        self.statements = []
        self.added = []
        self.commits = 0

    async def execute(self, stmt):
        self.statements.append(stmt)
        value = self._scalars.pop(0)
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        pass


def _values(stmt) -> dict:
    """Column name -> bound value of an UPDATE's SET clause."""
    return {col.key: bind.value for col, bind in stmt._values.items()}


def _request(ip="203.0.113.7"):
    return SimpleNamespace(headers={}, client=SimpleNamespace(host=ip))


def _user(tier="free", trial_expires_at=None):
    return SimpleNamespace(id=uuid.uuid4(), tier=tier, trial_expires_at=trial_expires_at)


def _pro_trial():
    return _user("pro", trial_expires_at=datetime.now(timezone.utc) + timedelta(hours=12))


GRAPH_IR = {"category": "system_architecture", "graph": {"nodes": [{"id": "api"}], "edges": []}}


def _generation(user_id=None, ir_data=GRAPH_IR):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        prompt="api talks to a db",
        puml_code="@startuml\n@enduml",
        renderer="plantuml",
        ir_data=ir_data,
    )


# ---------------------------------------------------------------------------
# rating
# ---------------------------------------------------------------------------

def test_thumbs_down_stores_reasons_and_comment():
    gid = uuid.uuid4()
    db = _ScriptedSession(gid)
    body = GenerationRating(rating=-1, reasons=["wrong_icons", "messy_layout"], comment="icons are off")

    asyncio.run(generate_v2.rate_generation(gid, body, db))

    values = _values(db.statements[0])
    assert values["rating"] == -1
    assert values["rating_reasons"] == ["wrong_icons", "messy_layout"]
    assert values["rating_comment"] == "icons are off"
    assert db.commits == 1


def test_thumbs_up_clears_earlier_reasons():
    """Changing a 👎 to a 👍 must not leave the old complaint behind."""
    gid = uuid.uuid4()
    db = _ScriptedSession(gid)

    asyncio.run(generate_v2.rate_generation(
        gid, GenerationRating(rating=1, reasons=["wrong_icons"], comment="x"), db,
    ))

    values = _values(db.statements[0])
    assert values["rating"] == 1
    assert values["rating_reasons"] is None
    assert values["rating_comment"] is None


def test_rating_unknown_generation_is_404():
    db = _ScriptedSession(None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(generate_v2.rate_generation(uuid.uuid4(), GenerationRating(rating=1), db))

    assert exc.value.status_code == 404
    assert db.commits == 0


@pytest.mark.parametrize("payload", [
    {"rating": 0},
    {"rating": 5},
    {"rating": -1, "reasons": ["not_a_reason"]},
    {"rating": -1, "comment": "x" * 1001},
])
def test_invalid_rating_payload_rejected(payload):
    with pytest.raises(ValidationError):
        GenerationRating(**payload)


# ---------------------------------------------------------------------------
# downloaded
# ---------------------------------------------------------------------------

def test_first_download_is_recorded():
    gid = uuid.uuid4()
    db = _ScriptedSession(gid)

    asyncio.run(generate_v2.record_downloaded(gid, db))

    assert db.commits == 1


def test_repeat_download_is_a_no_op():
    gid = uuid.uuid4()
    db = _ScriptedSession(None, gid)  # UPDATE matched nothing; row exists

    asyncio.run(generate_v2.record_downloaded(gid, db))

    assert db.commits == 0


def test_download_unknown_generation_is_404():
    db = _ScriptedSession(None, None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(generate_v2.record_downloaded(uuid.uuid4(), db))

    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# claim
# ---------------------------------------------------------------------------

def _claim(gid, user, db, ip="203.0.113.7"):
    return asyncio.run(generate_v2.claim_generation(gid, _request(ip), user, db))


def test_claim_attaches_row_and_returns_ir_for_pro():
    user = _pro_trial()
    gen = _generation(user_id=user.id)  # what UPDATE ... RETURNING hands back
    db = _ScriptedSession(gen)

    resp = _claim(gen.id, user, db)

    assert _values(db.statements[0])["user_id"] == user.id
    assert db.commits == 1
    assert resp.generation_id == gen.id
    assert resp.editable is True
    assert resp.ir == GRAPH_IR


def test_claim_hides_ir_from_free_user():
    user = _user("free")
    gen = _generation(user_id=user.id)
    db = _ScriptedSession(gen)

    resp = _claim(gen.id, user, db)

    assert resp.editable is True
    assert resp.ir is None


def test_claim_is_scoped_to_same_ip_recent_unowned_success():
    """The guards live in the UPDATE's WHERE clause; check they're all there."""
    db = _ScriptedSession(_generation())

    _claim(uuid.uuid4(), _pro_trial(), db, ip="198.51.100.9")

    sql = str(db.statements[0].compile(compile_kwargs={"literal_binds": False}))
    assert "generations.user_id IS NULL" in sql
    assert "generations.status" in sql
    assert "generations.ip_address = CAST" in sql
    assert "generations.created_at >" in sql
    params = db.statements[0].compile().params
    assert "198.51.100.9" in params.values()


def test_reclaim_by_same_user_returns_row_without_writing():
    user = _pro_trial()
    gen = _generation(user_id=user.id)
    db = _ScriptedSession(None, gen)  # UPDATE matched nothing; user already owns it

    resp = _claim(gen.id, user, db)

    assert db.commits == 0
    assert resp.generation_id == gen.id


def test_claim_not_allowed_is_404():
    """Other owner, other IP, too old or unknown all look the same."""
    db = _ScriptedSession(None, None)

    with pytest.raises(HTTPException) as exc:
        _claim(uuid.uuid4(), _pro_trial(), db)

    assert exc.value.status_code == 404
    assert db.commits == 0


def test_claim_spatial_diagram_is_not_editable():
    user = _pro_trial()
    gen = _generation(user_id=user.id, ir_data={"category": "building_plan", "spatial": {}})
    db = _ScriptedSession(gen)

    resp = _claim(gen.id, user, db)

    assert resp.editable is False
    assert resp.ir is None


# ---------------------------------------------------------------------------
# Pro trial on signup
# ---------------------------------------------------------------------------

def _oauth_callback(monkeypatch, db):
    info = SimpleNamespace(
        provider="google", oauth_id="123", email="a@example.com", name="A", avatar_url=None,
    )

    async def _exchange(provider, code):
        return info

    monkeypatch.setattr(auth.oauth, "exchange_code", _exchange)
    monkeypatch.setattr(auth, "decode_state_token", lambda state, provider: True)
    monkeypatch.setattr(auth, "create_session_token", lambda uid, email: "token")
    return asyncio.run(auth.callback("google", code="c", state="s", error=None, db=db))


def test_new_user_gets_pro_trial(monkeypatch):
    db = _ScriptedSession(None)  # no existing user

    _oauth_callback(monkeypatch, db)

    user = db.added[0]
    assert user.tier == "pro"
    expected = datetime.now(timezone.utc) + timedelta(days=settings.pro_trial_days)
    assert abs((user.trial_expires_at - expected).total_seconds()) < 60
    assert generate_v2._is_pro(user)


def test_existing_user_tier_unchanged(monkeypatch):
    existing = SimpleNamespace(
        id=uuid.uuid4(), email="old@example.com", name="Old", avatar_url=None,
        tier="free", trial_expires_at=None,
    )
    db = _ScriptedSession(existing)

    _oauth_callback(monkeypatch, db)

    assert db.added == []
    assert existing.tier == "free"
    assert existing.trial_expires_at is None

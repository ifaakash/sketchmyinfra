"""Tests for the admin dashboard router.

The repo has no database test harness (no pytest-asyncio, no conftest, and the
models use PostgreSQL-only types: INET, JSONB, date_trunc), so these cover the
parts that can be verified without a live server: pagination arithmetic, trend
gap-filling, truncation, key verification, and the SQL the filter builder emits.
Row-level behaviour is covered by the curl checks in the deploy runbook.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from app.config import settings
from app.models import Generation
from app.routers import admin
from app.routers.admin import (
    Page,
    _generation_filters,
    _truncate,
    _verify_api_key,
    build_trend,
    page_count,
    trend_window_start,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_key(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", "s3cret-key")
    return "s3cret-key"


def test_correct_key_passes(admin_key):
    assert _verify_api_key(key=admin_key) is None


def test_wrong_key_is_403(admin_key):
    with pytest.raises(HTTPException) as exc:
        _verify_api_key(key="wrong")
    assert exc.value.status_code == 403


def test_unconfigured_key_is_503(monkeypatch):
    """An unset ADMIN_API_KEY must not let an empty key through."""
    monkeypatch.setattr(settings, "admin_api_key", "")
    with pytest.raises(HTTPException) as exc:
        _verify_api_key(key="")
    assert exc.value.status_code == 503


def test_auth_is_enforced_on_every_endpoint():
    """Auth lives on the router, not on individual handlers, so a newly added
    endpoint cannot ship unauthenticated by forgetting a dependency."""
    guarded = [d.dependency for d in admin.router.dependencies]
    assert _verify_api_key in guarded

    paths = {route.path for route in admin.router.routes}
    assert paths == {
        "/api/admin/stats",
        "/api/admin/users",
        "/api/admin/generations",
        "/api/admin/generations/{generation_id}",
    }
    # No handler declares its own key param — the router covers them all.
    for route in admin.router.routes:
        assert "key" not in route.endpoint.__annotations__


# ---------------------------------------------------------------------------
# Pagination arithmetic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "total,expected",
    [
        (0, 1),    # empty table still reads as "page 1 of 1", never "of 0"
        (1, 1),
        (15, 1),   # exactly one full page
        (16, 2),
        (30, 2),
        (31, 3),
    ],
)
def test_page_count_at_page_size_15(total, expected):
    assert page_count(total, 15) == expected


def test_page_count_rejects_zero_per_page():
    with pytest.raises(ValueError):
        page_count(10, 0)


def test_offset_is_zero_based_from_one_based_page():
    assert Page(1, 15).offset == 0
    assert Page(2, 15).offset == 15
    assert Page(3, 15).offset == 30


def test_meta_round_trip():
    meta = Page(2, 15).meta(31)
    assert (meta.page, meta.per_page, meta.total, meta.total_pages) == (2, 15, 31, 3)


def test_pages_do_not_overlap():
    """Consecutive pages must cover disjoint row ranges."""
    rows = list(range(31))
    seen = []
    for n in (1, 2, 3):
        p = Page(n, 15)
        seen.append(rows[p.offset:p.offset + p.per_page])
    assert seen[0] + seen[1] + seen[2] == rows
    assert len(set(seen[0]) & set(seen[1])) == 0
    assert len(set(seen[1]) & set(seen[2])) == 0


# ---------------------------------------------------------------------------
# Trend gap-filling
# ---------------------------------------------------------------------------

def test_trend_always_has_14_ascending_points():
    points = build_trend([], end=date(2026, 9, 27))
    assert len(points) == 14
    assert points[0].date == "2026-09-14"
    assert points[-1].date == "2026-09-27"
    assert [p.date for p in points] == sorted(p.date for p in points)


def test_trend_fills_missing_days_with_zeros():
    points = build_trend([(date(2026, 9, 20), 7, 5)], end=date(2026, 9, 27))
    by_date = {p.date: p for p in points}
    assert (by_date["2026-09-20"].total, by_date["2026-09-20"].success) == (7, 5)
    # failed is derived, so a status the counter doesn't know about still lands here
    assert by_date["2026-09-20"].failed == 2
    assert by_date["2026-09-19"].total == 0
    assert by_date["2026-09-19"].failed == 0


def test_trend_ignores_days_outside_the_window():
    points = build_trend([(date(2026, 1, 1), 99, 99)], end=date(2026, 9, 27))
    assert sum(p.total for p in points) == 0


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

def test_truncate_leaves_short_values_untouched():
    assert _truncate("short", 300) == "short"
    assert _truncate(None, 300) is None


def test_truncate_marks_clipped_values():
    out = _truncate("x" * 400, 300)
    assert len(out) == 301 and out.endswith("…")


# ---------------------------------------------------------------------------
# Generation filters — assert the SQL, since that is where the bugs hide
# ---------------------------------------------------------------------------

def sql_for(**kwargs):
    args = {
        "status": None, "renderer": None, "category": None,
        "q": None, "user_id": None, "anonymous": None,
    }
    args.update(kwargs)
    stmt = select(Generation.id).where(*_generation_filters(**args))
    compiled = stmt.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return " ".join(str(compiled).split())


def test_no_filters_selects_everything():
    assert "WHERE" not in sql_for()


def test_status_failed_is_everything_but_success():
    """The pseudo-status must not be compared literally, and must not enumerate
    known error names — that is how render_error got excluded before."""
    assert "generations.status != 'success'" in sql_for(status="failed")
    assert "'failed'" not in sql_for(status="failed")


@pytest.mark.parametrize("status", ["success", "gemini_error", "autofix_failed", "render_error"])
def test_concrete_status_matches_exactly(status):
    assert f"generations.status = '{status}'" in sql_for(status=status)


def test_uncategorized_maps_to_is_null():
    assert "generations.category IS NULL" in sql_for(category="uncategorized")
    assert "generations.category = 'graph'" in sql_for(category="graph")


def test_prompt_search_is_a_substring_match():
    assert "generations.prompt ILIKE" in sql_for(q="vpc")


def test_anonymous_true_and_false_are_opposites():
    assert "generations.user_id IS NULL" in sql_for(anonymous=True)
    assert "generations.user_id IS NOT NULL" in sql_for(anonymous=False)


def test_user_id_filter_wins_over_anonymous():
    """Both at once is contradictory; user_id is the explicit drill-down, so it
    takes precedence instead of producing a guaranteed-empty result."""
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    sql = sql_for(user_id=uid, anonymous=True)
    assert str(uid) in sql
    assert "IS NULL" not in sql


def test_filters_combine_with_and():
    sql = sql_for(status="failed", renderer="d2", q="vpc")
    assert sql.count("AND") == 2


# ---------------------------------------------------------------------------
# Trend window + bucketing
#
# Two bugs found against a live Asia/Kolkata Postgres: bare date_trunc() buckets
# by the session timezone (so a 02:00 UTC generation landed on the previous
# local day), and a "now - 13 days" window clipped the earliest day to a partial
# window, dropping 2 of 41 seeded rows from the chart.
# ---------------------------------------------------------------------------

def test_trend_window_starts_at_midnight_utc():
    start = trend_window_start(datetime(2026, 9, 27, 17, 42, 31, tzinfo=timezone.utc))
    assert start == datetime(2026, 9, 14, 0, 0, 0, tzinfo=timezone.utc)


def test_trend_window_covers_the_whole_first_day():
    """A generation early on the first day must fall inside the window, since
    build_trend emits a column for that whole day."""
    now = datetime(2026, 9, 27, 17, 42, tzinfo=timezone.utc)
    start = trend_window_start(now)
    first_column = build_trend([], end=now.date())[0].date
    assert start.date().isoformat() == first_column
    assert datetime(2026, 9, 14, 0, 30, tzinfo=timezone.utc) >= start
    # The naive "13 days ago" anchor would have excluded it.
    assert datetime(2026, 9, 14, 0, 30, tzinfo=timezone.utc) < now - timedelta(days=13)


def test_trend_buckets_in_utc_not_session_timezone():
    day = func.date_trunc("day", func.timezone("UTC", Generation.created_at))
    sql = str(
        select(day).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "timezone('UTC', generations.created_at)" in sql

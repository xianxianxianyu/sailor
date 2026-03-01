"""S0 smoke tests — canonical data contract."""
from core.pipeline.stages import canonicalize_url, make_resource_id


def test_make_resource_id_deterministic():
    url = "https://example.com/article?utm_source=twitter"
    canonical = canonicalize_url(url)
    rid1 = make_resource_id(canonical)
    rid2 = make_resource_id(canonical)
    assert rid1 == rid2
    assert rid1.startswith("res_")
    assert len(rid1) == 16  # "res_" + 12 hex chars


def test_canonicalize_strips_tracking():
    url = "https://example.com/page?utm_source=x&utm_medium=y&keep=1"
    canonical = canonicalize_url(url)
    assert "utm_source" not in canonical
    assert "utm_medium" not in canonical
    assert "keep=1" in canonical


def test_same_url_different_tracking_same_id():
    url1 = "https://example.com/post?utm_source=a"
    url2 = "https://example.com/post?utm_source=b"
    assert make_resource_id(canonicalize_url(url1)) == make_resource_id(canonicalize_url(url2))


def test_published_at_parsing():
    """Verify _parse_datetime handles ISO strings and Z suffix."""
    from core.sources.collectors import _parse_datetime
    from datetime import datetime

    assert _parse_datetime("2024-01-15T10:30:00Z") is not None
    assert isinstance(_parse_datetime("2024-01-15T10:30:00+00:00"), datetime)
    assert _parse_datetime("not-a-date") is None
    assert _parse_datetime("") is None
    assert _parse_datetime(None) is None

from app.main import app, health
from app.services.market_data import _optional_float, _optional_int


def test_health_status() -> None:
    assert health() == {"status": "ok"}


def test_expected_api_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])

    assert "/health" in paths
    assert "/api/research/{ticker}" in paths
    assert "/api/research/{ticker}/generate" in paths
    assert "/api/compare" in paths
    assert "/api/reports" in paths
    assert "/api/watchlist" in paths
    assert "/api/triage" in paths


def test_optional_numeric_parsers_handle_provider_placeholders() -> None:
    assert _optional_float("12.34") == 12.34
    assert _optional_float("N/A") is None
    assert _optional_float("") is None
    assert _optional_int("123456789") == 123456789
    assert _optional_int("None") is None

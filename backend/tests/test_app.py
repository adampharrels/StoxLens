from app.main import app, health


def test_health_status() -> None:
    assert health() == {"status": "ok"}


def test_expected_api_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/api/research/{ticker}" in paths
    assert "/api/research/{ticker}/generate" in paths
    assert "/api/compare" in paths
    assert "/api/reports" in paths
    assert "/api/watchlist" in paths

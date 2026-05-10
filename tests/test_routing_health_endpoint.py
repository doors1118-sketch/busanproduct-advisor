from fastapi.testclient import TestClient

from app import api_server


def test_admin_routing_health_requires_token_when_configured(monkeypatch):
    monkeypatch.setenv("ADMIN_HEALTH_TOKEN", "unit-test-token")
    monkeypatch.setenv("ADMIN_HEALTH_PROBE_COMPANY_API", "false")

    client = TestClient(api_server.app)

    assert client.get("/admin/health/routing").status_code == 403

    response = client.get(
        "/admin/health/routing?recent_limit=1",
        headers={"X-Admin-Token": "unit-test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "busanproduct-advisor-api"
    assert data["settings"]["llm_adjudicator_enabled"] in {True, False}
    assert "intent_rag" in data
    assert "recent_routing" in data


def test_routing_runtime_settings_tolerates_invalid_numeric_env(monkeypatch):
    monkeypatch.setenv("GEMINI_ROUTER_THINKING_BUDGET", "not-an-int")
    monkeypatch.setenv("GEMINI_ROUTE_ADJUDICATOR_TIMEOUT_SEC", "not-a-float")
    monkeypatch.setenv("MAX_TOOL_CALL_ROUNDS", "not-an-int")

    settings = api_server._get_routing_runtime_settings()

    assert settings["gemini_router_thinking_budget"] == 0
    assert settings["gemini_route_adjudicator_timeout_sec"] == 3.0
    assert settings["max_tool_call_rounds"] == 2
    assert settings["llm_tool_loop_enabled"] is False
    assert settings["llm_internal_tools_disabled"] is True
    assert settings["gemini_router_provider"] in {
        "vertex_ai",
        "gemini_api",
        "unconfigured",
        "unknown",
    }

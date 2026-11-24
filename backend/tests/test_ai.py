from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def _settings(key=None):
    return Settings(data_mode="demo", backend="memory", database_url=None, state="telangana", cors_origins=["*"],
                    show_record_points=True, contact_email=None, ml_model_dir=Path("/nonexistent"),
                    min_zoom_potential=8, max_cells=8000, rate_limit_per_min=60,
                    ai_provider="openai-compatible", ai_base_url="https://api.openai.com/v1",
                    ai_model="test-model", ai_api_key=key)


def test_ai_reports_not_configured_without_secret():
    app = create_app(settings=_settings(), container=None)
    with TestClient(app) as client:
        response = client.post("/api/ai/explain", json={"report": {"data_mode": "demo", "is_demo": True}})
    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"


def test_ai_explanation_uses_only_whitelisted_fields(monkeypatch):
    import app.routers.ai as ai
    seen = {}

    def fake_provider(settings, prompt):
        seen["prompt"] = prompt
        return "This is a cautious explanation."

    monkeypatch.setattr(ai, "_call_provider", fake_provider)
    app = create_app(settings=_settings("secret"), container=None)
    report = {"data_mode": "demo", "is_demo": True, "potential": {"class": "moderate"},
              "lat": 17.3, "lon": 78.4, "private_name": "not forwarded"}
    with TestClient(app) as client:
        response = client.post("/api/ai/explain", json={"report": report, "language": "en"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "synthetic" in seen["prompt"]
    assert "17.3" not in seen["prompt"]
    assert "not forwarded" not in seen["prompt"]


def test_ai_rejects_unknown_language():
    app = create_app(settings=_settings("secret"), container=None)
    with TestClient(app) as client:
        response = client.post("/api/ai/explain", json={"report": {}, "language": "fr"})
    assert response.status_code == 422

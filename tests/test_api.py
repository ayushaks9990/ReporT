from __future__ import annotations

import os
from pathlib import Path


TEST_DATABASE = Path(__file__).with_name("ai-analytic-platform-test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE}"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-integration-tests"
os.environ["ENVIRONMENT"] = "test"
os.environ.pop("GROQ_API_KEY", None)

from fastapi.testclient import TestClient

from backend.database import Base, engine
from backend.main import app


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module() -> None:
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    TEST_DATABASE.unlink(missing_ok=True)


def test_complete_authenticated_intelligence_flow() -> None:
    with TestClient(app) as client:
        assert client.get("/api/dashboard").status_code == 401

        registration = client.post(
            "/api/auth/register",
            json={
                "name": "Ada Analyst",
                "email": "ada@example.com",
                "password": "AIAnalyticPlatform2026",
            },
        )
        assert registration.status_code == 201
        assert registration.json()["user"]["email"] == "ada@example.com"

        bundled = client.get("/api/dashboard")
        assert bundled.status_code == 200
        assert bundled.json()["coverage"] == {
            "sales_records": 1000,
            "marketing_records": 1000,
        }
        assert bundled.json()["charts"]["conversions_by_quarter"]
        assert bundled.json()["charts"]["spend_by_quarter"]
        assert [item["name"] for item in bundled.json()["charts"]["acquisition_funnel"]] == [
            "Impressions",
            "Clicks",
            "Conversions",
        ]

        status = client.get("/api/system/status")
        assert status.status_code == 200
        assert status.json()["autogen_available"] is True
        assert status.json()["autogen_enabled"] is False
        assert status.json()["agent_pipeline"] == [
            "Data Analyst",
            "Report Writer",
            "Independent Critic",
        ]

        source = (
            "Quarter,Market,Product,Net Sales,Quantity\n"
            "Q1 2026,North,Nova Suite,1200.50,4\n"
            "Q2 2026,South,Pulse Cloud,1999.50,7\n"
        )
        upload = client.post(
            "/api/datasets/upload",
            files={"file": ("quarterly-sales.csv", source, "text/csv")},
            data={"name": "Quarterly sales", "kind": "auto"},
        )
        assert upload.status_code == 201
        dataset = upload.json()
        assert dataset["status"] == "ready"
        assert dataset["kind"] == "sales"
        assert dataset["row_count"] == 2
        assert dataset["mapping"]["revenue"] == "net_sales"
        assert dataset["mapping"]["region"] == "market"
        assert dataset["mapping"]["units_sold"] == "quantity"

        dataset_id = dataset["id"]
        custom = client.get("/api/dashboard", params={"dataset_id": dataset_id})
        assert custom.status_code == 200
        payload = custom.json()
        assert payload["dataset"]["name"] == "Quarterly sales"
        assert payload["coverage"] == {"sales_records": 2, "marketing_records": 0}
        assert payload["kpis"]["revenue"] == 3200.0
        assert payload["kpis"]["units"] == 11.0
        assert [item["name"] for item in payload["charts"]["revenue_by_quarter"]] == [
            "Q1 2026",
            "Q2 2026",
        ]

        report_response = client.post(
            "/api/reports/generate",
            json={
                "report_type": "custom",
                "dataset_id": dataset_id,
                "filters": {},
                "focus": "Find the strongest quarter and next action.",
                "question": "What changed between the two quarters?",
            },
        )
        assert report_response.status_code == 201
        report = report_response.json()
        assert report["dataset_id"] == dataset_id
        assert report["provider"] == "Verified data engine"
        assert "$3,200" in report["content"]
        assert "## Recommended action plan" in report["content"]
        assert [item["name"] for item in report["chart_data"]["revenue_by_quarter"]] == [
            "Q1 2026",
            "Q2 2026",
        ]

        report_id = report["id"]
        favorite = client.patch(
            f"/api/reports/{report_id}/favorite",
            json={"favorite": True},
        )
        assert favorite.status_code == 200
        assert favorite.json()["favorite"] is True

        export = client.get(
            f"/api/reports/{report_id}/download",
            params={"format": "json"},
        )
        assert export.status_code == 200
        assert export.json()["metrics"]["revenue"] == 3200.0
        assert export.json()["chart_data"]["revenue_by_quarter"][1]["value"] == 1999.5

        assert client.delete(f"/api/reports/{report_id}").status_code == 204
        assert client.delete(f"/api/datasets/{dataset_id}").status_code == 204
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401

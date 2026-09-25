"""HTTP and WebSocket behaviour of the API."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.ml.taxonomy import STATUSES, URGENCIES, urgency_rank
from tests.conftest import OUTAGE


def test_health_reports_model_state(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_classify_scores_without_saving(client: TestClient) -> None:
    before = client.get("/api/tickets?page_size=1").json()["total"]

    response = client.post("/api/tickets/classify", json=OUTAGE)

    assert response.status_code == 200
    preview = response.json()
    assert preview["urgency"] in URGENCIES
    assert preview["category_scores"] and preview["urgency_rationale"] is not None
    assert client.get("/api/tickets?page_size=1").json()["total"] == before


def test_create_classifies_stores_and_returns_detail(ticket: dict) -> None:
    assert ticket["reference"] == f"TKT-{ticket['id']:06d}"
    assert ticket["status"] == "Open"
    assert ticket["category"] == ticket["ai_category"]
    assert ticket["urgency"] == ticket["ai_urgency"]
    assert ticket["body"].startswith("Our entire production checkout")
    assert ticket["overrides"] == []
    assert ticket["sla_minutes"] > 0


def test_validation_errors_are_flattened_per_field(client: TestClient) -> None:
    response = client.post("/api/tickets", json={"subject": "x", "body": "   ", "requester_email": "nope"})

    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["errors"]}
    assert {"subject", "body", "requester_email"} <= fields


def test_detail_and_missing_ticket(client: TestClient, ticket: dict) -> None:
    detail = client.get(f"/api/tickets/{ticket['id']}").json()
    assert detail["reference"] == ticket["reference"]
    assert client.get("/api/tickets/999999").status_code == 404


def test_list_filters_and_search(client: TestClient, ticket: dict) -> None:
    found = client.get("/api/tickets", params={"search": ticket["reference"]}).json()
    assert [item["id"] for item in found["items"]] == [ticket["id"]]

    open_items = client.get("/api/tickets", params={"status": "Open", "page_size": 200}).json()["items"]
    assert open_items and all(item["status"] == "Open" for item in open_items)


def test_severity_sort_orders_by_urgency_rank(client: TestClient, ticket: dict) -> None:
    items = client.get("/api/tickets", params={"sort": "severity", "page_size": 200}).json()["items"]
    ranks = [urgency_rank(item["urgency"]) for item in items]
    assert ranks == sorted(ranks)


def test_resolving_stamps_and_reopening_clears_resolved_at(client: TestClient, ticket: dict) -> None:
    resolved = client.patch(f"/api/tickets/{ticket['id']}", json={"status": "Resolved"}).json()
    assert resolved["resolved_at"] is not None

    reopened = client.patch(f"/api/tickets/{ticket['id']}", json={"status": "In Progress"}).json()
    assert reopened["status"] == "In Progress"
    assert reopened["resolved_at"] is None


def test_override_is_logged_and_keeps_the_original_prediction(client: TestClient, ticket: dict) -> None:
    corrected = next(urgency for urgency in URGENCIES if urgency != ticket["urgency"])

    updated = client.patch(f"/api/tickets/{ticket['id']}", json={"urgency": corrected}).json()

    assert updated["urgency"] == corrected
    assert updated["ai_urgency"] == ticket["ai_urgency"]
    assert updated["was_overridden"] is True
    [override] = updated["overrides"]
    assert (override["field"], override["from_value"], override["to_value"]) == (
        "urgency",
        ticket["urgency"],
        corrected,
    )
    assert override["model_confidence"] == ticket["ai_urgency_confidence"]


def test_bad_patches_are_rejected(client: TestClient, ticket: dict) -> None:
    assert client.patch(f"/api/tickets/{ticket['id']}", json={}).status_code == 400
    assert client.patch(f"/api/tickets/{ticket['id']}", json={"category": "Gardening"}).status_code == 422
    assert client.patch("/api/tickets/999999", json={"status": "Resolved"}).status_code == 404


def test_delete_removes_the_ticket(client: TestClient, ticket: dict) -> None:
    assert client.delete(f"/api/tickets/{ticket['id']}").status_code == 204
    assert client.get(f"/api/tickets/{ticket['id']}").status_code == 404


def test_analytics_summary_is_internally_consistent(client: TestClient, ticket: dict) -> None:
    summary = client.get("/api/analytics/summary", params={"days": 7}).json()
    total = summary["total_tickets"]

    assert sum(bucket["count"] for bucket in summary["by_status"]) == total
    assert sum(bucket["count"] for bucket in summary["by_category"]) == total
    assert [bucket["label"] for bucket in summary["by_status"]] == STATUSES
    assert len(summary["volume_over_time"]) == 7
    assert 0 <= summary["overrides"]["override_rate"] <= 1


def test_model_performance_endpoint(client: TestClient) -> None:
    body = client.get("/api/analytics/model").json()
    assert body["dataset"]["test"] > 0
    assert 0 < body["urgency"]["accuracy"] <= 1


def test_websocket_pushes_serialisable_ticket_events(client: TestClient) -> None:
    with client.websocket_connect("/ws/tickets") as socket:
        assert socket.receive_json()["type"] == "ready"

        created = client.post("/api/tickets", json=OUTAGE).json()
        event = socket.receive_json()
        assert event["type"] == "ticket.created"
        assert event["data"]["id"] == created["id"]
        # Regression: datetimes in the payload once made every send fail
        # silently, dropping all clients. They must arrive as ISO strings.
        datetime.fromisoformat(event["data"]["created_at"])

        corrected = next(urgency for urgency in URGENCIES if urgency != created["urgency"])
        client.patch(f"/api/tickets/{created['id']}", json={"urgency": corrected})
        event = socket.receive_json()
        assert event["type"] == "ticket.overridden"
        assert event["data"]["urgency"] == corrected

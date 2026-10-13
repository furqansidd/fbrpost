import pytest
from fastapi.testclient import TestClient
from src.dashboard.app import app

client = TestClient(app)

def test_dashboard_index_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "FBR IRIS" in response.text
    assert "Draft" in response.text

def test_api_parse_excel_route():
    excel_path = "Mohammad Azhar - Plastic (149).xls"
    with open(excel_path, "rb") as f:
        response = client.post("/api/parse-excel", files={"file": (excel_path, f, "application/vnd.ms-excel")})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["wealth"]["reconciled"] is True
    assert data["data"]["income"]["3029"] == 56254810.0

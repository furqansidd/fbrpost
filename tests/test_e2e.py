import os
import pytest
from src.parser import parse_and_validate_tax_data
from src.captcha_solver import sanitize_captcha_response
from src.dashboard.app import app
from fastapi.testclient import TestClient

def test_full_pipeline_verification():
    # 1. Verify Excel file exists and parses cleanly
    excel_file = "Mohammad Azhar - Plastic (149).xls"
    assert os.path.exists(excel_file)
    data = parse_and_validate_tax_data(excel_file, tax_year=2026)
    
    # 2. Strict tax reconciliation check
    assert data["wealth"]["reconciled"] is True
    assert data["wealth"]["difference"] == 0.0

    # 3. Verify OpenRouter API key is present in environment
    from dotenv import load_dotenv
    load_dotenv()
    assert os.getenv("OPENROUTER_API_KEY") is not None
    assert os.getenv("OPENROUTER_API_KEY").startswith("sk-or-v1-")

    # 4. Verify dashboard API endpoint parses uploaded workbook accurately
    client = TestClient(app)
    with open(excel_file, "rb") as f:
        res = client.post("/api/parse-excel", files={"file": (excel_file, f, "application/vnd.ms-excel")})
    assert res.status_code == 200
    res_data = res.json()["data"]
    assert res_data["income"]["3029"] == 56254810.0
    assert res_data["wealth"]["reconciled"] is True

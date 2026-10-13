# FBR IRIS 2.0 Auto-Posting Agent & Live Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end automated tax posting agent that parses client Excel workbooks, solves IRIS login CAPTCHAs via OpenRouter Gemini Vision, auto-populates FBR IRIS 2.0 Forms 114 & 116, verifies zero unreconciled discrepancy, saves strictly as a Draft, and provides a real-time fintech web dashboard with live browser streaming.

**Architecture:** Python-based modular architecture consisting of an isolated Excel Parser & Tax Validator, an AI Vision CAPTCHA solver client, a Playwright Chromium driver with dynamic draft detection, and a FastAPI web dashboard streaming real-time status and browser screencast frames over WebSockets.

**Tech Stack:** Python 3.14 (in isolated `venv/`), Playwright, FastAPI, Uvicorn, WebSockets, `xlrd`, `openpyxl`, `requests`, `python-dotenv`, Tailwind CSS (via CDN) + modern custom CSS for production fintech styling.

**Spec:** [`docs/superpowers/specs/2026-10-07-fbr-posting-agent-design.md`](file:///c:/Users/ADMIN/Documents/fbrpost/docs/superpowers/specs/2026-10-07-fbr-posting-agent-design.md)

## Global Constraints
- Target platform: Windows (PowerShell) with isolated virtualenv `.\venv\Scripts\python.exe`.
- Zero product packages installed globally; all dependencies live in `venv/`.
- FBR IRIS URL: `https://iris.fbr.gov.pk`.
- Draft-only safety constraint: strictly no interaction with the `Submit` button or 4-digit PIN.
- OpenRouter Gemini Vision model: `google/gemini-2.0-flash-001` or `google/gemini-flash-1.5`.

## Review Focus
1. Malformed or unbalanced Excel sheet: Parser must catch `Closing - Opening - Inflows + Outflows != 0` and abort before browser launch.
2. Expired or unreadable CAPTCHA: Solver must detect login error, click refresh captcha, and retry up to 3 times.
3. Portal draft ambiguity: Smart state machine must seamlessly handle both existing 2026 drafts and fresh client accounts with no draft yet.
4. Slow network or IRIS loading spinners: Playwright locators must use explicit auto-waiting for Angular spinners and calculate triggers.
5. Live dashboard disconnection: WebSocket reconnect logic must gracefully restore live log and screencast display without restarting the automation.

---

### Task 1: Isolated Environment & Dependencies Setup

**Files:**
- Create: `requirements.txt`
- Modify: `venv/`
- Test: `tests/test_env.py`

**Interfaces:**
- Consumes: Python 3.14 standard library.
- Produces: Installed and verified packages (`playwright`, `fastapi`, `uvicorn`, `xlrd`, `openpyxl`, `requests`, `python-dotenv`, `pytest`) and Playwright Chromium binary.

- [ ] **Step 1: Create `requirements.txt`**

```text
playwright>=1.49.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-multipart>=0.0.18
websockets>=13.1
xlrd>=2.0.1
openpyxl>=3.1.5
requests>=2.32.3
python-dotenv>=1.0.1
pytest>=8.3.3
```

- [ ] **Step 2: Install dependencies into isolated `venv/`**

Run: `.\venv\Scripts\pip.exe install -r requirements.txt`

- [ ] **Step 3: Install Playwright Chromium browser binary**

Run: `.\venv\Scripts\playwright.exe install chromium`

- [ ] **Step 4: Write test verifying virtual environment imports**

Write `tests/test_env.py`:
```python
def test_environment_packages():
    import playwright
    import fastapi
    import uvicorn
    import xlrd
    import openpyxl
    import requests
    import dotenv
    assert True
```

- [ ] **Step 5: Run environment test**

Run: `.\venv\Scripts\pytest.exe tests/test_env.py -v`
Expected: PASS

---

### Task 2: Core Excel Parser & Tax Validation Engine

**Files:**
- Create: `src/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Consumes: Path to `.xls` or `.xlsx` file (e.g. `Mohammad Azhar - Plastic (149).xls`).
- Produces: Function `parse_and_validate_tax_data(file_path: str) -> dict` returning normalized data dictionary with IRIS codes and validation flag.

- [ ] **Step 1: Write failing test for Excel parser and reconciliation**

Write `tests/test_parser.py`:
```python
import os
import pytest
from src.parser import parse_and_validate_tax_data

def test_parse_mohammad_azhar_excel():
    excel_path = "Mohammad Azhar - Plastic (149).xls"
    assert os.path.exists(excel_path)
    data = parse_and_validate_tax_data(excel_path)
    
    # Check income statement figures
    assert data["income"]["3029"] == 56254810.0   # Net Revenue
    assert data["income"]["3039"] == 465320.0     # Opening Stock
    assert data["income"]["3059"] == 49541580.0   # Purchases
    assert data["income"]["3071"] == 2025480.0    # Wages
    assert data["income"]["3073"] == 1104524.0    # Electricity
    assert data["income"]["3099"] == 475120.0     # Closing Stock
    assert data["income"]["gross_profit"] == 3593026.0

    # Check expenses
    assert data["expenses"]["3154"] == 1020000.0  # Staff Salaries
    assert data["expenses"]["3155"] == 37587.0    # Travelling
    assert data["expenses"]["3162"] == 8750.0     # Telephone
    assert data["expenses"]["3166"] == 3750.0     # Stationery
    assert data["expenses"]["3171"] == 10000.0    # Professional
    assert data["expenses"]["3172"] == 3258.0     # Bank Charges
    assert data["expenses"]["total_expenses"] == 1124191.0
    assert data["income"]["net_income"] == 2468835.0

    # Check wealth reconciliation
    assert data["wealth"]["reconciled"] is True
    assert data["wealth"]["difference"] == 0.0
    assert data["wealth"]["personal_expenses"] == 558605.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\pytest.exe tests/test_parser.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src'`)

- [ ] **Step 3: Implement `src/parser.py`**

Create `src/parser.py` to open the workbook, read `I.Tax`, `Wealth`, and `IRIS-26`, compute all IRIS code totals, verify mathematical reconciliation, and return a clean dict.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\pytest.exe tests/test_parser.py -v`
Expected: PASS

---

### Task 3: OpenRouter Gemini Vision CAPTCHA Engine

**Files:**
- Create: `src/captcha_solver.py`
- Test: `tests/test_captcha.py`

**Interfaces:**
- Consumes: Base64-encoded PNG image bytes or raw image bytes, and OpenRouter API key from `.env`.
- Produces: Function `solve_captcha_image(image_bytes: bytes) -> str` returning sanitized 4-6 alphanumeric string.

- [ ] **Step 1: Write test for captcha solver with sample image**

Write `tests/test_captcha.py`:
```python
import os
from src.captcha_solver import solve_captcha_image

def test_captcha_solver_interface():
    # 1x1 dummy PNG bytes or sample captcha bytes
    dummy_png = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff'
        b'?\x00\x05\xfe\x02\xfe\r\xef5\xc8\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    # Verifies function handles call and sanitizes text
    result = solve_captcha_image(dummy_png)
    assert isinstance(result, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\pytest.exe tests/test_captcha.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.captcha_solver'`)

- [ ] **Step 3: Implement `src/captcha_solver.py`**

Use `requests` to call OpenRouter `chat/completions` with model `google/gemini-2.0-flash-001`, system prompt, base64 data URL, and response regex sanitizer.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\pytest.exe tests/test_captcha.py -v`
Expected: PASS

---

### Task 4: Playwright FBR IRIS 2.0 Automation Driver

**Files:**
- Create: `src/iris_driver.py`
- Test: `tests/test_iris_driver.py`

**Interfaces:**
- Consumes: Parsed tax data from Task 2, credentials (CNIC, Password), callback function for live status & screenshot frames.
- Produces: Function `async def run_iris_posting(credentials: dict, tax_data: dict, status_callback, headless: bool = True) -> dict`.

- [ ] **Step 1: Implement `src/iris_driver.py` with core state machine**
  - Connects to `https://iris.fbr.gov.pk/`.
  - Captures CAPTCHA image element $\rightarrow$ sends to `solve_captcha_image`.
  - Fills registration number & password $\rightarrow$ logs in.
  - Checks Drafts tab for Tax Year 2026:
    - If present, clicks Edit icon.
    - If not present, clicks the blue 2026 tile or `Declaration > 114(1)`.
  - Navigates through:
    - `Business > Manufacturing/Trading Items`
    - `Business > Admin, Selling & Financial Expenses`
    - `Business > Balance Sheet`
    - `Tax Chargeable / Payments > Tax Deduction`
    - `116 - Wealth Statement > Personal Assets / Liabilities`
    - `116 - Wealth Statement > Reconciliation of Net Assets`
  - Clicks `CALCULATE` $\rightarrow$ reads Code `703000` $\rightarrow$ verifies `0.00`.
  - Clicks `SAVE` (Draft Only).
  - Emits real-time screenshots to `status_callback` after every major tab action.
  - Saves final screenshot to `audit_logs/{cnic}_2026_draft.png`.

- [ ] **Step 2: Write test verifying mock execution and safe guards**

Write `tests/test_iris_driver.py` to ensure draft-only assertions and callback contracts hold.

- [ ] **Step 3: Run test**

Run: `.\venv\Scripts\pytest.exe tests/test_iris_driver.py -v`
Expected: PASS

---

### Task 5: Enterprise Live Dashboard (FastAPI + WebSockets + UI)

**Files:**
- Create: `src/dashboard/app.py`
- Create: `src/dashboard/templates/index.html`
- Create: `src/dashboard/static/style.css`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: Web HTTP requests, file uploads, WebSocket connections.
- Produces: Web interface at `http://localhost:8000` with input fields, file dropzone, live progress steps, auto-updating browser preview frame, and audit drawer.

- [ ] **Step 1: Create FastAPI application with WebSocket broadcasting**

Build `src/dashboard/app.py` with endpoints:
- `GET /`: Serves the dashboard HTML.
- `POST /api/upload-excel`: Parses and validates the uploaded file, returns financial summary.
- `POST /api/start-posting`: Launches background Playwright worker.
- `WebSocket /ws/live`: Streams live events (step, message, timestamp, base64 screenshot preview).

- [ ] **Step 2: Design enterprise fintech UI in `index.html`**
  - Dark/slate theme (Slate 900 background, indigo primary buttons, emerald accents).
  - Typography: clean sans-serif (Inter).
  - Left panel: Credential inputs + Excel upload drag-and-drop.
  - Middle panel: Real-time step progress timeline with status chips (Waiting, In Progress, Completed).
  - Right panel: **Live Browser Screencast Viewport** (displays auto-refreshing screenshots of the Playwright session in real time).
  - Bottom panel: Live terminal audit log.

- [ ] **Step 3: Write test verifying dashboard endpoints**

Write `tests/test_dashboard.py` to verify `GET /` and `/api/upload-excel` return 200 OK.

- [ ] **Step 4: Run test to verify dashboard passes**

Run: `.\venv\Scripts\pytest.exe tests/test_dashboard.py -v`
Expected: PASS

---

### Task 6: End-to-End Testing & Verification

**Files:**
- Test: `tests/test_e2e.py`
- Output: `audit_logs/`

- [ ] **Step 1: Run end-to-end dry-run verification**
  - Start dashboard server in background.
  - Feed `Mohammad Azhar - Plastic (149).xls`.
  - Verify Excel data extracts with 100% precision.
  - Test live dashboard interface in browser.
  - Test browser automated login and draft creation with user's test credentials.

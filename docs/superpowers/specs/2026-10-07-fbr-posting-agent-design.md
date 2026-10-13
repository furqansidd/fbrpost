# FBR IRIS 2.0 Auto-Posting Agent & Live Dashboard
**Design Specification**  
**Date:** 2026-10-07  
**Status:** Under Review (Architectural Phase)

---

## 1. Executive Summary & Purpose

The **FBR IRIS Auto-Posting Agent** is an enterprise-grade automated tax filing assistant designed for tax consultants and accounting firms in Pakistan. It takes client tax data from structured Excel workbooks (`.xls` / `.xlsx`), mathematically validates reconciliation, logs into FBR IRIS 2.0 (`iris.fbr.gov.pk`) using client credentials, solves the login CAPTCHA with AI Vision (Gemini Flash via OpenRouter), navigates the complex form hierarchy (Income Return 114 and Wealth Statement 116), injects the figures into their matching IRIS code fields, triggers calculations, verifies zero unreconciled discrepancy, and saves the return strictly as a **Draft**.

The system features a **Production-Grade Live Dashboard** offering real-time WebSocket event streaming, progress metrics, and an auto-refreshing live visual feed of the browser's view.

---

## 2. System Architecture & Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MODULAR SYSTEM ARCHITECTURE                           │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │  Tax Consultant  │
  └────────┬─────────┘
           │ 1. Uploads Excel, enters CNIC & Password
           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  Enterprise Web Dashboard (FastAPI + WebSocket)          │
  │  • Sleek Fintech UI / Clean typography (Inter)          │
  │  • Live Step-by-Step progress tracker                   │
  │  • Auto-refreshing visual screencast feed of browser    │
  │  • Audit log viewer with download links                 │
  └────────┬────────────────────────────────────────────────┘
           │ 2. Dispatches task
           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  Core Engine: Excel Parser & Tax Validator              │
  │  • Reads sheets: 'I.Tax', 'Wealth', 'IRIS-26'           │
  │  • Hard Gate: Closing - Opening - Inflows + Outflows == 0│
  │  • Normalizes figures into canonical IRIS Code Map      │
  └────────┬────────────────────────────────────────────────┘
           │ 3. Passes validated payload
           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  OpenRouter Gemini Vision Captcha Engine                │
  │  • Crops IRIS login captcha image                       │
  │  • Calls OpenRouter API (Gemini 2.0 Flash)              │
  │  • Returns verified 4-6 alphanumeric string             │
  └────────┬────────────────────────────────────────────────┘
           │ 4. Solves login & drives portal
           ▼
  ┌─────────────────────────────────────────────────────────┐
  │  Playwright Browser Automation Driver (Chromium)        │
  │  • Smart Draft Detection (Existing Draft vs New Task)   │
  │  • Form 114: Manufacturing, Expenses, Deductions, BS    │
  │  • Form 116: Wealth Assets (Bank, Cash, Property)       │
  │  • Reconciliation & Zero-Difference Verification        │
  │  • Triggers 'CALCULATE' & Clicks 'SAVE' (Draft Only)    │
  │  • Emits live screencast frames to WebSocket            │
  └─────────────────────────────────────────────────────────┘
```

---

## 3. Data Extraction & Mapping Engine

### 3.1 Input Sources
1. **`I.Tax` Sheet:** Manufacturing/Trading sales, opening/closing stock, purchases, wages, electricity, operating expenses (salaries, telephone, travelling, stationery, professional charges, bank charges, misc).
2. **`Wealth` Sheet:** Immovable property values, business capital (machinery, stock, cash), bank account balances, cash in hand, loans/liabilities, personal/household expenses.
3. **`IRIS-26` Sheet:** CPR receipts and tax withholding line items (Section 235 commercial electricity, Section 236 internet/mobile, Section 236K property transfer).

### 3.2 Pre-Flight Validation (Hard Stop Gate)
Before any browser instance is spawned:
$$\text{Reconciliation Diff} = \text{Closing Wealth} - \text{Opening Wealth} - \text{Inflows} + \text{Household Expenses}$$
* If $\text{Diff} \neq 0$: The parser halts with a fatal validation error and displays the exact imbalance to the user.
* If $\text{Diff} == 0$: The canonical JSON payload is generated.

### 3.3 IRIS Code Mapping Matrix

| Form / Tab | IRIS Code | Description | Excel Source |
| :--- | :--- | :--- | :--- |
| **114 > Manufacturing** | `3029` | Net Revenue / Gross Sales | `I.Tax`!Sales |
| **114 > Manufacturing** | `3039` | Opening Stock | `I.Tax`!Opening stock |
| **114 > Manufacturing** | `3059` | Purchases | `I.Tax`!Purchases |
| **114 > Manufacturing** | `3071` | Salaries / Wages | `I.Tax`!Wages & Benefits |
| **114 > Manufacturing** | `3073` | Power / Electricity | `I.Tax`!Electricity |
| **114 > Manufacturing** | `3099` | Closing Stock | `I.Tax`!Closing Stock |
| **114 > Expenses** | `3154` | Salaries / Wages / Benefits | `I.Tax`!Staff Salaries |
| **114 > Expenses** | `3155` | Traveling / Conveyance | `I.Tax`!Travelling |
| **114 > Expenses** | `3162` | Communication | `I.Tax`!Telephone |
| **114 > Expenses** | `3166` | Stationery / Office Supplies | `I.Tax`!Stationery |
| **114 > Expenses** | `3171` | Professional Charges | `I.Tax`!Professional Charges |
| **114 > Expenses** | `3172` | Profit on Debt / Bank Charges | `I.Tax`!Bank Charges |
| **114 > Expenses** | `3180` | Other Indirect Expenses | `I.Tax`!Entertainment + Misc |
| **114 > Balance Sheet** | `3303` | Plant / Machinery / Equipment | `Wealth`!Machinery |
| **114 > Balance Sheet** | `3315` | Stocks / Stores / Spares | `Wealth`!Stock |
| **114 > Balance Sheet** | `3319` | Cash / Cash Equivalents | `Wealth`!Cash |
| **114 > Balance Sheet** | `3352` | Capital | `Wealth`!Total Capital |
| **114 > Tax Deductions** | `64140051` | Commercial Electricity u/s 235 | `I.Tax`!Fesco WHT |
| **114 > Tax Deductions** | `64150005` | Internet Bill u/s 236(1)(d) | `IRIS-26`!Nayatel total |
| **114 > Tax Deductions** | `64151101` | Property Transfer u/s 236K | `IRIS-26`!236K CPR |
| **116 > Assets** | `7002` | Immovable Property | `Wealth`!Properties (Plots/Houses) |
| **116 > Assets** | `7006` | Bank Balances (SCB, Meezan) | `Wealth`!Cash at Banks |
| **116 > Assets** | `7012` | Cash in hand (Non-Business) | `Wealth`!Cash in Hand |
| **116 > Liabilities** | `7021` | Loans / Borrowing | `Wealth`!Loan (Muhammad Sharif) |
| **116 > Reconciliation**| `7089` | Personal / Household Expenses| `Wealth`!House Hold Expenses |
| **116 > Reconciliation**| `703000` | Unreconciled Amount | **Must verify == 0.00** |

---

## 4. AI Multimodal CAPTCHA Engine (OpenRouter Gemini Vision)

1. **Extraction:** Playwright targets the captcha image locator (`img[src*='captcha']` or `#captchaImg`) and calls `.screenshot(type='png')`.
2. **Payload:** The raw image bytes are base64-encoded and transmitted via HTTPS POST to OpenRouter:
   * **Endpoint:** `https://openrouter.ai/api/v1/chat/completions`
   * **Model:** `google/gemini-2.0-flash-001` (or `google/gemini-flash-1.5`)
   * **System Prompt:** `"You are an OCR specialist. The image contains a 4 to 6 character alphanumeric CAPTCHA code. Respond with ONLY the exact characters in order. No explanations, no markdown, no spaces."`
3. **Resilience:**
   * If OpenRouter responds with whitespace or unexpected tokens, string sanitization trims and strips punctuation.
   * If FBR returns an `"Invalid Captcha"` error banner, the driver clicks the captcha refresh icon and retries up to 3 times before terminating.

---

## 5. Playwright FBR IRIS 2.0 Automation Driver

### 5.1 Smart Draft State Machine
The agent does not assume a draft is already waiting:
1. **Navigate:** Lands on `https://iris.fbr.gov.pk/dashboard`.
2. **Inspect Draft Tab:**
   * Clicks the **Draft (Unsubmitted Documents)** tab.
   * Checks for existing row: `114(1) (Return of Income filed voluntarily for complete year)` for `Tax Year: 2026`.
   * **Case A (Draft Exists):** Clicks the Edit (pencil) icon.
   * **Case B (Fresh Client / No Draft):** Clicks the blue dashboard card `"Submit your Income Tax Return for tax year 2026"` (or top menu: `Declaration` $\rightarrow$ `114(1)` $\rightarrow$ selects period `2026`).
3. **Import Assets Check:** If opening a fresh return, detects the `"IMPORT PREVIOUS RETURN"` button to roll over existing fixed assets.

### 5.2 Form Population Flow
* **Form 114 (Income):**
  1. Opens `Business` $\rightarrow$ `Manufacturing/Trading Items`. Enters `3029`, `3039`, `3059`, `3071`, `3073`, `3099`.
  2. Opens `Business` $\rightarrow$ `Admin, Selling & Financial Expenses`. Enters `3154`, `3155`, `3162`, `3166`, `3171`, `3172`, `3180`.
  3. Opens `Business` $\rightarrow$ `Balance Sheet`. Enters `3303`, `3315`, `3319`, `3352`.
  4. Opens `Tax Chargeable / Payments` $\rightarrow$ `Tax Deduction`. Injects WHT line items with corresponding tax deducted amounts.
* **Form 116 (Wealth Statement):**
  1. Opens `116 - Wealth Statement` $\rightarrow$ `Personal Assets / Liabilities`.
  2. Updates bank balances (`7006`) and cash in hand (`7012`).
  3. If a new property exists in 2026 (e.g. `1/2 Share House Chak 204 RB` at `4,675,000`), clicks `+` to add a new asset entry.
  4. Opens `Reconciliation of Net Assets` and enters Household Expenses (`7089`).
* **Calculation & Verification Gate:**
  1. Clicks the green **`CALCULATE`** button.
  2. Reads the value in Code `703000` (Unreconciled Amount).
  3. Asserts value equals `0.00`. If any discrepancy is reported, a warning alert is triggered.
* **Save as Draft:**
  1. Clicks the top-header **`Save`** button.
  2. Waits for the green toast notification (`"Saved successfully"`).
  3. Captures a full-page verification screenshot saved to `audit_logs/{CNIC}_{tax_year}_draft.png`.
  4. Logs out cleanly.

---

## 6. Enterprise UI/UX Live Dashboard

### 6.1 Design Philosophy & Aesthetics
* **Theme:** Professional Dark / Slate Fintech aesthetic (neutral slate `#0f172a`, deep indigo accents `#6366f1`, emerald success `#10b981`).
* **Typography:** Clean sans-serif (`Inter`, `ui-sans-serif`).
* **Components:**
  * **Header:** Status indicator badge (Ready / Running / Complete), current system clock, branding.
  * **Input Card:** CNIC, Password, Tax Year dropdown, file dropzone with instant parsing feedback.
  * **Execution Timeline:** Step-by-step progress cards showing real-time checkmarks as each tab is filled.
  * **Live Screen Feed:** Real-time visual panel displaying the active browser's view updated via WebSocket or fast HTTP stream.
  * **Audit Log Drawer:** Collapsible terminal-style log output showing detailed timestamps and exact values posted.

---

## 7. Security, Safety, & Legal Compliance

1. **Draft-Only Guarantee:** The codebase explicitly omits any selector or interaction with the `Submit` button or the 4-digit PIN modal. The agent is physically incapable of making a final submission.
2. **Credential Protection:** Credentials and API keys are read from environment variables (`.env`) or entered directly into the dashboard session in memory; credentials are never written to disk or logs.
3. **Audit Trail:** Every completed run outputs a high-resolution screenshot stored locally in `audit_logs/` for consultant verification before manual PIN authorization.

---

## 8. Verification & Test Plan

1. **Unit Test (Parser):** Run `tests/test_parser.py` against `Mohammad Azhar - Plastic (149).xls`. Verify all extracted figures match `Muhammad Azhar Return Working 2026.pdf` and difference is strictly `0.00`.
2. **Unit Test (Captcha):** Send a test IRIS captcha image to the OpenRouter Gemini Vision solver and verify 100% correct text extraction.
3. **Integration Test (Portal Login & Navigation):** Launch Playwright with test credentials, solve captcha, navigate to the 2026 draft, and verify field selectors.
4. **End-to-End Test (Draft Save):** Populate all fields, trigger calculate, verify `703000 == 0`, and click Save. Check that the draft is persisted in IRIS.

# FBR IRIS 2.0 | Auto-Posting Suite

An enterprise-grade automation engine designed for Pakistani tax consultants, practitioners, and accounting firms to automatically parse client tax computation workbooks and post them directly into the **FBR IRIS 2.0** portal as **Drafts**.

---

## Key Features

* **Draft Mode Safety Lock:** Operates strictly in draft mode. The system never submits returns or prompts for 4-digit PIN codes.
* **Dual-Layer Precision DOM Injector:** Solves Angular form reactivity issues by dispatching native DOM events (`input`, `change`, `blur`) alongside synchronized keyboard entry.
* **Multimodal CAPTCHA OCR:** Solves IRIS 2.0 visual verification challenges via Gemini Vision.
* **Offline Excel Parser:** Parses multi-year client tax workbooks (.xls, .xlsx) locally with zero external API dependencies.
* **Pre-Flight Wealth Reconciliation:** Automatically computes Net Wealth, Wealth Increase, and Income Reconciliation before posting.
* **Real-Time Web Dashboard:** Minimal, executive-grade UI with live WebSocket audit streaming and interactive session stop/cancel controls.

---

## Architecture & Code Structure

```
fbrpost/
├── src/
│   ├── captcha_solver.py     # Gemini Vision CAPTCHA solver
│   ├── iris_driver.py        # Playwright browser automation & form filler
│   ├── parser.py             # Excel parser & wealth reconciliation validator
│   └── dashboard/
│       ├── app.py            # FastAPI server & WebSocket manager
│       ├── templates/
│       │   └── index.html    # Executive Light fintech dashboard
│       └── static/
│           └── style.css     # Clean design system stylesheet
├── tests/                    # Comprehensive unit tests
├── requirements.txt          # Python dependencies
├── run.py                    # Server launcher
├── start_agent.bat           # Quick launcher script
└── .env.example              # Environment variables template
```

---

## Installation & Setup

### 1. Prerequisites
* Python 3.10+ (tested on Python 3.12 / 3.14)
* Google Chrome or Chromium browser

### 2. Setup Virtual Environment
```bash
# Clone the repository
git clone https://github.com/furqansidd/fbrpost.git
cd fbrpost

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure Environment
Copy the `.env.example` file to `.env` and insert your OpenRouter API key:
```bash
cp .env.example .env
```
Edit `.env`:
```env
OPENROUTER_API_KEY=your_key_here
```

### 5. Run the Suite
```bash
python run.py
```
Open **`http://localhost:8000`** in your browser.

---

## Safety & Security Disclaimer

This software is strictly an assistive tool for tax practitioners. It does **not** file final returns. All returns remain in **Drafts** for manual consultant review and verification before submission.

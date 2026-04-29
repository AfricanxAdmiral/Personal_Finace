# Finance Monitor

A personal finance dashboard built with Streamlit. Track your stock portfolio and bank accounts in one place, with all values converted to TWD for a unified view.

![CI](https://github.com/AfricanxAdmiral/Personal_Finace/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/AfricanxAdmiral/Personal_Finace/branch/main/graph/badge.svg)](https://codecov.io/gh/AfricanxAdmiral/Personal_Finace)

---

## Features

### 📋 Overview
- Total net worth in TWD with live USD/TWD and JPY/TWD exchange rates
- Three donut charts: overall allocation (stocks vs banking), breakdown by stock ticker, breakdown by bank account
- Summary tables with comma-formatted values

### 📈 Stocks
- **Portfolio** — All positions with cost basis, current value, P&L, return %, annualised return, days held; colour-coded green/red
- **Add Position** — Look up any ticker (stocks, ETFs, crypto via `BTC-USD`) and record a buy
- **Manage** — Edit any position, record a sale, or remove a position
- **Charts** — Interactive price history per position (with buy/sell markers) and total portfolio value over time
- **Performance** — Sharpe ratio, Sortino ratio, max drawdown chart, volatility, beta vs SPY, Calmar ratio, win rate, and per-position risk table
- **Price Lookup** — Live price and 1-year chart for any ticker

### 🏦 Banking
- **Accounts** — Multiple bank accounts (USD / TWD / JPY), current balances
- **Add Account** — Checking, Savings, Money Market, CD, or Other
- **Transactions** — Record deposits and withdrawals; colour-coded history table
- **Manage** — Edit account details, remove accounts (cascades to transactions), remove individual transactions

---

## Tech Stack

| Layer | Library |
|---|---|
| UI | [Streamlit](https://streamlit.io) |
| Charts | [Plotly](https://plotly.com/python/) |
| Market data | [yfinance](https://github.com/ranaroussi/yfinance) |
| Price cache | SQLite (via `sqlite3`) |
| Data storage | JSON files |
| Tests | pytest + pytest-cov |

---

## Getting Started

### Prerequisites
- Python 3.9+

### Installation

```bash
# Clone the repo
git clone https://github.com/<your-username>/Claude-Finance.git
cd Claude-Finance

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Running Tests

```bash
pytest
```

This runs all tests and generates a coverage report:

- **Terminal** — line-by-line missing coverage printed after the test summary
- **`htmlcov/`** — open `htmlcov/index.html` in a browser for a full interactive report
- **`coverage.xml`** — machine-readable XML for CI tools

Run a single test file:

```bash
pytest tests/test_portfolio.py -v
```

Run a specific test:

```bash
pytest tests/test_metrics.py::test_sharpe_higher_return_higher_ratio -v
```

---

## Project Structure

```
.
├── app.py                  # Streamlit app — all pages and routing
├── main.py                 # Legacy CLI entry point
├── requirements.txt
├── pyproject.toml          # pytest + coverage configuration
├── finace/
│   ├── bank.py             # Bank account & transaction CRUD
│   ├── cache.py            # SQLite price/info/history cache
│   ├── calculator.py       # CAGR, P&L, return metrics
│   ├── charts.py           # Plotly figure builders
│   ├── metrics.py          # Risk metrics (Sharpe, Sortino, Beta, …)
│   ├── portfolio.py        # Stock position CRUD (JSON-backed)
│   └── stock.py            # yfinance wrapper with incremental caching
├── tests/
│   ├── conftest.py         # Shared fixtures (tmp files, mock data)
│   ├── test_bank.py
│   ├── test_cache.py
│   ├── test_calculator.py
│   ├── test_charts.py
│   ├── test_metrics.py
│   ├── test_portfolio.py
│   └── test_stock.py
└── .github/
    └── workflows/
        └── ci.yml          # GitHub Actions — test + coverage on every push
```

### Data files (git-ignored)

| File | Contents |
|---|---|
| `portfolio.json` | Stock positions |
| `bank.json` | Bank accounts and transactions |
| `price_cache.db` | SQLite cache for prices, stock info, and price history |

---

## CI / CD

GitHub Actions runs on every push and pull request:

1. Installs dependencies from `requirements.txt`
2. Runs the full test suite with `pytest`
3. Enforces a minimum **80% coverage** threshold
4. Uploads the HTML and XML coverage reports as downloadable **Artifacts** (retained 30 days)

See the **Actions** tab for run history, or download the latest coverage report from the most recent run's Artifacts section.

---

## Caching Strategy

Stock price history is fetched **incrementally** — once a date range is stored in SQLite it is never re-fetched. Only the gap between the last cached date and today triggers a network call. This keeps yfinance API usage minimal across sessions.

Current prices and stock info have TTLs of 5 minutes and 24 hours respectively. An additional Streamlit-level `@st.cache_data` layer deduplicates calls within a single browser session.

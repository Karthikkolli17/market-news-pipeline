import os
import json
import logging
import sys
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
import argparse
from datetime import date, datetime, timedelta, timezone

load_dotenv()
API_KEY = os.environ["FINNHUB_API_KEY"]
URL = "https://finnhub.io/api/v1/company-news"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "JPM"]

TIMEOUT_SECONDS = 10
MAX_RETRIES = 4
RETRY_STATUS = {429, 500, 502, 503, 504}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("ingest")

def fetch_news(ticker: str, date: str) -> list[dict]:

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(
                URL,
                params={"symbol": ticker, "from": date, "to": date},
                headers={"X-Finnhub-Token": API_KEY},
                timeout=TIMEOUT_SECONDS,
            )
        
            if response.status_code not in RETRY_STATUS:
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError(f"Expected a list, got: {str(data)[:200]}")
                return data
            reason = f"HTTP {response.status_code}"
            retry_after = response.headers.get("Retry-After")
        except (requests.Timeout, requests.ConnectionError) as e:
            reason = type(e).__name__
            retry_after = None

        if attempt == MAX_RETRIES:
            raise RuntimeError(f"{ticker}: gave up after {MAX_RETRIES} retries ({reason})")
        wait = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt+1)
        log.warning("%s: %s, retry %d/%d in %ds", ticker, reason, attempt + 1, MAX_RETRIES, wait)
        time.sleep(wait)

def save_news(articles: list[dict], ticker: str, date: str) -> Path:

    out_dir = RAW_DIR / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ticker}.json"
    tmp_path = out_dir / f"{ticker}.json.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    tmp_path.replace(out_path)
    return out_path
    
def parse_args() -> str:

    parser = argparse.ArgumentParser(description="Fetch Finnhub company news for one date.")
    parser.add_argument("--date", type=date.fromisoformat, help="YYYY-MM-DD (default: yesterday UTC)")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).date()
    run_date = args.date or today - timedelta(days=1)
    if run_date >= today:
        parser.error(f"--date must be before today ({today}): the day isn't over yet")
    return run_date.isoformat()

if __name__ == "__main__":
    run_date = parse_args()
    log.info("Ingest started for %s", run_date)
    failed = []

    for ticker in TICKERS:
        path = RAW_DIR / run_date / f"{ticker}.json"
        if path.exists():
            log.info("%s: already saved, skipping", ticker)
            continue
        try:
            articles = fetch_news(ticker, run_date)
            path = save_news(articles, ticker, run_date)
            log.info("%s: saved %d articles to %s", ticker, len(articles), path)
        except Exception as e:
            log.error("%s: failed: %s", ticker, e)
            failed.append(ticker)

    if failed:
        log.error("Ingest finished with failures: %s", failed)
        sys.exit(1)
    log.info("Ingest finished OK")
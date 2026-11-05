import logging
from pathlib import Path
import json

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "warehouse" / "news.duckdb"
RAW_DIR = ROOT/ "data" / "raw"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load_raw")

CREATE_RAW_NEWS = """
CREATE TABLE IF NOT EXISTS raw_news (
    article_id          BIGINT      NOT NULL,
    ticker              VARCHAR     NOT NULL,
    published_epoch     BIGINT,
    headline            VARCHAR,
    summary             VARCHAR,
    source              VARCHAR,
    url                 VARCHAR,
    raw_json            JSON        NOT NULL,
    file_path           VARCHAR     NOT NULL,
    loaded_at           TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (article_id, ticker)
)
"""

INSERT_RAW_NEWS = """
INSERT INTO raw_news
    (article_id, ticker, published_epoch, headline, summary, source, url, raw_json, file_path)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT DO NOTHING
"""
def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(CREATE_RAW_NEWS)

def read_file(path: Path) -> list[tuple]:

    ticker = path.stem
    rel_path = str(path.relative_to(ROOT))
    with open(path, encoding="utf-8") as f:
        articles = json.load(f)
    return [
        (
            a["id"],
            ticker,
            a.get("datetime"),
            a.get("headline"),
            a.get("summary"),
            a.get("source"),
            a.get("url"),
            json.dumps(a, ensure_ascii=False),
            rel_path
        )
        for a in articles
    ]

if __name__ == "__main__":
    con = duckdb.connect(str(DB_PATH))
    create_tables(con)

    files = sorted(RAW_DIR.glob("*/*.json"))
    before = con.sql("SELECT count(*) FROM raw_news").fetchall()[0][0]
    total_rows = 0

    con.begin()
    try:
        for path in files:
            rows = read_file(path)
            con.executemany(INSERT_RAW_NEWS, rows)
            total_rows += len(rows)
        con.commit()
    except Exception:
        con.rollback()
        log.exception("Load failed, rolled back. raw_news is unchanged.")
        raise

    after = con.sql("SELECT count(*) FROM raw_news").fetchall()[0][0]
    inserted = after - before
    log.info("Read %d files, %d rows: inserted %d, skipped %d. raw_news now has %d rows.", len(files), total_rows, inserted, total_rows - inserted, after)
    con.close()

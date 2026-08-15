"""SQLite search snapshots and append-only price observations."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from dealfinder.models import RankedListing
from dealfinder.service import SearchRun

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    result_json TEXT
);
CREATE TABLE IF NOT EXISTS listings (
    listing_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    listing_id TEXT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES search_runs(id),
    listing_key TEXT NOT NULL REFERENCES listings(listing_key),
    rank INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    item_price TEXT NOT NULL,
    shipping_price TEXT NOT NULL,
    total_price TEXT NOT NULL,
    currency TEXT NOT NULL,
    availability INTEGER,
    score REAL NOT NULL,
    ranked_json TEXT NOT NULL,
    UNIQUE(run_id, listing_key)
);
CREATE INDEX IF NOT EXISTS observations_listing_time
ON observations(listing_key, observed_at);
"""


@dataclass(frozen=True)
class PriceObservation:
    observed_at: datetime
    total_price: Decimal
    availability: int | None
    score: float


def _listing_key(provider: str, listing_id: str | None, url: str) -> str:
    identity = listing_id or hashlib.sha256(url.encode()).hexdigest()
    return f"{provider}:{identity}"


class SQLiteRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(search_runs)")}
            if "result_json" not in columns:
                connection.execute("ALTER TABLE search_runs ADD COLUMN result_json TEXT")

    def save(self, ranked: list[RankedListing]) -> int:
        """Backward-compatible helper for callers that only have ranked listings."""

        return self.save_run(SearchRun(ranked=ranked, observed=ranked, provider_results={}))

    def save_run(self, run: SearchRun) -> int:
        observed_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO search_runs(started_at, result_json) VALUES (?, ?)",
                (observed_at, run.model_dump_json()),
            )
            run_id = int(cursor.lastrowid or 0)
            rank_by_key = {
                _listing_key(
                    result.listing.provider,
                    result.listing.listing_id,
                    str(result.listing.url),
                ): rank
                for rank, result in enumerate(run.ranked, start=1)
            }
            observed = run.observed or run.ranked
            unique_observed: dict[str, RankedListing] = {}
            for result in observed:
                listing = result.listing
                key = _listing_key(listing.provider, listing.listing_id, str(listing.url))
                unique_observed[key] = result
            for key, result in unique_observed.items():
                listing = result.listing
                rank = rank_by_key.get(key, 0)
                connection.execute(
                    """
                    INSERT INTO listings(
                        listing_key, provider, listing_id, url, title, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(listing_key) DO UPDATE SET
                        url=excluded.url, title=excluded.title, last_seen_at=excluded.last_seen_at
                    """,
                    (
                        key,
                        listing.provider,
                        listing.listing_id,
                        str(listing.url),
                        listing.title,
                        observed_at,
                        observed_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO observations(
                        run_id, listing_key, rank, observed_at, item_price, shipping_price,
                        total_price, currency, availability, score, ranked_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        key,
                        rank,
                        observed_at,
                        str(listing.item_price),
                        str(listing.shipping_price),
                        str(listing.total_price),
                        listing.currency,
                        listing.quantity_available,
                        result.score.total,
                        result.model_dump_json(),
                    ),
                )
            saved_run = run.model_copy(update={"run_id": run_id})
            connection.execute(
                "UPDATE search_runs SET result_json = ? WHERE id = ?",
                (saved_run.model_dump_json(), run_id),
            )
        return run_id

    def load_run(self, run_id: int | None = None) -> SearchRun:
        with self._connect() as connection:
            if run_id is None:
                row = connection.execute(
                    "SELECT id, result_json FROM search_runs ORDER BY id DESC LIMIT 1"
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT id, result_json FROM search_runs WHERE id = ?", (run_id,)
                ).fetchone()
        if row is None or not row["result_json"]:
            raise LookupError(f"search run {run_id or 'latest'} was not found")
        return SearchRun.model_validate_json(row["result_json"])

    def load_rank(self, rank: int, run_id: int | None = None) -> RankedListing:
        with self._connect() as connection:
            selected_run = run_id
            if selected_run is None:
                row = connection.execute("SELECT MAX(id) AS id FROM search_runs").fetchone()
                selected_run = int(row["id"]) if row and row["id"] is not None else 0
            row = connection.execute(
                "SELECT ranked_json FROM observations WHERE run_id = ? AND rank = ?",
                (selected_run, rank),
            ).fetchone()
        if row is None:
            raise LookupError(f"rank {rank} was not found in search run {selected_run}")
        return RankedListing.model_validate_json(row["ranked_json"])

    def price_history(self, provider: str, listing_id: str) -> list[PriceObservation]:
        key = _listing_key(provider, listing_id, "")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT observed_at, total_price, availability, score
                FROM observations WHERE listing_key = ? ORDER BY id
                """,
                (key,),
            ).fetchall()
        return [
            PriceObservation(
                observed_at=datetime.fromisoformat(row["observed_at"]),
                total_price=Decimal(row["total_price"]),
                availability=row["availability"],
                score=row["score"],
            )
            for row in rows
        ]

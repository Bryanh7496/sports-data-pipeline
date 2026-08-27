"""
Entry point: pull one season of NBA games from the balldontlie API and land
the raw response as JSON.

Where this fits in the bigger pipeline (see README for the full picture):

    [this script] -> storage/raw/*.json -> (Month 2: S3) -> Snowflake RAW
        -> dbt staging/marts -> dbt tests -> (Month 3: Airflow orchestrates
        all of it)

Today this writes to a local `storage/raw/` folder as a stand-in for S3,
which lets the ingestion logic (auth, pagination, retries, validation) get
built and tested before the AWS piece exists. Swapping the local write for
an S3 upload later should only touch `write_raw_json()` -- everything
upstream of it stays the same, which is the point of separating "fetch
the data" from "land the data" in the first place.

Usage:
    python -m ingestion.fetch_games --season 2024
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ingestion.client import BallDontLieAPIError, BallDontLieClient
from ingestion.config import ConfigError, Settings
from ingestion.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

REQUIRED_GAME_FIELDS = {"id", "date", "home_team", "visitor_team", "season"}


def validate_game(game: dict[str, Any]) -> bool:
    """
    Minimal schema check on each record before we consider it safe to land.

    This is intentionally simple (are the fields we depend on downstream
    present?) rather than a full schema validator -- the goal is to catch
    "the API changed shape under us" or "this record is garbage" before bad
    data reaches storage, not to replace the dbt tests that check the data
    more thoroughly once it's in the warehouse.
    """
    missing = REQUIRED_GAME_FIELDS - game.keys()
    if missing:
        logger.warning("Dropping record %s: missing fields %s", game.get("id", "?"), missing)
        return False
    return True


def write_raw_json(games: list[dict[str, Any]], season: int, raw_data_dir: Path) -> Path:
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = raw_data_dir / f"games_season{season}_{run_timestamp}.json"

    payload = {
        "extracted_at": run_timestamp,
        "season": season,
        "record_count": len(games),
        "data": games,
    }

    output_path.write_text(json.dumps(payload, indent=2))
    return output_path


def run(season: int) -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        logger.error(str(exc))
        return 1

    client = BallDontLieClient(settings)

    valid_games: list[dict[str, Any]] = []
    dropped_count = 0

    try:
        for game in client.get_games(season=season):
            if validate_game(game):
                valid_games.append(game)
            else:
                dropped_count += 1
    except BallDontLieAPIError as exc:
        logger.error("Ingestion failed: %s", exc)
        return 1

    if not valid_games:
        # An empty result isn't necessarily a bug (an off-season query could
        # legitimately return nothing), but it's worth being loud about it
        # rather than silently writing an empty file, since a silent empty
        # load is exactly the kind of failure that goes unnoticed for weeks.
        logger.warning(
            "No valid games retrieved for season %d (dropped %d invalid records). "
            "Nothing written.",
            season, dropped_count,
        )
        return 0

    output_path = write_raw_json(valid_games, season, settings.raw_data_dir)
    logger.info(
        "Wrote %d records (%d dropped) to %s",
        len(valid_games), dropped_count, output_path,
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NBA games from balldontlie API")
    parser.add_argument(
        "--season", type=int, required=True,
        help="Season year, e.g. 2024 for the 2024-25 season",
    )
    args = parser.parse_args()
    sys.exit(run(args.season))


if __name__ == "__main__":
    main()

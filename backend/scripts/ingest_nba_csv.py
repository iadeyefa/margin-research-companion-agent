import argparse
import asyncio
import csv
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.services.pinecone import store_text_records  # noqa: E402


DEFAULT_FILE = ROOT / "data" / "raw" / "Games.csv"


def normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def value(row: dict[str, str], *candidates: str) -> str:
    normalized = {normalize_key(key): value for key, value in row.items()}
    for candidate in candidates:
        found = normalized.get(normalize_key(candidate))
        if found not in (None, ""):
            return found.strip()
    return ""


def clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, item in metadata.items():
        if item in (None, ""):
            continue
        if isinstance(item, str):
            cleaned[key] = item[:1000]
        elif isinstance(item, (int, float, bool)):
            cleaned[key] = item
        else:
            cleaned[key] = str(item)[:1000]
    return cleaned


def fallback_summary(row: dict[str, str], max_fields: int = 18) -> str:
    fields = []
    for key, item in row.items():
        if item not in (None, ""):
            fields.append(f"{key}: {item}")
        if len(fields) >= max_fields:
            break
    return "NBA game record. " + "; ".join(fields)


def make_record(row: dict[str, str], row_number: int) -> dict[str, Any]:
    game_id = value(row, "game_id", "gameid", "id", "gameorder") or f"row-{row_number}"
    date = value(row, "date", "date_game", "gamedate", "game_date")
    season = value(row, "season", "year_id", "season_year", "year")
    team = value(row, "team", "team_name", "teamname", "team_id", "teamid", "home_team", "hometeam")
    opponent = value(row, "opponent", "opp_id", "oppid", "away_team", "awayteam", "visitor_team")
    points = value(row, "pts", "points", "score", "team_score", "teamscore", "home_score", "homescore")
    opponent_points = value(
        row,
        "opp_pts",
        "opponent_points",
        "opponent_score",
        "opponentscore",
        "away_score",
        "awayscore",
    )
    result = value(row, "game_result", "result", "wl", "win_loss")
    location = value(row, "game_location", "location", "venue", "arena")
    playoffs = value(row, "is_playoffs", "playoffs", "isplayoffs")

    if team and opponent and points and opponent_points:
        summary = f"NBA game"
        if date:
            summary += f" on {date}"
        if season:
            summary += f" during the {season} season"
        summary += f": {team} played {opponent} and the score was {team} {points}, {opponent} {opponent_points}."
        if result:
            summary += f" {team}'s result was {result}."
        if location:
            summary += f" Game location or venue: {location}."
        if playoffs:
            summary += f" Playoff game flag: {playoffs}."
    else:
        summary = fallback_summary(row)

    record_id_parts = ["nba", str(game_id)]
    if team:
        record_id_parts.append(team)
    record_id = "-".join(re.sub(r"[^A-Za-z0-9]+", "-", part).strip("-") for part in record_id_parts)

    return {
        "id": record_id[:512],
        "text": summary,
        "metadata": clean_metadata(
            {
                "sport": "NBA",
                "source": "csv",
                "row_number": row_number,
                "game_id": game_id,
                "date": date,
                "season": season,
                "team": team,
                "opponent": opponent,
                "result": result,
            }
        ),
    }


def load_records(csv_path: Path, limit: int | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=1):
            records.append(make_record(row, row_number))
            if limit and len(records) >= limit:
                break
    return records


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NBA CSV rows into Pinecone.")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="CSV file to ingest.")
    parser.add_argument("--limit", type=int, default=None, help="Only ingest the first N rows.")
    parser.add_argument("--batch-size", type=int, default=100, help="Pinecone upsert batch size.")
    parser.add_argument("--namespace", default=None, help="Optional Pinecone namespace.")
    parser.add_argument("--dry-run", action="store_true", help="Preview records without uploading to Pinecone.")
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"CSV not found: {args.file}")

    records = load_records(args.file, args.limit)
    if not records:
        raise SystemExit(f"No records found in: {args.file}")

    print(f"Loaded {len(records)} records from {args.file}")
    print("Example text:")
    print(records[0]["text"])

    if args.dry_run:
        print("Dry run complete. Nothing was uploaded to Pinecone.")
        return

    total = await store_text_records(
        records,
        batch_size=args.batch_size,
        namespace=args.namespace,
    )
    print(f"Uploaded {total} records to Pinecone.")


if __name__ == "__main__":
    asyncio.run(main())

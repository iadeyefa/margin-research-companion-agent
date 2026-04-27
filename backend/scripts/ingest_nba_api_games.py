import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from nba_api.stats.endpoints import leaguegamefinder  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.nba_teams import TEAM_BY_ABBREVIATION  # noqa: E402
from app.services.pinecone import store_text_records  # noqa: E402


settings = get_settings()


def normalize_date(raw_date: str) -> str:
    raw_date = (raw_date or "").strip()
    if not raw_date:
        return ""
    for pattern in ("%b %d, %Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_date, pattern).date().isoformat()
        except ValueError:
            continue
    return raw_date


def season_year_from_label(season_label: str) -> int | None:
    if not season_label or "-" not in season_label:
        return None
    start, end = season_label.split("-", maxsplit=1)
    if not (start.isdigit() and end.isdigit()):
        return None
    century = start[:2]
    return int(f"{century}{end}")


def parse_opponent(matchup: str) -> tuple[str, str]:
    matchup = (matchup or "").strip()
    if not matchup:
        return "", ""
    parts = matchup.split()
    opponent_abbreviation = parts[-1].upper() if parts else ""
    return TEAM_BY_ABBREVIATION.get(opponent_abbreviation, opponent_abbreviation), opponent_abbreviation


def clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value in (None, ""):
            continue
        cleaned[key] = value
    return cleaned


def make_record(row: dict[str, Any], season_label: str, season_type: str, row_number: int) -> dict[str, Any]:
    game_id = str(row.get("GAME_ID", "")).strip() or f"nba-api-{season_type}-{row_number}"
    team = " ".join(
        part for part in [str(row.get("TEAM_CITY", "")).strip(), str(row.get("TEAM_NAME", "")).strip()] if part
    ).strip() or str(row.get("TEAM_NAME", "")).strip()
    team_abbreviation = str(row.get("TEAM_ABBREVIATION", "")).strip().upper()
    opponent, opponent_abbreviation = parse_opponent(str(row.get("MATCHUP", "")))
    date = normalize_date(str(row.get("GAME_DATE", "")))
    result = str(row.get("WL", "")).strip()
    points = int(row["PTS"]) if row.get("PTS") not in (None, "") else None
    plus_minus = float(row["PLUS_MINUS"]) if row.get("PLUS_MINUS") not in (None, "") else None
    opponent_points = int(points - plus_minus) if points is not None and plus_minus is not None else None
    rebounds = int(row["REB"]) if row.get("REB") not in (None, "") else None
    assists = int(row["AST"]) if row.get("AST") not in (None, "") else None
    steals = int(row["STL"]) if row.get("STL") not in (None, "") else None
    blocks = int(row["BLK"]) if row.get("BLK") not in (None, "") else None
    turnovers = int(row["TOV"]) if row.get("TOV") not in (None, "") else None
    fg_pct = float(row["FG_PCT"]) if row.get("FG_PCT") not in (None, "") else None
    three_pct = float(row["FG3_PCT"]) if row.get("FG3_PCT") not in (None, "") else None
    season_year = season_year_from_label(season_label)

    summary = (
        f"NBA {season_type.lower()} game on {date} during the {season_label} season: "
        f"{team} played {opponent} and the score was {team} {points}, {opponent} {opponent_points}. "
        f"{team}'s result was {result}. "
        f"Team stats: {assists} assists, {rebounds} rebounds, {steals} steals, {blocks} blocks, {turnovers} turnovers. "
        f"Shooting: {fg_pct} field goal percentage, {three_pct} three-point percentage. "
        f"Plus-minus points: {plus_minus}. "
        f"Game context: {season_type}."
    )

    return {
        "id": f"nba-api-{season_type.lower().replace(' ', '-')}-{game_id}-{team_abbreviation}".lower(),
        "text": summary,
        "metadata": clean_metadata(
            {
                "sport": "NBA",
                "source": "nba_api",
                "source_detail": "leaguegamefinder",
                "row_number": row_number,
                "game_id": game_id,
                "date": date,
                "season_label": season_label,
                "season_year": season_year,
                "team": team,
                "team_abbreviation": team_abbreviation,
                "opponent": opponent,
                "opponent_abbreviation": opponent_abbreviation,
                "matchup": str(row.get("MATCHUP", "")).strip(),
                "result": result,
                "game_type": season_type,
                "points": points,
                "opponent_points": opponent_points,
                "assists": assists,
                "rebounds": rebounds,
                "steals": steals,
                "blocks": blocks,
                "turnovers": turnovers,
                "fg_pct": fg_pct,
                "three_pct": three_pct,
                "plus_minus": plus_minus,
            }
        ),
    }


def fetch_rows(season_label: str, season_type: str) -> list[dict[str, Any]]:
    response = leaguegamefinder.LeagueGameFinder(
        player_or_team_abbreviation="T",
        season_nullable=season_label,
        season_type_nullable=season_type,
    )
    return response.get_normalized_dict().get("LeagueGameFinderResults", [])


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest current NBA.com game logs into Pinecone.")
    parser.add_argument("--season", default=settings.current_nba_season, help="NBA season label, for example 2025-26.")
    parser.add_argument(
        "--season-type",
        action="append",
        choices=["Regular Season", "Playoffs"],
        help="Season type to ingest. Repeat the flag to ingest both.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only ingest the first N rows per season type.")
    parser.add_argument("--batch-size", type=int, default=100, help="Pinecone upsert batch size.")
    parser.add_argument("--namespace", default=None, help="Optional Pinecone namespace.")
    parser.add_argument("--dry-run", action="store_true", help="Preview records without uploading to Pinecone.")
    args = parser.parse_args()

    season_types = args.season_type or ["Regular Season", "Playoffs"]
    records: list[dict[str, Any]] = []

    for season_type in season_types:
        rows = fetch_rows(args.season, season_type)
        if args.limit is not None:
            rows = rows[: args.limit]
        for row_number, row in enumerate(rows, start=1):
            records.append(make_record(row, args.season, season_type, row_number))

    if not records:
        raise SystemExit("No NBA API records were returned.")

    print(f"Loaded {len(records)} records from nba_api for season {args.season}.")
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

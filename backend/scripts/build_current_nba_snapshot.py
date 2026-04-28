import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from nba_api.stats.endpoints import leaguegamefinder  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.nba_teams import TEAM_BY_ABBREVIATION  # noqa: E402


settings = get_settings()


def parse_opponent(matchup: str) -> str:
    parts = str(matchup or "").strip().split()
    abbreviation = parts[-1].upper() if parts else ""
    return TEAM_BY_ABBREVIATION.get(abbreviation, abbreviation)


def aggregate_team_games(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, float | str]] = defaultdict(
        lambda: {
            "team": "",
            "games": 0.0,
            "wins": 0.0,
            "losses": 0.0,
            "points": 0.0,
            "opponent_points": 0.0,
            "rebounds": 0.0,
            "assists": 0.0,
            "fg_pct": 0.0,
            "three_pct": 0.0,
            "plus_minus": 0.0,
        }
    )

    for row in rows:
        team = " ".join(
            part for part in [str(row.get("TEAM_CITY", "")).strip(), str(row.get("TEAM_NAME", "")).strip()] if part
        ).strip()
        if not team:
            continue

        stats = grouped[team]
        stats["team"] = team
        stats["games"] += 1
        stats["wins"] += 1 if str(row.get("WL", "")).strip().upper() == "W" else 0
        stats["losses"] += 1 if str(row.get("WL", "")).strip().upper() == "L" else 0

        points = float(row.get("PTS") or 0)
        plus_minus = float(row.get("PLUS_MINUS") or 0)
        stats["points"] += points
        stats["opponent_points"] += points - plus_minus
        stats["rebounds"] += float(row.get("REB") or 0)
        stats["assists"] += float(row.get("AST") or 0)
        stats["fg_pct"] += float(row.get("FG_PCT") or 0)
        stats["three_pct"] += float(row.get("FG3_PCT") or 0)
        stats["plus_minus"] += plus_minus

    aggregates: list[dict[str, Any]] = []
    for team, stats in grouped.items():
        games = int(stats["games"])
        if games == 0:
            continue
        wins = int(stats["wins"])
        losses = int(stats["losses"])
        avg_points = float(stats["points"]) / games
        avg_opponent_points = float(stats["opponent_points"]) / games
        avg_plus_minus = float(stats["plus_minus"]) / games

        opponent_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            row_team = " ".join(
                part for part in [str(row.get("TEAM_CITY", "")).strip(), str(row.get("TEAM_NAME", "")).strip()] if part
            ).strip()
            if row_team == team:
                opponent_counts[parse_opponent(str(row.get("MATCHUP", "")))] += 1

        aggregates.append(
            {
                "team": team,
                "games": games,
                "wins": wins,
                "losses": losses,
                "win_rate": wins / games,
                "avg_points": avg_points,
                "avg_opponent_points": avg_opponent_points,
                "avg_point_diff": avg_points - avg_opponent_points,
                "avg_rebounds": float(stats["rebounds"]) / games,
                "avg_assists": float(stats["assists"]) / games,
                "avg_fg_pct": float(stats["fg_pct"]) / games,
                "avg_three_pct": float(stats["three_pct"]) / games,
                "avg_plus_minus": avg_plus_minus,
                "opponents_seen": dict(sorted(opponent_counts.items())),
            }
        )

    return sorted(
        aggregates,
        key=lambda item: (item["win_rate"], item["avg_point_diff"], item["avg_points"]),
        reverse=True,
    )


def fetch_rows(season: str, season_type: str) -> list[dict[str, Any]]:
    response = leaguegamefinder.LeagueGameFinder(
        player_or_team_abbreviation="T",
        season_nullable=season,
        season_type_nullable=season_type,
    )
    return response.get_normalized_dict().get("LeagueGameFinderResults", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a structured current NBA snapshot for chat answers.")
    parser.add_argument("--season", default=settings.current_nba_season, help="Season label, for example 2025-26.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(settings.current_nba_snapshot_path),
        help="Where to write the snapshot JSON.",
    )
    args = parser.parse_args()

    regular_rows = fetch_rows(args.season, "Regular Season")
    playoff_rows = fetch_rows(args.season, "Playoffs")

    snapshot = {
        "season": args.season,
        "regular_season": aggregate_team_games(regular_rows),
        "playoffs": aggregate_team_games(playoff_rows),
    }

    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Wrote snapshot to {output_path}")


if __name__ == "__main__":
    main()

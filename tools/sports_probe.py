"""Probe football-data.org without starting the server or printing the token."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minitel.http import HttpError
from services.sports.config import SportsConfig
from services.sports.source import FootballDataSource


def _print_match(match):
    score = "-"
    if match.home_goals is not None and match.away_goals is not None:
        score = f"{match.home_goals}-{match.away_goals}"
    minute = ""
    if match.minute is not None:
        minute = f" {match.minute}'"
    print(
        f"{match.competition_code:<3} {match.home.short:<3} "
        f"{score:>5} {match.away.short:<3} "
        f"{match.status.value:<10}{minute}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Probe football-data.org through the sports source"
    )
    parser.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    parser.add_argument(
        "--standings",
        metavar="CODE",
        help="also fetch a competition table, for example PL",
    )
    args = parser.parse_args()

    config = SportsConfig.from_env()
    if not config.configured:
        print(
            "FOOTBALL_API_KEY is not set. Put it in .env or export it.",
            file=sys.stderr,
        )
        return 2

    source = FootballDataSource(
        config.token,
        base_url=config.base_url,
        competitions=config.competitions,
        timeout=config.timeout,
    )
    try:
        result = source.fetch_day(args.date)
    except HttpError as exc:
        body = exc.body.decode("utf-8", "replace")[:120] if exc.body else ""
        message = exc.message or body
        print(f"HTTP {exc.status}: {message}", file=sys.stderr)
        if exc.status in (401, 403):
            print("Check FOOTBALL_API_KEY and your plan.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(
        f"date={args.date or 'today'} competitions={','.join(config.competitions)}"
    )
    print(
        f"matches={len(result.value)} "
        f"quota_remaining={result.quota_remaining} "
        f"quota_reset={result.quota_reset}"
    )
    for match in result.value:
        _print_match(match)

    if args.standings:
        try:
            table = source.fetch_standings(args.standings)
        except HttpError as exc:
            print(f"HTTP {exc.status}: {exc.message}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(f"standings {args.standings.upper()} rows={len(table.value)}")
        for row in table.value[:5]:
            print(
                f"{row.position:>2} {row.team.short:<3} "
                f"{row.played:>2} {row.goal_difference:>+3} {row.points:>3}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

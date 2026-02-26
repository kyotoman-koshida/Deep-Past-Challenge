#!/usr/bin/env python3

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _parse_utc_datetime(value: str) -> datetime:
    # Kaggle uses RFC3339-ish strings like "2026-02-26T11:24:42.197Z"
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class RankedNotebook:
    ref: str
    title: str
    author: str
    total_votes: int
    last_run_time: datetime
    days_since_last_run: float
    vote_score: float
    recency_score: float
    score: float


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def rank_notebooks(
    items: list[dict[str, Any]],
    *,
    alpha: float,
    half_life_days: float,
    now: datetime,
) -> list[RankedNotebook]:
    if not items:
        return []

    max_votes = max((_safe_int(it.get("total_votes")) for it in items), default=0)
    max_votes_log = math.log1p(max_votes) if max_votes > 0 else 1.0

    ranked: list[RankedNotebook] = []
    for it in items:
        ref = str(it.get("ref", "")).strip()
        if not ref:
            continue

        title = str(it.get("title", "")).strip()
        author = str(it.get("author", "")).strip()
        votes = max(0, _safe_int(it.get("total_votes")))

        last_run_raw = it.get("last_run_time") or it.get("lastRunTime")
        if not last_run_raw:
            continue
        last_run_time = _parse_utc_datetime(str(last_run_raw))
        days_since = max(0.0, (now - last_run_time).total_seconds() / 86400.0)

        vote_score = (math.log1p(votes) / max_votes_log) if votes > 0 else 0.0
        recency_score = math.exp(-days_since / half_life_days) if half_life_days > 0 else 0.0
        score = alpha * vote_score + (1.0 - alpha) * recency_score

        ranked.append(
            RankedNotebook(
                ref=ref,
                title=title,
                author=author,
                total_votes=votes,
                last_run_time=last_run_time,
                days_since_last_run=days_since,
                vote_score=vote_score,
                recency_score=recency_score,
                score=score,
            )
        )

    ranked.sort(key=lambda x: (x.score, x.total_votes, x.last_run_time), reverse=True)
    return ranked


def _md_escape(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").strip()


def render_markdown_table(items: list[RankedNotebook], *, top_k: int) -> str:
    rows = items[: max(0, top_k)]
    out: list[str] = []
    out.append("| rank | ref | votes | last_run_time (UTC) | score |")
    out.append("|---:|---|---:|---|---:|")
    for idx, it in enumerate(rows, start=1):
        out.append(
            "| "
            + " | ".join(
                [
                    str(idx),
                    _md_escape(it.ref),
                    str(it.total_votes),
                    it.last_run_time.strftime("%Y-%m-%d %H:%M:%S"),
                    f"{it.score:.4f}",
                ]
            )
            + " |"
        )
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rank Kaggle notebooks by upvotes (primary) and recency (secondary)."
    )
    parser.add_argument("input_json", help="Path to a JSON file containing notebook items.")
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--alpha", type=float, default=0.8, help="Weight for votes vs recency.")
    parser.add_argument("--half-life-days", type=float, default=30.0)
    parser.add_argument(
        "--now-utc",
        type=str,
        default="",
        help='Optional override for "now" in UTC, e.g. 2026-02-26T00:00:00Z',
    )
    parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (Markdown table or JSON).",
    )
    args = parser.parse_args()

    now = _parse_utc_datetime(args.now_utc) if args.now_utc else datetime.now(timezone.utc)

    with open(args.input_json, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise SystemExit("Input JSON must be a list of notebook objects.")

    ranked = rank_notebooks(
        payload, alpha=float(args.alpha), half_life_days=float(args.half_life_days), now=now
    )

    if args.format == "json":
        as_json = [
            {
                "ref": it.ref,
                "title": it.title,
                "author": it.author,
                "total_votes": it.total_votes,
                "last_run_time": it.last_run_time.isoformat(),
                "days_since_last_run": it.days_since_last_run,
                "vote_score": it.vote_score,
                "recency_score": it.recency_score,
                "score": it.score,
            }
            for it in ranked[: max(0, int(args.top_k))]
        ]
        print(json.dumps(as_json, ensure_ascii=False, indent=2))
        return 0

    print(render_markdown_table(ranked, top_k=int(args.top_k)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


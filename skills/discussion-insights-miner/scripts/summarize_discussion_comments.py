#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


ENTRY_RE = re.compile(r"^## Entry: `(?P<id>[^`]+)`\s*$")
FIELD_RE = re.compile(r"^- (?P<k>[^:]+): (?P<v>.*)$")


@dataclass
class Comment:
    url: str | None = None
    author: str | None = None
    created_at: str | None = None
    upvotes: int | None = None
    body: str | None = None


@dataclass
class Entry:
    entry_id: str
    url: str | None = None
    title: str | None = None
    author: str | None = None
    created_at: str | None = None
    upvotes: int | None = None
    body: str | None = None
    comments: list[Comment] | None = None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except Exception:
        return None


def _parse_date_yyyy_mm_dd(value: str | None) -> dt.date | None:
    if not value:
        return None
    value = value.strip()
    if len(value) >= 10:
        value = value[:10]
    try:
        return dt.date.fromisoformat(value)
    except Exception:
        return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_discussion_capture(markdown: str) -> list[Entry]:
    lines = markdown.splitlines()
    entries: list[Entry] = []

    i = 0
    while i < len(lines):
        m = ENTRY_RE.match(lines[i])
        if not m:
            i += 1
            continue

        entry_id = m.group("id").strip()
        entry = Entry(entry_id=entry_id, comments=[])
        i += 1

        # Parse entry header bullet fields until we reach body or comments.
        current_body: list[str] = []
        in_entry_body = False

        while i < len(lines):
            if ENTRY_RE.match(lines[i]):
                break

            if lines[i].startswith("### Comments"):
                break

            field_m = FIELD_RE.match(lines[i])
            if field_m and not in_entry_body:
                k = field_m.group("k").strip()
                v = field_m.group("v").strip()
                if k == "URL":
                    entry.url = v
                elif k == "タイトル":
                    entry.title = v
                elif k == "投稿者":
                    entry.author = v
                elif k == "投稿日時":
                    entry.created_at = v
                elif k == "upvote":
                    entry.upvotes = _parse_int(v)
                elif k == "本文":
                    in_entry_body = True
                    if v:
                        current_body.append(v)
                i += 1
                continue

            if in_entry_body:
                current_body.append(lines[i])
                i += 1
                continue

            i += 1

        entry.body = "\n".join([ln.rstrip() for ln in current_body]).strip() or None

        # Parse comments blocks.
        while i < len(lines) and lines[i].startswith("### Comments"):
            i += 1
            comment = Comment()
            comment_body: list[str] = []
            in_comment_body = False

            while i < len(lines):
                if lines[i].startswith("### Comments") or ENTRY_RE.match(lines[i]):
                    break
                field_m = FIELD_RE.match(lines[i])
                if field_m and not in_comment_body:
                    k = field_m.group("k").strip()
                    v = field_m.group("v").strip()
                    if k == "URL":
                        comment.url = v
                    elif k == "投稿者":
                        comment.author = v
                    elif k == "投稿日時":
                        comment.created_at = v
                    elif k == "upvote":
                        comment.upvotes = _parse_int(v)
                    elif k == "本文":
                        in_comment_body = True
                        if v:
                            comment_body.append(v)
                    i += 1
                    continue

                if in_comment_body:
                    comment_body.append(lines[i])
                    i += 1
                    continue

                i += 1

            comment.body = "\n".join([ln.rstrip() for ln in comment_body]).strip() or None
            entry.comments.append(comment)

        entries.append(entry)

    return entries


KEYWORDS = [
    ("<gap>", re.compile(r"<gap>|big_gap", re.IGNORECASE)),
    ("determinative", re.compile(r"\{d\}|\{ki\}|\(d\)|\(ki\)|determinative", re.IGNORECASE)),
    ("rescore/LB", re.compile(r"\b(rescore|leaderboard|LB)\b", re.IGNORECASE)),
    ("metric", re.compile(r"\b(BLEU|chrF)\b", re.IGNORECASE)),
    ("decode", re.compile(r"\b(beam|beams|length_penalty|max_new_tokens)\b", re.IGNORECASE)),
    ("normalization", re.compile(r"\b(normalize|normalization|unicode|roman numeral)\b", re.IGNORECASE)),
    ("data update", re.compile(r"\b(update|data is now live)\b", re.IGNORECASE)),
]


def guess_tags(entry: Entry) -> list[str]:
    hay = "\n".join(
        [
            entry.title or "",
            entry.author or "",
            entry.body or "",
            *(c.body or "" for c in (entry.comments or [])),
            *(c.author or "" for c in (entry.comments or [])),
        ]
    )
    tags: list[str] = []
    for label, rx in KEYWORDS:
        if rx.search(hay):
            tags.append(label)
    return tags


def iter_filtered(
    entries: Iterable[Entry],
    *,
    since: dt.date | None,
    min_upvotes: int | None,
    host_only: bool,
) -> list[Entry]:
    host_handles = {"@deeppast", "@ryanholbrook"}

    out: list[Entry] = []
    for e in entries:
        e_date = _parse_date_yyyy_mm_dd(e.created_at)
        if since and e_date and e_date < since:
            continue
        if min_upvotes is not None and (e.upvotes or 0) < min_upvotes:
            continue
        if host_only:
            is_host = (e.author or "").strip() in host_handles
            is_host |= any((c.author or "").strip() in host_handles for c in (e.comments or []))
            if not is_host:
                continue
        out.append(e)
    return out


def to_markdown_table(entries: list[Entry]) -> str:
    header = "| entry_id | date | upvotes | author | title | tags | url |\n|---:|---|---:|---|---|---|---|\n"
    rows: list[str] = []
    for e in entries:
        tags = ", ".join(guess_tags(e))
        title = (e.title or "").replace("|", "\\|")
        author = (e.author or "").replace("|", "\\|")
        url = e.url or ""
        date = (e.created_at or "")[:10]
        upvotes = "" if e.upvotes is None else str(e.upvotes)
        rows.append(f"| `{e.entry_id}` | {date} | {upvotes} | {author} | {title} | {tags} | {url} |")
    return header + "\n".join(rows) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Summarize .codex/docs/discussion_comments.md into a compact index.")
    p.add_argument("path", type=Path, help="Path to discussion_comments.md")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--top-k", type=int, default=50, help="Keep top-k entries by upvotes (after filtering).")
    p.add_argument("--since", type=str, default=None, help="Filter entries with date >= YYYY-MM-DD (best-effort).")
    p.add_argument("--min-upvotes", type=int, default=None)
    p.add_argument("--host-only", action="store_true", help="Keep only entries involving @deeppast/@ryanholbrook.")
    args = p.parse_args()

    since = dt.date.fromisoformat(args.since) if args.since else None
    entries = parse_discussion_capture(_read_text(args.path))
    entries = iter_filtered(entries, since=since, min_upvotes=args.min_upvotes, host_only=args.host_only)

    # Sort: upvotes desc, then date desc, then id.
    def sort_key(e: Entry) -> tuple:
        date = _parse_date_yyyy_mm_dd(e.created_at) or dt.date(1970, 1, 1)
        return (-(e.upvotes or 0), date.toordinal() * -1, e.entry_id)

    entries = sorted(entries, key=sort_key)
    entries = entries[: max(args.top_k, 0)]

    if args.format == "json":
        payload = []
        for e in entries:
            obj = asdict(e)
            obj["tags"] = guess_tags(e)
            payload.append(obj)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(to_markdown_table(entries))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


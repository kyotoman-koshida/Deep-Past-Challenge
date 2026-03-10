#!/usr/bin/env python3
"""
train.csv の品質スキャン（PDF不要の優先度付け）

目的:
  - 1561行を全部直す前に「怪しい行」を自動で順位付けして、レビューキューを作る。
  - PDF/OCRでの修正作業に入る前の “当たり付け” 用。

使い方:
  UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/scan_train_quality.py

  # パスを明示する場合
  UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/scan_train_quality.py \\
    --train data/kaggle/deep-past-initiative-machine-translation/train.csv \\
    --published-texts data/kaggle/deep-past-initiative-machine-translation/published_texts.csv \\
    --out reports/train_quality_scan.csv
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd


DEFAULT_TRAIN = "data/kaggle/deep-past-initiative-machine-translation/train.csv"
DEFAULT_PUBLISHED_TEXTS = (
    "data/kaggle/deep-past-initiative-machine-translation/published_texts.csv"
)
DEFAULT_OUT = "reports/train_quality_scan.csv"


FRACTION_RE = re.compile(r"\b\d+\s*/\s*\d+\b|\b\d+\s+\d+\s*/\s*\d+\b")
DECIMAL_RE = re.compile(r"\b\d+\.\d+\b")
ELLIPSIS_RE = re.compile(r"\.\.\.|…")
GAP_BRACKET_RE = re.compile(r"\[(?:x+|\.\.\.)\]")
WEIRD_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def find_all(pattern: re.Pattern[str], text: str) -> list[str]:
    return [m.group(0) for m in pattern.finditer(text)]


def count_unbalanced(text: str, open_char: str, close_char: str) -> int:
    return abs(text.count(open_char) - text.count(close_char))


def looks_truncated_english(text: str) -> bool:
    t = text.strip()
    if len(t) < 40:
        return False
    # 末尾が句読点/閉じ括弧類で終わらない長文は「途中で切れた」可能性が上がる
    return not t.endswith((".", "?", "!", ")", "]", "}", "\"", "'"))


def has_gap_like_but_no_gap_token(text: str) -> bool:
    t = text
    has_gap_like = bool(ELLIPSIS_RE.search(t) or GAP_BRACKET_RE.search(t))
    has_gap_token = "<gap>" in t
    return has_gap_like and not has_gap_token


def has_gap_token_variants(text: str) -> bool:
    # ありがちな表記揺れ（確定ではなく「要確認」フラグ）
    t = text.lower()
    return any(x in t for x in ["< gap >", "<gap >", "< gap>", "<g ap>", "<gap/>", "&lt;gap&gt;"])


def long_decimal_candidates(text: str, max_decimals: int) -> list[str]:
    hits: list[str] = []
    for m in DECIMAL_RE.finditer(text):
        token = m.group(0)
        decimals = token.split(".", 1)[1]
        if len(decimals) > max_decimals:
            hits.append(token)
    return hits


@dataclass(frozen=True)
class Issue:
    code: str
    weight: int
    detail: str


def scan_row(transliteration: str, translation: str, *, max_decimals: int) -> list[Issue]:
    issues: list[Issue] = []

    tr_in = transliteration or ""
    tr_out = translation or ""

    in_len = len(tr_in)
    out_len = len(tr_out)
    ratio = (out_len / in_len) if in_len else 0.0

    if in_len > 0 and (ratio < 0.25 or ratio > 6.0):
        issues.append(Issue("len_ratio_extreme", 3, f"len_out/len_in={ratio:.2f}"))

    if looks_truncated_english(tr_out):
        issues.append(Issue("translation_maybe_truncated", 2, "末尾が句読点等で終わらない"))

    frac_hits = find_all(FRACTION_RE, tr_out)
    if frac_hits:
        issues.append(Issue("fraction_in_translation", 2, f"hits={frac_hits[:3]}"))

    long_dec_hits = long_decimal_candidates(tr_out, max_decimals=max_decimals)
    if long_dec_hits:
        issues.append(
            Issue(
                "long_decimals_in_translation",
                1,
                f"hits={long_dec_hits[:3]} (>{max_decimals} dp)",
            )
        )

    if has_gap_like_but_no_gap_token(tr_out):
        issues.append(Issue("gap_like_but_no_gap_token", 2, "…/[x]/[...] あり, <gap> なし"))

    if has_gap_token_variants(tr_out):
        issues.append(Issue("gap_token_variant", 1, " <gap> 表記揺れの疑い"))

    for open_c, close_c, code in [
        ("(", ")", "paren_unbalanced"),
        ("[", "]", "bracket_unbalanced"),
        ("{", "}", "brace_unbalanced"),
        ("<", ">", "angle_unbalanced"),
    ]:
        unbalanced = count_unbalanced(tr_out, open_c, close_c)
        if unbalanced:
            issues.append(Issue(code, 1, f"{open_c}{close_c} diff={unbalanced}"))

    if WEIRD_CONTROL_RE.search(tr_out):
        issues.append(Issue("control_chars", 2, "制御文字の混入"))

    return issues


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--train", default=DEFAULT_TRAIN, help="train.csv のパス")
    p.add_argument(
        "--published-texts",
        default=DEFAULT_PUBLISHED_TEXTS,
        help="published_texts.csv のパス（label/URL付与用、任意）",
    )
    p.add_argument("--out", default=DEFAULT_OUT, help="出力CSVのパス")
    p.add_argument(
        "--max-decimals",
        type=int,
        default=4,
        help="小数点以下の許容桁数（これより多いとフラグ）",
    )
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()

    train = pd.read_csv(args.train)
    required_cols = {"oare_id", "transliteration", "translation"}
    missing = required_cols - set(train.columns)
    if missing:
        raise SystemExit(f"[ERROR] train missing columns: {sorted(missing)}")

    out = train[["oare_id", "transliteration", "translation"]].copy()

    # 任意: label と OARE URL を付与（レビュー作業で便利）
    if args.published_texts and os.path.exists(args.published_texts):
        pt = pd.read_csv(args.published_texts, usecols=["oare_id", "label", "online transcript"])
        out = out.merge(pt, on="oare_id", how="left")
    else:
        out["label"] = pd.NA
        out["online transcript"] = pd.NA

    issues_col: list[str] = []
    details_col: list[str] = []
    scores_col: list[int] = []

    for _, row in out.iterrows():
        issues = scan_row(
            row.get("transliteration", ""),
            row.get("translation", ""),
            max_decimals=args.max_decimals,
        )
        score = sum(i.weight for i in issues)
        scores_col.append(score)
        issues_col.append("|".join(i.code for i in issues))
        details_col.append(" / ".join(f"{i.code}:{i.detail}" for i in issues))

    out["score"] = scores_col
    out["issues"] = issues_col
    out["details"] = details_col
    out["transliteration_len"] = out["transliteration"].astype(str).map(len)
    out["translation_len"] = out["translation"].astype(str).map(len)
    out["len_ratio"] = out["translation_len"] / out["transliteration_len"].replace(0, pd.NA)

    out = out.sort_values(["score", "oare_id"], ascending=[False, True])

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    out.to_csv(args.out, index=False)

    flagged = int((out["score"] > 0).sum())
    print(f"[OK] rows={len(out)} flagged={flagged} out={args.out}")
    if flagged:
        print("[TOP10]")
        print(out.head(10)[["oare_id", "score", "issues"]].to_string(index=False))


if __name__ == "__main__":
    main()


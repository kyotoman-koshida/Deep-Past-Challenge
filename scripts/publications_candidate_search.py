#!/usr/bin/env python3
"""
publications.csv（ページ単位OCRテキスト）を検索し、oare_id ごとに候補 pdf_name/page を返す。

設計:
  - SQLite FTS5 で全文検索インデックスを作成（初回のみ重い）
  - train.csv / published_texts.csv からクエリを組み立てて検索
  - 上位K件を oare_id ごとにCSV出力

注意:
  - publications.csv は 216k 行あるため、毎回 pandas で全走査すると現実的でない。
  - FTS の精度は「表記揺れ」「OCR品質」「元PDFに当該文字列が含まれるか」に強く依存する。
    取り違え修正の “探索支援” と割り切り、最終確定は人が行う。

実行例:
  UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/publications_candidate_search.py --build-index
  UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/publications_candidate_search.py --topk 3 --out /tmp/candidates.csv
  UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/publications_candidate_search.py --oare-id <UUID> --topk 10
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd


DEFAULT_TRAIN = Path("data/kaggle/deep-past-initiative-machine-translation/train.csv")
DEFAULT_PUBLISHED_TEXTS = Path(
    "data/kaggle/deep-past-initiative-machine-translation/published_texts.csv"
)
DEFAULT_PUBLICATIONS = Path(
    "data/kaggle/deep-past-initiative-machine-translation/publications.csv"
)
DEFAULT_DB = Path("data/index/publications_fts.sqlite")
DEFAULT_OUT = Path("data/index/publications_candidates_top3.csv")


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "as",
    "by",
    "from",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "it",
    "this",
    "that",
    "these",
    "those",
}


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts_test USING fts5(x)")
        conn.execute("DROP TABLE __fts_test")
        return True
    except sqlite3.OperationalError:
        return False


def _meta_get(conn: sqlite3.Connection, key: str) -> str | None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return None if row is None else str(row["value"])


def _meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def _csv_fingerprint(path: Path) -> str:
    st = path.stat()
    return f"mtime={int(st.st_mtime)};size={st.st_size}"


def ensure_publications_fts(
    *,
    publications_csv: Path,
    db_path: Path,
    chunk_size: int = 5000,
    rebuild: bool = False,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        if not _fts_available(conn):
            raise RuntimeError(
                "SQLite FTS5 が利用できません（このPython/SQLiteビルドでは無効の可能性）"
            )

        fp = _csv_fingerprint(publications_csv)
        existing_fp = _meta_get(conn, "publications_csv_fp")
        if (not rebuild) and existing_fp == fp:
            return

        conn.execute("DROP TABLE IF EXISTS publications_fts")
        conn.execute(
            """
            CREATE VIRTUAL TABLE publications_fts USING fts5(
              pdf_name UNINDEXED,
              page UNINDEXED,
              has_akkadian UNINDEXED,
              page_text
            )
            """
        )

        start = time.time()
        inserted = 0
        for chunk in pd.read_csv(
            publications_csv,
            chunksize=chunk_size,
            usecols=["pdf_name", "page", "page_text", "has_akkadian"],
        ):
            rows = [
                (
                    str(r.pdf_name),
                    int(r.page),
                    int(bool(r.has_akkadian)),
                    "" if pd.isna(r.page_text) else str(r.page_text),
                )
                for r in chunk.itertuples(index=False)
            ]
            conn.executemany(
                "INSERT INTO publications_fts(pdf_name,page,has_akkadian,page_text) VALUES (?,?,?,?)",
                rows,
            )
            inserted += len(rows)
            conn.commit()

        _meta_set(conn, "publications_csv_fp", fp)
        _meta_set(conn, "publications_fts_rows", str(inserted))
        _meta_set(conn, "built_at_unix", str(int(time.time())))
        conn.commit()
        elapsed = time.time() - start
        print(f"[OK] built FTS db={db_path} rows={inserted} elapsed_sec={elapsed:.1f}")
    finally:
        conn.close()


def _tokenize_query_terms(text: str) -> list[str]:
    # FTS5 のトークナイザ（unicode61）を想定し、英数字中心に寄せる
    raw = re.findall(r"[A-Za-z0-9]+", text)
    terms: list[str] = []
    for t in raw:
        tl = t.lower()
        if len(tl) <= 2:
            continue
        if tl in STOPWORDS:
            continue
        terms.append(t)
    # 重複除去（順序維持）
    seen: set[str] = set()
    uniq: list[str] = []
    for t in terms:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def build_fts_query(
    *,
    translation: str,
    transliteration: str,
    label: str | None,
    cdli_id: str | None,
    max_terms: int = 12,
) -> str:
    terms: list[str] = []

    if cdli_id and isinstance(cdli_id, str) and cdli_id.strip():
        terms.append(cdli_id.strip())

    if label and isinstance(label, str) and label.strip():
        # 例: "AKT 6c 705" のような参照語が入っていることが多い
        terms.extend(_tokenize_query_terms(label))

    # 英訳: 固有名詞/数字っぽい語がヒットしやすい
    if translation and isinstance(translation, str) and translation.strip():
        cap = re.findall(r"\b[A-Z][a-z]{2,}\b", translation)
        nums = re.findall(r"\b\d+\b", translation)
        terms.extend(cap[:6])
        terms.extend(nums[:6])
        # それでも弱い場合の保険（一般語はSTOPWORDSで減る）
        terms.extend(_tokenize_query_terms(translation)[:6])

    # 転写: OCR側に乗っていないことも多いので、低めに少数だけ
    if transliteration and isinstance(transliteration, str) and transliteration.strip():
        t_terms = _tokenize_query_terms(transliteration)
        terms.extend(t_terms[:4])

    # 最終的に OR で投げる（AND は厳しすぎて0件になりがち）
    uniq: list[str] = []
    seen: set[str] = set()
    for t in terms:
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)

    uniq = uniq[:max_terms]
    return " OR ".join(uniq)


@dataclass(frozen=True)
class FtsHit:
    pdf_name: str
    page: int
    has_akkadian: int
    score: float
    snippet: str


def search_publications_fts(
    conn: sqlite3.Connection, query: str, *, topk: int
) -> list[FtsHit]:
    if not query.strip():
        return []

    # bm25() は値が小さいほど良いことが多いので ASC。
    # 同一(pdf_name,page)が重複して返るケースがあるので後段で重複除去する。
    rows = conn.execute(
        """
        SELECT
          pdf_name,
          page,
          has_akkadian,
          bm25(publications_fts) AS score,
          snippet(publications_fts, 3, '[', ']', '…', 16) AS snippet
        FROM publications_fts
        WHERE publications_fts MATCH ?
        ORDER BY score ASC
        LIMIT ?
        """,
        (query, int(max(topk * 10, topk))),
    ).fetchall()

    hits: list[FtsHit] = []
    seen: set[tuple[str, int]] = set()
    for r in rows:
        key = (str(r["pdf_name"]), int(r["page"]))
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            FtsHit(
                pdf_name=key[0],
                page=key[1],
                has_akkadian=int(r["has_akkadian"]),
                score=float(r["score"]),
                snippet=str(r["snippet"]),
            )
        )
        if len(hits) >= topk:
            break
    return hits


def _iter_target_rows(
    merged: pd.DataFrame, oare_id: str | None
) -> Iterator[pd.Series]:
    if oare_id:
        sub = merged.loc[merged["oare_id"] == oare_id]
        for _, r in sub.iterrows():
            yield r
        return
    for _, r in merged.iterrows():
        yield r


def generate_candidates(
    *,
    train_csv: Path,
    published_texts_csv: Path,
    db_path: Path,
    oare_id: str | None,
    topk: int,
    max_terms: int,
) -> pd.DataFrame:
    train = pd.read_csv(train_csv, usecols=["oare_id", "transliteration", "translation"])
    pt = pd.read_csv(published_texts_csv, usecols=["oare_id", "label", "cdli_id"])
    merged = train.merge(pt, on="oare_id", how="left")

    conn = _connect(db_path)
    try:
        rows_out: list[dict] = []
        for r in _iter_target_rows(merged, oare_id=oare_id):
            q = build_fts_query(
                translation=str(r.get("translation", "") or ""),
                transliteration=str(r.get("transliteration", "") or ""),
                label=None if pd.isna(r.get("label")) else str(r.get("label")),
                cdli_id=None if pd.isna(r.get("cdli_id")) else str(r.get("cdli_id")),
                max_terms=max_terms,
            )
            hits = search_publications_fts(conn, q, topk=topk)
            for rank, h in enumerate(hits, start=1):
                rows_out.append(
                    {
                        "oare_id": r["oare_id"],
                        "rank": rank,
                        "pdf_name": h.pdf_name,
                        "page": h.page,
                        "score": h.score,
                        "has_akkadian": h.has_akkadian,
                        "label": None if pd.isna(r.get("label")) else r.get("label"),
                        "cdli_id": None if pd.isna(r.get("cdli_id")) else r.get("cdli_id"),
                        "query": q,
                        "snippet": h.snippet,
                    }
                )
            if not hits:
                rows_out.append(
                    {
                        "oare_id": r["oare_id"],
                        "rank": None,
                        "pdf_name": None,
                        "page": None,
                        "score": None,
                        "has_akkadian": None,
                        "label": None if pd.isna(r.get("label")) else r.get("label"),
                        "cdli_id": None if pd.isna(r.get("cdli_id")) else r.get("cdli_id"),
                        "query": q,
                        "snippet": None,
                    }
                )
        return pd.DataFrame(rows_out)
    finally:
        conn.close()


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    p.add_argument("--published-texts", type=Path, default=DEFAULT_PUBLISHED_TEXTS)
    p.add_argument("--publications", type=Path, default=DEFAULT_PUBLICATIONS)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--oare-id", type=str, default=None, help="単一UUIDのみ検索（任意）")
    p.add_argument("--topk", type=int, default=3)
    p.add_argument("--max-terms", type=int, default=12)
    p.add_argument(
        "--build-index",
        action="store_true",
        help="FTSインデックスを作成/更新して終了",
    )
    p.add_argument("--rebuild", action="store_true", help="FTSインデックスを強制再構築")
    p.add_argument("--chunk-size", type=int, default=5000, help="インデックス作成時のchunk")
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()

    if args.build_index:
        ensure_publications_fts(
            publications_csv=args.publications,
            db_path=args.db,
            chunk_size=args.chunk_size,
            rebuild=args.rebuild,
        )
        return

    ensure_publications_fts(
        publications_csv=args.publications,
        db_path=args.db,
        chunk_size=args.chunk_size,
        rebuild=False,
    )

    df = generate_candidates(
        train_csv=args.train,
        published_texts_csv=args.published_texts,
        db_path=args.db,
        oare_id=args.oare_id,
        topk=args.topk,
        max_terms=args.max_terms,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"[OK] out={args.out} rows={len(df)}")

    if args.oare_id:
        # 端末で見やすいように上位だけ表示
        show = df.head(min(10, len(df)))
        cols = ["rank", "pdf_name", "page", "score", "snippet"]
        print(show[cols].to_string(index=False))


if __name__ == "__main__":
    # uv の cache が書けない環境向けの注意（ユーザー向けにはREADME/Notebookで補足）
    if "UV_CACHE_DIR" not in os.environ:
        pass
    main()

---
name: discussion-insights-miner
description: Use when asked to extract actionable, comparable insights from this repo’s large `.codex/docs/discussion_comments.md` capture. Triages by recency/upvotes/host posts, turns threads into experiment-ready hypotheses, and can optionally persist summaries into `.codex/docs/public_insights.md` / `.codex/docs/notebook_digest.md` (but must not write `.codex/docs/experiments_log.md`).
---

# Discussion Insights Miner (from captured comments)

## Goal

Turn `.codex/docs/discussion_comments.md` (manual capture) into:

- comparable, experiment-ready hypotheses (what to change + why + risks)
- a compact shortlist/index of important threads
- cross-cutting learnings persisted in `.codex/docs/public_insights.md`

## Non-negotiable repo rules

- Treat `.codex/docs` as Single Source of Truth.
- Do **not** write `.codex/docs/experiments_log.md` (user updates it manually).
- Prefer minimal, reproducible notes: data version/date, eval metric, CV split, key params.

## Inputs / outputs

- Primary input: `.codex/docs/discussion_comments.md`
- Context inputs (for consistency checks):  
  - `.codex/docs/competition_context.md` (metric / constraints / data notes)
  - `.codex/docs/public_insights.md` (existing cross-cutting learnings)
  - `.codex/docs/notebook_digest.md` (per-notebook/thread pointers)
- Optional outputs:
  - `.codex/docs/public_insights.md` (append “discussion-derived” insights)
  - `.codex/docs/notebook_digest.md` (fill/update the discussion shortlist table)
  - `.codex/docs/discussion_index.md` (new compact index generated from the capture)

## Workflow

### 1) Triage: pick which threads to read

Fast paths:

- **Host / official updates first**: prioritize anything authored by `@deeppast` / `@ryanholbrook` (data updates, rescoring, evaluation clarifications).
- **High upvotes second**: threads with high `upvote` are usually “shared pain points” or “widely useful tricks”.
- **Recency third**: prefer the most recent when time is limited.

Use the bundled script to get a compact index from the large file:

```bash
python3 skills/discussion-insights-miner/scripts/summarize_discussion_comments.py \
  .codex/docs/discussion_comments.md --format md --top-k 50
```

Useful grep patterns (when you already know the topic):

```bash
rg -n '^## Entry: ' .codex/docs/discussion_comments.md
rg -n '@deeppast|@ryanholbrook' .codex/docs/discussion_comments.md
rg -n '<gap>|big_gap|determinative|\\{d\\}|\\{ki\\}|SacreBLEU|chrF|BLEU|rescore|LB' .codex/docs/discussion_comments.md
```

### 2) Extract: convert each chosen thread to “comparable insight”

For each selected `Entry: <id>`, write a compact record (don’t overquote; paraphrase and keep a few exact tokens when necessary):

- **What**: the claim/recommendation (1–2 lines)
- **Evidence**: which `Entry` and (optionally) which comment URL supports it
- **Where**: map to pipeline stage: `data` / `preprocess` / `model` / `train` / `infer` / `postprocess` / `eval`
- **Conditions**: data version/date, text normalization assumptions, decoding knobs, etc.
- **Risk / tradeoff**: what could break (metric sensitivity, mismatch with hidden test, etc.)
- **Next experiment candidate**: a concrete “toggle” the user can log/run (but do not write to `experiments_log.md`)

Always sanity-check against `.codex/docs/competition_context.md` (metric definition, code competition constraints, known data updates).

### 3) Persist: put learnings where they belong

#### A) Cross-cutting learnings → `.codex/docs/public_insights.md`

Append a dated section like:

- `## Discussion-derived insights (YYYY-MM-DD)`
  - bullets formatted as: `Insight → Evidence (Entry IDs) → Why it matters → Next experiment candidate`

Keep every bullet “comparable”: mention the lever (normalization / decoding / training recipe) rather than just “good/bad”.

#### B) Thread shortlist → `.codex/docs/notebook_digest.md`

Update the “ディスカッション・コメント一覧” table:

- “内容の一言”: the lever/issue (e.g., `<gap> normalization`, `LB rescore`, `determinative alignment`)
- “URL”: the discussion URL already captured per Entry
- “日付 / 要点 / 自分用メモ”: keep short, link to `Entry: <id>` for traceability

#### C) Optional compact index → `.codex/docs/discussion_index.md`

If the capture has grown too large to scan by hand, generate/update a compact index:

```bash
python3 skills/discussion-insights-miner/scripts/summarize_discussion_comments.py \
  .codex/docs/discussion_comments.md --format md --top-k 200 > .codex/docs/discussion_index.md
```

Then add a brief reference link in `.codex/docs/public_insights.md` (one line) so the index doesn’t become an orphan.


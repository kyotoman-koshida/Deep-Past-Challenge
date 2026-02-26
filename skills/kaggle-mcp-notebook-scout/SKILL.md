---
name: kaggle-mcp-notebook-scout
description: Use when asked to investigate Kaggle competition public notebooks using Kaggle MCP, prioritizing importance by upvotes (higher is better) and recency (newer is better). Produce a ranked shortlist with notebook refs, vote counts, and last run times; optionally persist results into this repo’s .codex/docs/notebook_digest.md and .codex/docs/public_insights.md.
---

# Kaggle MCP Notebook Scout

## Goal

Collect and rank public Kaggle notebooks for a competition. Rank primarily by `total_votes` and secondarily by recency derived from `last_run_time`.

## Workflow

### 1) Resolve competition slug (if needed)

If the user provides a competition name instead of a slug:

- Call `mcp__kaggle__search_competitions(search=...)`.
- Choose the best match and extract the competition slug from the competition URL.

### 2) Fetch candidate notebooks (votes + recency)

- Fetch by upvotes:
  - Call `mcp__kaggle__search_notebooks(competition=..., sortBy="voteCount", pageSize=100, page=1...)`.
  - Paginate until you collect `N_votes` (default 200) or results end.
- Fetch by recency:
  - Call `mcp__kaggle__search_notebooks(competition=..., sortBy="dateRun", pageSize=100, page=1...)`.
  - Paginate until you collect `N_recent` (default 200) or results end.

De-duplicate by `ref`, retaining: `ref`, `title`, `author`, `last_run_time`, `total_votes`.

### 3) Rank by votes + recency

Use a composite score that heavily favors votes and mildly favors recency:

- `vote_score = log1p(votes) / log1p(max_votes)`
- `recency_score = exp(-days_since_last_run / half_life_days)`
- `score = alpha * vote_score + (1 - alpha) * recency_score`

Defaults: `alpha=0.8`, `half_life_days=30`, `top_k=30`.

For deterministic ranking + Markdown output, write the merged candidates to JSON and run:

```bash
python3 skills/kaggle-mcp-notebook-scout/scripts/rank_notebooks.py notebooks.json --top-k 30 --alpha 0.8 --half-life-days 30
```

### 4) Verify the top candidates (recommended)

For the top `top_k` (or top 10 if moving fast), confirm details using:

- `mcp__kaggle__get_notebook_info(userName=..., kernelSlug=...)`

Use this to confirm `total_votes` and capture useful context (e.g., `enable_internet`, `enable_gpu`, `current_version_number`) before spending time reading.

### 5) Produce deliverables

Return a ranked shortlist as a Markdown table with:

- rank, `ref`, title, author, votes, last_run_time (UTC), score
- a 1-line “why it matters” note (very high votes vs very recent)

If operating in this repo, optionally persist:

- `.codex/docs/notebook_digest.md`: add an entry (date, competition slug, criteria, ranked list, and a “next reading plan”)
- `.codex/docs/public_insights.md`: after reading notebooks, write cross-cutting learnings

Do not create/append ops/infra logs.

## Script input format

`scripts/rank_notebooks.py` expects JSON like:

```json
[
  {
    "ref": "username/notebook-slug",
    "title": "Notebook title",
    "author": "Author name",
    "last_run_time": "2026-02-26T11:24:42.197Z",
    "total_votes": 123
  }
]
```

# Ops log

## 2026-02-28

### Added a Codex skill to mine captured Discussions

- Skill: `skills/discussion-insights-miner/`
- Purpose: triage + extract experiment-ready insights from `.codex/docs/discussion_comments.md`, optionally persisting summaries into `.codex/docs/public_insights.md` / `.codex/docs/notebook_digest.md`
- Helper script: `python3 skills/discussion-insights-miner/scripts/summarize_discussion_comments.py .codex/docs/discussion_comments.md --format md --top-k 50`

## 2026-02-27

### Kaggle official data download (Deep Past Challenge)

- Competition: `deep-past-initiative-machine-translation`
- Destination: `data/kaggle/deep-past-initiative-machine-translation/`
- Method: Kaggle MCP to obtain a signed download URL, then `curl` to fetch `archive.zip` and `unzip` it locally.
- Note: In the default sandboxed shell, DNS/network access was unavailable; the download required running `curl` with escalated permissions.

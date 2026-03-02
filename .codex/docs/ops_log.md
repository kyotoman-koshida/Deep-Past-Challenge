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

## 2026-03-01

### ByT5 CV notebook decode crash in Kaggle

- Symptom: running `notebooks/002/[3]dpc-starter-train-cv5-v3.ipynb` hit `ValueError: chr() arg not in range(0x110000)` during evaluation after ~40 minutes.
- Cause: `compute_metrics` called `tokenizer.batch_decode(preds)` with invalid ids (e.g., logits array, negative ids, or out-of-vocab ids). ByT5’s decode path can raise when given out-of-range values (internally uses `chr()`).
- Mitigation: created `notebooks/002/[4]dpc-starter-train-cv5-v4.ipynb` with a defensive `compute_metrics` that (a) converts logits via `argmax` when `preds.ndim==3` and (b) casts to `int64`, replaces negatives, and clips ids to `[0, vocab_size-1]` before decoding.

### Notebook naming conventions memo

- Consolidated the `notebooks/<NNN>/` naming rules into `.codex/docs/notebook_naming_rules.md` so Codex and humans can reference the same convention.

## 2026-03-02

### Colab A100 (40GB) for faster CV training + batch size scaling notes

- Target notebook: `notebooks/002/[3]dpc-starter-train-cv5-v4.ipynb` (ByT5-small, `MAX_LENGTH=512`, `fp16=False`, `per_device_*_batch_size=4`, `gradient_accumulation_steps=2`).
- Rule of thumb: max batch size is usually **~linear with VRAM** for the same model/seq_len. A100 40GB vs P100 16GB gives ~2.5× headroom → batch `4 -> ~8–12` if keeping FP32.
- Mixed precision on A100: switching to `bf16=True` (or `fp16=True`) typically halves activation memory, so the practical range often becomes `~16–24` (sometimes higher with gradient checkpointing), but generation-based eval (`predict_with_generate=True`, beams) can force a smaller `per_device_eval_batch_size`.
- Safer approach: keep `per_device_eval_batch_size` smaller than train batch (e.g. train=16, eval=4–8) and empirically search the max executable batch on a short warmup run (1–5% of data) before running full CV.
- Playbook (reusable): `.codex/docs/colab_porting_playbook.md`

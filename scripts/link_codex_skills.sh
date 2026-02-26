#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

SKILLS_SRC_DIR="$REPO_ROOT/skills"
SKILLS_DST_DIR="$CODEX_HOME/skills"

mkdir -p "$SKILLS_DST_DIR"

if [[ ! -d "$SKILLS_SRC_DIR" ]]; then
  echo "[ERROR] skills/ directory not found at: $SKILLS_SRC_DIR" >&2
  exit 1
fi

linked=0
skipped=0

for skill_dir in "$SKILLS_SRC_DIR"/*; do
  [[ -d "$skill_dir" ]] || continue
  skill_name="$(basename "$skill_dir")"

  # Only link directories that look like skills (have SKILL.md).
  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    echo "[SKIP] $skill_name (missing SKILL.md)"
    skipped=$((skipped + 1))
    continue
  fi

  ln -sfn "$skill_dir" "$SKILLS_DST_DIR/$skill_name"
  echo "[LINK] $skill_name -> $SKILLS_DST_DIR/$skill_name"
  linked=$((linked + 1))
done

echo "[OK] linked=$linked skipped=$skipped dst=$SKILLS_DST_DIR"


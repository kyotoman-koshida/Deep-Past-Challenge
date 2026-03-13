# 置換・正規化ルール整理（transliteration / translation）

最終更新: 2026-03-13

このリポジトリ内で散在している「置換・正規化（pre/post）」観点を、**入力（transliteration）**と**出力（translation）**に分けて一覧化する。

- 公式/host 推奨（@deeppast Entry `678899`）の一次メモ: `.codex/docs/discussion_comments.md`
- Dataset Instructions（公式の表記方針）: `.codex/docs/dataset_instructions.md`
- 実装例（推論ノート）: `notebooks/006/lb-35-9-ensembling-post-processing-baseline.ipynb`

> 注意: “学術的に正しい” 置換が LB で必ず有利とは限らないため、**host 推奨の test 整合**と、**ノートブック独自のクリーニング**を分けて扱う（ablation 前提）。

---

## 1) Transliteration（入力側）— 置換観点

### A. host（@deeppast）推奨の test 整合（Entry `678899`, 2026-02-26）

- **Gap 統一（欠損表現 → `<gap>`）**
  - 例: `x`, `[x]`, `…`, `(break)`, `(large break)`, `(n broken lines)` → `<gap>`
  - 連続 `<gap>` は 1 個に縮約（`<gap> <gap>` → `<gap>`）
- **決定詞（determinatives）の表記を test 側に寄せる**
  - 例: `(d)` → `{d}`, `(ki)` → `{ki}`, `(TÚG)` → `TÚG`
  - 実装上は「大文字決定詞はカッコを外す」「小文字決定詞は `{}` にする」等のルールで近似されることがある
- **長すぎる小数の短縮**（小数点以下 4 桁）
  - 例: `1.3333300000000001` → `1.3333`
- （任意）**音価記号の単純化**
  - 例: `Ḫ` → `H`, `ḫ` → `h`
- （任意）**略記の展開**
  - 例: `KÙ.B.` → `KÙ.BABBAR`
- （任意）**Unicode 下付き数字の正規化**
  - 例: `₀..₉` → `0..9`
- （任意）**小数→Unicode分数**
  - 例: `0.3333` → `⅓`, `0.6666` → `⅔`, `0.5` → `½` など

### B. Dataset Instructions に由来する観点（公式データの“意図”）

- **決定詞は `{}` で保持される**（分類子として意味を持つ可能性）
  - 例: `a-lim{ki}`, `A-mur-{d}UTU`
- **角括弧 `[]` は document-level で除去されることがある**
  - 例: `[KÙ.BABBAR]` → `KÙ.BABBAR`

### C. 実装例（`lb-35-9` ノート）に見られる追加の入力正規化

`notebooks/006/lb-35-9-ensembling-post-processing-baseline.ipynb` の `OptimizedPreprocessor` では、上の host 推奨をほぼ含みつつ、次のような追加の置換が入っている。

- **ASCII風の表記→ダイアクリティクス**
  - 例: `sz`→`š`, `s,`→`ṣ`, `t,`→`ṭ`
  - 例: 母音+`2/3` をアクセント表記へ（`a2`→`á` 等）
- **記号の単純化 / 除去**
  - `ʾ` を除去
  - ダッシュ類（`—/–`）を `-` に統一
  - 下付き `ₓ` を除去
- **`big_gap` / `<big_gap>` の扱い**
  - ノート内では `<big_gap>` / `big_gap` も `<gap>` に統一している（host 推奨では “最終的に `<gap>` へ統一” の方針に整合）

---

## 2) Translation（出力側）— 置換観点

### A. host（@deeppast）推奨（Entry `678899`, 2026-02-26）

- **注釈の除去（訳文側）**
  - `fem.`, `sing.`, `pl.`, `plural`, `(?)` など
  - `<< >>`, `< >`（ただし `<gap>` を除く）や、`..`, `?`, `x`, `xx` 等の stray marks
- **`/` で併記された代替訳の扱い**
  - 例: `"you / she brought"` → `"you brought"`（どちらか片方を選ぶ/落とす）
- **置換**
  - `PN` → `<gap>`
  - `-gold` → `pašallum gold`
  - `-tax` → `šadduātum tax`
  - `-textiles` → `kutānum textiles`
- **数値（分数/小数）正規化**
  - 一部の `x / 12` 系（shekel）を言い換え
  - 小数→Unicode分数（`0.5`→`½` 等）
- **月のローマ数字→整数**
  - 例: `month V` → `month 5`
- **除去しない（test にもある想定）**
  - `"`（直線の引用符）, `'`（アポストロフィ）
  - “意味のある” `?` / `!`

### B. 実装例（`lb-35-9` ノート）に見られる追加の出力整形

`notebooks/006/lb-35-9-ensembling-post-processing-baseline.ipynb` の `VectorizedPostprocessor` では、host 推奨をベースにしつつ、次が追加されている。

- **`<gap>` の整形**
  - `<gap>` の重複を縮約し、禁則文字除去の前後で `<gap>` を保護してスペースを付与（`" <gap> "`）
- **括弧・角括弧などの“禁則文字”を強めに削除**
  - `()`, `[]`, `<>`（`<gap>` を除く）, `+`, `;` 等を落とす（= かなり攻撃的なクリーニング）
- **スラッシュによる代替訳の片側除去**
  - 数字の分数 `1/12` 等は除外しつつ、語の代替 `/` を落とす
- **繰り返しの縮約**
  - 同一語の繰り返し、短いフレーズ繰り返し、句読点の繰り返しを縮約
- **引用符の扱い**
  - curly quotes（“ ” ‘ ’）だけを除去し、直線の引用符/アポストロフィは維持

---

## 3) 運用メモ（比較可能性）

- 置換は最低でも次の 2 系統に分けて ablation できる形に固定するのが安全:
  - `B`: host 推奨（test 整合）中心
  - `C`: ノートブック独自の追加クリーニング込み（攻撃的）
- “入力側の正規化” と “出力側の正規化” は評価（chrF++/BLEU）に与える影響が異なるため、**片側だけON/OFF**できる設計が望ましい。


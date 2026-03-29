# 1位 writeup 要約: Data Quality Dictates Everything

作成日: 2026-03-29

元記事:
- タイトル: `[DPC 1st] Data Quality Dictates Everything`
- URL: `https://www.kaggle.com/competitions/deep-past-initiative-machine-translation/writeups/dpc-1st-data-quality-dictates-everything`
- 著者: guoqingu team
- 公開: 2026-03-25
- 取得: Kaggle MCP `get_writeup_by_slug`

関連:
- 横断メモ: `.codex/docs/public_insights.md`
- ノート/議論ダイジェスト: `.codex/docs/notebook_digest.md`
- データ品質の実務メモ: `.codex/docs/data_quality_playbook.md`

## TL;DR

- 1位チームの主張はかなり明快で、**勝因はモデル細工よりデータ品質**にある。
- 最終系は **`byt5-xl` 11本のアンサンブル**。各モデルが **10候補**を出し、最後は **重み付き MBR** で 1 文ずつ最終候補を選ぶ。
- ただし writeup 本文でもっとも強調されているのは推論器ではなく、**PDF/書籍/OARE 由来の並列データをどう抽出し、どこを再抽出し、どこを手で確認したか**。
- 公式 `train.csv` は **完全に捨てた** と明言している。学習は自前で再構成した OCR ペア、LLM 疑似ラベル、LLM synthetic を主軸にしている。
- 後処理は最小限に留める方針で、Public LB に合わせた post-process は **過学習と shake-up の温床**だと見ている。

## 最終提出の構成

- ベスト提出そのものは **Public 41.5 / Private 43.2** だったが、締切時にはそれを未選択にしていた。
- 11本の `byt5-xl` モデルを使い、各モデルで以下の候補を生成:
  - beam search: `beam_size=8` から 4候補
  - sampling: 温度 `0.60`, `0.80`, `1.05` で各 2候補
  - 合計 10候補 / model
- 候補は共通後処理のあと、**chrF++ / BLEU / Jaccard / length reward** を混ぜた重み付き MBR で最終選択。
- 推論は `ctranslate2` で **`int8_float32` 量子化**した `byt5-xl` を事前コンパイルし、**T4 x 2** でデータ並列実行。9時間制限をほぼ使い切った。

## 勝因としてのデータ作成

### 1. OCR data

- 学習の中核は、ホスト配布 PDF と自前収集 PDF から作った **転写-英訳の文単位ペア**。
- 構造化しやすい書籍（AKT 系、ICK_4、Larsen_2002、Michel_2020、POAT など）は、次の 2 段で抽出:
  1. GLM-OCR + regex で **tablet/chapter -> page range** の `chapter_dict` を作る
  2. Gemini に **tablet 名 + 該当ページ画像 + prompt** を渡して、文単位の転写-訳文ペアを抽出
- ドイツ語/トルコ語訳しかない箇所は、さらに Gemini に英訳生成を依頼。
- 構造の悪い open-access テキスト群は、スクリーンショットを大量投入できる手製フロントエンドで半手動抽出。

### 2. LLM labeled data

- OARE 上の**未訳転写データ**を対象に、tablet 名と複数系列マッチで OCR 済みデータを除外。
- 辞書引きと類似例検索を組み合わせて、Gemini で英訳を付与。
- 本物データよりは弱いが、単独でも **Public 35.0 / Private 37.1** を出しており、補助データとしてはかなり強い。

### 3. LLM synthetic data

- `synth1`: 辞書 coverage gap を見て、**train に出ていない語彙だけ**を狙って synthetic 文対を生成。
- `synth2`: train からランダム抽出した 100 文を seed に、自由生成で 3-7 文対を作る。
- synthetic は補助的で、主役はあくまで OCR の高品質並列データという位置づけ。

## データセットの増築プロセス

### data1

- 完成日: 2026-03-08
- 件数: **29,908 文対 / 4,472 tablets**
- 特徴: LLM 抽出結果をそのまま使用し、**手修正なし**

### data2

- 完成日: 2026-03-14
- 件数: **30,931 文対 / 4,476 tablets**
- 改善方法:
  - data1 で 4-fold CV モデルを学習
  - 各 fold モデルで自分の train fold を推論
  - 学習集合なのに訳が大きくズレるサンプルを **error / hard sample** と見なす
  - cross-fold 平均 `geo_metric < 20` の tablet/chapter を 740 件抽出
  - それらを **再抽出 + 手確認** して data2 を作成

### data3

- 完成日: 2026-03-19
- 件数: **34,146 文対 / 4,837 tablets**
- 改善方法:
  - data2 の上に追加入力
  - `translation` と `transliteration` の長さ不整合、特に
    - 文字長差 `> 100`
    - 転写文字長 `> 500`
    を持つ 131 tablets を抽出
  - それらを **再抽出 + 手確認**

この流れは、単なる「データを足す」ではなく、**モデル自身を監査器として使い、怪しい tablet を再抽出するループ**になっている。ここが再現上の最重要ポイント。

## 使った学習データの規模

| データ名 | 完成日 | 件数 | 補足 |
| --- | --- | ---: | --- |
| `data1` | 2026-03-08 | 29,908 | OCR 抽出のみ、手修正なし |
| `data2` | 2026-03-14 | 30,931 | `geo_metric < 20` で再抽出 |
| `data3` | 2026-03-19 | 34,146 | 長さ不整合サンプルを再抽出 |
| `llmlabel` | 2026-03-20 | 21,759 | OARE 未訳データへの LLM 訳付け |
| `synth1` | 2026-03-08 | 9,685 | 辞書 coverage gap 補完 |
| `synth2` | 2026-03-20 | 4,972 | train seed の自由 synthetic |

## 11 モデルの学習組成

- 10本は `Seq2SeqTrainer`, `bs=64`, 3 epochs
- 1本だけは **data quality weighted loss**, `bs=48`, 4 epochs

| model | data1 | data2 | data3 | llmlabel | synth1 | synth2 | split | note | Public | Private |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| A | ✅ |  |  |  |  |  | all |  | 39.6 | 40.4 |
| B | ✅ |  |  | ✅ |  |  | all |  | 40.1 | 41.2 |
| C |  | ✅ |  |  |  |  | all |  | 39.7 | 40.9 |
| D |  | ✅ |  | ✅ |  |  | all |  | 40.3 | 41.3 |
| E |  |  | ✅ |  |  |  | all |  | 40.1 | 40.6 |
| F |  |  | ✅ | ✅ |  |  | all |  | 40.1 | 41.6 |
| G |  | ✅ |  | ✅ | ✅ | ✅ | all |  | 40.1 | 41.3 |
| H |  |  | ✅ | ✅ | ✅ | ✅ | all |  | 40.0 | 40.6 |
| I |  | ✅ |  |  |  |  | split | 9:1 train-valid split | 40.0 | 41.2 |
| J |  |  | ✅ |  |  |  | split |  | 40.4 | 41.1 |
| K |  | ✅ |  |  |  |  | split | quality weighted loss | 39.1 | 40.0 |

補足:
- writeup では **単体モデルでも金圏に入る**と述べている。
- 例として示された float16 `transformers` 推論の中では、`data2 + llmlabel + synth2` の all 学習が **Private 42.0** まで出ている。
- 一方で weighted loss モデル K は単体では弱く、**品質重み付けだけで万能ではない**。

## 学習と推論の示唆

### 1. checkpoint 選択は `eval_loss` 重視

- local valid と hidden test は分布・文体差があるので、3 epoch を超えたあとに `eval_bleu` / `chrf` が伸びても信用しづらいと判断。
- そのため 3 epoch 学習の checkpoint 選別は **`eval_loss` 基準**。
- 含意:
  - このチームは local metric の絶対値より、**汎化しやすい訓練挙動**を見ている。
  - data quality 改善が進むほど、loss のほうが安定指標になりやすいという前提。

### 2. 大きいモデルは、きれいなデータがあると効く

- 競技終盤 10 日ほどで `byt5-base -> byt5-large -> byt5-xl` に移行し、Public LB が明確に伸びたとしている。
- ただしこれは **十分でクリーンな訓練データがあること**が前提条件。

### 3. MBR は有効だが、前提は候補多様性

- beam 4候補 + sampling 6候補の混成。
- 単純に beam を増やすのでなく、**温度違い sampling を混ぜて候補空間を広げる**のがポイント。
- 選別は community の MBR selector を土台にした重み付き合意選択。

### 4. 推論実務の細部も効いている

- `test_df` を `char_length` 降順に sort
- full precision を少数回すより **量子化モデルを多数回す**
- `ct2` の事前コンパイルで **約 30 分短縮**
- MBR を **4 CPU cores** で並列実行

## 捨てた施策

writeup で「試したが本筋にしなかった」とされているもの:

- decoder-only モデル（Qwen, translate-gemma など）
- CPT（pretraining corpus の品質が悪く、掃除も難しいという判断）
- multilingual training（`akka->en/de/tr` prefix）
- context 利用
- test-time augmentation
- 前処理での強い正規化
  - Sumerian spelling の標準化
  - determinative format の標準化
  - 訳文中の括弧補足除去
- 後処理での強い置換
  - `onomasticon.csv` に基づく人名・地名標準化
  - repeated n-gram 除去

重要なのは、「全部ダメだった」より **このチームの改善余地はデータ品質のほうが圧倒的に大きかった**という優先順位。

## この repo への落とし込み

### すぐ取り入れられる考え方

- **`train.csv` の改良より、外部ソースから文単位並列データを組み直す**発想を優先する
- 学習モデルをそのまま **データ品質スキャナ**として使う
  - train 内再推論
  - `geo_metric` や長さ不整合で怪しい tablet を抽出
  - 怪しいまとまりだけ再抽出 / 再確認
- synthetic は量より役割分担
  - 辞書 coverage gap を埋める synthetic
  - 自由生成 synthetic
  - ただし OCR 本体より下位の補助に留める

### この repo で具体化したい実験候補

1. `published_texts.csv` / `publications.csv` / PDF 群から、**tablet 単位で再抽出候補を作るパイプライン**を整備する
2. 既存モデルで train を自己推論し、**低 `geo_metric` / 長さ不整合 / 数量表現崩れ**を持つ行をスコアリングして review queue を作る
3. `ct2` 量子化 + beam/sampling 混成 + weighted MBR を、既存の ByT5 submit notebook に移植する
4. checkpoint 選択で `eval_bleu` だけでなく **`eval_loss` 優先**の比較を追加する

## writeup からは分からない点

- `geo_metric` の厳密定義
- data quality weighted loss の式
- 各モデルの exact LR / max length / scheduler 詳細
- OCR / llmlabel / synth の混合比
- MBR の各 reward の重み
- 前処理コードの具体的な正規化規則の全量

ただし、詳細未公開でも方針は十分読み取れる。特に重要なのは次の 3 点:

1. **公式 `train.csv` 依存から離れる**
2. **怪しい tablet を再抽出するループを作る**
3. **post-process より data-process に時間を使う**

# 5位解法の日本語要約

原文: `solutions/5th/5th_place_solution.md`  
参照元: <https://www.kaggle.com/competitions/deep-past-initiative-machine-translation/writeups/5th-solution>

## 概要

5位チームの解法は、`ByT5-xl` を中心にした比較的素直な翻訳パイプラインですが、改善の主因はモデル構造ではなく **データ拡張の設計** にあります。  
特に重要なのは次の2本柱です。

1. 学術 PDF からの **VLM ベース抽出で約 2 万件の parallel pair を追加**
2. **pseudo-labeling と back-translation** で synthetic data を作り、段階的に fine-tuning

最終推論では test-time ensemble は使わず、**fold モデルの重み平均 + beam search** で提出しています。

## この解法の中心

### 1. PDF からの対訳抽出

公式 `train.csv` は 1,561 ペアしかないため、このチームは AKT シリーズや関連 scholarly PDF 20冊から **約 20,251 pair** を自前で構築しています。  
抽出パイプラインは 4 段階です。

1. excavation number を検出
2. `published_texts.csv` / `train.csv` と照合して参照情報を付与
3. VLM で transliteration と translation を抽出
4. トルコ語・ドイツ語部分を英訳

対象 PDF はレイアウトが2種類あり、それぞれ別 prompt を使っています。

- **side-by-side**
  英語版に多く、転写と訳が左右カラムに並ぶ形式
- **sequential**
  トルコ語・ドイツ語版に多く、転写ブロックの後ろに訳文が続く形式

また、tablet が複数ページにまたがる場合はページ画像を結合し、抽出失敗時は失敗理由を付けて再投入する、という再試行設計も入っています。

### 2. EvaCun の利用

外部コーパスとして [EvaCun (ORACC Akkadian Parallel Corpus)](https://zenodo.org/records/17220688) の **45k pair** を使っています。  
ここでは competition 用の標準前処理に加えて、**連続重複語の圧縮** を transliteration 側に適用しています。

例:

- 元: `... É-hi-il-la-na-te É-hi-il-la-na-te ma-a im-ma-te im-ma-te ...`
- 正規化後: `... É-hi-il-la-na-te ma-a im-ma-te ...`

つまり、EvaCun はそのまま混ぜるのではなく、ノイズを少し落としてから使っています。

### 3. synthetic data の生成

この解法の特徴は、forward だけでなく **reverse model（English → Akkadian）** も作って synthetic data を増やしている点です。

Stage 2 でやっていることは次の2つです。

- **Pseudo-label**
  `published_texts.csv` の transliteration に forward model で英訳を付ける
- **Back-translation**
  Qwen3.5-27B で translation-like English sentence を 10,000 件作り、それを reverse model で Akkadian に戻す

さらに back-translation を 100,000 件まで増やす実験もしており、原文では

- public: `-0.1`
- private: `+0.3`

と書かれています。  
つまり synthetic を増やせば必ず public が伸びるわけではないが、private 側には効く可能性がある、という整理です。

## 学習パイプライン

学習は 3 段階です。

### Stage 1: ベースモデル構築

1. `published_texts.csv` の transliteration で **continued pre-training**
2. EvaCun で fine-tuning
3. PDF 抽出データで fine-tuning

ここで forward model と reverse model の両方を作ります。

### Stage 2: synthetic data 生成

Stage 1 のモデルを使って pseudo-label と back-translation を作ります。

### Stage 3: 最終学習

1. EvaCun checkpoint から synthetic data で fine-tuning
2. その後、**tablet context 付き** で PDF データに再度 fine-tuning

context 形式は次のように、直前 2 行までを prepend する方式です。

```text
[context] <prev_line_1> [sep] <prev_line_2> [/context] <current_input>
```

この設計は、行単位翻訳であっても tablet 内の前文脈を与えた方がよい、という考え方です。

## 推論

推論では **CTranslate2** を使い、HuggingFace 推論より約 5 倍高速化したと書かれています。  
また、`int8_float32` 量子化と tensor parallelism により ByT5-xxl の推論も可能にしていたものの、量子化で `-0.1` 程度悪化し、かつ学習時間不足のため、最良提出では使っていません。

最終提出の基本方針は以下です。

- CV fold ごとのモデルを **weight averaging**
- `test.csv` の `line_start` を使って **前行 context を付加**
- **beam search** で decode
- test-time ensemble は使わない

## CV とアブレーション

CV は `train.csv` の 25% hold-out で、**source/target の長さ比で層化** しています。  
原文では validation loss が LB と比較的相関したとされ、オフラインの主指標として使っています。

アブレーション結果は次の通りです。

| 構成 | Private LB | Public LB |
| --- | ---: | ---: |
| PDF data only | 35.4 | 35.1 |
| + CPT | 38.9 | 38.0 |
| + EvaCun | 39.7 | 38.7 |
| + tablet context | 39.8 | 39.2 |
| + synthetic data | 40.7 | 40.2 |
| + 4 fold weight average | 40.8 | 40.1 |

ここから読み取れるのは次の点です。

- PDF 抽出データだけでは弱い
- `published_texts.csv` を使った CPT が大きく効く
- EvaCun 追加も明確に効く
- tablet context は小幅だがプラス
- synthetic data が最後の押し上げ要因
- decoding-time ensemble より **weight averaging** の方が安定

## 効かなかったもの

原文で明示的に失敗扱いされているのは次の項目です。

- **ReRanking**
  - LGBM reranker: CV は少し改善したが LB には効かず
  - fine-tuned LLM listwise reranker: CV/LB とも改善なし
- **別形式の back-translation**
  - sampling ベース生成は不発
  - tagged back-translation も不発
- **decoding-time ensemble**
  - 初期の弱いモデル同士では少し効いたが、モデルが強くなると効果が消えた

## この解法から読み取れること

5位解法は、1位や2位ほど巨大な独自データパイプラインではないものの、かなり再現しやすい構成です。  
特に重要なのは次の点です。

1. **PDF 抽出だけでは足りず、CPT と external corpus を組み合わせて初めて伸びる**
2. synthetic data は雑に混ぜるのではなく、**reverse model を用いた back-translation** として設計している
3. 行単位翻訳でも、**tablet の前文脈** が少し効く
4. test-time の複雑な ensemble より、**学習済み fold の weight averaging** の方が扱いやすい

## 実験に落とすなら

この repo 観点では、次の仮説が直接つながります。

- `published_texts.csv` だけを使った **CPT の有無** でどれだけ変わるか
- 既存の PDF 抽出資産に **EvaCun を足したときの増分** を確認する
- reverse model を作って **back-translation 1万件 / 10万件** の差を比較する
- `line_start` や前文脈を使って **tablet context あり/なし** を比較する
- decoding-time rerank より **weight averaging** を優先して試す

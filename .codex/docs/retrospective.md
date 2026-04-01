# 反省メモ（Retrospective）

目的: Deep Past Challenge の取り組みを振り返り、次の実験設計に効く「反省点」と「学び」を蓄積する。

運用:
- 反省点は「3位解法から得たもの」に限らない。自分の実装・評価・運用・意思決定の反省も追記する。
- 追加する場合は、下の `Entry` をコピーして日付・題名・要点を埋める。

参照:
- `solutions/2nd/2nd_place_solution.md`（2位 writeup のローカル保存）
- `solutions/3rd/3rd_place_solution.md`（3位 writeup のローカル保存）
- `.codex/docs/public_insights.md`（公開物からの横断メモ。3位要約も追記済み）
- 自分の現状パイプライン例: `notebooks/002/[2-10]dpc-starter-train-v6-colab.ipynb`

---

## Entry テンプレ

```
## Entry: YYYY-MM-DD 題名

### 0. 背景（状況）
- ...

### 1. 何が起きたか（事実）
- ...

### 2. 反省（原因・見落とし）
- ...

### 3. 学び（次に効く原則）
- ...
```

---

## Entry: 2026-03-29 3位解法から見えた「データ設計の観点不足」

### 0. 自分の状況（何をやっていたか）

- 学習データは「公式train + 手作業curation（ノイズ削減）」中心で、基本は `transliteration -> translation` の翻訳ペアを覚えさせる発想だった。
- 拡張は sentence alignment や `akk2en/en2akk` の方向反転など「量を増やす最低限」に留め、精度を上げるための“能力別の教材設計”はほぼ考えていなかった。

---

### 1. 3位解法の理解（データをどう見ているか）

3位解法は「データを綺麗にする」より先に「モデルに何の能力を入れるか」を分解していた。

- CPT（continued pretraining）: OA の基礎（語彙/文法/定型/曖昧性）を synthetic drill で先に教える
- FT（fine-tuning）: 高品質 scholar translation に寄せて最終スタイルを合わせる

ここで重要なのは、synthetic drill も最終的には全て `transliteration -> translation` の並列ペアに落ちており、lossや目的関数を変えるのではなく「ペアの性質」を変えている点。

---

### 2. 反省点（何が足りなかったか）

#### 2.1 「データ品質＝ノイズ除去」になっていた

- ノイズを減らすことは必要条件だが、十分条件ではない。
- ノイズ除去だけだと、モデルが苦手な能力（固有名詞、定型文、文法差、数量表現など）に“狙って”強くならない。

#### 2.2 「能力別のデータ設計」をしていなかった

3位解法の synthetic drill は、能力を分割して教材化している。自分はその設計をしていなかった。

- 語彙（多義語含む）: vocab drill / polysemy drill
- 文法: grammar drill（時制・人称・態・法・節構造の最小変更）
- 定型文: slot-fill template（借財/利子/証人/月名/数量/commodity 等）
- 固有名詞/一般語の曖昧性: PN vs word contrastive
- 長文・文書構造: synthetic tablet など

#### 2.3 「学習フェーズの役割分担」が弱かった

- 自分は基本的に「一回のfine-tuneで全部やる」発想だった。
- 3位は「CPTで言語基礎」「FTで訳文スタイル」という役割分担が明確で、学習データもフェーズごとに変えている。

#### 2.4 「量のスケール感」を過小評価していた

- 自分の学習は数万サンプル規模になりがちだった。
- 3位は CPT だけで数百万サンプル級（effective batch 128 * 18k steps）を回しており、同じ思想をやるならミニ版でも“量と多様性”が要る。

#### 2.5 「固有名詞が壊れる局面」への備えが薄かった

- 3位は CPT を回し過ぎると rare name が崩れて hallucination が出る、と明示して checkpoint を選んでいる。
- 自分は「学習を増やせば良い」寄りで、固有名詞の壊れ方（頻出名への吸着）を監視していなかった。

---

## Entry: 2026-03-30 1位解法から見えた「推論実務と checkpoint 判断の甘さ」

### 0. 背景（状況）

- これまで自分は、改善の中心を学習レシピや追加データに置きがちで、submit notebook の推論実装は「動けばよい」寄りだった。
- checkpoint 選択でも local `BLEU` / `chrF` の上下をかなり信用しており、`eval_loss` は補助的にしか見ていなかった。
- 並列化についても、「GPU を何枚使うか」の意識はあったが、GPU 推論と CPU 後処理を別系統で最適化する発想が弱かった。

### 1. 何が起きたか（事実）

- 1位チームは、最終提出を **`byt5-xl` 11本 + beam/sampling 混成 + weighted MBR** で組んでいた。
- その量の候補生成を 9 時間制限内に収めるため、`transformers.generate()` ではなく **CTranslate2 へ事前変換した `int8_float32` 量子化モデル**を使い、**T4 x 2 でデータ並列推論**していた。
- notebook 実装では、入力を長さ順に並べた後で奇偶交差に 2 分割し、同じモデルを `cuda:0` と `cuda:1` に載せ、**`Thread` 2本で同時推論**している。
- その後の MBR は GPU ではなく、**`joblib.Parallel(n_jobs=4)` で CPU 4 cores 並列**に回している。つまり GPU 推論最適化と CPU 後処理最適化を分けていた。
- checkpoint 選択では、local valid と hidden test の文体・分布差を重く見て、**3 epoch 学習の選別を `eval_bleu` / `chrf` ではなく `eval_loss` 基準**で行っていた。
- 背景には、`data1 -> data2 -> data3` と再抽出・手確認を回した結果、**データ品質が上がるほど loss が「ノイズへの過適合」より「学習の安定性」を反映しやすい**という前提がある。

### 2. 反省（原因・見落とし）

#### 2.1 submit notebook を「研究の付属物」と見ていた

- 自分は submit notebook を、学習済み重みを流すだけの最終工程として軽く扱っていた。
- 1位は逆で、推論実装そのものを競争力の一部として最適化していた。
- 特に、量子化、事前コンパイル、2GPU へのデータ分割、CPU での MBR 並列化まで含めて「提出を成立させる設計」を詰めていた点を軽視していた。

#### 2.2 「GPU を使う」と「推論全体を速くする」を混同していた

- GPU を増やせば速くなる、という粗い理解で止まっていた。
- 実際には、1位の notebook は
  - GPU: CT2 推論を `Thread` で 2 系統同時実行
  - CPU: MBR を `joblib.Parallel` で 4 cores 並列
  と役割分担している。
- 自分は GPU と CPU を一体でしか考えておらず、後処理まで含めたボトルネック分解が足りなかった。

#### 2.3 checkpoint 選択で local metric を信用し過ぎていた

- local `BLEU` / `chrF` の小さな差を、そのまま hidden test の差だと読みがちだった。
- 1位の考え方は、分布ずれがある以上、生成ベースの metric は valid の書きぶりに引っ張られやすく、後半 epoch の改善は信用し過ぎるべきでない、というものだった。
- 自分は「metric が上がったなら良い checkpoint」と短絡しやすく、汎化挙動の監視が弱かった。

#### 2.4 データ品質が上がった後の監視指標を整理していなかった

- データが汚い段階では `loss` も誤ラベルを真面目に追うので扱いづらいが、1位は再抽出と手確認でそこをかなり改善している。
- 自分は「データ品質が変わると、信用できる監視指標も変わる」という整理をしていなかった。
- そのため、データ改善後も惰性で同じ local metric を見続ける危険がある。

#### 2.5 候補生成の多様性と計算予算を同時に設計していなかった

- 1位は beam 4候補 + 温度違い sampling 6候補を 11 モデルに対して回し、その大量候補を weighted MBR でまとめている。
- これは「候補多様性が必要」という decoding 設計と、「その量を時間内で回す」という systems 設計が一体になっている。
- 自分は decode 設計と実行時間設計を別々に考えがちで、候補を増やす議論が submit 制約と繋がっていなかった。

### 3. 学び（次に効く原則）

- 提出 notebook は後工程ではなく、**精度と成立性を両立する本体の一部**として設計する。
- 並列化は「GPU を何枚使うか」ではなく、**GPU 推論と CPU 後処理を分けてボトルネックを潰す**観点で考える。
- `Thread` は「GPU/C++ ランタイムに仕事を投げる制御」に向き、`joblib.Parallel` は「CPU 上の独立 sample 処理」に向く。処理内容で並列化手段を選ぶ。
- local metric が hidden test をどこまで代表するかは、**split の作り方とデータ品質**に依存する。生成 metric だけで checkpoint を決め打ちしない。
- データ再抽出・手確認が進んだ段階では、`eval_loss` を **汎化しやすい訓練挙動の proxy**として比較対象に入れる。
- decode 設計は「beam/sampling/MBR の精度議論」だけで終えず、**量子化・事前変換・並列化を含む実行予算**まで含めて組む。

---

## Entry: 2026-03-31 2位解法から見えた「長さ設計と optimizer 理解の浅さ」

### 0. 背景（状況）

- このチャットで 2位解法を読んだあと、自分が特に引っかかったのは `768-byte chunk`, `chunk 境界の違いを augmentation にする`, `Adafactor の β₁=0.9`, `group_by_length=True` による勾配不安定化の説明だった。
- つまり今回は、解法全体よりも **長さ設計と optimizer の挙動理解** の浅さが露出した。

### 1. 何が起きたか（事実）

- 2位チームは sentence pair だけでなく、**連続文を 768-byte 以内の chunk に切って document-level 学習例**を作っていた。
- その説明として、「chunk 境界の違いを augmentation にする」と書いていた。
- さらに学習では `group_by_length=True` を使い、長さの近いサンプルをまとめる一方で、**勾配スケールが不安定になる副作用**があると説明していた。
- それに対する対策として、Adafactor のデフォルト寄り設定ではなく、**`β₁=0.9` を入れて momentum を持たせる**話が出ていた。

### 2. 反省（原因・見落とし）

#### 2.1 chunk を「単なる長さ制約の器」と見ていた

- 自分は chunk を、長文を `max_len` に収めるための切り方として見がちだった。
- そのため「同じ連続文でも、どこで窓を切るかを変えると別の学習例になる」という発想を、すぐには言語化できなかった。
- 実際には 2位解法の chunk は、切り捨て回避だけでなく、**前後文脈を変えながら同じ資料を複数の見え方で学習させる augmentation** になっている。

#### 2.2 Adafactor の `β₁` を“よくあるハイパラ”としてしか見ていなかった

- `β₁=0.9` を見ても、その場では「optimizer の調整項目」くらいの理解で止まりがちだった。
- しかし実際には、これは **一次モーメントの移動平均を持たせて更新に慣性を入れる** ためのパラメータで、今回の文脈では length bucket による step 間の揺れをならす役割だった。
- 自分は optimizer のパラメータを、loss を下げるための魔法の数字のように見がちで、**何の不安定性に対する処方箋か** を結び付けて理解する癖が弱かった。

#### 2.3 `group_by_length` の副作用を計算効率の裏面として捉え切れていなかった

- `group_by_length=True` について、自分は主に padding 削減や throughput 向上の利点を先に考えがちだった。
- でも 2位解法が示していたのは、長い batch が続く区間と短い batch が続く区間で、**1 step あたりの損失項の数や勾配ノルムの傾向が変わりやすい** という話だった。
- 自分は「長さで揃えると速い」までは分かっていても、**長さで揃えると勾配統計の時間変動が大きくなる** ところまで意識できていなかった。

#### 2.4 学習の不安定さを “モデルのせい” や “LR のせい” に寄せて見がちだった

- 勾配が荒れる理由を考えるとき、自分はまず LR や mixed precision、あるいはモデル規模を疑いがちだった。
- しかし今回の話では、**batch の構成自体が step ごとの勾配スケールを揺らしている**。
- つまり optimizer の問題というより、まず **データの並べ方と batching の問題** として見るべき場面がある。

### 3. 学び（次に効く原則）

- chunk は「長さ制限への対処」だけでなく、**文脈窓をずらして同じ資料を複数の学習例に変える手段**として考える。
- optimizer のハイパラは名前だけで覚えず、**どの不安定性に効くのか** を結び付けて理解する。
- `β₁` は Adafactor に慣性を持たせる項であり、今回のような **length bucket 起因の step 間変動をならす用途**で見る。
- `group_by_length=True` は throughput 改善だけでなく、**勾配分布の時間的偏り**を生む可能性がある前提で使う。
- 学習が荒れたときは LR やモデルだけでなく、**batch 構成、token 数、長さ bucket の並び**も原因候補として先に点検する。

---

## Entry: 2026-04-01 5位解法から見えた「synthetic data と推論実務のつなぎ方の甘さ」

### 0. 背景（状況）

- このセッションでは、5位 writeup を `solutions/5th/5th_place_solution.md` に保全し、日本語要約も `solutions/5th/5th_place_solution_ja_summary.md` に作成した。
- その過程で、`back-translation`, `Qwen3.5-27B を使った理由の推測`, `test-time ensemble と decoding-time ensemble の違い`, `weight averaging`, `CTranslate2` の役割を言語化した。
- さらに `solutions/5th/5th-solution.ipynb` を確認し、back-translation の実装は含まれず、**context 付き単一モデル推論 + CT2 実行 notebook** であることも確認した。

### 1. 何が起きたか（事実）

- 5位解法は、巨大な最終 ensemble よりも **PDF 抽出データ + EvaCun + synthetic data** を段階的に積み上げる構成だった。
- synthetic data は「何でも混ぜる」形ではなく、**reverse model（English -> Akkadian）を作って back-translation 用の擬似ペアを生成する**明確な設計になっていた。
- back-translation では、`Qwen3.5-27B` で translation-like English sentence を生成し、それを reverse model で Akkadian 側へ戻して学習データ化していた。
- さらに 10k だけでなく 100k まで増やす比較もしており、**public では悪化しても private では改善**するケースを確認していた。
- 推論では複数モデルを test-time / decoding-time に束ねるのではなく、**fold モデルを weight averaging して 1 本にまとめ、その単一モデルを CTranslate2 で高速実行**していた。
- notebook を見ると、実際に確認できたのは `context_num_prev=2`, `prepend_context=True`, `ct2_model_path`, `beam` 設定などで、**training や synthetic 生成の実装は notebook 外**にあった。

### 2. 反省（原因・見落とし）

#### 2.1 synthetic data を「追加データの一種」として雑に見ていた

- 自分は synthetic data を、既存ペアに後付けで足す“量増し”に近い発想で見がちだった。
- しかし 5位解法は、forward / reverse の役割を分け、**reverse model を介した back-translation を独立した学習段階として設計**していた。
- つまり synthetic は「足すか足さないか」ではなく、**どの向きのモデルで、どの文体の文を、どの段階で作るか**まで含めて設計すべきだった。

#### 2.2 「高品質な生成モデルを使えば良い」と短絡しやすかった

- Qwen3.5-27B を見たとき、自分はまず「GPT-5.4 / Claude / Gemini Pro の方が高品質では」と反応した。
- ただし 5位解法の文脈では、必要なのは“文学的に最良の英文”ではなく、**大量に・安定して・翻訳文らしい英文を作り、reverse model に流し込めること**だった。
- 自分は生成元 LLM の性能を単体で見がちで、**最終的なボトルネックが reverse model 側にある可能性**や、10k / 100k スケールでのコスト・反復性を十分に考えていなかった。

#### 2.3 ensemble 周りの用語と実務上の意味を曖昧に扱っていた

- `test-time ensemble`, `decoding-time ensemble`, `weight averaging` を、自分の頭の中でかなり近いものとして雑にまとめていた。
- しかし実際には、
  - test-time ensemble: 各モデルを別々に走らせて最後に統合
  - decoding-time ensemble: token ごとに複数モデルの確率を統合
  - weight averaging: **推論前に重みを平均して 1 モデル化**
  と全く違う。
- 5位解法の強みは、複雑な ensemble を避けて **1 モデル化した上で submit notebook を軽くした**点にあり、その区別を最初から意識できていなかった。

#### 2.4 CTranslate2 を「速くなるツール」以上に理解していなかった

- CTranslate2 についても、当初は「transformers より速い推論ランタイム」くらいの認識だった。
- だが 5位解法では、weight averaged 済みモデルを **CT2 形式へ変換し、tensor parallel や量子化も視野に入れて submit 実行性を確保する**位置づけになっていた。
- 自分は推論高速化を“最後の最適化”として見がちで、**モデル統合の方法と推論ランタイム選択が一体**だという見方が弱かった。

#### 2.5 writeup と notebook の役割分担を読み分ける意識が弱かった

- `solutions/5th/5th-solution.ipynb` を開く前は、back-translation 生成や reverse model 学習の痕跡まで notebook に入っているかもしれない、と期待していた。
- 実際には notebook は **推論用の薄い公開物**で、重要な training / data generation 部分は writeup にしか出ていなかった。
- 自分は「公開 notebook を見れば全工程が追える」と期待しがちで、**writeup は方針、notebook は提出実装、という分業**を前提に読む姿勢が足りなかった。

### 3. 学び（次に効く原則）

- synthetic data は量ではなく、**生成方向・生成元文体・投入段階**まで含めて設計する。
- back-translation では、英文生成 LLM の単体品質より、**大量生成の安定性・コスト・reverse model と組み合わせた最終品質**で評価する。
- ensemble を議論するときは、**予測統合なのか、token 時統合なのか、重み平均なのか** を明示して混同しない。
- weight averaging は「軽い ensemble 代替」ではなく、**submit 制約下で 1 モデルに圧縮する実務手段**として優先的に考える。
- CTranslate2 は単なる高速化ライブラリではなく、**量子化・並列化・単一モデル化と組み合わせて提出を成立させる推論基盤**として見る。
- 公開物を読むときは、**writeup は設計思想、notebook は最終実装** と役割分担している可能性を前提にし、両者を補完して解釈する。

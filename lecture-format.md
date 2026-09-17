# 講義輸出格式

逐字遵守。這份檔案決定讀者實際讀到的東西長什麼樣。一篇論文最多兩份講義：
`broad.md`（廣讀）與 `deep.md`（精讀），格式各自在下方定義；兩者共用「共通規則」。

問題區塊的出題與格式另見 `questions.md`。

---

# 共通規則

## 檔頭

front matter 是這份講義的 metadata 來源——不另寫 meta.json。欄位全部來自
`fetch.py` 輸出的 `meta`，缺的留空不要刪。

```markdown
---
type: reading
mode: broad
lecture_read: false
generated: claude
title: Attention Is All You Need
authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin]
year: 2017
venue:
doi:
arxiv: 1706.03762
url: https://arxiv.org/abs/1706.03762
tier: 1
created: 2026-09-15
---
```

- `mode` 為 `broad` 或 `deep`，與檔名一致。
- `lecture_read` 一律寫 `false`。讀者讀完後自己勾選；Obsidian 會把它顯示成核取方塊。
  重新產生講義時也重設為 `false`——內容換了，原本的「讀完」指的是舊內容。
- `generated: claude` 不可省略。它明示這是機器產物、可重生，與讀者自己寫的卡片不同。
- `tier` 不可省略：tier 1 代表公式與引用取自 LaTeX 原始碼、精確；tier 5–6 代表是從
  PDF 還原的，可能有誤。讀者有權知道自己在讀哪一種。
- 同一篇論文的兩份講義，front matter 除了 `mode`、`lecture_read`、`created` 以外必須一致。

**講義中不出現「第一層」「第二層」之類的層級字樣。** 章節骨架本身就是閱讀順序。

## 段落單元

```markdown
### 3.2.1　Scaled Dot-Product Attention

> We call our particular attention "Scaled Dot-Product Attention". The input
> consists of queries and keys of dimension $d_k$, and values of dimension
> $d_v$. We compute the dot products of the query with all keys, divide each
> by $\sqrt{d_k}$, and apply a softmax function to obtain the weights on the
> values.

**中文翻譯**　本文把採用的注意力機制稱為 Scaled Dot-Product Attention。輸入包含維度為
$d_k$ 的 query 與 key，以及維度為 $d_v$ 的 value。計算方式是把 query 與所有 key
做點積，各除以 $\sqrt{d_k}$，再經過 softmax 函數得到 value 的權重。

- **為什麼要除以 $\sqrt{d_k}$**　這是整段唯一不顯然的設計。點積的變異數隨 $d_k$
  線性成長，$d_k$ 大時點積會落在 softmax 的飽和區——梯度趨近於零，訓練停滯。除以
  $\sqrt{d_k}$ 把變異數壓回 $O(1)$。論文在腳註才提這件事，但它是這個機制能 work
  的前提。
- **與前人工作的關係**　Bahdanau et al. (2014) 的 additive attention 用一層
  前饋網路算相容性分數。理論複雜度相同，但點積能直接呼叫高度最佳化的矩陣乘法
  核心，實務上快得多。作者選點積是工程考量而非理論優勢。
```

| 部分 | 內容 | 紀律 |
|---|---|---|
| `> ` 引用塊 | 英文原文，逐字 | 不改寫、不節錄成摘要。原文長就整段放。 |
| `**中文翻譯**　` | 繁體中文翻譯 | 忠於原文，包括原文含糊之處。不補充、不解釋、不評論。 |
| 條列解說 | 每條以粗體小標題開頭 | 補上原文沒說的東西。 |

解說**一律**寫成「粗體小標題＋條列」，不加「解」之類的總標籤。翻譯是一整段文字、
解說是條列——排版本身區分兩者，所以「翻譯裡不夾解釋」才守得住。某段不需要解說時，
翻譯之後直接接下一個段落單元。

用粗體標籤而非標題，是為了不污染 Obsidian 大綱——大綱只該有章節。

### `> ` 引用塊中的引用巨集

LaTeX 路線的原文常夾著 `\citep`、`\citet`、`\citealp` 等巨集。這些**不逐字重現**：
巨集是原始碼，不是讀者讀到的東西——讀者在 `\citep{vaswani2017}` 這個位置實際讀到
的是渲染後的作者年份，所以渲染反而比照抄巨集更貼近「逐字」原本要擋住的東西
（改寫、節錄、摘要），兩者不矛盾。

渲染方式：從 `src/` 底下的 `.bib` 解析出對應條目，比照巨集自身的顯示形式輸出——
`\citep{vaswani2017}` 給括號形式 `(Vaswani et al., 2017)`，`\citet{vaswani2017}`
給行文形式 `Vaswani et al. (2017)`。

- 一條巨集掛多個 key、全部列出會淹掉句子時，寫第一個作者年份加「等」或「et al.」
  再加總數，例如 `(Brown et al., 2020 等 12 篇)`。
- key 在 `.bib` 裡查不到時，原樣保留巨集，不用猜的。

## 解說面向不是必填欄位

各文件列出的解說面向，依段落性質挑用得上的，用不上的整條不寫。寫死成模板的後果是
一整排「本段無」——純雜訊，會把真正有東西的段落淹掉。寧可某段只有一條，也不要湊滿。

## 分段單位

以**論文的自然段落**為單位。兩個調整：

- 連續的短過場段（一兩句話、只做承接）合併成一個單元
- 單一段落塞了多個獨立論點時可以拆開，但拆點要落在句號，不可切斷句子

判準是「這個單元值不值得配一份獨立的解說」。不值得就合併。

## 圖表單元

```markdown
### Figure 2　Scaled Dot-Product Attention 與 Multi-Head Attention

![[assets/attention-is-all-you-need/ModalNet-19.png]]

> (left) Scaled Dot-Product Attention. (right) Multi-Head Attention consists of
> several attention layers running in parallel.

**中文翻譯**　（左）Scaled Dot-Product Attention。（右）Multi-Head Attention 由數個
平行運行的注意力層組成。

- **怎麼讀**　左圖由下往上是資料流：Q 與 K 進 MatMul，Scale 即除以 $\sqrt{d_k}$，
  Mask 只在 decoder 用到⋯⋯
- **這張圖在證明什麼**　（或：這張圖不證明任何事，只是架構示意）
```

數據圖（折線、長條、散佈）的解說必須額外交代：兩軸各是什麼、哪一條線是本文方法、
差距多大才算有意義、以及這張圖有沒有被挑過（例如只報最好的一次跑）。

無法檢視的圖（`.pdf`／`.eps`）照實說明，改由 caption 與上下文解釋，不要假裝看過。

## 外部論文的寫法

講義中提到本篇以外的論文時，一律「作者 et al. (年份)」並附連結，例如
[Bahdanau et al. (2014)](https://arxiv.org/abs/1409.0473)。這些論文必須來自
`fetch.py --graph` 或通過 `fetch.py --verify`（見 SKILL.md〈Discipline〉），
查證不過的不寫。

## 反例（兩種文件皆適用）

- **翻譯裡夾解釋**——「⋯⋯再經過 softmax（一種把向量正規化成機率分布的函數）⋯⋯」。
  括號內容屬於解說。
- **解說只是把翻譯換句話說**——「這段在說注意力機制的計算方式」。沒有增加任何資訊。
- **出現「譯」「解」標籤或層級字樣**——已廢止。
- **腦補公式**——PDF 路線讀到 `x2` 就寫成 $x^2$。必須標 `⚠️ 此處公式從 PDF 抽取受損，無法確認原式`。
- **引用寫成編號**——「如 [12] 所示」。應寫成「如 Bahdanau et al. (2014) 所示」。
- **摘要式跳躍**——把三段原文併成一段翻譯。逐段對照的價值就在於逐段。
- **憑記憶列文獻**——延伸閱讀或脈絡區塊出現沒有經過 `--graph`／`--verify` 的論文。

---

# 廣讀文件 `broad.md`

目的：定位這篇論文——它回答什麼問題、讀懂它要先知道什麼、它的核心想法、它在研究
脈絡中的位置、接著該讀什麼。**深度以「能定位這篇論文」為限**，不處理推導與實驗細節。

## 骨架

```markdown
# Attention Is All You Need

> **來源**　arXiv:1706.03762 ｜ **保真度**　tier 1（LaTeX 原始碼，公式與引用為原文）
> **本篇在做什麼**　（兩句話，不是摘要的翻譯，是判斷）

## 論文全貌

### Abstract
### 1 Introduction
### 7 Conclusion

## 讀懂它需要先知道的

## 核心方法速覽

## 它在研究脈絡中的位置

### 繼承的工作
### 其他路線
### 後續發展

## 延伸閱讀

## 問題
```

「論文全貌」下的小節標題沿用論文自己的編號與名稱。

## 論文全貌

Abstract、Introduction、Conclusion 逐段做段落單元。解說聚焦**論證結構**：

- **在論文中的位置**——這段在論證鏈的哪一環
- **問題設定**——作者認為要解決的是什麼、為什麼現有方法不夠
- **宣稱的貢獻**——每項貢獻在正文哪一節被證明（只指路，不評斷證據強弱，那是精讀的事）
- **術語**——首次出現的術語，中英並列：`注意力機制（attention mechanism）`

## 讀懂它需要先知道的

論文沒寫、讀者不知道就會卡住的論文外知識。每項一個 `###` 小節：

```markdown
### BLEU 與 COMET

- **卡在哪裡**　§5 主結果只報 BLEU 與 COMET，兩者差距的解讀方向相反時不知道該信誰。
- **要懂到什麼程度**　知道 BLEU 是 n-gram 重疊率、對同義改寫不敏感；COMET 是以
  人工評分訓練的神經網路評分器。不必會算。
- **去哪裡補**　[Papineni et al. (2002)](https://aclanthology.org/P02-1040) §2；
  [Rei et al. (2020)](https://arxiv.org/abs/2009.09025) §1–2。
```

「要懂到什麼程度」不可省略：少了它，這一區會膨脹成一門課。

## 核心方法速覽

不逐段講。只挑**摘要主張直接依賴**的段落——通常是方法總覽段、主架構圖、那一條
核心公式——做段落單元。解說面向：

- **它做了什麼**——一句話講清楚機制
- **與對手差在哪**——跟最直接的替代做法比，關鍵差異是哪一個
- **看圖的方法**——主架構圖怎麼讀

推導、超參數、ablation 一律不講。

## 它在研究脈絡中的位置

**以這篇論文為中心**，不描繪整個研究領域。這一區沒有原文可引，以條列解說為主。
本小節包含三個 `###` 小節：繼承的工作、其他路線、後續發展。

### 繼承的工作

取自 `--graph` 的 `references` 中 `influential: true` 或 `intents` 含 `methodology` 者。每篇說明本篇借用或改良了什麼。

### 其他路線

解決同一問題的其他派別。每派一個粗體小標題，交代：核心主張、至少一篇查證過的代表論文、與本篇分歧在哪個假設上。派別的歸納屬評論，句子寫成「可歸為⋯⋯」而非事實陳述。

### 後續發展

取自 `citations`。`citations_complete` 為 `false` 時，本小節第一行寫：

```markdown
> 以下取自最新的 3000 篇引用（查詢日期 2026-09-15），不代表影響力排序。
```

數字與日期取自 `citations_scanned` 與 `fetched_on`。

`--graph` 回傳 `graph-unavailable` 但 `--verify` 仍可用時（混合失效）：
「繼承的工作」與「其他路線」改由本篇論文自己的參考文獻重建、每篇都跑過
`--verify`，寫法照常。但「後續發展」要的是後向引用本文的論文，只有 `--graph`
查得到，`--verify` 無法替代，因此這一小節不可留白，寫一行說明查不到的原因
（取自 `graph-unavailable` 的 `reason` 欄位）：

```markdown
> 本次無法取得後續引用本文的論文（原因：HTTP 429），此區從缺。
```

空白小節與被漏寫的小節，讀者分不出來，所以永遠寫這一行，不留空。

`--graph` 與 `--verify` 都無法使用時，整個「它在研究脈絡中的位置」只寫一行：

```markdown
> 本次無法查證外部文獻（Semantic Scholar 無法連線），此區從缺。
```

同樣的情況下，「延伸閱讀」也不畫表格——每一列都需要一篇查證過的論文，查證不到就沒有列可畫，畫出空表頭只會誤導讀者以為漏填。改成同樣形狀的一行：

```markdown
> 本次無法查證外部文獻（Semantic Scholar 無法連線），此區從缺。
```

## 延伸閱讀

```markdown
| 論文 | 為什麼讀 | 本篇之前或之後 | 建議 |
|---|---|---|---|
| [Neural Machine Translation by Jointly Learning to Align and Translate](https://arxiv.org/abs/1409.0473)（Bahdanau et al., 2014） | additive attention 的原型，本篇 §3.2 的比較對象 | 之前 | 廣讀 |
```

- 「建議」只有 `廣讀`／`精讀` 兩值。
- 連結優先 arXiv（`https://arxiv.org/abs/<id>`），其次 DOI（`https://doi.org/<doi>`）。
- 查證失敗者不列，不以警告標記代替。
- `--graph` 與 `--verify` 都無法使用時不畫表格，見前一節「它在研究脈絡中的位置」結尾的替代寫法。

## 問題

見 `questions.md`。

---

# 精讀文件 `deep.md`

目的：只談這篇論文。論述是否成立、每個設計決策為何如此、證據撐不撐得起主張。

## 骨架

```markdown
# Attention Is All You Need

> **來源**　arXiv:1706.03762 ｜ **保真度**　tier 1（LaTeX 原始碼，公式與引用為原文）
> **廣讀**　[broad.md](./broad.md)
> **核心主張**　（一句話）
> **最值得懷疑的地方**　（一句話——讀之前先立一個靶子）

## Abstract

## 1 Introduction

…（論文自己的章節，依原順序）

## 主張與證據

## 設計決策

## 問題
```

- `broad.md` 不存在時，「廣讀」一行寫 `無（可另跑 /ppread --broad）`。
- 連回廣讀用相對路徑 Markdown 連結 `[broad.md](./broad.md)`，不用 `[[broad]]`：
  每個論文資料夾都有同名的 `broad.md`，wikilink 無法唯一解析。
- 章節標題沿用論文自己的編號與名稱；Step 1 若縮小範圍，只寫選定的章節，
  「主張與證據」「設計決策」「問題」三區仍然要寫。

## 與 `broad.md` 的關係

- **`broad.md` 存在**：它講過的前置知識與研究脈絡不重講，需要時寫
  「見廣讀〈讀懂它需要先知道的〉」。
- **`broad.md` 不存在**：只在某段確實依賴某背景才讀得懂時，在該段補到該段所需的程度。
- 兩種情況下 Abstract 與 Introduction 都要重新做段落單元：「本文貢獻有三點」在精讀
  中是被檢驗的對象，不是導讀。

## 解說面向

| 面向 | 回答什麼 |
|---|---|
| **論證位置** | 這段支撐哪個主張，是前提、推論還是證據 |
| **設計動機** | 為什麼這樣做，不這樣做會壞在哪 |
| **替代方案** | 顯而易見的其他做法是什麼、為何未採用 |
| **公式拆解** | 每個符號是什麼、整體在算什麼、哪一項是關鍵 |
| **實驗設計** | 為什麼這樣切資料、這樣設 baseline，這個設計能／不能支持什麼結論 |
| **隱含假設** | 作者沒寫出來、結論卻依賴的前提 |
| **存疑之處** | 推論跳躍、證據不足、與已知結果衝突 |
| 術語、背景知識 | 輔助面向，只在 §「與 broad.md 的關係」允許時使用 |

## 批判的底線

- 每條批判指向具體位置（段落、表格、公式）。
  - ✗「樣本數偏少。」
  - ✓「Table 2 每個設定只跑一個 seed，最大差距 0.3 BLEU，不足以排除隨機波動。」
- 以「與某篇論文的結果衝突」為據時，那篇論文同樣要經過 `--graph`／`--verify`。

## 本節收束

每個 `##` 層級的論文章節結束時補一句：

```markdown
> **本節收束**　（這一節確立了什麼，下一節要用它做什麼）
```

## 主張與證據

把 Abstract 與 Introduction 裡的每一條主張，對應到正文的證據：

```markdown
| 主張 | 原文位置 | 證據 | 強度 | 落差 |
|---|---|---|---|---|
| 在 WMT 2014 英德翻譯上達到新的 state of the art | Abstract | Table 2 | 支持 | — |
| 訓練成本只有既有最佳模型的一小部分 | Abstract | Table 2 訓練成本欄 | 部分支持 | 成本以 FLOPs 估算，未報實際硬體時數的變異 |
```

「強度」只有四個值：`支持`／`部分支持`／`未支持`／`無對應證據`。
`支持` 時「落差」寫 `—`。

## 設計決策

每個決策一個 `###` 小節，依重要性排序：

```markdown
### D1　用 scaled dot-product attention 而非 additive attention

- **選擇**　相容性分數用點積並除以 $\sqrt{d_k}$。
- **放棄的替代方案**　additive attention（Bahdanau et al., 2014）；不縮放的點積。
- **作者的理由**　§3.2.1：「dot-product attention is much faster and more space-efficient in practice」。
- **證據**　§3.2.1 腳註的變異數論證；未見直接比較兩者翻譯品質的實驗。
- **撐不撐得起**　速度論點成立；「$d_k$ 大時不縮放會變差」只引用 Britz et al. (2017)
  的觀察，本篇沒有自己的 ablation。
```

作者沒說明理由時：

```markdown
- **作者的理由**　論文未說明。
- **推測**　⋯⋯（並交代這個推測的根據有多強）
```

一篇論文沒解釋自己的設計決策，本身就是精讀要挖出的資訊，不可被合理的補述掩蓋。

## 問題

見 `questions.md`。

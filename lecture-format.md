# 講義輸出格式

逐字遵守。這份檔案決定使用者實際讀到的東西長什麼樣。

## 檔頭

這份 front matter 是這篇論文**唯一**的 metadata 來源——不另外寫 meta.json。
欄位全部來自 `fetch.py` 輸出的 `meta`，缺的留空不要刪。

```markdown
---
type: reading
generated: claude
title: Attention Is All You Need
authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin]
year: 2017
venue:
doi:
arxiv: 1706.03762
url: https://arxiv.org/abs/1706.03762
tier: 1
created: 2026-09-12
---

# Attention Is All You Need

> **來源**　arXiv:1706.03762 ｜ **保真度**　tier 1（LaTeX 原始碼，公式與引用為原文）
> **本篇在做什麼**　（兩句話，不是摘要的翻譯，是判斷）
> **預設的背景知識**　（列出論文沒寫、但讀者不知道就會卡住的東西）
```

`generated: claude` 這欄不可省略。它明示這份檔案是機器產物、可重生，與 `notes/`
底下自己寫的卡片在性質上不同——後者不可重生，那才是卡片盒的核心資產。

`tier` 也不可省略：tier 1 代表公式與引用取自 LaTeX 原始碼、精確；tier 5–6 代表
是從 PDF 還原的，可能有誤。讀者有權知道自己在讀哪一種。

## 段落單元

骨架固定，三個部分依序出現：

```markdown
### 3.2.1　Scaled Dot-Product Attention

> We call our particular attention "Scaled Dot-Product Attention". The input
> consists of queries and keys of dimension $d_k$, and values of dimension
> $d_v$. We compute the dot products of the query with all keys, divide each
> by $\sqrt{d_k}$, and apply a softmax function to obtain the weights on the
> values.

**譯**　本文把採用的注意力機制稱為 Scaled Dot-Product Attention。輸入包含維度為
$d_k$ 的 query 與 key，以及維度為 $d_v$ 的 value。計算方式是把 query 與所有 key
做點積，各除以 $\sqrt{d_k}$，再經過 softmax 函數得到 value 的權重。

**解**

- **為什麼要除以 $\sqrt{d_k}$**　這是整段唯一不顯然的設計。點積的變異數隨 $d_k$
  線性成長，$d_k$ 大時點積會落在 softmax 的飽和區——梯度趨近於零，訓練停滯。除以
  $\sqrt{d_k}$ 把變異數壓回 $O(1)$。論文在腳註才提這件事，但它是這個機制能 work
  的前提。
- **與前人工作的關係**　Bahdanau et al. (2014) 的 additive attention 用一層
  前饋網路算相容性分數。理論複雜度相同，但點積能直接呼叫高度最佳化的矩陣乘法
  核心，實務上快得多。作者選點積是工程考量而非理論優勢。
```

### 骨架的三個部分

| 標記 | 內容 | 紀律 |
|---|---|---|
| `> ` 引用塊 | 英文原文，逐字 | 不改寫、不節錄成摘要。原文長就整段放。 |
| `**譯**　` | 中文翻譯 | 忠於原文，包括原文含糊之處。不補充、不解釋、不評論。 |
| `**解**` | 解說 | 補上原文沒說的東西。可以批評。 |

用粗體標籤而非標題，是為了不污染 Obsidian 大綱——大綱只該有論文自己的章節。

## 「解」的欄位不固定

**不要把下列面向當成必填欄位逐一填寫。** 依段落性質挑用得上的，用不上的整條不寫。

可用的面向：

- **在論文中的位置**——這段在論證鏈的哪一環，承接什麼、為下文鋪什麼
- **背景知識**——論文預設讀者已經知道、但實際上未必知道的東西
- **與前人工作的關係**——在反駁誰、改良誰、借用誰的想法
- **設計動機**——為什麼這樣做而不是更顯然的替代方案，不這樣做會壞在哪
- **實驗設計**——為什麼這樣切資料、這樣設 baseline，這個設計能／不能支持什麼結論
- **公式拆解**——每個符號是什麼、整體在算什麼、哪一項是關鍵
- **術語**——首次出現的術語，中英並列
- **存疑之處**——推論跳躍、實驗不支持結論、與已知結果衝突

寫死成模板的後果是一整排「本段無」。那是純雜訊，而且會把真正有東西的段落淹掉。寧可某段只有一條「解」，也不要湊滿六條。

## 分段單位

以**論文的自然段落**為單位。兩個調整：

- 連續的短過場段（一兩句話、只做承接）合併成一個單元
- 單一段落塞了多個獨立論點時可以拆開，但拆點要落在句號，不可切斷句子

判準是「這個單元值不值得配一份獨立的解說」。不值得就合併。

## 圖表單元

```markdown
### Figure 2　Scaled Dot-Product Attention 與 Multi-Head Attention

![[attention-is-all-you-need/ModalNet-19.png]]

> (left) Scaled Dot-Product Attention. (right) Multi-Head Attention consists of
> several attention layers running in parallel.

**譯**　（左）Scaled Dot-Product Attention。（右）Multi-Head Attention 由數個
平行運行的注意力層組成。

**解**

- **怎麼讀**　左圖由下往上是資料流：Q 與 K 進 MatMul，Scale 即除以 $\sqrt{d_k}$，
  Mask 只在 decoder 用到⋯⋯
- **這張圖在證明什麼**　（或：這張圖不證明任何事，只是架構示意）
```

數據圖（折線、長條、散佈）的「解」必須額外交代：兩軸各是什麼、哪一條線是本文方法、
差距多大才算有意義、以及這張圖有沒有被挑過（例如只報最好的一次跑）。

無法檢視的圖（`.pdf`／`.eps`）照實說明，改由 caption 與上下文解釋，不要假裝看過。

## 章節之間

每個大章節結束時補一句銜接：

```markdown
> **本節收束**　（這一節確立了什麼，下一節要用它做什麼）
```

只在大章節（`##` 層級）結束時寫，不是每個小節都寫。

## 反例

以下是不合格的輸出：

- **翻譯裡夾解釋**——「⋯⋯再經過 softmax（一種把向量正規化成機率分布的函數）⋯⋯」。
  括號內容屬於「解」。
- **解只是把翻譯換句話說**——「這段在說注意力機制的計算方式」。這沒有增加任何資訊。
- **腦補公式**——PDF 路線讀到 `x2` 就寫成 $x^2$。必須標 `⚠️ 此處公式從 PDF 抽取受損，無法確認原式`。
- **引用寫成編號**——「如 [12] 所示」。應寫成「如 Bahdanau et al. (2014) 所示」。
- **摘要式跳躍**——把三段原文併成一段翻譯。逐段對照的價值就在於逐段。

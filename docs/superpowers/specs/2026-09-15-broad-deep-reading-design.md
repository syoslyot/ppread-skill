# 廣讀／精讀雙模式設計

- 日期：2026-09-15
- 目標版本：`0.2.0`
- 分支：`feature/broad-deep-reading`（自 `develop`）

## 1. 動機

`v0.1.0` 的講義是線性的：從 Abstract 逐段讀到 Appendix。實際閱讀時，先看全貌、再補背景、最後才進核心方法的順序效果更好；而且讀者的需求分成兩種，線性講義同時滿足不了：

- **廣讀**：定位這篇論文——它回答什麼問題、需要哪些論文外的知識、在研究脈絡中繼承誰、與誰對立、之後該讀什麼。
- **精讀**：只談這篇論文——論述是否成立、每個設計決策為何如此、證據撐不撐得起主張。

兩種模式都要出題讓讀者作答，並附參考答案，讓讀者量出自己的思考與參考答案的落差。

## 2. 範圍

**包含**

- 兩份獨立文件 `broad.md`、`deep.md`，取代 `lecture.md`
- 每份文件結尾的問題區塊，參考答案預設摺疊
- 以引用網路與標題查證為根據的外部文獻（`fetch.py --graph`、`--verify`）
- 每份文件的閱讀完成標記 `lecture_read`，以及 `--list` 與 Obsidian Bases 視圖
- 寫作期間的暫存檔名 `<mode>.part.md`，用於中斷偵測

**不包含**

- 代寫 literature note 或 permanent note（產品邊界不變，見 §10）
- 舊版 `lecture.md` 的自動轉換
- 閱讀日期、次數、進度等額外追蹤欄位
- 整個研究領域的藍圖（屬於讀者自己的 structure note）

## 3. 呼叫與模式判斷

```
/ppread [--broad | --deep] <source>
/ppread --list [dir]
```

模式用 flag 指定，不用裸關鍵字：`<source>` 可以是標題，`/ppread deep residual learning ...` 的 `deep` 會被誤吃成模式。flag 由 agent 解析，不傳給 `fetch.py`。

`fetch.py` 在所有已知 `workdir` 的 route 回傳 `docs`（見 §8.1），agent 依下表決定動作：

| `docs` 狀態 | 不帶 flag | `--broad` | `--deep` |
|---|---|---|---|
| broad、deep 皆 `absent` | 寫 broad | 寫 broad | 寫 deep |
| 只有 broad | 寫 deep | 已存在，停止 | 寫 deep |
| 只有 deep | 寫 broad | 寫 broad | 已存在，停止 |
| 兩者皆有 | 停止 | 停止 | 停止 |
| 目標模式為 `partial` | 詢問續寫或重寫 | 同左 | 同左 |

- 「已存在，停止」時回報檔案位置。重新產生只在讀者明確要求時執行：刪除舊檔、重寫、`lecture_read` 重設為 `false`，並在回報中說明。
- 舊版 `lecture.md`（`docs.legacy: true`）不擋路，可與新文件並存。
- 續寫：從 `.part.md` 最後一個 `##` 標題往後截斷並重寫該區塊。寫作一次一個 `##` 區塊，中斷時只有最後一個可能不完整。

## 4. 共通格式

### 4.1 Front matter

```yaml
---
type: reading
mode: broad            # broad | deep
lecture_read: false
generated: claude
title: Attention Is All You Need
authors: [...]
year: 2017
venue:
doi:
arxiv: 1706.03762
url: https://arxiv.org/abs/1706.03762
tier: 1
created: 2026-09-15
---
```

- 兩份文件各帶完整 front matter，皆由同一次 fetch 的 `meta` 產生。這不違反「不另寫 `meta.json`」的原則：當初否決的是「一份機器產物、一份會被手改」的同步問題，兩份都可重生。
- `lecture_read` 用 snake_case：Bases 公式讀不到含 `-` 的屬性鍵，且 Bases 會把空白與連字號正規化為底線。名稱指涉「這份講義」，不是「這篇論文」——一篇論文有兩份講義各自標記。
- `true`／`false` 值讓 Obsidian 將該屬性判為 Checkbox 類型，讀者在 Properties 區塊直接點選。

### 4.2 段落單元

```markdown
### 3.2.1　Scaled Dot-Product Attention

> We call our particular attention "Scaled Dot-Product Attention". ...

**中文翻譯**　本文把採用的注意力機制稱為 Scaled Dot-Product Attention。⋯⋯

- **為什麼要除以 $\sqrt{d_k}$**　⋯⋯
- **與前人工作的關係**　⋯⋯
```

- 不再有「譯」「解」標籤。翻譯是一整段文字，解說一律是「粗體小標題＋條列」；排版本身即區分兩者，「翻譯與解說分離」的紀律不變。
- 解說面向不是必填欄位，用不上的整條不寫（沿用 `v0.1.0` 規則）。
- 分段單位、圖表單元、PDF 公式受損標記、引用寫名不寫編號：沿用 `v0.1.0` 規則。

### 4.3 文件內不出現層級字樣

不寫「第一層」「第二層」等字樣。章節骨架即是閱讀順序。

## 5. 廣讀文件 `broad.md`

### 5.1 骨架

```markdown
# <論文標題>
> **來源** ｜ **保真度** ｜ **本篇在做什麼**（兩句話判斷）

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

「研究脈絡」排在「核心方法速覽」之後：比較路線之前，讀者須先知道這篇做了什麼。

### 5.2 各區塊

**論文全貌**　Abstract、Introduction、Conclusion 逐段雙語。解說聚焦論證結構：問題、宣稱的貢獻、每項貢獻在正文何處被證明。不評斷證據強度（精讀的工作）。

**讀懂它需要先知道的**　論文未寫、讀者須知道的論文外知識。每項交代：

1. 為什麼需要——卡在論文哪裡
2. **懂到什麼程度**——例：「知道 BLEU 是 n-gram 重疊率、對同義改寫不敏感即可，不必會算」
3. 去哪裡補——引用須經查證（§7）

第 2 點是廣讀與教科書的分界，缺了它此區塊會膨脹成一門課。

**核心方法速覽**　只挑摘要主張直接依賴的段落——通常是主架構圖、方法總覽段、核心公式——做雙語對照。深度以「能說出它做了什麼、與對手差在哪」為限；推導、超參數、ablation 不講。

**它在研究脈絡中的位置**　以這篇論文為中心，不描繪整個領域：

- **繼承的工作**：取自 `--graph` 的 `references` 中 `influential: true` 或 intent 含 `methodology` 者，說明借用或改良了什麼。
- **其他路線**：解決同一問題的其他派別。派別歸納可依賴模型知識，但標示為評論；每派至少一篇查證過的代表論文，並指出雙方分歧在哪個假設。
- **後續發展**：取自 `citations`。`citations_complete: false` 時明寫「以下取自最新的 N 篇引用，不代表影響力排序」並附 `fetched_on`。

每份廣讀從自己的視角寫脈絡，彼此不會因劃分方式不同而矛盾；跨論文的領域地圖留給讀者。

**延伸閱讀**

```markdown
| 論文 | 為什麼讀 | 本篇之前或之後 | 建議 |
|---|---|---|---|
| [Neural Machine Translation by Jointly Learning to Align and Translate](https://arxiv.org/abs/1409.0473) (Bahdanau et al., 2014) | additive attention 的原型，本篇 §3.2 的比較對象 | 之前 | 廣讀 |
```

只列查證通過者，每篇附 arXiv 或 DOI 連結。查證失敗者不列，不以警告標記代替——警告標記會被習慣性忽略。

## 6. 精讀文件 `deep.md`

### 6.1 骨架

```markdown
# <論文標題>
> **來源** ｜ **保真度** ｜ **廣讀**　[broad.md](./broad.md)（不存在時寫「無」）
> **核心主張**（一句話）｜ **最值得懷疑的地方**（一句話）

## Abstract
## 1 Introduction
…（論文自己的章節，逐段雙語）
## 主張與證據
## 設計決策
## 問題
```

- 連回廣讀用相對路徑 Markdown 連結。每個資料夾都有同名 `broad.md`，`[[broad]]` 無法唯一解析。
- 大章節結束時保留「本節收束」一句。

### 6.2 與 `broad.md` 的關係

- **存在**：先讀它；已講過的前置知識與脈絡不重講，需要時寫「見廣讀〈讀懂它需要先知道的〉」。
- **不存在**：照常寫；只在某段確實依賴某背景才讀得懂時，在該段解說補到該段所需程度。開頭加一行提示可另跑 `--broad`。
- 兩種情況皆涵蓋全文，含 Abstract、Introduction 的重新翻譯與分析：「本文貢獻有三點」在精讀中是被檢驗的對象。Step 1 仍可縮小範圍。

### 6.3 解說面向

| 面向 | 回答什麼 |
|---|---|
| 論證位置 | 這段支撐哪個主張，是前提、推論還是證據 |
| 設計動機 | 為什麼這樣做，不這樣做會壞在哪 |
| 替代方案 | 顯而易見的其他做法是什麼、為何未採用 |
| 公式拆解 | 符號、整體在算什麼、關鍵項 |
| 實驗設計 | 此設定能／不能支持什麼結論 |
| 隱含假設 | 作者未明寫、結論卻依賴的前提 |
| 存疑之處 | 推論跳躍、證據不足、與已知結果衝突 |

「術語」「背景知識」降為輔助面向（見 §6.2）。

### 6.4 主張與證據

把 Abstract 與 Introduction 的每條主張對應到正文證據：

```markdown
| 主張 | 原文位置 | 證據 | 強度 | 落差 |
|---|---|---|---|---|
| 在低資源語對上優於 X | §1 貢獻 2 | Table 2 | 部分支持 | 只測 3 個語對，皆為印歐語系 |
```

「強度」限四值：`支持`／`部分支持`／`未支持`／`無對應證據`。

### 6.5 設計決策

```markdown
### D1　用 LoRA 而非 full fine-tuning
- **選擇**　⋯⋯
- **放棄的替代方案**　full fine-tuning、adapter
- **作者的理由**　§3.2：「⋯⋯」
- **證據**　Table 3 ablation（§6.1）
- **撐不撐得起**　只比了 7B，外推到 70B 無實驗支持
```

作者未說明理由時，「作者的理由」寫 `論文未說明`；推測的理由另起一行標 `**推測**`，並交代支持該推測的證據強度。一篇論文未解釋自己的設計決策，本身就是精讀要挖出的資訊，不可被合理的補述掩蓋。

### 6.6 批判的底線

- 每條批判指向具體位置。「樣本數偏少」不算；「Table 2 每設定只跑一個 seed、差距 0.3 BLEU」才算。
- 以「與某篇論文結果衝突」為據時，該論文同樣須經 §7 查證。

## 7. 外部文獻查證紀律

講義中出現的每一篇外部論文，只能來自：

1. `fetch.py --graph` 的輸出；或
2. `fetch.py --verify` 回報 `status: exact`。

- `mismatch` 附帶的 `candidate` 不得採用。允許「很接近應該就是」等於重開憑感覺的通道；記錯標題導致真實論文被漏列的 false negative 可接受。
- `graph-unavailable` 時：延伸文獻改從論文自身 bibliography 挑選（tier 1 的 `.bib` 精確），每篇仍須通過 `--verify`。`--verify` 也無法使用時，脈絡區塊明寫「本次無法查證外部文獻」，不列任何論文。
- 不存在退回憑記憶列文獻的路徑。

理由：憑記憶產生的文獻清單常見作者、年份或標題錯一項，甚至整篇不存在。這與 `v0.1.0` 禁止「依上下文腦補 PDF 公式」同構——產物讀來合理而內容錯誤；放在「延伸閱讀」中傷害更大，因為讀者會照單去找。

## 8. `fetch.py` 變更

維持單一檔案、僅標準函式庫、stdout 一律 JSON。預估由 774 行增至約 950 行。未拆出 `graph.py`：拆檔需多部署一份，且 import 路徑依賴部署位置，換來的只是檔案較短。

### 8.1 Front matter 掃描泛化

```python
def front_matter(f: Path) -> dict | None   # 任一 .md 的 key: value 掃描，沿用現行解析
def lecture_docs(workdir: Path) -> dict    # 讀 broad(.part).md、deep(.part).md、lecture.md
def folder_conflict(workdir, meta, slug)   # 任一份文件與 meta 不符 → conflict
```

- 取代現行 `lecture_identity()`。衝突判斷改為「任一份不符即衝突」，`occupant` 指出是哪個檔案。
- 回傳欄位：

  ```json
  "docs": {"broad": "read", "deep": "partial", "legacy": false}
  ```

  `broad`／`deep` ∈ `absent`／`partial`／`unread`／`read`。`partial` 由 `<mode>.part.md` 存在判定（同時存在正式檔與暫存檔時以 `partial` 為準）；`unread`／`read` 由 `lecture_read` 判定。
- `adopt_local()` 的「資料夾已有其他檔案」檢查，排除清單擴為 `broad.md`、`deep.md`、`broad.part.md`、`deep.part.md`、`lecture.md`。

### 8.2 `--graph <arXiv ID | DOI | 標題>`

**流程**

1. `identify()` 分類：arXiv → `ARXIV:<id>`；DOI → `DOI:<doi>`；標題 → 先打 `GET /graph/v1/paper/search/match`，`_norm_title()` 完全相等才繼續。本機路徑不接受（agent 改傳 `meta` 中的 ID 或標題）。
2. `GET /paper/{id}?fields=title,year,externalIds,citationCount,referenceCount`——確認解析並取得被引總數（`citations` endpoint 不回傳總數，已實測）。
3. `GET /paper/{id}/references?limit=1000&fields=title,year,externalIds,citationCount,isInfluential,intents`，一頁。
4. `GET /paper/{id}/citations?limit=1000&offset=…&fields=同上`，最多 3 頁。
5. 本機排序：`isInfluential` 優先，再依 `citationCount` 降序。references 全數回傳，citations 回傳前 50。

**已實測的 API 行為**（2026-09-15）

- `references` 每筆帶 `isInfluential` 與 `intents`（`background`／`methodology`／`result`）。
- `citations` 依時間新到舊排列，無法依被引數排序；`offset + limit` 須 < 10000，超過回 `{"error":"offset + limit must be < 10000"}`。
- 無 API key 時連續第三次請求即回 429。

**取 3 頁的理由**：9 頁是上限，但無 key 下 9 次請求加 backoff 可能耗時數分鐘；且結果由新到舊，後續頁只是更多近期論文，補不回高影響力的後續工作。被引數在 3000 以下的論文可完整取得。

**輸出**

```json
{
  "route": "graph",
  "paper": {"title": "...", "year": 2017, "arxiv": "1706.03762", "doi": ""},
  "references": [{"title": "...", "year": 2014, "arxiv": "1409.0473", "doi": "",
                  "citations": 30000, "influential": true, "intents": ["methodology"]}],
  "citations": [],
  "citation_count": 170000,
  "citations_scanned": 3000,
  "citations_complete": false,
  "fetched_on": "2026-09-15"
}
```

**失敗處理**

| 狀況 | 行為 |
|---|---|
| 解析不到論文 | `{"route": "graph-unavailable", "reason": "not found"}` |
| 重試用盡仍 429 或網路錯誤 | `{"route": "graph-unavailable", "reason": "<錯誤>"}` |
| references 成功、citations 中途失敗 | 回傳已取得部分，`citations_complete: false`，加 `citations_error` |

以上皆 exit 0，與既有 route 慣例一致。

**連線節奏**：沿用 `get()` 的 exponential backoff，另於連續請求間固定間隔 1 秒（保守選擇，非官方數字）。選用環境變數 `PPREAD_S2_API_KEY`：設定時加 `x-api-key` 標頭以取得獨立配額，命名比照 `PPREAD_CONTACT`；未設定時照常運作。此 key 同樣適用於既有的 `s2_lookup()`。

### 8.3 `--verify "<標題>" ["<標題>" ...]`

- 單次上限 25 個標題，超過 exit 2。
- 每個標題打一次 `search/match`，以 `_norm_title()` 比對。

```json
{"route": "verify", "results": [
  {"query": "...", "status": "exact", "title": "...", "year": 2014, "arxiv": "1409.0473", "doi": ""},
  {"query": "...", "status": "mismatch", "candidate": "..."},
  {"query": "...", "status": "not-found"},
  {"query": "...", "status": "error", "reason": "HTTP 429"}
]}
```

`not-found`（可能不存在）與 `error`（本次無法查證）分開：講義處理相同（不列），但回報讀者時說明是哪一種。

### 8.4 `--list [dir]`

- 無 `dir` 時掃描設定的 library；未設定且未給 `dir` 時回傳既有的 `needs-output-config`。
- 只掃一層子資料夾，每個資料夾讀 `lecture_docs()`；無任何講義、只有原始檔的資料夾也列出。
- 輸出 JSON，由 `/ppread --list` 轉表格；不做 `--status` 篩選旗標，篩選由 agent 依要求處理。
- 本機路線建在各處的論文不在 library 中，需以 `--list <dir>` 指定。刻意不建立全域登錄檔——那會是另一個需同步的真相來源。

```json
{"route": "list", "library": "/abs/papers", "papers": [
  {"slug": "attention-is-all-you-need", "title": "...", "year": "2017", "tier": "1",
   "broad": "read", "deep": "unread", "legacy": false}
]}
```

### 8.5 `papers.base`

網路路線首次在 library 建立 `workdir` 時，若 library 根目錄無 `papers.base` 則寫入；已存在則永不覆寫（讀者可能已自訂）。本機路線與 `--list` 不建立。

```yaml
filters:
  and:
    - 'type == "reading"'
    - 'generated == "claude"'
views:
  - type: table
    name: 未讀講義
    filters:
      and:
        - 'lecture_read != true'
    order:
      - title
      - mode
      - year
      - lecture_read
  - type: table
    name: 全部講義
    order:
      - title
      - mode
      - year
      - lecture_read
    groupBy:
      property: note.mode
      direction: ASC
```

- 語法依 Obsidian Help〈Bases syntax〉。全域篩選用屬性而非資料夾，使 vault 內本機路線的講義也入列，且不誤抓讀者其他 `type: reading` 的筆記。
- **未驗證**：`lecture_read != true` 的布林字面值寫法，官方語法頁無範例。實作時須在 Obsidian 實開確認；不成立則改為 `not` 包 `lecture_read == true`。
- 舊版 `lecture.md` 無 `mode`、`lecture_read`，會出現在「未讀講義」且 `mode` 空白；`.part.md` 亦會出現。兩者確實是未讀，可接受。

## 9. 問題區塊與 `questions.md`

### 9.1 結構

固定題在前（題號與題目跨論文一致），客製題在後，總數 ≤ 8。固定題號一致，讀者可跨論文回顧同一題的作答；題數設上限，避免作答負擔過重導致整批跳過。

### 9.2 固定題

依 S. Keshav, "How to Read a Paper," *ACM SIGCOMM Computer Communication Review*, 37(3):83–84, 2007（DOI `10.1145/1273445.1273458`，已經 Crossref 查證）。該文三遍閱讀法中，第一遍的目的是決定是否繼續讀，第三遍是在腦中重新實作、找出隱含假設，與本設計的兩種模式同構。

**廣讀**

| # | 題目 | 對應 |
|---|---|---|
| B1 | 這篇論文要解決什麼問題？為什麼這個問題值得解決？ | Context |
| B2 | 用一段話說明它的核心想法與宣稱的貢獻。 | Contributions |
| B3 | 它屬於哪一類研究（新方法、分析、benchmark、系統、理論）？該用什麼標準評價這一類研究？ | Category |
| B4 | 它繼承了哪些工作、與哪條路線立場相對？分歧點在哪個假設上？ | Context |
| B5 | 這篇值得精讀嗎？理由是什麼？精讀時最該檢查哪個地方？ | 第一遍的決策目的 |

**精讀**

| # | 題目 | 對應 |
|---|---|---|
| D1 | 不看論文，說出方法的完整流程，以及每一步為什麼必要。 | 第三遍：重新實作 |
| D2 | 最弱的主張是哪一條？證據缺了什麼？ | §6.4 |
| D3 | 哪一個設計決策最關鍵？換成替代方案，預期會發生什麼？ | §6.5 |
| D4 | 結論依賴哪些沒有明說的假設？在什麼條件下會不成立？ | 第三遍：隱含假設 |
| D5 | 要接續這篇做研究，第一個實驗會做什麼？ | — |

### 9.3 客製題判準

1. 沒讀過這篇就答不出來。能套用到任何論文的題目若有價值應升為固定題，否則即是空泛題。
2. 瞄準這篇的關鍵點：特定設計決策、特定圖表、出乎意料的結果、與對立路線的衝突。
3. 不考查表題（「Table 2 最高分是多少」）。
4. 題型比例：廣讀偏理解與定位；精讀偏評估與推演。

### 9.4 參考答案紀律

- **表態**：開放題給明確立場與理由，不寫「兩者皆有道理」。確無唯一正解時，先給立場，再以一句帶出另一個站得住的立場。
- **事實附原文位置**（§、Table、Figure）；推測標 `**推測**`。
- **篇幅約 3–6 句**，與實際作答長度相當，才能對照。
- **附「關鍵點」2–3 條**，供讀者逐條自評。

### 9.5 格式

```markdown
## 問題

> [!question] B1　這篇論文要解決什麼問題？為什麼這個問題值得解決？

> [!answer]- 參考答案（先作答再展開）
> 本文處理低資源語對的翻譯品質問題⋯⋯（§1 第 2 段）
>
> **關鍵點**
> - 問題的具體範圍：⋯⋯
> - 為什麼既有方法不夠：⋯⋯

> [!question] Q6　作者為什麼只用 COMET 挑選 checkpoint，卻同時回報 BLEU？
```

- 相鄰 callout 之間必須空行，否則 Obsidian 會合併為同一區塊。
- `[!answer]` 非內建類型，預期以預設樣式呈現，摺疊語法 `-` 適用任何類型——實作時對照 Obsidian Help〈Callouts〉確認。
- 客製題題號接續固定題，從 Q6 起。
- 參考答案預設摺疊：先看到答案會錨定讀者的思考，對照即失效。

## 10. 與卡片盒邊界的關係

產品邊界不變：skill 產出講義後停手，不寫 literature note 或 permanent note，也不把讀者在對話中貼出的作答整理成筆記。SKILL.md Step 5 補述：參考答案是對照材料，不是筆記；它預設摺疊、在讀者作答之後才被看到，並以 `generated: claude` 標示為可重生的機器產物。

## 11. SKILL.md 流程

| 步驟 | 內容 |
|---|---|
| **0 Fetch** | 跑 `fetch.py`，讀 `route` 與 `docs`，依 §3 決定模式；`partial` 時詢問 |
| **1 Survey** | 共通：兩句主張、章節結構、fetch 遺失內容。廣讀另提規劃（「論文全貌」「核心方法速覽」各收哪些段落、前置知識清單草案）；精讀另確認涵蓋範圍與 `broad.md` 是否存在。確認後才動筆 |
| **2 查證**（僅廣讀） | 跑 `--graph`；憑模型知識想到的論文跑 `--verify`；只有 `exact` 可入講義 |
| **3 寫作** | 載入 `lecture-format.md`；寫入 `<mode>.part.md`，一次一個 `##` 區塊；front matter 先寫，`lecture_read: false` |
| **4 出題** | 載入 `questions.md`；寫問題區塊；完成後改名為 `<mode>.md` |
| **5 停止** | 回報路徑與長度，提醒讀完後勾選 `lecture_read`；卡片盒邊界（§10） |

`/ppread --list [dir]`：跑 `fetch.py --list`，JSON 轉表格，依要求篩選。

Discipline 新增：外部文獻查證（§7）、作者理由與推測分開（§6.5）、批判指向具體位置（§6.6）。

## 12. 檔案變更

| 檔案 | 變更 |
|---|---|
| `SKILL.md` | 依 §11 重寫；`description` 納入 `--broad`／`--deep`／`--list` |
| `lecture-format.md` | §4、§5、§6 的格式規格；反例清單更新 |
| `questions.md` | 新增，內容為 §9 |
| `fetch.py` | §8 全部 |
| `deploy.sh` | 增部署 `questions.md` |
| `CLAUDE.md` | 可部署檔 3 → 4；Architecture 補 `questions.md`；Non-obvious decisions 增：兩份文件的理由、外部文獻無憑記憶路徑、狀態存 front matter 而非資料夾名稱、`.part.md`、`papers.base` 永不覆寫、citations 只取 3 頁；Testing 更新 |
| `README.md` | 範例改新標籤；兩種模式、`--list`、Bases、`PPREAD_S2_API_KEY`；「刻意不做的事」補參考答案說明 |
| `VERSION` | `0.1.0` → `0.2.0`（輸出契約不相容變更；SemVer 在 major 為 0 時以 minor 反映） |

### 否決的替代方案

- **單一 `lecture.md` 分層續寫**：廣讀的內容以研究脈絡為主、精讀只談論文本身，兩者性質不同，不是同一份文件的深淺兩段。
- **`fetch.py` 解析 LaTeX 章節樹自動分層**：廣讀段落的挑選是判斷工作（例如「補課」內容不對應任何章節），且只在 tier 1 有效。
- **資料夾名稱前綴標示狀態**（`[deep]slug`）：狀態變更需改名，會斷掉圖片嵌入與外部筆記的連結；`[` `]` 在 shell 是 glob 字元類別、在 Obsidian 是連結保留字元；狀態出現兩個真相來源。
- **允許憑記憶列文獻並加警告**：警告會被忽略，且產物讀來合理而內容錯誤。

## 13. 測試計畫

無測試框架，依慣例從 shell 對真實來源測試；輸出寫至 scratchpad。

| # | 案例 | 預期 |
|---|---|---|
| 1 | `1706.03762` | `route: latex`；`docs` 皆 `absent` |
| 2 | `--graph 1706.03762` | `citations_complete: false`、`citations_scanned: 3000`；references 含 `influential: true` |
| 3 | `--graph 1905.02175`（*Adversarial Examples Are Not Bugs, They Are Features*，2026-09-15 被引 2173） | 翻 3 頁、`citations_complete: true`；同時驗證分頁邏輯 |
| 4 | `--graph 10.1109/CVPR.2016.90` | 經 DOI 解析成功 |
| 5 | `--verify`：Bahdanau 原標題、捏造標題、大小寫不同的真實標題 | `exact`、`not-found` 或 `mismatch`、`exact` |
| 6 | `--verify` 26 個標題 | exit 2 |
| 7 | scratchpad 假 library：broad 已讀、deep 未讀、舊版 `lecture.md`、只有原始檔、`.part.md`；跑 `--list` | 五種狀態正確 |
| 8 | 資料夾 `broad.md` 屬論文 A，以 `--title` 使論文 B 撞同一 slug | `conflict`，`occupant` 指向 `broad.md` |
| 9 | `broad.md` 相符、`deep.md` 不符 | `conflict` |
| 10 | 首次抓論文建立 `papers.base`；手動修改後重跑 | 保留修改內容 |
| 11 | 本機 PDF（拋棄式副本） | 行為同 `v0.1.0` |

**需人工確認**（無法由 agent 驗證）：`papers.base` 在 Obsidian 的顯示與 `lecture_read != true` 篩選；`[!answer]-` 摺疊。

**端對端**：須先 `./deploy.sh`（覆寫 `~/.claude/skills/ppread/`），執行前先確認。挑一篇短論文依序跑 `--broad`、`--deep`，檢查：無「譯」「解」標籤；外部文獻皆可以 `--verify` 重現；B1–B5、D1–D5 齊全；參考答案皆摺疊；完成後檔名為正式名。

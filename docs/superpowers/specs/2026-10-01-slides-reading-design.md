# 課程簡報閱讀設計

- 日期：2026-10-01
- 目標版本：`0.3.0`
- 分支：`feature/slides-reading`（自 `develop`）
- 設計樣本：`VLSI_Design_1_Introduction.pdf`（NCKU EE，M. D. Shieh，79 頁，未納入版控）

## 1. 動機

`ppread` 目前只讀論文。課程簡報同樣需要被讀懂，但論文的 broad／deep 不能照搬：

- 論文的 deep 是**評判**作者的主張；簡報沒有待評判的主張，讀者要的是**學會**。
- 簡報的閱讀障礙集中在**專有名詞**：樣本前半（約 p.1–33）幾乎全是術語清單（Wiener／Kalman／LMS／RLS、SVD、bitonic sort、TCM／VSB／COFDM、RS(204,188)），每個名詞只出現一次、投影片不解釋。
- 簡報沒有 arXiv、DOI，也幾乎不引用（樣本只有 p.12「BWRC, UCB」、p.17 Wikipedia），論文 broad 依賴的引用圖沒有種子。

閱讀目的有兩個：課後複習與考試準備，以及長期知識建構——從章節延伸到相關論文與目前研究進展。因此簡報有三個模式：broad、deep、research。

## 2. 範圍

**包含**

- 本機 PDF 的文件種類判定（`paper`／`slides`）
- 簡報的兩層資料夾 `<course-slug>/<title-slug>/`
- 三份簡報講義：`broad.md`、`deep.md`、`research.md`
- `fetch.py --search`：Semantic Scholar 主題檢索
- 課堂筆記（打字註記、手寫、螢光筆、手寫插頁）作為獨立一層處理並核對
- 簡報專屬的流程檔 `slides.md`、格式規範 `slides-format.md`、`questions.md` 的簡報題組

**不包含**

- PDF 以外的簡報格式（`.pptx`、`.key`）
- 網路來源的簡報（URL 一律仍視為論文）
- 一般「文件」（規格書、報告、手冊）——本次只做課程簡報
- 跨章節的課程總覽講義
- 論文的 research 模式（論文 broad 已含文獻脈絡）
- 代寫 literature note 或 permanent note（產品邊界不變）

## 3. 樣本觀察（設計依據）

| 觀察 | 對設計的影響 |
|---|---|
| PDF 是 iOS 匯出的筆記檔：投影片原文＋打字中文筆記（如 p.8「老師說：架構沒有最佳解，只有比上次更好的解」）＋手寫推導＋螢光筆 | 內容分層（§6.2）；筆記核對進 deep（§5.2） |
| p.9 是整頁手寫插頁，之後 PDF 頁碼比投影片印的頁碼多 1 | 頁碼雙標（§6.3） |
| 前半是術語清單、後半（p.34–79）是推導與方法（transfer function、DCT 矩陣、SFG／DFG／DG、ASAP／ALAP、Verilog） | broad 以術語為主體、deep 只處理技術單元（§5） |
| `pdfinfo` 無 `Title`；第 1 頁只有「Chapter 1 Introduction」；課程名、學校、講者只在頁首頁尾 | 簡報強制 `--course` 與 `--title`（§4.2） |
| `Page size: 720 x 540 pts`（橫向 4:3） | 以頁面方向判定種類（§4.1） |
| 筆記有錯：p.8「floding／upfloding」應為 folding／unfolding | 筆記要核對，不是照抄（§5.2） |

## 4. `fetch.py`

所有改動只作用於**本機 PDF**。網路路線不變，一律為 `paper`。

### 4.1 文件種類判定

```python
def pdf_kind(path: Path) -> str   # "paper" | "slides" | ""
```

1. `pdfinfo` 的 `Page size`（第一頁）：寬 > 高 → `slides`，否則 `paper`。`pdf_title()` 已依賴 `pdfinfo`，不新增相依。
2. 無 `pdfinfo` 時，以 regex 掃原始位元組的第一個 `/MediaBox [x0 y0 x1 y1]`。
3. 兩者皆失敗（例如 MediaBox 在壓縮的 object stream 中）→ 回傳 `""`，`adopt_local` 回 `route: needs-kind`，不移動檔案。agent 看第一頁後以 `--kind slides|paper` 重跑。
4. `--kind` 明確指定時優先於自動判定。

### 4.2 命名與資料夾

- 新增 `--course "<課程名>"`。簡報缺 `--course` 或缺標題（`--title` 或可用的 metadata `Title`）→ `needs-title`，`reason` 寫明缺哪一個。metadata 的 `Title` 對簡報不採信——只認 `--title`——因為簡報 metadata 常是「Slide 1」「PowerPoint Presentation」之類的匯出預設值，採信會產生錯而不報的資料夾名。
- 資料夾：`<PDF 所在目錄>/<slugify(course)>/<slugify(title)>/`。
- 冪等規則（重跑不重複巢狀）：
  - PDF 已在 `<course-slug>/<title-slug>/` 中 → 原地沿用
  - PDF 所在目錄名即 `<course-slug>` → 只建 `<title-slug>/`
  - 其餘 → 兩層都建
- `--out <dir>` 時：`<dir>/<course-slug>/<title-slug>/`。
- 章號補零（`Ch01`）是 `slides.md` 對 agent 的規定，不是 `fetch.py` 的轉換——`fetch.py` 只 slugify 傳入的字串。

### 4.3 資料夾身分判定

`same_paper(ident, meta)` 擴充：兩邊都有 `course` 時，正規化後的 course 也必須相等，才進入既有的 arXiv → DOI → 標題比對。兩層資料夾通常已隔開不同課程，但 `--out` 與手動搬移可能讓兩門課的「Ch01 Introduction」落到同一處。

### 4.4 講義狀態

- `DOC_FILES` 加入 `research.md`、`research.part.md`。
- `lecture_docs(workdir, kind="")` 回傳加入 `kind`：呼叫端已知時直接用（`adopt_local` 知道自己判定的種類）；否則取任一份講義 front matter 的 `kind`，皆無則依資料夾內來源 PDF 的 `pdf_kind`，再無則 `paper`。
- `adopt_local` 判定種類的順序：`--kind` → 所在資料夾講義 front matter 的 `kind` → `pdf_kind`。中間那一步讓「已有講義的直式簡報」重跑時不需要再帶 `--kind`，也不會被誤判成論文而搬進新的巢狀資料夾。
- `kind: slides` 時多回報 `research` 的狀態；`paper` 維持 `broad`、`deep`。
- 模式選擇規則（SKILL.md）改為依種類的模式序列：`paper` = broad → deep；`slides` = broad → deep → research。無旗標時取第一個未完成者。

### 4.5 Front matter

簡報：

```yaml
---
type: reading
kind: slides
mode: broad
lecture_read: false
generated: claude
title: Ch01 Introduction
course: VLSI DSP
authors: [M. D. Shieh]
institution: NCKU EE
year: 2026
pages: 79
tier: 6
created: 2026-10-01
---
```

- 無 `doi`、`arxiv`、`venue`。`authors` 填講者，沿用同欄位，`--list` 與 `papers.base` 不需特判。
- 論文的 front matter 新增 `kind: paper`。缺 `kind` 的既有講義一律視為 `paper`，不遷移。
- `papers.base` 不覆寫（既有決策），所以舊的 base 不會自動多出 `kind` 欄；簡報仍會出現，因為 filter 是 `type` 與 `generated`。

### 4.6 `--search`

```bash
fetch.py --search "<query>" [--since YEAR] [--limit N]   # N 預設 10
```

- 端點：Semantic Scholar `/graph/v1/paper/search/bulk`，`sort=citationCount:desc`；`--since` 對應 `year=<YEAR>-`。
- 欄位：`title`、`year`、`authors`、`venue`、`citationCount`、`externalIds`（取 `ArXiv`、`DOI`）、`abstract`（截斷至約 300 字元）、`fieldsOfStudy`。
- 輸出：`{"route": "search", "query", "since", "total", "papers": [...], "fetched_on"}`；失敗為 `{"route": "search-unavailable", "query", "reason"}`。零筆結果是 `route: search` 且 `papers: []`，與失敗區分。
- 走 `s2_get`，沿用重試、退避與 `PPREAD_S2_API_KEY`。
- **實測結果（2026-10-01，`"systolic array"`）**：
  - `sort=citationCount:desc` 與 `year=2023-` 如預期運作；加引號的片語查詢有效（total 5756，加年份後 794）。
  - **`limit` 被忽略**：每次回最多 1000 筆，截斷必須在 `fetch.py` 做。
  - **`abstract` 常為 null**（多數舊論文與部分出版商），所以加上 `fieldsOfStudy` 輔助相關性判斷。
  - 引用數排序的前幾名會混入只在內文提到該詞的邊緣論文（第一名是 "Unifying computers and dynamical systems..."），agent 端過濾是必要的，不是保險。
- 代價：每主題 2 次 search＋1 次 graph（最多 3 頁），5 個主題約 25 次請求；keyless 時 429 退避使 research 成為最慢的模式。

### 4.7 `--list`

`papers` 每列加 `kind`；簡報列多 `research` 狀態。

簡報是兩層資料夾，課程資料夾本身沒有檔案、只有章節子資料夾——現行「直接含檔案才算論文資料夾」的規則會把它當容器跳過，章節永遠列不出來。所以：沒有直接含檔案的非隱藏資料夾（`assets` 除外）往下看一層，其中直接含檔案的子資料夾列為一筆，`slug` 為 `<course-slug>/<title-slug>`。

## 5. 三份簡報講義

共通：講解單位是**單元**——連續講同一件事的投影片合為一個，例如 `DSP Algorithm 2: DCT (1)–(3)`。

### 5.1 `broad.md`——章節地圖＋術語

1. **章節地圖**：這章回答什麼問題、論證如何推進，以頁碼範圍標出（樣本：為何需要 VLSI DSP 2–13 → 系統實例 14–18 → 設計議題 19–33 → 演算法表示法 34–55 → high-level synthesis 56–79）。結構上的異常要指出（例如後半疑似另一份講義接上）。
2. **術語**（主體）：投影片上每個專有名詞，依主題分組，不照字母排。
   - **本章核心**（如 SFG、DFG、DG、pipelining、retiming、scheduling、systolic array）：英文精確定義、中文解釋、出現的投影片、在本章扮演的角色。
   - **點到**（如 TCM、VSB、Kalman filter、bitonic sort）：一兩句說明，讓讀者不卡住即可。
   - 中英雙語集中在這裡；不逐條翻譯投影片條列。
3. **先備知識**：本章假設已會什麼（如 z-transform、FIR／IIR、Verilog 基礎），各需懂到什麼程度。
4. **老師強調的重點**：從課堂筆記挑出口頭補充的論點，標明出處是筆記。
5. **問題**：SB1–SB5，客製題 SB6 起最多 3 題，參考答案摺疊。

### 5.2 `deep.md`——學會並做得出來

只處理**技術單元**（有推導、方法或可操作內容者）。純術語清單頁寫一行「見 broad 術語段」。每個單元：

- **投影片原文**：英文引用；公式從頁面圖像轉為 LaTeX，標註「自投影片圖像轉寫」。
- **補完**：投影片省略的推導步驟、每一步為何成立、與前面單元的關係。
- **實作例**：用投影片自己的例子實際走一遍（如 3-tap FIR 的 SFG transposition、p.74 DFG 的 ASAP／ALAP）。
- **筆記核對**：列出對應的課堂筆記，判定為正確、需補充或有誤，附理由。
- 依賴圖表的單元：有 `pdftoppm` 時把該頁輸出為 `<workdir>/assets/pdf-pNNN.png`（NNN 為補零的 PDF 頁碼），以相對路徑 `![投影片 9](./assets/pdf-p010.png)` 嵌入；沒有則只寫頁碼。放在章節資料夾內而非 library 的 `assets/<slug>/`：簡報資料夾建在 PDF 旁，可能根本不在 library 裡；用相對路徑而非 `![[...]]`：每個章節都有 `pdf-p010.png`，wikilink 無法唯一解析。

結尾：SD1–SD5，客製題 SD6 起最多 3 題，形式為考題式的計算或推導。

### 5.3 `research.md`——從章節延伸到研究

1. 從章節選 4–6 個值得延伸的主題，每個寫明來源投影片。
2. 每主題三層，全部來自 API 輸出：
   - **奠基**：`--search`，依引用數排序
   - **發展脈絡**：對核心奠基論文跑 `--graph`
   - **近期進展**：`--search --since <今年−3>`
3. 每篇論文寫明對該主題的貢獻、與投影片哪個概念相接；有 arXiv ID 者附 `/ppread <id>`。
4. 建議閱讀順序與抓取日期。
5. **問題**：SR1–SR3，客製題 SR4 起最多 2 題。

## 6. `SKILL.md` 與 `slides.md`

### 6.1 檔案拆分

| 檔案 | 狀態 | 內容 |
|---|---|---|
| `SKILL.md` | 改 | 共用的觸發方式、Step 0（新 route）、Listing、Discipline；`kind: slides` 時改讀 `slides.md`，論文的 Step 1–4 原地保留 |
| `slides.md` | 新 | 簡報流程：閱讀方法、Step 1–4、research 查詢 |
| `slides-format.md` | 新 | 三份簡報講義的輸出規範，中文撰寫 |
| `questions.md` | 改 | 新增「簡報」部分 |
| `deploy.sh` | 改 | 部署 6 個檔案 |

讀論文時不載入簡報規則，反之亦然。

觸發方式：新增 `--research`（只限簡報；用於論文時說明不支援及理由）。`--course`、`--kind` 是 `fetch.py` 參數，agent 在處理 `needs-title`／`needs-kind` 時補上，使用者不需輸入。`description` 改寫為涵蓋論文與課程簡報。

### 6.2 閱讀方法

- **以看圖為主**：Read 的 `pages` 參數，每次 ≤ 20 頁，看完整份。`pdftotext -layout` 只用來精確取字串（術語拼法）。
- **四層分辨**：投影片原文、打字筆記、手寫、螢光筆。依據：位於投影片範本框外、字體或字級不同、中文、手寫筆跡。分不清時直說。
- **公式**：投影片公式是渲染好的圖像，看得到，允許轉寫並標註來源；看不清者寫 ⚠️。手寫公式同此規則。

### 6.3 頁碼

有印頁碼的頁：「投影片 9（PDF p.10）」。插頁：「PDF p.9（手寫插頁）」。

### 6.4 Step 1：總覽

先回報章節問題、頁碼範圍結構、技術單元與術語清單頁的數量、筆記密度與插頁位置。依模式附計畫：

- broad：術語草稿（核心／點到兩級及數量）、先備知識清單
- deep：技術單元清單、各單元的實作例、要核對的筆記
- research：主題、來源投影片、查詢字串、預估請求數與耗時

等使用者確認後才寫。

### 6.5 Step 2：research 查詢

每主題依序：`--search`（引用數排序）→ `--search --since <今年−3>` → 選一篇核心論文跑 `--graph`。請求循序發出。agent 依標題與 abstract 剔除不相關的檢索結果（關鍵字檢索必然混入同名異領域的論文，例如 "systolic" 會撈到醫學文獻），並回報剔除數。

### 6.6 Step 3–4

沿用論文的寫法：寫入 `<mode>.part.md`，一個 `##` 區塊一回合，問題寫完後才 `mv` 為 `<mode>.md`。

### 6.7 Discipline 新增

- **筆記與投影片不可混寫。** 把筆記寫成投影片原文，等於捏造老師的說法；把投影片寫成筆記，會抹掉使用者自己的痕跡。
- **「投影片未說明」與「沒有做」分開。** 簡報是演講的殘缺紀錄；補上的解釋一律放在「補完」，不寫成老師的意思。
- **不逐條翻譯。** 雙語只在術語段；首次出現中英並列的規則照舊。
- 既有規則全部適用，尤其是「外部論文只能來自 API 輸出」。

## 7. `questions.md` 簡報題組

固定題由本專案設計，無外部出處。

**廣讀**

| # | 題目 |
|---|---|
| SB1 | 這一章要回答什麼問題？用一段話串起整章的論證。 |
| SB2 | 本章最核心的三個術語各是什麼？各用一句話定義，並說明三者的關係。 |
| SB3 | 這一章依賴哪些先備知識？各從哪一頁開始用到？ |
| SB4 | 本章的方法在完整的設計流程中負責哪一段？上游輸入什麼、向下游交出什麼？ |
| SB5 | 深讀時最該花時間在哪幾個單元？理由是什麼？ |

**深讀**

| # | 題目 |
|---|---|
| SD1 | 不看投影片，重現本章最核心的推導或演算法步驟。 |
| SD2 | 用一個不在投影片上的新例子，把本章的方法走一遍。 |
| SD3 | 本章的方法在什麼條件下不適用，或會失效？ |
| SD4 | 投影片省略了哪一步？少了它，會讓人誤解什麼？ |
| SD5 | 本章哪兩個概念最容易混淆？差別在哪裡？ |

**研究**

| # | 題目 |
|---|---|
| SR1 | 這些主題中，哪一條離目前的研究前沿最近？從本章走到那裡，中間缺哪些知識？ |
| SR2 | 選一篇近期論文：它在本章的哪個概念上做了延伸？延伸的方向是什麼？ |
| SR3 | 本章教的方法中，哪一個在近期研究中已經被取代或大幅修改？證據來自哪一篇？ |

## 8. 測試與驗收

**離線**（`tests/offline_checks.py`）

- `pdf_kind`：合成 PDF 位元組的橫向、直向、無法判定；`--kind` 覆寫
- `adopt_local`（簡報）：兩層建立、三種冪等情況、缺 `--course`／`--title` 時回 `needs-title` 且不移動檔案、`needs-kind` 時不移動檔案
- `same_paper`：course 相同／不同／單邊缺
- `lecture_docs`：簡報的 `research` 狀態、`kind` 推斷、缺 `kind` 的舊講義視為 `paper`
- `--search`：以替身 `s2_get` 測解析、abstract 截斷、`search-unavailable`
- `--list`：`kind` 欄與 `research` 狀態

**Live**

- 實作後再對真實 S2 端點跑一次 `--search`，確認 `fetch.py` 的編碼（`urlencode`）送出的請求與 §4.6 實測時一致
- 樣本 PDF 的拋棄式複本，`--out` 指向暫存目錄，三個模式各產一份。檢查：兩層資料夾、頁碼雙標、p.8 筆記核對抓到 floding → folding、術語段涵蓋 p.20–23 的名詞、research 每篇論文都在 API 輸出中出現
- `CLAUDE_SKILLS_DIR=<tmp> ./deploy.sh`：6 個檔案皆部署

**收尾**：`CLAUDE.md` 更新部署清單、架構段（新增兩個檔案）與非顯而易見決策（簡報不採信 metadata `Title`、課堂筆記分層）。

## 9. 決策紀錄

| 決策 | 否決的替代方案與理由 |
|---|---|
| 整合進 `ppread`，以 `kind` 分流 | 另開 `/slread`：本機檔案流程、`.part.md`、`lecture_read`、`--list`、`papers.base` 都要複製，兩份副本會分歧，且 `deploy.sh` 要重新設計共用程式碼的部署。通用外掛架構：只有兩種文件，是為假設需求預留擴充點 |
| research 以 `--search`＋`--graph` 取材 | 記憶點名＋`--verify`：選文受記憶偏誤主導、偏向經典、近期進展最弱，而近期進展正是需求；精確標題比對的偽陰性高。兩者並用：多一條路徑、規則變複雜，收益有限 |
| 課堂筆記為獨立一層並核對 | 只當線索：筆記承載老師的口頭敘事，是投影片缺的那一半。忽略：丟掉最有價值的資訊 |
| 課程／章節兩層資料夾 | 扁平：同課程章節只能靠前綴分組。放在 PDF 旁不分課程：分組完全交給使用者手動 |
| broad 以術語為主體、不逐條翻譯 | 沿用論文的逐段三件組：投影片條列是片段，翻譯價值低，真正的障礙是名詞 |
| deep 只處理技術單元 | 逐頁全講：術語清單頁在 broad 已處理，重講只會稀釋 |
| 簡報不採信 metadata `Title` | 採信：匯出預設值（「Slide 1」）會產生錯而不報的資料夾名 |

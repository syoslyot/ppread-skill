# ppread

A Claude Code skill that turns one research paper into a paragraph-level bilingual
lecture: English original, Traditional Chinese translation, and an explanation of
the background, prior work, experimental rationale and formulas behind it.

把一篇論文變成逐段對照的講義——原文、中譯、詳解。給讀英文論文還很慢的人。

## 這不是翻譯工具

翻譯只解決「字看不懂」。論文難讀，難在作者預設了一堆背景知識沒寫出來、
難在看不出這段在反駁誰、難在不知道實驗為什麼這樣設計。

所以每一段都給三樣東西：

```markdown
### 3.2.1　Scaled Dot-Product Attention

> We compute the dot products of the query with all keys, divide each by
> $\sqrt{d_k}$, and apply a softmax function to obtain the weights on the values.

**譯**　計算方式是把 query 與所有 key 做點積，各除以 $\sqrt{d_k}$，再經過
softmax 函數得到 value 的權重。

**解**

- **為什麼要除以 $\sqrt{d_k}$**　點積的變異數隨 $d_k$ 線性成長，$d_k$ 大時會落在
  softmax 的飽和區，梯度趨近於零。除以 $\sqrt{d_k}$ 把變異數壓回 $O(1)$。論文在
  腳註才提，但這是整個機制能 work 的前提。
- **與前人工作的關係**　Bahdanau et al. (2014) 用一層前饋網路算相容性分數，理論
  複雜度相同，但點積能直接呼叫最佳化過的矩陣乘法核心。這是工程考量而非理論優勢。
```

翻譯與解釋嚴格分離：翻譯忠於原文（包括原文含糊之處），評論與補充一律進「解」。

## 保真度階梯

輸入什麼格式都可以：arXiv ID、DOI、出版商網址、論文標題、本機 PDF 路徑。
`fetch.py` 會盡可能往上爬：

| tier | 來源 | 公式與引用 |
|---|---|---|
| 1 | arXiv e-print 的 LaTeX 原始碼 | 原文，精確 |
| 4 | arXiv 的 LaTeXML HTML | MathML，良好 |
| 5 | 出版商 HTML 或 OA PDF | 普通 |
| 6 | 只有 PDF | 不可靠 |

**最有價值的是 tier 2 這一步**：給一個 IEEE 或 ACM 的 DOI，先問 Semantic Scholar
有沒有對應的 arXiv ID。大量付費牆 CS 論文在 arXiv 上有同一篇的預印本，命中就直接
拉回 tier 1。實測 `10.1109/CVPR.2016.90` → `1512.03385`（ResNet）、
`10.1145/3292500.3330701` → `1907.10902`（Optuna）。

為什麼要這麼麻煩？因為 PDF 抽取會真的弄丟資訊，不是只是變亂。PDF 裡沒有「公式」
這種東西，只有一堆帶座標的字元——`x²` 是 `x` 加上一個往右上偏移的 `2`，抽出來變
`x2`，而究竟原本是 `x²`、`x_2` 還是真的 `x2`，已經無從得知。雙欄排版同理。

這類錯誤 LLM 修不掉，而且失敗方式很陰險：它不會說「這裡讀不出來」，而會依上下文
補一個看起來合理的公式。講義讀起來完全正常，公式卻是錯的。所以 SKILL.md 明文
規定寧可標記 `⚠️ 此處公式從 PDF 抽取受損，無法確認原式`，也不准推測。

## 安裝

```bash
git clone https://github.com/syoslyot/ppread-skill.git
cd ppread-skill && ./deploy.sh      # → ~/.claude/skills/ppread/
```

只需要 `python3`（>=3.10）。`fetch.py` 純標準函式庫，沒有任何第三方依賴，
也不需要 pandoc——LaTeX 直接交給 agent 讀，不做格式轉換。

**PDF 路線的選用依賴。** 只有在論文既沒有 arXiv 原始碼也沒有 HTML 全文時才會用到，
依序偵測、有哪個用哪個，都沒有才會提示安裝：

| 優先 | 工具 | 取得方式 |
|---|---|---|
| 1 | MarkItDown MCP | Claude Code 的 MCP server |
| 2 | `markitdown` CLI | `pip install 'markitdown[pdf]'` |
| 3 | `pdftotext -layout` | 多數 Linux 內建（`poppler-utils`） |

要注意的是這些工具改善的是**結構**（標題、表格、雙欄順序），不是**公式**。PDF 裡
只有字形座標，沒有上標／分數／求和上下限這類結構資訊，那在檔案產生時就已經消失，
任何工具都還原不回來。裝了 MarkItDown 會讓 tier 6 更好讀，不會更正確——真正的解法
永遠是爬回 tier 1 拿 LaTeX 原始碼。

選用：`export PPREAD_CONTACT=you@example.com` 可進入 Crossref 的 polite pool
（較快的查詢佇列）。不設也完全能用。

## 第一次執行：決定講義放哪裡

第一次跑 `/ppread` 時會先問一個問題，**在下載任何東西之前**：

- **固定一個位置** — 不管從哪個目錄啟動，論文都進同一個資料庫
- **當前目錄下的 `papers/`** — 每個專案各有各的資料庫

答案記在 `~/.config/ppread/config.json`，之後不再問。

```bash
# 直接設定，跳過詢問
fetch.py --set-output "fixed:/home/me/research/papers"
fetch.py --set-output "cwd:papers"

fetch.py --show-config     # 看目前設定與實際解析到的路徑
fetch.py <source> --out X  # 單次覆寫，不改設定
```

刻意不給預設值：預設成 `./papers` 意味著在 session 恰好啟動的任何目錄裡憑空長出
一個資料夾——可能是別人的 repo，可能是家目錄。這個問題只問一次，換來的是這個
工具永遠不會寫到沒被同意的地方。

## 用法

```
/ppread 1706.03762
/ppread 10.1109/CVPR.2016.90
/ppread https://dl.acm.org/doi/10.1145/3292500.3330701
/ppread ./papers/某篇論文.pdf
```

一篇論文一個資料夾，原始檔與講義放在一起：

```
papers/attention-is-all-you-need/
    source.tex     # 只有走 LaTeX 路線才有
    src/           # 解壓出的 e-print 樹，圖檔在這裡
    lecture.md     # 講義
```

metadata（標題、作者、年份、DOI、arXiv ID、保真度 tier）全部寫在 `lecture.md`
的 YAML front matter，不另開 metadata 檔。

手邊已經有 PDF 的話丟路徑即可，結構會一致：ppread 讀該檔自己的 metadata 取得
標題，建立同名資料夾，並把檔案**移動**進去，跟從網路抓的論文長得一樣。檔案沒有
標題 metadata 時會停下來要求補上，不會亂猜；目標已存在時拒絕覆寫。

## 它刻意不做的事

**不代寫讀書筆記。** 講義是加工過的原文，不是筆記。這個 skill 產出講義後就停手，
不會生成 literature note 或 permanent note。

如果用 Zettelkasten，這條界線是整個設計的重點：那套方法的價值來自自己用話重述
想法，那個動作本身就是思考發生的地方。代寫卡片會留下一堆看起來很整齊、卻沒有
任何一個念頭真的經過大腦的檔案——卡片盒被掏空成剪貼簿。

## 授權

MIT

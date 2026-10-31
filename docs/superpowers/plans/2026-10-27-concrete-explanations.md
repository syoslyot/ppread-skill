# Concrete Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every ppread lecture explain mechanisms from their parts, concrete operations and step-by-step traces with real values, instead of functional definitions ("X 是一種可以用來⋯⋯的工具"), and never by dropping or replacing the term.

**Architecture:** Prose-only change to the output contracts. `lecture-format.md` gains a common-rules section〈解說的具體度〉, and its exemplars that currently model the abstract style are rewritten to obey it; `slides-format.md` gets its own copy of the rules (a slides run never loads `lecture-format.md` — `slides.md:132`) and the same exemplar fixes; `SKILL.md`'s〈Discipline〉gets one sentence. No `fetch.py` change.

**Tech Stack:** Markdown. Verification is `grep` over the spec files plus one live `/ppread --broad 1706.03762` run.

**Spec:** GitHub issue #28 and the user's requirement, verbatim:

> 你要做的不是把專有名詞或困難的東西替換掉或省略，請不要這樣做，我會聽不懂幾乎都是沒有完整解釋、太過攏統、太抽象沒實際例子和具體表述，例如我問你尖嘴鉗是什麼，請不要像課本那樣說，尖嘴鉗可以用來..是…的好用工具，這太抽象也太白痴了，今天水電工或是需要用到尖嘴鉗的人，都不會去讀這段文字（也不需要），才了解尖嘴鉗是什麼、怎麼用

## Why the current contract needs this

- No rule asks for concreteness. `SKILL.md`'s「Explain what the paper assumes」covers *what* to explain (why this step, what breaks without it), not *how concretely*.
- The exemplars teach the abstract style. `lecture-format.md:207-208`「知道 BLEU 是 n-gram 重疊率⋯⋯COMET 是以人工評分訓練的神經網路評分器」and `slides-format.md:160`「⋯⋯提高抗雜訊能力的技術」are functional definitions, and the agent copies exemplars more faithfully than prose.
- `slides-format.md`'s「實作例」already demands a worked example, but never demands intermediate values, so a run can list results without showing who read what.

## Global Constraints

- The six rules: (1) 禁止「X 是一種可以用來⋯⋯的工具／機制」這類功能性定義句，列進反例清單；(2) 從實物與操作講起：組成部件 → 具體情境下的逐步操作 → 為什麼這樣設計 → 沒有它時會怎樣、用什麼替代、代價多大；(3) 每個背景機制至少附一個有真實數值的逐步追蹤例子（欄位值、表格內容、矩陣），步驟編號，標明每一步誰讀了什麼、改了什麼、輸出什麼；(4)「原本 vs. 改成」兩邊用同一個例子各走一遍；(5) 類比只能輔助，給了類比就要寫出它在哪裡失效；(6) 不准替換或省略術語來降低難度——術語照寫，然後講清楚。
- Every example stays inside the skill's existing exemplar world: *Attention Is All You Need* / machine translation for `lecture-format.md`, the VLSI DSP chapter for `slides-format.md`. No other paper is introduced.
- Format files stay in Chinese; `SKILL.md` stays in English.
- An exemplar must itself obey every rule in its file.
- Branch: `feature/concrete-explanations` off `develop`. No merge, no PR without the user's explicit instruction.
- Commits: Conventional Commits subject; body = technical bullets, a blank line, then `問題：ppread 的講義解說常寫成籠統抽象的功能性定義（像課本說「尖嘴鉗是可以用來⋯⋯的好用工具」），讀完還是不懂；要改從實物、具體操作與有真實數值的例子講起，且不准靠替換或省略術語降低難度（#28）`; then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `questions.md` is out of scope: reference answers are capped at 3–6 sentences (`questions.md:62`), which a numbered trace does not fit.

## Review Focus

1. **Depth limit vs. concreteness** — 「要懂到什麼程度」keeps the prerequisite section from growing into a course (`lecture-format.md:214`). The new rule must make each layer concrete, not add layers. Pinned by the「具體不等於更深」grep in Task 1 Step 5.
2. **The「點到即可」table** — its「是什麼」column is one sentence by design; it must stay one sentence but state what physically happens. Pinned in Task 2 Step 5.
3. **Exemplars contradicting the rule** — no exemplar in either file may use the banned form outside a 反例. Pinned by the last grep in Task 1 Step 5 and Task 2 Step 5.
4. **Scope beyond prerequisites** — the rule must cover every 解說 bullet (paragraph units, figure units, core-method units), not only〈讀懂它需要先知道的〉. Pinned by the scope sentence (Task 1 Step 2) and checked in Task 3.
5. **Invented numbers read as the paper's** — a trace whose values are not from the source must say so:「此例非論文所有」/「此例非投影片所有」(mirrors `slides-format.md:254`). Pinned in Task 1 Step 5 and Task 2 Step 5.

---

### Task 1: `lecture-format.md` and `SKILL.md`

**Files:**
- Modify: `lecture-format.md` — new `## 解說的具體度` after `## 解說面向不是必填欄位` (~line 101); rewrite the BLEU/COMET exemplar in `## 讀懂它需要先知道的` (~lines 202–212); one bullet in `## 反例（兩種文件皆適用）` (~line 142)
- Modify: `SKILL.md` — the paragraph starting `**Explain what the paper assumes, not what it says.**` (~line 386)

**Interfaces:**
- Produces: section title `解說的具體度`, mirrored by Task 2.

- [ ] **Step 1: Record the failing baseline**

```bash
grep -c '解說的具體度' lecture-format.md SKILL.md; grep -n 'BLEU 是 n-gram 重疊率' lecture-format.md
```
Expected: counts `0`; one hit.

- [ ] **Step 2: Write `## 解說的具體度`**

In order:
- Premise: 讀者看不懂，幾乎都是因為解說不完整、太籠統、太抽象、沒有實例，不是因為術語太多。
- The pliers contrast as the illustration of rule (1)/(2): 反——「尖嘴鉗是可以用來夾小東西的好用工具」；正——兩支握柄、細長尖頭的鉗口、支點旁的刃口；在配電盒裡夾住電線末端彎成勾掛上螺絲；尖頭能伸進手指進不去的空間。One closing line: 講義裡的機制同理。
- The six rules from Global Constraints, numbered; rule (2)'s four stages as sub-bullets.
- Depth sentence:「要懂到什麼程度」決定往下講幾層；本節決定每一層怎麼講。具體不等於更深。
- Scope sentence: 適用於兩份文件的每一條解說，包括段落單元、圖表單元、核心方法速覽與「要懂到什麼程度」。
- 數值出處: 例子的數值不是論文給的，標「此例非論文所有」。

- [ ] **Step 3: Rewrite the BLEU/COMET exemplar**

Keep title `### BLEU 與 COMET` and 卡在哪裡／去哪裡補 as they are. Replace「要懂到什麼程度」with:
- BLEU 組成: 拿系統譯文與人工參考譯文，數兩者共有多少個連續 n 個字（n-gram）；同一個 n-gram 在譯文出現的次數，最多只算到它在參考譯文出現的次數。
- Numbered trace (此例非論文所有), 參考譯文 `the cat is on the mat`:
  1. 譯文 `the cat sat on the mat`：6 個 unigram 中 `the`×2、`cat`、`on`、`mat` 在參考中有 → 5/6。
  2. 同一句的 bigram：`the cat`、`cat sat`、`sat on`、`on the`、`the mat` 中命中 `the cat`、`on the`、`the mat` → 3/5。
  3. 意思相同的改寫 `a kitten is on the rug`：unigram 只命中 `is`、`on`、`the` → 3/6。分數掉了一半，意思幾乎相同——這就是「對同義改寫不敏感」的具體樣子。
- COMET 組成與流程: 原文、系統譯文、參考譯文三句一起送進預訓練的多語言編碼器，各得一個句向量；組合三個向量後送進前饋網路，輸出一個分數；這個網路是拿人工評分當目標訓練出來的，所以步驟 3 那種改寫不會像 BLEU 一樣被重罰。
- 不必懂: brevity penalty 與 1–4-gram 幾何平均的算式；COMET 的編碼器架構。

- [ ] **Step 4: Add the 反例 bullet and the `SKILL.md` sentence**

反例 bullet, after「解說只是把翻譯換句話說」: **功能性定義**——「layer normalization 是一種可以穩定訓練的技術」。只說了用途；應依〈解說的具體度〉從它對哪個向量、做了哪些運算講起，附數值。

`SKILL.md`, appended to `Explain what the paper assumes`: one sentence — explain a mechanism from its parts and a step-by-step trace with real values, never with a "X is a tool for Y" definition and never by dropping the term; `lecture-format.md`〈解說的具體度〉has the full rule.

- [ ] **Step 5: Verify**

```bash
grep -c '解說的具體度' lecture-format.md SKILL.md
grep -n 'BLEU 是 n-gram 重疊率' lecture-format.md
grep -n '具體不等於更深\|此例非論文所有\|功能性定義\|a kitten is on the rug' lecture-format.md
grep -nE '是一種.{0,20}(工具|機制|技術|指標)|可以用來|好用工具' lecture-format.md
```
Expected: `lecture-format.md` ≥ 2 (section heading + 反例 bullet), `SKILL.md` 1; BLEU grep empty; all four phrases found; the last grep hits only the pliers 反 line in〈解說的具體度〉and the 反例 bullet.

- [ ] **Step 6: Commit**

```bash
git add lecture-format.md SKILL.md
git commit   # subject: docs(format): require parts-and-trace explanations in paper lectures
```

---

### Task 2: `slides-format.md`

**Files:**
- Modify: `slides-format.md` — new `## 解說的具體度` before `## 反例（三份皆適用）` (~line 85); DFG exemplar (~lines 142–148);「點到即可」table (~lines 156–162);「實作例」paragraph (~line 254); one 反例 bullet

**Interfaces:**
- Consumes: section name and six rules from Task 1 Step 2. Copy the rules; do not point at `lecture-format.md`.

- [ ] **Step 1: Record the failing baseline**

```bash
grep -c '解說的具體度' slides-format.md; grep -n '的技術 |' slides-format.md
```
Expected: `0`; one hit (TCM row).

- [ ] **Step 2: Write `## 解說的具體度`**

Same premise, pliers contrast, six rules and depth sentence as Task 1 Step 2, with「此例非投影片所有」. Scope: 「中文解釋」、先備知識的「要懂到什麼程度」、每一條「補完」、「實作例」.

- [ ] **Step 3: Give the DFG「中文解釋」a trace**

Keep its two sentences, then add (此例非投影片所有) $y(n)=2x(n)+3x(n-1)$, $x(0)=1, x(1)=4$:
- 組成: 乘法節點 ×2、×3，加法節點一個；輸入到 ×3 的邊標 `1D`，該暫存器初值 0。
- n=0: ×2 讀 1 得 2；×3 讀暫存器 0 得 0；$y(0)=2$；暫存器改存 1。
- n=1: ×2 讀 4 得 8；×3 讀暫存器 1 得 3；$y(1)=11$；暫存器改存 4。
- 結語: 邊上那個 `1D` 就是 ×3 看到上一拍輸入的原因。

- [ ] **Step 4: Fix「點到即可」, 實作例, 反例**

- Table rule: 「是什麼」一句話，但寫它實際做了什麼，不寫「⋯⋯的技術」。
- TCM row: 先用卷積編碼器編碼位元，再把編碼後的位元組直接對應到星座圖上的點，並讓容易混淆的序列在星座上距離最遠；接收端用 Viterbi 演算法在格狀圖上找最可能的點序列。
- Kalman row: 每收到一筆量測，就把模型對這一步的預測與量測值加權平均作為新估計，權重依兩者的誤差變異數決定。
- 實作例 paragraph: 每一步寫明讀了哪個值、算出什麼、哪個暫存器或變數改成什麼；只有結果、沒有中間值的不算實作例。
- 反例 bullet: **功能性定義**——「DFG 是一種描述演算法的圖形工具」。

- [ ] **Step 5: Verify**

```bash
grep -c '解說的具體度' slides-format.md
grep -n '的技術 |' slides-format.md
grep -n '具體不等於更深\|此例非投影片所有\|y(1)=11' slides-format.md
grep -nE '是一種.{0,20}(工具|機制|技術|指標)|可以用來|好用工具' slides-format.md
```
Expected: ≥ 2 (section heading + 反例 bullet); TCM grep empty; all three found; last grep hits only the pliers 反 line and the 反例 bullet.

- [ ] **Step 6: Commit**

```bash
git add slides-format.md
git commit   # subject: docs(format): require parts-and-trace explanations in slide lectures
```

---

### Task 3: Deploy and live check

**Files:**
- No source changes. Output goes to the session scratchpad.

**Executed by the controller, not a subagent:** ppread's Step 1 stops for the user's confirmation, which a subagent cannot obtain. The live skill at `~/.claude/skills/ppread/` is not touched before merge.

- [ ] **Step 1: Deploy to a scratch skills dir**

Run: `CLAUDE_SKILLS_DIR=<scratchpad>/skills ./deploy.sh`
Expected: `deployed -> <scratchpad>/skills/ppread`; `diff lecture-format.md <scratchpad>/skills/ppread/lecture-format.md` empty.

- [ ] **Step 2: Run on the repo's standard test paper**

Follow `<scratchpad>/skills/ppread/SKILL.md` for `--broad 1706.03762`, calling that copy's `fetch.py` with `--out <scratchpad>/papers` so nothing lands in the user's library.

- [ ] **Step 3: Check**

In the new `broad.md`, every〈讀懂它需要先知道的〉subsection's「要懂到什麼程度」contains a numbered trace with concrete values, and
```bash
grep -nE '是一種.{0,20}(工具|機制|技術|指標)|可以用來' <new broad.md>
```
prints nothing. Hand two of those subsections to the user: whether they read as understandable is the user's call.

- [ ] **Step 4: Close out**

If accepted, comment on #28 (`gh issue comment 28`) and leave closure to the merge. If not, adjust the rule text in Task 1/2, redeploy, rerun. If the user defers the read-through, open an issue for the pending manual check.

# Primer Figures and Tables, Quiz Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (A) 導讀 `primer.md` lets the reader understand every figure and every table of the paper, beside the prerequisites, Abstract, Introduction and Conclusion. (B) A `--quiz` mode that questions the reader one question at a time and grades each answer against the paper, plus `--check` for the reader's own notes, both recorded in `quiz.md`. (C) 精讀 tells an evidence gap from a reasoning gap; 通讀's further reading says what kind of evidence each paper adds.

**Architecture:** (A) `fetch.py` gains `--floats WORKDIR`, a deterministic inventory of every figure and table (from `source.tex`, else a caption scan of `source.md` or the PDF) that also puts a viewable PNG of every figure into `assets/<slug>/`. `lecture-format.md` replaces〈方法速覽〉with〈圖表導覽〉, one unit per numbered caption. `SKILL.md` plans the primer from the inventory and writes the new section in bounded passes. (B) No `fetch.py` change: the quiz contract goes into `questions.md` (what to ask and how to answer is that file's concern), the workflow into `SKILL.md`; a test pins that `quiz.md` is never mistaken for a lecture. (C) Two columns in `lecture-format.md`.

**Tech Stack:** Python 3 standard library; optional `pdftoppm`, `pdftotext` (poppler) and `gs` (Ghostscript); Markdown specs; `tests/offline_checks.py` (plain asserts, `CHECKS` list).

**Spec:** this plan's Design sections. Part A — the user's request (2026-11-01): 導讀要提供先備知識、摘要、Introduction、Conclusion、圖、表的說明，讓讀者看懂每張圖和表格; the user declined design questions ("每篇論文都不一樣"), so A's decisions are the planner's calls. Parts B and C — the user's approval (2026-11-03) of the analysis of three literature-review prompts: add quiz mode, with both open design questions decided as proposed (an interactive mode is allowed; sessions are recorded). The research-direction mode from the same analysis is deferred to issue #37.

**Parts are independent:** A (Tasks 1–4), B (Tasks 5–6) and C (Task 7) touch disjoint sections; Task 8 closes all three. Any part can ship without the others.

## Design A — primer figures and tables

**Why.** A primer that skips the figures and tables leaves the reader unable to open the paper's evidence: the results live in tables, the method lives in the architecture figure. Today the primer has no figure units at all and broad gives units only to figures a claim cites.

**Primer skeleton after this change:**

```
# <title>
> header block
## 一頁看懂                       (kept unchanged — the planner's call: it is the decision table P4/P5 rely on)
## 讀懂它需要先知道的              (now must also cover every term needed to read any figure or table)
## 論文全貌  ### Abstract  ### 1 Introduction  ### N Conclusion
## 圖表導覽                        (new: every figure and table, in source order)
## 問題
```

**Removed:**〈方法速覽〉. Its one numbered worked trace moves into the figure unit of the figure that depicts the mechanism the abstract's central claim depends on. With no such figure, it goes into an `**方法的一個例子**` bullet of the Introduction paragraph unit that first states the method. The「篇幅明顯短於舊版 broad（同篇約六成以下）」rule is removed: the length now follows the paper's figure count.

**Primer figure/table unit** (the common 圖表單元 plus two bullets):

- caption original in `> `, then **中文翻譯**
- figure: the image embed `![[assets/<slug>/<file>.png]]`; table: the table **transcribed** as a Markdown table — numbers verbatim, `\textbf`/`\underline` kept as `**`/`<u>`, `\multirow`/`\multicolumn` flattened by repeating the label in each spanned cell
- **圖上有什麼** — every visual element: panels (a)/(b), boxes, arrows, axes with units, legend, colours/line styles; for a table every column and row group, units, `↑`/`↓`, what bold/underline mark, every abbreviation in the header
- **怎麼讀** — a numbered walk through one concrete reading with values actually on the figure/table (one data point, one cell compared with another, one input followed through the boxes); values read off a plot are marked `目測，約`
- **這張圖表在說什麼** — what the authors use it for, citing the section that references it; no judgment of whether it suffices (that is 精讀's)
- terms point to〈讀懂它需要先知道的〉, never re-explained

Appendix floats use a short form: caption + 中文翻譯 + embed/transcription + **圖上有什麼** + one sentence of **這張圖表在說什麼**; no trace.

**Figure explanations live once** (same rule as prerequisites): when `primer.md` is finished, a broad/deep figure unit for the same figure keeps only its mode's analysis and links to the primer unit for 圖上有什麼/怎麼讀.

**`--floats WORKDIR` output:**

```json
{"route": "floats", "inventory": "latex", "source": "<path>", "numbering": "default|custom",
 "floats": [{"env": "figure*", "kind": "figure", "line": 120, "origin": "sec/model.tex",
             "appendix": false,
             "graphics": [{"path": "figs/arch.pdf", "asset": "assets/<slug>/figs-arch.png"}],
             "captions": [{"ordinal": 1, "label": "fig:arch", "caption": "<raw LaTeX>"}]}]}
```

- One float may hold several numbered captions (two minipages); a `\caption` inside a `subfigure`/`subtable` env is not numbered and not listed. `ordinal` counts numbered captions per kind (`figure*` counts as figure, `table*` as table) in source order, continuing into the appendix. `numbering: "custom"` when the source contains `\renewcommand{\thefigure}` or `\renewcommand{\thetable}` (with or without braces around the macro) — the agent then takes the printed numbers from the paper, not `ordinal`.
- `appendix` is true after a line matching `\appendix` or `\begin{appendix}` (or `\begin{appendices}`).
- `graphics[].path` is the `\includegraphics` argument resolved inside `src/`, trying the argument as written, then with `.png`, `.jpg`, `.jpeg`, `.pdf`, `.eps`. `asset` is the embed path relative to `workdir.parent`, or `null` with a `reason` (`"not found in src/"`, `"pdftoppm not available"`, `"gs not available"`, `"conversion failed: …"`).
- caption-scan route (no `source.tex`): `"inventory": "caption-scan"`; each float is `{"kind", "number" (as printed: "3", "A1", "IV"), "caption", "line", "page" (PDF only), "asset" (PDF only: the rendered page)}`; no `graphics`/`captions`/`ordinal`.
- `{"route": "floats-unavailable", "reason": …}` when there is nothing to read.

## Design B — quiz mode

**Why.** Every lecture today is one-way: the reader reads, and each question's reference answer sits one click away, so nothing forces recall. Being made to retrieve an answer is remembered markedly better a week later than rereading the same material (the testing effect; Roediger & Karpicke 2006, "Test-Enhanced Learning", *Psychological Science* — the claim stays out of every lecture unless `--verify` confirms the title). `--check` serves the Zettelkasten boundary instead of crossing it: it never writes the reader's note, it only checks the one the reader wrote. Slides 深讀 already checks a student's notes (`slides-format.md:68-77`), so the separation rule exists.

**Invocation.**

| Command | Does |
|---|---|
| `/ppread --quiz <source>` | Questions the reader on what the finished lectures covered, one question per message, grades each answer |
| `/ppread --check <note path> <source>` | Checks every claim in the reader's own note against the source |

Both work on papers and slides. Both flags are stripped before `fetch.py`, which runs as Step 0 only to locate the folder and its `docs`; no lecture is fetched-for or written.

**Gate.** At least one lecture in `docs` must be finished (state not `absent` and not `partial`). Otherwise stop with one line: the quiz asks about what a lecture taught, run `/ppread <source>` first. That is a stop, not a question.

**The no-questions principle is restated, not dropped.** `SKILL.md:20` becomes: writing a lecture never stops to ask a choice it can make itself; `--quiz` and `--check` are conversations the reader started, and their questions are the content, not choices. The fetch-failure questions are unchanged.

**Scope.** Questions come only from what the finished lectures cover — primer: Abstract, Introduction, Conclusion, prerequisites, every figure and table; broad: every section, the author-stated limitations, the context; deep: also the argument chain, claims versus evidence, design decisions. Slides by their own modes. Never reuse a lecture's printed `[!question]` verbatim: its answer is visible in the same file.

**Session.**

1. Default 5 questions. The reader can end at any message (「停」/「stop」) or ask for more.
2. Order: open points from `quiz.md`〈待加強〉first, oldest first; then questions not asked in any earlier session, spread over the scope.
3. Four question types, mixed: 回想 (a definition, a number with its condition), 解釋 (why or how a part works), 讀圖表 (one figure or table: the embed or transcription is shown, the reader reads a value or explains a mark), 推演 (what changes if one design choice changes).
4. One question per message. No hint and no reference answer before the reader answers.
5. Grading: the expected answer is split into 2–3 key points; each gets `正確`／`部分正確`／`錯誤`／`遺漏`. Every point that is not `正確` quotes the source verbatim (`> ` original, then 中文翻譯) with its location (`§3.2`, `Table 2`, slide 12 / PDF p.14). A claim in the answer that the source never addresses is `論文未說明`, not `錯誤`.
6. At most one follow-up question per question, aimed at the missed point; then the next question.
7. After every graded answer, append it to `quiz.md` before asking the next question, so an interrupted session loses at most the question in progress.

**`--check`.** Read the note; never edit it, move it, or write beside it. Split it into claims (one per sentence or bullet). Each claim gets `正確`／`誤讀`／`數字錯誤`／`作者未說`／`個人觀點（不查證）`; every non-`正確` quotes the source with its location. Describe what is wrong; never offer a replacement sentence — the note must stay in the reader's own words. Report the table in the conversation and append it to `quiz.md`; every `誤讀` and `數字錯誤` becomes an open point.

**`quiz.md`** in the paper or chapter folder:

```markdown
---
type: quiz
generated: claude
title: Attention Is All You Need
arxiv: 1706.03762
doi:
sessions: 2
last_quiz: 2026-11-03
open_points: 1
---

## 待加強

- [ ] base model 與 big model 的訓練時數各是多少（§5.2）— 首次答錯 2026-11-03，累計 1 次

## 紀錄

### 2026-11-03 quiz（範圍：primer）

#### Q1　〈讀圖表〉Table 2 中 EN-DE 的 28.4 與 26.36 各是哪個系統？差距在數什麼？

> [!quote]- 作答原文
> （the reader's answer, verbatim）

- 正確　28.4 是 Transformer (big)
- 錯誤　⋯⋯
  > （source quote）
  （中文翻譯，Table 2）
```

- Identity keys copied from the lecture's front matter (`title`, `arxiv`, `doi`; slides also `course`). **No `mode` key and never `type: reading`**: that keeps `is_lecture()` false, keeps it out of `papers.base` (which filters `type == "reading"`), and keeps the folder checks ignoring it — the same way they ignore the reader's own `notes.md`. The template is the planner's call; field names are fixed by this section.
- An open point answered `正確` in a later session is ticked `- [x]` and stays; `open_points` counts the unticked ones.
- `questions.md`〈邊界〉is amended: answers given inside `--quiz`/`--check` are recorded **verbatim** in `quiz.md` only — never edited, summarised or turned into notes; everywhere else the existing rule holds.
- Non-goals: no `quiz` column in `--list`, no change to `papers.base` (it is written once and never overwritten; an Obsidian view on `type == "quiz"` is the reader's to add), no spaced-repetition schedule.

## Design C — gap types and evidence kinds

- 精讀〈主張與證據〉gains a column `缺口類型` after `強度`, values `證據缺口`／`論證跳躍`／`—`. `證據缺口`: the inference from evidence to claim would hold, but the measurement is missing or is a proxy (the FLOPs row, the parallelisation row). `論證跳躍`: even if every cited result is correct it would not establish the claim, because a step of reasoning is missing (a theoretical O(1) sequential-operation count offered as proof of faster wall-clock training, with memory bandwidth and kernel launch overhead unaddressed). `支持` → `—`; `無對應證據` → `證據缺口`. Reason: the two failures call for different repairs — more data versus repaired reasoning — and a bare `未支持` hides which.
- 通讀〈延伸閱讀〉gains a column `類型`, values `方法來源`／`對照做法`／`後續延伸`／`複現或反證`. When `--graph` returns any paper that replicates, contradicts or re-evaluates this one, at least one row is `複現或反證`. Reason: the reader's next paper should be chosen by what kind of evidence it adds, not only by topic.

## Global Constraints

- `fetch.py` stays standard-library only; `pdftoppm`, `pdftotext`, `gs` are optional and detected with `shutil.which`, like `pdfinfo`.
- Deployable files stay exactly: `SKILL.md`, `lecture-format.md`, `questions.md`, `slides.md`, `slides-format.md`, `fetch.py`.
- Assets go to `<workdir.parent>/assets/<workdir.name>/` — the existing `assets/<slug>/` convention, which `list_library` already skips. File name = path inside `src/` with `/` replaced by `-`, extension `.png` after conversion (`figs/arch.pdf` → `figs-arch.png`; `a.png` → `a.png`).
- Conversion: PDF → `pdftoppm -png -r 150 -singlefile -f 1 -l 1 <in> <out-stem>`; EPS → `gs -q -dSAFER -dBATCH -dNOPAUSE -dEPSCrop -sDEVICE=png16m -r150 -o <out> <in>`; PDF page for caption scan → `pdftoppm -png -r 110 -singlefile -f P -l P <pdf> assets/<slug>/page-P`. Every subprocess has `timeout=60`.
- A destination that already exists and is not older than its source is not rewritten.
- No new deployable file: the quiz contract goes into `questions.md`. `slides.md` and `slides-format.md` do not change (quiz on slides is driven from `SKILL.md`).
- `quiz.md` is the log's file name; it is never added to `DOC_FILES`.
- Branch `feature/primer-figures-tables` off `develop`. No merge or PR without the user's explicit instruction.
- Commits: Conventional Commits subject; body = technical bullets in Chinese, blank line, the part's 問題 line, blank line, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - Part A: `問題：關於導讀的版本，還需要讓我可以看懂每張圖和表格。導讀要提供：先備知識、摘要、introduction、summary、圖、表的說明`
  - Parts B, C and Task 8: `問題：我想要新增 quiz模式，要先決定的兩個設計問題也支持，然後把研究方向模式寫入issue`
- Run `python3 tests/offline_checks.py` after every `fetch.py` change; every line must print `ok`.

## Review Focus

1. **`\caption[short]{long with {nested} braces}`** must yield the whole long caption, not the short one or a truncated one. Pinned in Task 1 (`check_floats_latex`).
2. **A float commented out by whole-line `%`** must not be inventoried, and inline `% \caption{x}` must not add a caption. Pinned in Task 1.
3. **`\includegraphics[width=...]{figs/arch}` with no extension, or a missing file,** must resolve to `figs/arch.pdf` or report `asset: null` with a reason — never raise. Pinned in Task 2 (`check_floats_assets`).
4. **Re-running `--floats`** must not re-convert an up-to-date asset and must return identical JSON. Pinned in Task 2.
5. **A body line starting "Table 2. shows…" before the real caption "Table 2: …"** must not win over the colon caption; IEEE `TABLE IV` and `Fig. 3.` must be found. Pinned in Task 3 (`check_floats_caption_scan`).

Part B (no executable code beyond the pin test; the rest is enforced by contract wording and reviewed against these):

6. **`quiz.md` whose `title` differs from the lecture's** (a typo, a renamed paper) must not trigger `route: conflict`, change `library_row`'s title, or appear in `lecture_docs`. Pinned in Task 5 (`check_quiz_log_is_not_a_lecture`).
7. **The reader answers "不知道"** or leaves the question blank: every key point is `遺漏`, each quoted with its source, and the point enters〈待加強〉— never a hint followed by the same question again.
8. **The reader's answer contains a true statement the paper never makes**: graded `論文未說明`, not `錯誤`, and not added to〈待加強〉.
9. **`--check` on a note that paraphrases correctly in different words**: `正確` — the check compares meaning, not wording, and never suggests a rewording.
10. **`--quiz` on a folder whose only lecture is `partial`**: the gate stops; it does not quiz from a half-written lecture.

---

### Task 1: LaTeX float inventory

**Files:**
- Modify: `fetch.py` (new functions after `limitations()`, ~line 877)
- Test: `tests/offline_checks.py` (new `check_floats_latex`, added to `CHECKS`)

**Interfaces:**
- Produces: `_brace_arg(s: str, i: int) -> tuple[str, int]` — `s[i]` is `{`; returns the content up to the matching `}` (escaped `\{` `\}` ignored) and the index after it.
- Produces: `latex_floats(text: str, origin_top: str = "") -> dict` — returns `{"numbering": "default"|"custom", "floats": [...]}` with every field of the Design's float object except `graphics[].asset` (Task 2 adds it); `graphics[].path` is the raw `\includegraphics` argument here.

- [ ] **Step 1: Write the failing test** `check_floats_latex`:

```python
def check_floats_latex() -> None:
    tex = (
        "\\section{Intro}\n"
        "% [ppread] >>> sec/model.tex\n"
        "\\begin{figure*}[t]\n\\includegraphics[width=\\linewidth]{figs/arch}\n"
        "\\caption[Short]{The {Transformer} model.}\\label{fig:arch}\n\\end{figure*}\n"
        "% [ppread] <<< sec/model.tex\n"
        "%\\begin{figure}\n%\\caption{Gone}\n%\\end{figure}\n"
        "\\begin{table}\n\\caption{BLEU scores.} % \\caption{x}\n\\label{tab:bleu}\n"
        "\\begin{tabular}{ll}a & b\\\\\\end{tabular}\n\\end{table}\n"
        "\\begin{figure}\n\\begin{minipage}{.5\\linewidth}\\includegraphics{a.png}"
        "\\caption{Left.}\\end{minipage}\n"
        "\\begin{minipage}{.5\\linewidth}\\begin{subfigure}{1\\linewidth}"
        "\\includegraphics{b.png}\\caption{sub}\\end{subfigure}"
        "\\caption{Right.}\\label{fig:r}\\end{minipage}\n\\end{figure}\n"
        "\\appendix\n\\begin{table}\\caption{Extra.}\\end{table}\n")
    r = fetch.latex_floats(tex, "main.tex")
    assert r["numbering"] == "default"
    fl = r["floats"]
    assert [f["env"] for f in fl] == ["figure*", "table", "figure", "table"], fl
    assert fl[0]["origin"] == "sec/model.tex" and fl[0]["line"] == 3
    assert fl[0]["graphics"] == [{"path": "figs/arch"}]
    assert fl[0]["captions"] == [{"ordinal": 1, "label": "fig:arch",
                                  "caption": "The {Transformer} model."}]
    assert fl[1]["captions"] == [{"ordinal": 1, "label": "tab:bleu", "caption": "BLEU scores."}]
    assert [c["caption"] for c in fl[2]["captions"]] == ["Left.", "Right."]
    assert [c["ordinal"] for c in fl[2]["captions"]] == [2, 3]
    assert fl[2]["captions"][1]["label"] == "fig:r"
    assert [g["path"] for g in fl[2]["graphics"]] == ["a.png", "b.png"]
    assert [f["appendix"] for f in fl] == [False, False, False, True]
    assert fl[3]["captions"][0]["ordinal"] == 2 and fl[3]["origin"] == "main.tex"
    assert fetch.latex_floats("\\renewcommand\\thetable{A\\arabic{table}}\n")["numbering"] == "custom"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: `AttributeError: module 'fetch' has no attribute 'latex_floats'`

- [ ] **Step 3: Implement `_brace_arg` and `latex_floats` in `fetch.py`**

Line-based scan like `_limitation_hits`: skip whole-line `%` lines; cut each line at the first unescaped `%` (`re.split(r"(?<!\\)%", raw, 1)[0]`); track `% [ppread] >>>/<<<` markers with the same `_MARKER_RE` stack for `origin` (fallback `origin_top`). Float envs: `figure`, `table`, `wrapfigure`, `wraptable`, `sidewaysfigure`, `sidewaystable`, each optionally starred; `kind` = `"figure"` or `"table"` by suffix. Join the float's (comment-cut) lines with `\n`, then scan the joined body in order for `\includegraphics` (skip an optional `[...]`, take `_brace_arg`), `\begin{subfigure|subtable}`/`\end{...}` depth, `\caption` (skip optional `[...]`; when subfigure depth is 0 it is numbered) and `\label` (attach to the nearest numbered caption before it, else the next one after it). `line` is the 1-based `\begin` line in `text`. A float may open and close on the same line (the appendix table in the test).

- [ ] **Step 4: Run to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: every line `ok`, including `ok  check_floats_latex`

- [ ] **Step 5: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit   # subject: feat(fetch): inventory LaTeX figures and tables
```

### Task 2: `--floats` on the latex route, with viewable assets

**Files:**
- Modify: `fetch.py` (new `floats()` and `_asset()`, `--floats` argparse option next to `--limitations` ~line 1308, dispatch next to `if args.limitations:` ~line 1336)
- Test: `tests/offline_checks.py` (new `check_floats_assets`)

**Interfaces:**
- Consumes: `latex_floats(text, origin_top)` from Task 1; `find_main_tex` (existing).
- Produces: `floats(workdir: Path) -> dict` — the Design's output. On `source.tex` it fills `graphics[].path` (resolved, relative to `src/`) and `graphics[].asset`/`reason`. Task 3 extends the same function with the caption-scan branch.
- Produces: `_asset(src: Path, dest_dir: Path, name: str) -> tuple[str | None, str | None]` — `(file name written or up to date, None)` or `(None, reason)`.
- CLI: `python3 fetch.py --floats WORKDIR` prints the JSON.

- [ ] **Step 1: Write the failing test** `check_floats_assets`:

```python
def check_floats_assets() -> None:
    lib = Path(tempfile.mkdtemp()); w = lib / "my-paper"; (w / "src" / "figs").mkdir(parents=True)
    (w / "src" / "figs" / "arch.pdf").write_bytes(b"%PDF")
    (w / "src" / "a.png").write_bytes(b"\x89PNG")
    (w / "source.tex").write_text(
        "\\begin{figure}\\includegraphics{figs/arch}\\includegraphics{a.png}"
        "\\includegraphics{gone}\\caption{X.}\\end{figure}\n", "utf-8")
    ow, orun = fetch.shutil.which, fetch.subprocess.run
    calls = []
    def run(cmd, **k):
        calls.append(cmd[0]); Path(cmd[-1] + ".png").write_bytes(b"\x89PNG")
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    fetch.shutil.which = lambda n: f"/usr/bin/{n}"; fetch.subprocess.run = run
    try:
        r = fetch.floats(w)
        g = r["floats"][0]["graphics"]
        assert r["route"] == "floats" and r["inventory"] == "latex"
        assert [x["path"] for x in g] == ["figs/arch.pdf", "a.png", "gone"]
        assert g[0]["asset"] == "assets/my-paper/figs-arch.png"
        assert g[1]["asset"] == "assets/my-paper/a.png"
        assert (lib / "assets" / "my-paper" / "a.png").read_bytes() == b"\x89PNG"
        assert g[2]["asset"] is None and g[2]["reason"] == "not found in src/"
        assert calls == ["pdftoppm"]
        assert fetch.floats(w) == r and calls == ["pdftoppm"]   # up to date: no re-run
        fetch.shutil.which = lambda n: None
        (lib / "assets" / "my-paper" / "figs-arch.png").unlink()
        g = fetch.floats(w)["floats"][0]["graphics"]
        assert g[0]["asset"] is None and g[0]["reason"] == "pdftoppm not available"
    finally:
        fetch.shutil.which, fetch.subprocess.run = ow, orun
    assert fetch.floats(Path(tempfile.mkdtemp()))["route"] == "floats-unavailable"
```

(`pdftoppm -singlefile` writes `<out-stem>.png`, so the stub writes `cmd[-1] + ".png"`; the `gs` branch passes `-o <out>` and is exercised in the live check of Task 5.)

- [ ] **Step 2: Run to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: `AttributeError: module 'fetch' has no attribute 'floats'`

- [ ] **Step 3: Implement `_asset` and the latex branch of `floats` in `fetch.py`, and wire `--floats`**

`floats` reads `source.tex` with `errors="replace"`, takes `origin_top` the same way `limitations()` does, resolves each graphic in `src/`, and calls `_asset` with `dest_dir = workdir.parent / "assets" / workdir.name`. `_asset`: `.png`/`.jpg`/`.jpeg` → `shutil.copy2`; `.pdf` → `pdftoppm`; `.eps` → `gs`; the commands and the up-to-date rule are in Global Constraints; a non-zero return code gives `"conversion failed: <first stderr line>"`. With no `source.tex` and (until Task 3) nothing else, return `floats-unavailable` with reason `"no source.tex, no source.md, and no PDF"`.

- [ ] **Step 4: Run to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: every line `ok`

- [ ] **Step 5: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit   # subject: feat(fetch): add --floats with viewable figure assets
```

### Task 3: Caption scan for `source.md` and PDF

**Files:**
- Modify: `fetch.py` (`_caption_scan()`, second and third branches of `floats()`)
- Test: `tests/offline_checks.py` (new `check_floats_caption_scan`)

**Interfaces:**
- Consumes: `floats(workdir)` and `_asset`-style destination from Task 2.
- Produces: `_caption_scan(text: str) -> list[dict]` — entries `{"kind", "number", "caption", "line"}` plus `"page"` when `text` contains `\f` (pages are 1-based, split on `\f`). Order = first appearance.

- [ ] **Step 1: Write the failing test** `check_floats_caption_scan`:

```python
def check_floats_caption_scan() -> None:
    text = ("Intro text.\nTable 2. shows that we win.\n\fFigure 1: The model\n"
            "architecture overview.\n\nTable 2: BLEU on WMT.\nFig. 3. Loss curve.\n"
            "TABLE IV\nCOMPARISON OF METHODS\n")
    r = fetch._caption_scan(text)
    assert [(e["kind"], e["number"]) for e in r] == [
        ("figure", "1"), ("table", "2"), ("figure", "3"), ("table", "IV")], r
    assert r[0]["caption"] == "Figure 1: The model architecture overview."
    assert r[0]["page"] == 2 and r[0]["line"] == 3
    assert r[1]["caption"] == "Table 2: BLEU on WMT." and r[1]["line"] == 6
    assert r[2]["caption"] == "Fig. 3. Loss curve."
    assert r[3]["caption"] == "TABLE IV COMPARISON OF METHODS"
    w = Path(tempfile.mkdtemp()); (w / ".primer.parts").mkdir()
    (w / ".primer.parts" / "source.md").write_text("Figure 1: A.\n", "utf-8")
    m = fetch.floats(w)
    assert m["inventory"] == "caption-scan" and m["floats"][0]["number"] == "1"
    assert "page" not in m["floats"][0] and "asset" not in m["floats"][0]
```

Order is by the kept caption's own `line`: `Table 2.` (period form, line 2) loses to the colon form on line 6, so Table 2 sorts after Figure 1 (line 3). Lines are counted with `text.split("\n")` — not `splitlines()`, which also splits on `\f` and would shift every line number; `page` = 1 + the number of `\f` before the line.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: `AttributeError: module 'fetch' has no attribute '_caption_scan'`

- [ ] **Step 3: Implement `_caption_scan` and the two `floats` branches**

Caption line: `^\s*(Figure|FIGURE|Fig\.|Table|TABLE)\s+([A-Z]?\d+|[IVXLC]+)\s*([:.]?)\s*(.*)$`. Prefer `:` over `.` over no separator per `(kind, number)`; the no-separator form is accepted only for all-caps `TABLE`/`FIGURE` (IEEE). Caption = that line plus following lines, at most 3, stopping at a blank line or at another caption line, whitespace-joined (`\f` stripped). Branch order in `floats` after `source.tex`: `sorted(workdir.glob(".*.parts/source.md"))[0]` (no `page`, no `asset`), then `sorted(workdir.glob("*.pdf"))[0]` via `pdftotext -layout` (same failure handling as `limitations()`: `floats-unavailable` on error, non-zero exit or empty text), adding `asset` per float from the rendered page (`page-P.png`, one render per page, the PDF page command in Global Constraints; `null` + reason without `pdftoppm`).

- [ ] **Step 4: Run to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: every line `ok`

- [ ] **Step 5: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit   # subject: feat(fetch): scan captions when there is no LaTeX
```

### Task 4: Primer contract — 圖表導覽 replaces 方法速覽

**Files:**
- Modify: `lecture-format.md:155-160` (concreteness scope mentions〈方法速覽〉), `:185-206` (common 圖表單元), `:240-247` (primer purpose and length), `:249-268` (skeleton), `:336` (prerequisites coverage), `:354-395` (〈方法速覽〉section → `## 圖表導覽`), broad's「篇幅上限」figure line (`:463`), deep's figure rule if any
- Modify: `SKILL.md:3` (description), `:12-16` (primer bullet), `:118-123` (resume), `:251-257` (Step 1 primer plan), `:287` (primer work dir), `:355-362` (導讀 writer), `:370-380` (brief: figure units link to primer), `:536-540` (Figures paragraph)

**Interfaces:**
- Consumes: `python3 ~/.claude/skills/ppread/fetch.py --floats <workdir>` and its JSON from Tasks 2–3.

- [ ] **Step 1: Rewrite `lecture-format.md`'s primer part to the Design**

Purpose line becomes「這篇在做什麼、當時卡在哪裡、它怎麼做、實驗動了哪些變因、結果如何，以及每張圖、每張表在畫什麼、怎麼讀」. Remove the「篇幅明顯短於舊版 broad」paragraph; keep「這兩節單薄⋯等於失敗」and add〈圖表導覽〉to it. Skeleton per Design. New `## 圖表導覽` section: one unit per numbered caption, figures and tables interleaved in `--floats` order, headings `### Figure N　<short title>`/`### Table N　<short title>` using the printed number; the unit bullets, table transcription rule, appendix short form and the moved worked trace exactly as in the Design; one complete exemplar for a table (Table 2 of 1706.03762: transcribe two rows, trace the EN-DE 28.4 vs. 26.36 comparison, numbers with `（Table 2）`) and the existing Figure 2 exemplar extended with 圖上有什麼; a figure whose `asset` is `null` says so in one line and is explained from caption and text, never described as if seen; a caption-scan table whose columns cannot be aligned from the text embeds the page image and says the transcription was not possible. 〈讀懂它需要先知道的〉gains: its list covers every term needed to read any figure or table (metrics, axis quantities, units). Common rules: update `:155-160` to name〈圖表導覽〉instead of〈方法速覽〉, add「圖表說明只寫一次」beside「前置知識只寫一次」. Broad's cap line becomes「圖表單元只給被正文主張引用的圖表；`primer.md` 已完成時，圖上有什麼與怎麼讀連回導讀的該單元，不重寫」.

- [ ] **Step 2: Rewrite `SKILL.md`'s primer steps**

Step 1 primer plan: drop the〈方法速覽〉line; add「Run `fetch.py --floats <workdir>`; list every numbered caption it returns as a planned unit (state `inventory`, `numbering`, and any `asset: null`)」and「which figure carries the worked trace」; the prerequisite list must cover every term the figures and tables need. Step 2: on `needs-html`/`needs-pdf` the primer saves the converted text to `<workdir>/.primer.parts/source.md` before `--floats`/`--limitations` (the directory holds only that file). Resume: `.<mode>.parts/` → orchestrated resume **for broad and deep**; for primer, the part-file rule — and inside〈圖表導覽〉truncate from the last `###` unit heading, not from `## 圖表導覽`. 導讀 writer: 〈圖表導覽〉is written in passes of at most 4 units each, appended. Brief (broad/deep): when `primer.md` is finished, list its figure-unit headings so writers link instead of rewriting. Figures paragraph: `--floats` already put viewable PNGs in `assets/<slug>/` — embed `asset` as given; `asset: null` → say the figure could not be viewed. Description (`:3`): primer clause becomes「every prerequisite the paper assumes, abstract, introduction and conclusion paragraph by paragraph …, every figure and table explained so the reader can read it, and a one-glance table …」(drop "the method as one worked example").

- [ ] **Step 3: Verify no stale references remain**

Run: `grep -n '方法速覽\|六成以下\|method as one worked example' SKILL.md lecture-format.md questions.md CLAUDE.md`
Expected: no output

Run: `python3 tests/offline_checks.py`
Expected: every line `ok`

- [ ] **Step 4: Commit**

```bash
git add lecture-format.md SKILL.md
git commit   # subject: docs(format): primer explains every figure and table
```

### Task 5: Quiz contract in `questions.md`

**Files:**
- Modify: `questions.md` (new top-level `# 拷問與筆記檢查` part after the paper parts, before `# 簡報`; `〈邊界〉` at `:110-115`)
- Test: `tests/offline_checks.py` (new `check_quiz_log_is_not_a_lecture`, added to `CHECKS`)

**Interfaces:**
- Produces: the `quiz.md` format and the grading values of Design B, which Task 6's `SKILL.md` steps cite by section name (`拷問`, `筆記檢查`, `紀錄檔 quiz.md`).

- [ ] **Step 1: Write the pin test** `check_quiz_log_is_not_a_lecture`:

```python
def check_quiz_log_is_not_a_lecture() -> None:
    d = Path(tempfile.mkdtemp()) / "paper-a"
    write_doc(d / "broad.md", {**A, "mode": "broad"})
    before = fetch.lecture_docs(d)
    (d / "quiz.md").write_text(
        "---\ntype: quiz\ngenerated: claude\ntitle: Paper A (typo)\n"
        "arxiv: 1111.11111\nsessions: 1\nopen_points: 1\n---\n\n## 待加強\n", "utf-8")
    assert fetch.folder_conflict(d, A_META, "paper-a") is None
    assert fetch.library_row(d, "paper-a")["title"] == "Paper A"
    assert fetch.lecture_docs(d) == before
    rows = fetch.list_library(d.parent)["papers"]
    assert [r["title"] for r in rows] == ["Paper A"], rows
```

- [ ] **Step 2: Run it**

Run: `python3 tests/offline_checks.py`
Expected: every line `ok`, including `ok  check_quiz_log_is_not_a_lecture`. This pins existing behaviour (no `fetch.py` change is planned); if it fails, `quiz.md` would be read as a lecture — fix `fetch.py` so that a file outside `DOC_FILES` is never read for identity, and add that to the commit.

- [ ] **Step 3: Write the `questions.md` quiz part**

Sections, each to Design B: `## 拷問`（gate、scope、session steps 1–7、four question types with one example each taken from 1706.03762 and its location）、`## 筆記檢查`（claim split、five verdicts、no replacement sentence）、`## 紀錄檔 quiz.md`（the template, the front-matter rules and why `mode` and `type: reading` are forbidden, ticking rule）. 〈邊界〉gains the verbatim-in-`quiz.md` exception, worded so that everything outside `--quiz`/`--check` is unchanged.

- [ ] **Step 4: Verify the wording covers Review Focus 7–10**

Run: `grep -n '不知道\|論文未說明\|不提供改寫\|partial' questions.md`
Expected: each of Review Focus 7–10 has a sentence in the new part (blank answer → all `遺漏`; true-but-unstated → `論文未說明`, not an open point; paraphrase → `正確`, no rewording; `partial` → gate stops).

- [ ] **Step 5: Commit**

```bash
git add questions.md tests/offline_checks.py
git commit   # subject: docs(questions): quiz and note-check contract
```

### Task 6: Quiz workflow in `SKILL.md`

**Files:**
- Modify: `SKILL.md:3` (description), `:20-21` (the no-questions principle), `:30-50` (Invocation table and flag stripping), new `## Quiz and note check` section after Step 4 (before「Listing」)

**Interfaces:**
- Consumes: `questions.md`〈拷問〉〈筆記檢查〉〈紀錄檔 quiz.md〉from Task 5; Step 0's `fetch.py` JSON (`workdir`, `docs`).

- [ ] **Step 1: Edit the principle and the invocation**

`:20` to Design B's restatement. Invocation table gains the two rows of Design B. The strip list becomes `--primer`/`--broad`/`--deep`/`--research`/`--quiz`/`--check <note>`; `--check` takes the next argument as the note path, and the path is never passed to `fetch.py`.

- [ ] **Step 2: Write `## Quiz and note check`**

Steps: (1) Step 0 only — on any non-success route handle it as Step 0 says; on success apply the gate to `docs`. (2) Read every finished lecture and, if present, `quiz.md`; the source file (`source_path`, `.<mode>.parts/source.md`, or the PDF) is where quotes come from — never quote a lecture as if it were the paper. (3) Run the session or the check exactly as `questions.md` says. (4) Create `quiz.md` on the first graded answer, not before (an abandoned quiz leaves nothing). Description (`:3`): add「--quiz questions the reader one question at a time on what the finished lectures cover and grades each answer against the source; --check checks the reader's own note claim by claim without rewriting it; both keep a verbatim log in quiz.md」; replace「Never stops to ask a choice it can make itself」with「Writing a lecture never stops to ask a choice it can make itself」.

- [ ] **Step 3: Verify**

Run: `grep -n -- '--quiz\|--check\|quiz.md' SKILL.md`
Expected: hits in the description, the principle, the Invocation table, the strip list and the new section.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md
git commit   # subject: docs(skill): add --quiz and --check
```

### Task 7: Gap types in 精讀, evidence kinds in 通讀

**Files:**
- Modify: `lecture-format.md:674-693` (精讀〈主張與證據〉table and rules), `:559-570` (通讀〈延伸閱讀〉table and rules)
- Modify: `questions.md` 精讀 fixed questions only if one of D1–D5 asks about evidence strength — then its reference-answer note names `缺口類型`

- [ ] **Step 1: Add `缺口類型` to the claims table**

Column after `強度`; exemplar rows: FLOPs row `證據缺口`, parallelisation row `證據缺口`, ConvS2S row `—`. Rules from Design C, with the 論證跳躍 definition and its O(1) example verbatim from Design C.

- [ ] **Step 2: Add `類型` to the further-reading table**

Column after `為什麼讀`; exemplar Bahdanau row `對照做法`; rules from Design C.

- [ ] **Step 3: Verify**

Run: `grep -n '缺口類型\|複現或反證' lecture-format.md SKILL.md`
Expected: both terms in `lecture-format.md`; if `SKILL.md`'s checker instructions (broad/deep checker brief) list the table columns, they name the new columns too.

- [ ] **Step 4: Commit**

```bash
git add lecture-format.md questions.md SKILL.md
git commit   # subject: docs(format): gap types in deep, evidence kinds in broad
```

### Task 8: Project docs, deploy and live check

**Files:**
- Modify: `CLAUDE.md` (What this is: primer sentence and the quiz sentence; Architecture: `fetch.py` list adds `--floats`, `questions.md` line adds the quiz contract; Non-obvious decisions: two new bullets, and the「The skill never asks a choice it can make itself」bullet restated; Testing: list the four new checks and the live case)
- Modify: `~/computer-science/TOOLS.md` (`/ppread` paper row, a new `/ppread --quiz｜--check` row, the「選工具速查」row; separate repo, commit on its `main` per that repo's CLAUDE.md)

- [ ] **Step 1: Add the CLAUDE.md decision bullets**

Figures: the primer explains every figure and table, so「every」must be checkable — `--floats` inventories numbered captions deterministically (subfigure captions are not numbered; `numbering: custom` defers to printed numbers) and converts PDF/EPS figures to PNG because the agent cannot view them, which was the reason most figure units used to say "could not be viewed"; caption scan is the lower-fidelity fallback and says so in `inventory`.
Quiz: lectures are one-way and their answers sit one click away; `--quiz` makes the reader retrieve, `--check` checks the reader's own note without writing it, which serves the Zettelkasten boundary; `quiz.md` has no `mode` and is not `type: reading`, so it is invisible to every lecture check; answers are logged verbatim, never turned into notes; the topic-level research mode is deferred to issue #37, to be designed with the Obsidian paper map.

- [ ] **Step 2: Live check**

Run: `python3 fetch.py 1706.03762 --out "$TMP/lib"` then `python3 fetch.py --floats "$TMP/lib/attention-is-all-you-need"` (`$TMP` = the session scratchpad)
Expected: `inventory: latex`; figure ordinals 1–5 and table ordinals 1–4 matching the paper's printed Figure 1–5 / Table 1–4 (the published paper has these; if the count differs, record the actual numbers and check against https://arxiv.org/abs/1706.03762 before proceeding); every figure `asset` non-null and each PNG opens with Read.

- [ ] **Step 3: Deploy and run the offline checks**

Run: `./deploy.sh && python3 tests/offline_checks.py`
Expected: `deployed -> /home/wassup/.claude/skills/ppread`, every line `ok`

- [ ] **Step 4: Live quiz check (manual)**

On a library folder that already has a finished lecture (`python3 fetch.py --list` shows one), run `/ppread --quiz <its source>`, answer two questions — one correctly, one with「不知道」— then「停」.
Expected: one question per message; the second answer's points all `遺漏`, each with a verbatim source quote; `quiz.md` created with `type: quiz`, no `mode`, `sessions: 1`, `open_points` ≥ 1; `python3 fetch.py --list` output identical to before the quiz (no new row, no `conflict`). If no finished lecture exists in the library, or the check is not run in this conversation, open a GitHub issue for it per the user's global rule (what to run, what to expect, why it was not run) instead of marking the step done.

- [ ] **Step 5: Commit both repos**

```bash
git add CLAUDE.md
git commit   # subject: docs(claude): record the figure inventory and quiz mode
git -C ~/computer-science add TOOLS.md
git -C ~/computer-science commit   # subject: docs(tools): ppread primer figures and quiz mode
```

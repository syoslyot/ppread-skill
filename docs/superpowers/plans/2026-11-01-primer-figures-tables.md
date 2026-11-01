# Primer Figures and Tables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 導讀 `primer.md` lets the reader understand every figure and every table of the paper, beside the prerequisites, Abstract, Introduction and Conclusion.

**Architecture:** `fetch.py` gains `--floats WORKDIR`, a deterministic inventory of every figure and table (from `source.tex`, else a caption scan of `source.md` or the PDF) that also puts a viewable PNG of every figure into `assets/<slug>/`. `lecture-format.md` replaces〈方法速覽〉with〈圖表導覽〉, one unit per numbered caption. `SKILL.md` plans the primer from the inventory and writes the new section in bounded passes.

**Tech Stack:** Python 3 standard library; optional `pdftoppm`, `pdftotext` (poppler) and `gs` (Ghostscript); Markdown specs; `tests/offline_checks.py` (plain asserts, `CHECKS` list).

**Spec:** this plan's Design section. The user's request (2026-11-01): 導讀要提供先備知識、摘要、Introduction、Conclusion、圖、表的說明，讓讀者看懂每張圖和表格。The user declined design questions ("每篇論文都不一樣"), so the decisions below are the planner's calls.

## Design

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

## Global Constraints

- `fetch.py` stays standard-library only; `pdftoppm`, `pdftotext`, `gs` are optional and detected with `shutil.which`, like `pdfinfo`.
- Deployable files stay exactly: `SKILL.md`, `lecture-format.md`, `questions.md`, `slides.md`, `slides-format.md`, `fetch.py`.
- Assets go to `<workdir.parent>/assets/<workdir.name>/` — the existing `assets/<slug>/` convention, which `list_library` already skips. File name = path inside `src/` with `/` replaced by `-`, extension `.png` after conversion (`figs/arch.pdf` → `figs-arch.png`; `a.png` → `a.png`).
- Conversion: PDF → `pdftoppm -png -r 150 -singlefile -f 1 -l 1 <in> <out-stem>`; EPS → `gs -q -dSAFER -dBATCH -dNOPAUSE -dEPSCrop -sDEVICE=png16m -r150 -o <out> <in>`; PDF page for caption scan → `pdftoppm -png -r 110 -singlefile -f P -l P <pdf> assets/<slug>/page-P`. Every subprocess has `timeout=60`.
- A destination that already exists and is not older than its source is not rewritten.
- `questions.md`, slides workflow and slide files do not change.
- Branch `feature/primer-figures-tables` off `develop`. No merge or PR without the user's explicit instruction.
- Commits: Conventional Commits subject; body = technical bullets in Chinese, blank line, `問題：關於導讀的版本，還需要讓我可以看懂每張圖和表格。導讀要提供：先備知識、摘要、introduction、summary、圖、表的說明`, blank line, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run `python3 tests/offline_checks.py` after every `fetch.py` change; every line must print `ok`.

## Review Focus

1. **`\caption[short]{long with {nested} braces}`** must yield the whole long caption, not the short one or a truncated one. Pinned in Task 1 (`check_floats_latex`).
2. **A float commented out by whole-line `%`** must not be inventoried, and inline `% \caption{x}` must not add a caption. Pinned in Task 1.
3. **`\includegraphics[width=...]{figs/arch}` with no extension, or a missing file,** must resolve to `figs/arch.pdf` or report `asset: null` with a reason — never raise. Pinned in Task 2 (`check_floats_assets`).
4. **Re-running `--floats`** must not re-convert an up-to-date asset and must return identical JSON. Pinned in Task 2.
5. **A body line starting "Table 2. shows…" before the real caption "Table 2: …"** must not win over the colon caption; IEEE `TABLE IV` and `Fig. 3.` must be found. Pinned in Task 3 (`check_floats_caption_scan`).

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

### Task 5: Project docs, deploy and live check

**Files:**
- Modify: `CLAUDE.md` (What this is: primer sentence; Architecture `fetch.py` list adds figure/table inventory (`--floats`); Non-obvious decisions: new bullet; Testing: list the three new checks and the live case)
- Modify: `~/computer-science/TOOLS.md` (`/ppread` paper row; separate repo, commit on its `main` per that repo's CLAUDE.md)

- [ ] **Step 1: Add the CLAUDE.md decision bullet**

Content: the primer explains every figure and table, so「every」must be checkable — `--floats` inventories numbered captions deterministically (subfigure captions are not numbered; `numbering: custom` defers to printed numbers) and converts PDF/EPS figures to PNG because the agent cannot view them, which was the reason most figure units used to say "could not be viewed"; caption scan is the lower-fidelity fallback and says so in `inventory`.

- [ ] **Step 2: Live check**

Run: `python3 fetch.py 1706.03762 --out "$TMP/lib"` then `python3 fetch.py --floats "$TMP/lib/attention-is-all-you-need"` (`$TMP` = the session scratchpad)
Expected: `inventory: latex`; figure ordinals 1–5 and table ordinals 1–4 matching the paper's printed Figure 1–5 / Table 1–4 (the published paper has these; if the count differs, record the actual numbers and check against https://arxiv.org/abs/1706.03762 before proceeding); every figure `asset` non-null and each PNG opens with Read.

- [ ] **Step 3: Deploy and run the offline checks**

Run: `./deploy.sh && python3 tests/offline_checks.py`
Expected: `deployed -> /home/wassup/.claude/skills/ppread`, every line `ok`

- [ ] **Step 4: Commit both repos**

```bash
git add CLAUDE.md
git commit   # subject: docs(claude): record the figure and table inventory
git -C ~/computer-science add TOOLS.md
git -C ~/computer-science commit   # subject: docs(tools): ppread primer explains every figure and table
```

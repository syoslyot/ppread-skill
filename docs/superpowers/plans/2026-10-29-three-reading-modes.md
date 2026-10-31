# Three Reading Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `/ppread` three paper modes — 導讀 `primer`, 通讀 `broad`, 精讀 `deep` — that never ask the user a choice, with 通讀 and 精讀 written by an orchestrator plus parallel section writers.

**Architecture:** `fetch.py` gains the third mode in its state model, a hidden per-lecture work directory, and three deterministic commands (`--assemble`, `--finish`, `--limitations`). `SKILL.md` gets the new mode sequence, the no-questions rules and the production protocol. `lecture-format.md` and `questions.md` get the 導讀 contract, the whole-paper 通讀 contract and the #24/#25/#26 additions.

**Tech Stack:** Python 3 standard library (`pdftotext` optional); Markdown specs; `tests/offline_checks.py` (plain asserts, `CHECKS` list).

**Spec:** `docs/superpowers/specs/2026-10-29-three-reading-modes-design.md`

## Global Constraints

- `MODES["paper"] == ("primer", "broad", "deep")`; `MODES["slides"]` unchanged `("broad", "deep", "research")`.
- `DOC_FILES` gains `"primer.md"` and `"primer.part.md"`.
- Work directory: `<workdir>/.<mode>.parts/` holding `00-header.md`, `brief-NN.md`, `NN-<slug>.md` (finished) / `NN-<slug>.tmp.md` (in progress), `context.json`, optional `source.md`.
- `fetch.py` stays standard-library only; `pdftotext` optional, like `pdfinfo`.
- Deployable files stay exactly: `SKILL.md`, `lecture-format.md`, `questions.md`, `slides.md`, `slides-format.md`, `fetch.py`.
- Slides workflow and its files do not change.
- Paper 中文 labels: 導讀 / 通讀 / 精讀. Slides keep 廣讀 / 深讀 / 研究.
- Branch `feature/three-reading-modes` (stacked on `feature/concrete-explanations`). No merge or PR without the user's explicit instruction.
- Commits: Conventional Commits subject; body = technical bullets in Chinese, blank line, `問題：講義加入具體化規則後變長，單一 agent 負擔太大；想新增一個專注摘要、導論、結論與完整前提知識的概要模式，三種模式的名稱與製作方式也要重新設計，且使用者只需下 /ppread 與模式，不被詢問任何選擇`, blank line, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run `python3 tests/offline_checks.py` after every `fetch.py` change; every line must print `ok`.

## Review Focus

1. **A folder read before this change** (finished old `broad.md` + `deep.md`) run with no flag must write a 導讀, not stop and not touch the old files. Pinned in Task 1 (`check_primer_state`).
2. **Re-running `--assemble` after an interruption** must yield a byte-identical `<mode>.part.md`, never duplicated parts. Pinned in Task 2 (`check_assemble`).
3. **A writer that died mid-part** (`NN-x.tmp.md` present, no `NN-x.md`) must make `--assemble` refuse and name that brief. Pinned in Task 2 (`check_assemble`).
4. **The hidden work directory and `source.md`** must never show in `--list`, never count as a rival source, never make a course container. Pinned in Task 2 (`check_parts_dir_hidden`).
5. **LaTeX quirks in `--limitations`**: a phrase inside a whole-line `%` comment is not reported; a phrase broken across a line wrap is found. Pinned in Task 3 (`check_limitations`).

---

### Task 1: Third mode in the state model

**Files:**
- Modify: `fetch.py:654-656` (`DOC_FILES`, `MODES`), `fetch.py:713-731` (`lecture_docs`)
- Test: `tests/offline_checks.py`

**Interfaces:**
- Produces: `MODES["paper"] == ("primer", "broad", "deep")`; `lecture_docs(workdir, kind="") -> dict` now includes `"primer"` for papers and reports `"partial"` when `<workdir>/.<mode>.parts/` exists.

- [ ] **Step 1: Write the failing test** — add `check_primer_state` to `CHECKS`:

```python
def check_primer_state() -> None:
    d = Path(tempfile.mkdtemp())
    assert fetch.lecture_docs(d) == {"kind": "paper", "legacy": False,
        "primer": "absent", "broad": "absent", "deep": "absent"}
    # Folder finished before this change: old broad + deep, no primer.
    write_doc(d / "broad.md", {**A, "mode": "broad", "lecture_read": "true"})
    write_doc(d / "deep.md", {**A, "mode": "deep", "lecture_read": "false"})
    docs = fetch.lecture_docs(d)
    assert (docs["primer"], docs["broad"], docs["deep"]) == ("absent", "read", "unread")
    # A hidden work directory alone means in progress.
    (d / ".primer.parts").mkdir()
    assert fetch.lecture_docs(d)["primer"] == "partial"
    assert "primer.md" in fetch.DOC_FILES and "primer.part.md" in fetch.DOC_FILES
    s = Path(tempfile.mkdtemp())
    write_doc(s / "broad.md", {**A, "kind": "slides", "mode": "broad"})
    assert "primer" not in fetch.lecture_docs(s)
```

- [ ] **Step 2: Run** `python3 tests/offline_checks.py` — Expected: `check_primer_state` fails (KeyError/assert on `primer`).

- [ ] **Step 3: Implement** the `MODES`/`DOC_FILES` change and, in `lecture_docs`, treat `(workdir / f".{mode}.parts").is_dir()` like an existing `.part.md`. Update every existing assertion in `tests/offline_checks.py` that spells out a paper `lecture_docs` dict to include `"primer": "absent"` (or the right state) — they are expected to break, not to be deleted.

- [ ] **Step 4: Run** `python3 tests/offline_checks.py` — Expected: every line `ok`.

- [ ] **Step 5: Commit** — subject `feat(fetch): add primer as the first paper mode`.

---

### Task 2: `--assemble` and `--finish`

**Files:**
- Modify: `fetch.py` (new functions after `lecture_docs`; argparse + dispatch in `main`, before the `--list` branch)
- Test: `tests/offline_checks.py`

**Interfaces:**
- Consumes: `MODES` from Task 1.
- Produces:
  - `assemble(workdir: Path, mode: str) -> dict` — routes `"assembled"` `{path, parts}`, `"assemble-incomplete"` `{missing: [brief names]}`, `"assemble-unavailable"` `{reason}` (no parts dir or no `00-header.md`).
  - `finish(workdir: Path, mode: str) -> dict` — routes `"finished"` `{path}`, `"finish-unavailable"` `{reason}` (no `<mode>.part.md`).
  - CLI: `--assemble WORKDIR MODE`, `--finish WORKDIR MODE` (`nargs=2`); a mode not in `("primer","broad","deep")` → log and exit 2. JSON on stdout, exit 0 otherwise.

- [ ] **Step 1: Write the failing tests** — `check_assemble`, `check_finish`, `check_parts_dir_hidden`:

```python
def check_assemble() -> None:
    d = Path(tempfile.mkdtemp()); p = d / ".broad.parts"; p.mkdir()
    (p / "00-header.md").write_text("HEAD\n", "utf-8")
    for n in ("01", "02"):
        (p / f"brief-{n}.md").write_text("b", "utf-8")
    (p / "02-results.md").write_text("TWO\n", "utf-8")
    (p / "01-intro.tmp.md").write_text("half", "utf-8")
    r = fetch.assemble(d, "broad")
    assert r["route"] == "assemble-incomplete" and r["missing"] == ["brief-01.md"]
    assert not (d / "broad.part.md").exists()
    (p / "01-intro.tmp.md").rename(p / "01-intro.md")
    (p / "01-intro.md").write_text("ONE\n", "utf-8")
    r = fetch.assemble(d, "broad")
    assert r["route"] == "assembled"
    first = (d / "broad.part.md").read_text("utf-8")
    assert first.index("HEAD") < first.index("ONE") < first.index("TWO")
    assert "half" not in first and "\nb" not in first   # briefs and tmp never assembled
    (d / "broad.part.md").write_text(first + "STEP7\n", "utf-8")
    fetch.assemble(d, "broad")                           # rerun after interruption
    assert (d / "broad.part.md").read_text("utf-8") == first
    assert p.is_dir()                                    # assemble never deletes
    assert fetch.assemble(Path(tempfile.mkdtemp()), "broad")["route"] == "assemble-unavailable"

def check_finish() -> None:
    d = Path(tempfile.mkdtemp())
    (d / ".deep.parts").mkdir(); (d / "deep.part.md").write_text("x", "utf-8")
    assert fetch.finish(d, "deep")["route"] == "finished"
    assert (d / "deep.md").read_text("utf-8") == "x"
    assert not (d / "deep.part.md").exists() and not (d / ".deep.parts").exists()
    e = Path(tempfile.mkdtemp()); (e / "primer.part.md").write_text("y", "utf-8")
    assert fetch.finish(e, "primer")["route"] == "finished"   # no parts dir: rename only
    assert fetch.finish(e, "primer")["route"] == "finish-unavailable"

def check_parts_dir_hidden() -> None:
    lib = Path(tempfile.mkdtemp()); d = lib / "paper-a"
    write_doc(d / "broad.md", {**A, "mode": "broad"})
    (d / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    p = d / ".deep.parts"; p.mkdir()
    (p / "source.md").write_text("text", "utf-8"); (p / "x.pdf").write_bytes(b"%PDF")
    rows = fetch.list_library(lib)
    slugs = [r["slug"] for r in rows["papers"]]
    assert slugs == ["paper-a"]
    assert rows["papers"][0]["deep"] == "partial"
```

Also extend `check_parts_dir_hidden` with an `adopt_local` re-run on `d / "paper.pdf"` asserting the route is not `conflict` (the hidden `x.pdf` is no rival). Mirror the call shape of the existing adoption checks in the file.

- [ ] **Step 2: Run** `python3 tests/offline_checks.py` — Expected: the three new checks fail (`assemble`/`finish` undefined).

- [ ] **Step 3: Implement** `assemble` and `finish` and the CLI flags. `assemble`: brief `brief-NN.md` is satisfied by a file matching `NN-*.md` that does not end in `.tmp.md`; output = `00-header.md` then finished parts sorted by name, joined with a blank line, written to a temp file in `workdir` and moved over `<mode>.part.md` with `os.replace`. `finish`: `os.replace` the `.part.md` to `<mode>.md`, then `shutil.rmtree` the parts dir if present. If `check_parts_dir_hidden` fails, fix the listing/adoption code so hidden directories are ignored everywhere — do not weaken the test.

- [ ] **Step 4: Run** `python3 tests/offline_checks.py` — Expected: every line `ok`.

- [ ] **Step 5: Commit** — subject `feat(fetch): assemble parallel-written parts and finish lectures`.

---

### Task 3: `--limitations`

**Files:**
- Modify: `fetch.py` (new constant + function; argparse + dispatch)
- Test: `tests/offline_checks.py`

**Interfaces:**
- Produces: `LIMITATION_PHRASES: tuple[str, ...]` = `("future work", "future research", "remains unclear", "remains poorly understood", "has not been examined", "limited evidence", "little is known", "is left for", "we leave", "beyond the scope", "limitation", "to our knowledge", "does not address", "not yet")`; `limitations(workdir: Path) -> dict` → `{"route": "limitations", "source": <path read>, "hits": [{"sentence", "section", "file", "line"}]}` or `{"route": "limitations-unavailable", "reason"}`; CLI `--limitations WORKDIR`.
- Source order, first that exists: `src/*.tex` → `.*.parts/source.md` → the folder's `*.pdf` via `pdftotext -layout <pdf> -` when `shutil.which("pdftotext")`.

- [ ] **Step 1: Write the failing test** — `check_limitations`:

```python
def check_limitations() -> None:
    d = Path(tempfile.mkdtemp()); (d / "src").mkdir()
    (d / "src" / "main.tex").write_text(
        "\\section{Method}\nWe propose X.\n"
        "% We leave this for future work.\n"
        "\\section{Discussion}\nOur evaluation is small. Scaling remains\n"
        "unclear for larger graphs. Results are good.\n", "utf-8")
    r = fetch.limitations(d)
    assert r["route"] == "limitations"
    assert [h["sentence"] for h in r["hits"]] == [
        "Scaling remains unclear for larger graphs."]
    assert r["hits"][0]["section"] == "Discussion" and r["hits"][0]["file"] == "main.tex"
    assert r["hits"][0]["line"] == 5
    e = Path(tempfile.mkdtemp()); (e / ".broad.parts").mkdir()
    (e / ".broad.parts" / "source.md").write_text("A. Little is known about B. C.", "utf-8")
    assert [h["sentence"] for h in fetch.limitations(e)["hits"]] == ["Little is known about B."]
    assert fetch.limitations(Path(tempfile.mkdtemp()))["route"] == "limitations-unavailable"
```

- [ ] **Step 2: Run** `python3 tests/offline_checks.py` — Expected: `check_limitations` fails.

- [ ] **Step 3: Implement.** Whole-line `%` comments are dropped before matching; lines within a paragraph are joined with a space so a wrapped phrase matches; sentences split after `.`/`!`/`?` followed by whitespace; matching is case-insensitive; `line` = 1-based line where the sentence starts; `section` = title of the nearest preceding `\section`/`\subsection` (`""` for non-LaTeX); each sentence reported once even if several phrases hit. Collapse internal whitespace in reported sentences.

- [ ] **Step 4: Run** `python3 tests/offline_checks.py` — Expected: every line `ok`.

- [ ] **Step 5: Commit** — subject `feat(fetch): extract author-stated limitations verbatim`.

---

### Task 4: `SKILL.md` and `CLAUDE.md`

**Files:**
- Modify: `SKILL.md` (frontmatter `description`, Invocation, Step 0 "Choosing the mode", Step 1, Step 2, Step 3, Step 4, Discipline), `CLAUDE.md` (What this is, Architecture, Non-obvious decisions, Testing)

**Interfaces:**
- Consumes: `--assemble`, `--finish`, `--limitations` (Tasks 2–3); state model (Task 1).

- [ ] **Step 1: Baseline** — `grep -n 'Wait for the user\|ask the user whether to resume\|mv "<workdir>' SKILL.md` prints 3 hits; `grep -c 'primer' SKILL.md` prints 0.

- [ ] **Step 2: Edit `SKILL.md`:**
  - Invocation: add `/ppread --primer <source>` 導讀; describe broad as 通讀 (whole paper). Strip `--primer` like the other flags. Description line: three paper modes.
  - Mode sequence: paper = primer, broad, deep; table rows rewritten for three modes; `partial` → always resume per the spec's "Resume" rules (no question); remove "ask the user".
  - Step 1: survey printed as a status block, no waiting. Per-mode plan bullets: primer (units for 論文全貌, prerequisite list with depth limits, the 一頁看懂 sources); broad/deep (part split, term-owner list).
  - Step 2 (Ground the literature): applies to broad; outputs saved into `.<mode>.parts/context.json`; add `--limitations` call for broad.
  - Step 3: split into "導讀 — single writer" (today's loop into `primer.part.md`) and "通讀/精讀 — orchestrator" with the spec's steps 1–8 verbatim in substance (parts dir, `00-header.md`, briefs with owned/linked terms and allowed citations, parallel writers on the session's model with `.tmp.md` → `.md`, one checker, `--assemble`, whole-paper sections from `context.json`, questions). Include the no-Agent-tool fallback and the "prerequisites live once" rule (lowest existing lecture owns them; others link).
  - Step 4: replace the `mv` with `fetch.py --finish <workdir> <mode>`.
  - Discipline: add the #25 rule (load-bearing numbers carry inline provenance `（§4.3）`/`（Table 2）`/`（Figure 5 目測，約）`; critique resting only on a read-off value is `**推測**`) and the #24 rule (〈論證鏈〉before item-by-item critique).
- [ ] **Step 3: Edit `CLAUDE.md`** — three modes in "What this is" and the Architecture bullets; replace the "Two lectures, not one layered file" decision with three; add decisions for the hidden parts dir (why hidden, why `--assemble` overwrites, why only the orchestrator touches the network), `--limitations` (deterministic, verbatim only), and the no-questions rule; add the new checks to Testing.

- [ ] **Step 4: Verify** — `grep -n 'Wait for the user\|ask the user whether to resume\|mv "<workdir>' SKILL.md` prints nothing; `grep -c 'primer' SKILL.md` ≥ 5; `grep -n -- '--assemble\|--finish\|--limitations\|context.json' SKILL.md` finds each; `wc -l SKILL.md` ≤ 520; if over, report DONE_WITH_CONCERNS and let the controller rule.

- [ ] **Step 5: Commit** — subject `docs(skill): three paper modes, no mid-run questions, parallel production`.

---

### Task 5: `lecture-format.md` and `questions.md`

**Files:**
- Modify: `lecture-format.md` (title area, 共通規則 references to 廣讀, new `# 導讀文件 primer.md`, rewritten `# 通讀文件 broad.md`, `# 精讀文件 deep.md` additions), `questions.md` (paper part only)

**Interfaces:**
- Consumes: section names Task 4's `SKILL.md` points at: 「共通規則」「導讀文件」「通讀文件」「精讀文件」; `--limitations` output fields `sentence/section/line`.

- [ ] **Step 1: Baseline** — `grep -c '導讀\|通讀' lecture-format.md` prints 0; `grep -n '論證鏈\|量測它的變數\|作者自述的限制\|一頁看懂' lecture-format.md` prints nothing.

- [ ] **Step 2: Write `# 導讀文件 primer.md`** with the spec's skeleton (header block, 〈一頁看懂〉, 〈讀懂它需要先知道的〉, 〈論文全貌〉 Abstract/Introduction/Conclusion paragraph units, 〈方法速覽〉, 〈問題〉). 〈一頁看懂〉 exemplar = a five-row table (要解決的問題 / 當時的困難 / 做法 / 實驗的變因 / 結果) for *Attention Is All You Need*, every number with its provenance. 〈方法速覽〉: no paragraph units; one worked example with real values (此例非論文所有) and one analogy with its failure point. Move the existing BLEU/COMET prerequisite exemplar here. Paragraph-unit 解說 link to prerequisites rather than re-explain.

- [ ] **Step 3: Rewrite the broad section as `# 通讀文件 broad.md`** with the spec's skeleton: prerequisites only when `primer.md` is absent (else one relative-link line), one `##` per paper section with key paragraphs as paragraph units and the rest in 解說 bullets, figure units, no critique; then 〈作者自述的限制〉 (each hit: `> ` quote, 中文翻譯, 位置, one 解說 bullet classifying it as 方法／資料／概念 and, marked `**推測**`, whether it is a follow-on topic; zero hits → one explicit line), then 〈它在研究脈絡中的位置〉 and 〈延伸閱讀〉 unchanged. Rename 廣讀→通讀 everywhere in this file.

- [ ] **Step 4: Extend `# 精讀文件 deep.md`** — 〈論證鏈〉 before 〈主張與證據〉 (one chain line `研究問題 → 設計 → 資料 → 方法 → 分析 → 詮釋 → 結論 → 標題`, each break with its location, or 「未發現斷點」); add column 「量測它的變數」 to the 主張與證據 table (none → strength 「未支持」); background line points to `primer.md` when it exists. Show #25 provenance in the exemplars.

- [ ] **Step 5: Edit `questions.md` (paper part)** — add `### 導讀` with P1–P5 based on Keshav's first-pass five Cs (category, context, correctness of assumptions, contributions, clarity), P5 = 「值得通讀嗎？」 with an explicit verdict; retitle `### 廣讀` → `### 通讀`, keep B1–B5 numbering, reword for a whole-paper read; keep D1–D5, note D2's answer draws on〈論證鏈〉first. Do not touch the `# 簡報` part.

- [ ] **Step 6: Verify** — `grep -c '導讀' lecture-format.md` ≥ 3; `grep -c '通讀' lecture-format.md` ≥ 3; `grep -n '論證鏈\|量測它的變數\|作者自述的限制\|一頁看懂' lecture-format.md` finds all four; `grep -n 'P1\|P5' questions.md` finds both; `grep -nE '是一種.{0,20}(工具|機制|技術|指標)|可以用來' lecture-format.md` hits only rule text / 反例 lines; `sed -n '/^# 簡報/,$p' questions.md | git diff --no-index --quiet - <(git show HEAD:questions.md | sed -n '/^# 簡報/,$p') && echo slides-unchanged`.

- [ ] **Step 7: Commit** — subject `docs(format): primer contract, whole-paper broad, argument chain in deep`.

---

### Task 6: Deploy and live runs (controller)

**Files:** none changed. Output under the session scratchpad only.

Executed by the controller: the 通讀 run needs the Agent tool to dispatch writers, which a subagent does not have.

- [ ] **Step 1:** `CLAUDE_SKILLS_DIR=<scratchpad>/skills ./deploy.sh`; `diff` each deployable against the copy — empty.
- [ ] **Step 2:** Follow the scratch copy's `SKILL.md` for `--primer 1706.03762` with `--out <scratchpad>/papers`. Check: 〈一頁看懂〉 has five rows with provenance; prerequisites have numbered traces; the file is shorter than the earlier `broad.md` of the same paper (62 KB); `primer.md` exists and `primer.part.md` does not.
- [ ] **Step 3:** Same copy, `--broad 1512.03385` with `--out <scratchpad>/papers`, acting as orchestrator. Check: writers ran in parallel; `.broad.parts/` is gone after `--finish`; every paper section has a `##`; 〈作者自述的限制〉 quotes only `--limitations` hits; no outside paper absent from `context.json`; banned-phrase grep empty.
- [ ] **Step 4:** Report sizes and any rule the runs broke; fix through the review loop before the final review.

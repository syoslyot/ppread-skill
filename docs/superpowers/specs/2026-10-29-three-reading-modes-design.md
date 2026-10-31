# Three Reading Modes — Design

Date: 2026-10-29
Branch: `feature/three-reading-modes` (stacked on `feature/concrete-explanations`, #28)

## Intent

The user reads a paper to answer, in order: what is this about, what was hard
at the time, what does it set out to solve, how, which variables the experiments
turn, and how it came out. Today's two paper modes do not fit that order:
`broad.md` explains abstract/introduction/conclusion plus a sliver of method and
the literature graph, and `deep.md` critiques every paragraph. #28 made every
explanation concrete (parts → numbered trace with real values → why → what
breaks), which is right but roughly triples the length of any section that
explains background — too much for one agent writing a whole-paper lecture in
one context.

This design adds a short entry lecture, widens the middle one to the whole
paper, and makes the long lectures be written by several agents in parallel —
without the user ever being asked how.

Grounding: Keshav's three passes ("How to Read a Paper", SIGCOMM CCR 2007,
already the basis of `questions.md`): pass 1 decides whether to read on; pass 2
grasps the content well enough to summarise it with evidence; pass 3 re-creates
the paper and challenges its assumptions. The three modes map onto them.

## Goals

1. Three paper modes, in reading order:

   | 中文 | flag / file | Keshav | covers |
   |---|---|---|---|
   | 導讀 | `--primer` / `primer.md` | pass 1 + full prerequisites | abstract, introduction, conclusion paragraph by paragraph; complete prerequisites; method as one worked example + one analogy; a one-glance table of problem / difficulty / approach / variables / results |
   | 通讀 | `--broad` / `broad.md` | pass 2 | every section of the paper explained at moderate depth, no critique; literature context from `--graph`; author-stated limitations |
   | 精讀 | `--deep` / `deep.md` | pass 3 | as today, plus〈論證鏈〉and a measured-variable column (#24) |

2. With no flag, the first unfinished mode in `primer → broad → deep` is written
   (today's rule, new sequence). So `/ppread <paper>` starts with 導讀.
3. The skill never stops to ask the user a choice it can make itself (see
   "No questions").
4. 通讀 and 精讀 are written by an orchestrator plus parallel section writers
   (see "Production"); 導讀 by a single agent. The user sees none of this.
5. Fold in: #24 (精讀〈論證鏈〉+ 構念效度欄), #25 (承重數字標出處), #26
   (作者自述的限制 via a deterministic `fetch.py` extractor). Close #27 as
   superseded (the confirmation it wanted to improve is removed).

## Non-goals

- Course-slide modes (`slides.md`, `slides-format.md`) do not change. Slides keep
  broad / deep / research and single-agent production.
- No migration of existing `broad.md` files. Old ones were written to the old
  contract (abstract/intro/conclusion + core method + context); they remain
  valid finished lectures, keep their state, and are not rewritten. Regenerating
  is the user's explicit request, as today.
- No change to `papers.base` (it already shows `mode` generically; new files
  carry `mode: primer`). No change to the Zettelkasten boundary: lectures only.

## Anti-goals

- A 導讀 that is just a translated abstract. Its value is the prerequisites and
  the one-glance table; if those are thin the mode has failed.
- Length for its own sake. The concreteness rule (#28) decides how each layer
  is explained, the depth limit decides how many layers; 導讀 must come out
  clearly shorter than today's `broad.md` for the same paper.
- Section writers inventing numbers or outside papers. Every rule in
  〈Discipline〉binds every agent, and only the orchestrator talks to the network.
- A skill that asks "should I…?" mid-run.

## Decisions

### Names

- 導讀 / `primer`: Chinese publishing's「導讀」is the text that walks a reader
  into a book — background, gist, why it matters. 「略讀」was rejected: it
  reads as "skip through", the opposite of "prerequisites complete".
- 通讀 / `broad`: Chinese label changes from 廣讀 to 通讀 ("read the whole text
  through"), which is what the mode now does. Flag and file stay `--broad` /
  `broad.md` so the user's habits, Obsidian views and existing files keep
  working. Slides keep the label 廣讀 for their own broad mode — different
  document, unchanged.
- 精讀 / `deep`: unchanged.

### 導讀 `primer.md` skeleton

```
# <title>
> 來源 / 保真度 / 本篇在做什麼（兩句判斷）
## 一頁看懂          ← five-row table, see below
## 讀懂它需要先知道的 ← full #28 concreteness, numbered traces
## 論文全貌
### Abstract / ### 1 Introduction / ### N Conclusion   ← paragraph units
## 方法速覽          ← no paragraph units; one worked example, one analogy with its failure point
## 問題
```

〈一頁看懂〉rows, each one or two sentences with its source location:
要解決的問題 / 當時的困難（為什麼既有做法不夠）/ 做法（一句話）/
實驗的變因（自變數、固定條件、評估指標）/ 結果（附數字與出處）. Numbers
carry #25 provenance. This is the table the user asked for verbatim.

Paragraph-unit 解說 in 導讀 point back to〈讀懂它需要先知道的〉instead of
re-explaining (the demo that tripled the abstract unit inlined five prerequisites;
that is what the section exists to prevent).

### 通讀 `broad.md` skeleton

```
# <title>
> 來源 / 保真度 / 本篇在做什麼
## 讀懂它需要先知道的   ← only when primer.md is absent; else one line linking to it
## <each paper section, in the paper's own numbering>
   key paragraphs as paragraph units; the rest summarised in 解說 bullets;
   figures and tables as figure units; no critique (that is 精讀's)
## 作者自述的限制        ← from fetch.py --limitations, verbatim (#26)
## 它在研究脈絡中的位置   ← moved unchanged from today's broad
## 延伸閱讀
## 問題
```

"Key paragraph" = one the section's claim depends on (method overview, the
defining formula, an experimental-setup paragraph, a result paragraph). The
writer of each section chooses; the orchestrator's plan names the section range,
not the paragraphs.

### 精讀 `deep.md`

Unchanged skeleton, plus (#24): a〈論證鏈〉section before「主張與證據」— one
line `研究問題 → 設計 → 資料 → 方法 → 分析 → 詮釋 → 結論 → 標題`, each break
marked with its location, or「未發現斷點」— and a「量測它的變數」column in
「主張與證據」(no variable → strength「未支持」). Its background reference line
points to `primer.md`〈讀懂它需要先知道的〉when that exists (today it points to
broad).

### Prerequisites live once

The lowest existing lecture in `primer → broad → deep` owns
〈讀懂它需要先知道的〉; higher ones link to it with a relative link. A higher
mode run without a lower one writes its own. (Each lecture stays self-contained
in front matter, as decided in v0.2.)

### #25 number provenance

〈Discipline〉gains a rule: every load-bearing number (one that supports an
explanation, critique or answer) carries its provenance inline —
`（§4.3）`, `（Table 2）`, `（Figure 5 目測，約）`. A critique resting only on a
read-off-the-figure value is marked `**推測**`. Format files' exemplars show it.

### #26 `fetch.py --limitations <workdir>`

Deterministic extractor. Input: the workdir; it reads, first match wins,
`src/*.tex` (latex route), `.<mode>.parts/source.md` (saved by the orchestrator),
or the folder's PDF via `pdftotext` when present. Phrases (case-
insensitive, extensible constant): "future work", "future research", "remains
unclear", "remains poorly understood", "has not been examined", "limited
evidence", "little is known", "is left for", "we leave", "beyond the scope",
"limitation", "to our knowledge", "does not address", "not yet". Output JSON:
`{"route": "limitations", "hits": [{"sentence", "section", "line"}], "source"}`;
`section` from the nearest preceding `\section`/`\subsection` on latex, `""` on
PDF with ±1 sentence of context instead. `route: limitations-unavailable` with a
reason when no text can be read (PDF without `pdftotext`). The lecture quotes
only returned sentences; zero hits → one explicit line, never an empty section.

### No questions

Removed:
- Step 1's "wait for the user to confirm or adjust" — the survey is printed as a
  status block and the run continues.
- `partial` → "ask resume or restart" — always resume (rule below).

Kept, because no default exists: `needs-output-config` (one-time, first ever run),
`needs-title`, `conflict`, `unresolved`, `needs-kind`. These are fetch failures,
not choices.

### Production

**導讀**: one agent, today's loop — sections appended one `##` per pass to
`primer.part.md`, questions, rename.

**通讀 and 精讀**: orchestrator (the session running the skill) + writers.
Everything in progress lives in one hidden directory, `<workdir>/.<mode>.parts/`
— hidden so `--list`, the folder checks and the rival-source checks never see it.

1. Orchestrator: fetch; read the whole source. On routes where `fetch.py` leaves
   no text on disk (`needs-html`, `needs-pdf`), save the converted text as
   `.<mode>.parts/source.md` so writers and `--limitations` can read it. Run
   every network call the lecture needs (`--graph`, all `--verify`) and save the
   raw JSON in `.<mode>.parts/context.json` — writers never touch the network, so
   parallel writers cannot multiply 429s, and a resumed run never repeats a
   call. Run `--limitations` (offline) and save it there too.
2. Write `.<mode>.parts/00-header.md`: front matter, header block, and (when this
   lecture owns them) the prerequisites.
3. Plan: split the paper's sections into 3–6 contiguous parts of similar source
   length. List every background term the paper needs and assign each one
   owner: the prerequisites if it is needed before or across parts, else the
   single part where it first appears. Write one `brief-NN.md` per part: section
   range, source path, which format sections to read, terms it owns (explain
   fully), terms owned elsewhere (link, never re-explain), the verified outside
   papers it may cite (nothing else), figure paths.
4. Dispatch all writers in parallel, same model as the session. Each writes
   `NN-<slug>.tmp.md` and renames it to `NN-<slug>.md` when its last unit is done
   — the rename is the part's completion signal.
5. One checker agent re-computes every numbered trace and checks every
   load-bearing number against the source; it may only correct arithmetic and
   provenance in place, and reports what it changed.
6. `fetch.py --assemble <workdir> <mode>`: concatenates `00-header.md` and the
   finished parts in name order into a temp file and atomically renames it to
   `<mode>.part.md`, overwriting. Idempotent: re-running yields the same file.
   Refuses with `route: assemble-incomplete` (listing them) when a brief has no
   finished part. Does not delete the directory.
7. Orchestrator appends the whole-paper sections that need everything, reading
   `context.json`: 通讀 — 作者自述的限制, 它在研究脈絡中的位置, 延伸閱讀;
   精讀 — 論證鏈, 主張與證據, 設計決策. Then questions.
8. `fetch.py --finish <workdir> <mode>`: renames `<mode>.part.md` to `<mode>.md`
   and removes `.<mode>.parts/`. Used by every mode, 導讀 included (no directory
   → just the rename), replacing the shell `mv`.

State: `lecture_docs` reports `partial` when either `<mode>.part.md` or
`.<mode>.parts/` exists.

Resume (no question asked):
- `.<mode>.parts/` exists → re-dispatch only briefs with no finished part, then
  rerun from step 5. Re-assembling overwrites `<mode>.part.md`, which discards
  any step-7 sections from the interrupted run; step 7 is redone from
  `context.json`. No network call is repeated.
- Only `<mode>.part.md` exists (導讀, or a legacy interruption) → delete from the
  last `##` heading and continue (today's rule).

Fallback when the Agent tool is unavailable: the orchestrator writes each brief's
part itself, sequentially, into the same files; everything else is identical.

### Existing folders

No special case for old-contract `broad.md`. With no flag the first unfinished
mode in `primer → broad → deep` is written, so a paper read before this change
gets a 導讀 on its next bare run, then deep. (Builder's call, recorded: 導讀 is new
content and the cheapest mode; skipping it would need a marker telling old
broad from new.)

## Constraints

- `fetch.py` stays standard library only; `pdftotext` optional like `pdfinfo`.
- Only `SKILL.md`, `lecture-format.md`, `questions.md`, `slides.md`,
  `slides-format.md`, `fetch.py` deploy. New deployables would need `deploy.sh`
  and CLAUDE.md updated — avoid unless a file split is clearly better.
- `MODES["paper"] = ("primer", "broad", "deep")`; `DOC_FILES` gains `primer.md`,
  `primer.part.md`. Every place that enumerates modes or doc files follows.
- `questions.md`: new fixed set for 導讀 (P1–P5, Keshav pass-1 five Cs: category,
  context, correctness of assumptions, contributions, clarity — reworded to suit);
  broad set keeps B1–B5 with wording adjusted to a whole-paper read (B5 still
  "值得精讀嗎"); deep D1–D5 unchanged, D2's answer drawing on〈論證鏈〉first.
- CLAUDE.md's architecture/decisions text updated to the three modes.
- Offline tests cover every `fetch.py` change: `MODES`, `DOC_FILES`, state with
  primer, `partial` from a hidden parts dir, `--assemble` (order, overwrite
  idempotence, incomplete), `--finish` (with and without parts dir), hidden
  parts dir and `source.md` ignored by `--list` and the folder/rival-source
  checks, `--limitations` on a latex fixture and the unavailable route.

## Left to the builder

- Exact wording of rules and exemplars (Attention / machine-translation world for
  `lecture-format.md`, as #28 required).
- Whether the production protocol lives in `SKILL.md` or a new deployable file
  (prefer `SKILL.md` unless it pushes past ~500 lines).
- Part-size heuristic details within "3–6 parts of similar size".
- The phrase list may grow; it must stay a single constant.

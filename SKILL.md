---
name: ppread
description: "Bilingual lectures from research papers and course slides — invoke with /ppread [--primer | --broad | --deep | --research] <arXiv ID | DOI | URL | title | PDF path>, or /ppread --list [dir]. Papers have three modes, read in order: --primer writes primer.md (導讀: abstract, introduction and conclusion paragraph by paragraph — English original, Traditional Chinese translation, explanation — every prerequisite the paper assumes, the method as one worked example, and a one-glance table of problem, difficulty, approach, experimental variables and results); --broad writes broad.md (通讀: every section of the paper explained at moderate depth without critique, the limitations the authors state, and its place in the literature from the Semantic Scholar citation graph); --deep writes deep.md (精讀: the whole paper with critical analysis, the argument chain, a claims-versus-evidence table and design decisions). With no flag, the first unfinished mode in primer → broad → deep is written; the long modes are written by parallel section writers. Course slides (a landscape PDF lecture deck, often carrying the student's own annotations): --broad maps the chapter and explains every technical term in both languages; --deep works through each technical unit with filled-in derivations, worked examples and a check of the student's notes; --research links the chapter's topics to foundational and recent papers found through Semantic Scholar search. Every lecture ends with questions and folded reference answers. --list shows every paper's and chapter's lectures and whether each has been read. Never stops to ask a choice it can make itself. Stops at the lecture and never writes the user's own notes."
---

# /ppread — Lectures from Papers and Course Slides

Turn one paper, or one course chapter, into lectures the user can read straight
through. A paper gets three modes, each written to its own file, in the order a
reader meets the paper (Keshav's three passes):

- **導讀 primer** (`primer.md`) — enter the paper: what it is about, what was hard,
  what it does and how it came out, and every prerequisite needed to read it.
- **通讀 broad** (`broad.md`) — read the whole paper through: every section
  explained at moderate depth, the limitations the authors state, where it sits
  among other work, what to read next. No critique.
- **精讀 deep** (`deep.md`) — judge the paper: does the argument hold, why was each
  design decision made, does the evidence carry the claims.

The skill never stops to ask a choice it can make itself. It asks only when a
fetch fails in a way no default can fix (see Step 0's routes).

A local PDF can also be a **course slide deck**. Slides get three lectures —
broad, deep and research — and their own workflow in `slides.md`; Step 0 below
says when to switch to it.

Fetching and every other step with a right answer lives in `fetch.py`; reading,
translating, explaining and questioning are judgment and live here.

## Invocation

| Command | Does |
|---|---|
| `/ppread <source>` | Picks the mode from what already exists (table in Step 0) |
| `/ppread --primer <source>` | 導讀 — papers only |
| `/ppread --broad <source>` | 通讀 the whole paper (slides: 廣讀) |
| `/ppread --deep <source>` | 精讀 (slides: 深讀) |
| `/ppread --research <slides PDF>` | Research lecture — slides only |
| `/ppread --list [dir]` | Lists papers and lecture state — see "Listing" |

`<source>` may be an arXiv ID or URL, a DOI, a publisher URL, a paper title, or a
local PDF path. The mode is a flag, never a bare word: a title such as
`deep residual learning for image recognition` would otherwise lose its first word
to the mode and resolve to the wrong paper. Strip
`--primer`/`--broad`/`--deep`/`--research` before passing the source to
`fetch.py`; `fetch.py` does not accept them.
`--research` exists only for slides: on a paper, say that a paper's broad lecture
already places it in the literature, and stop. `--primer` exists only for papers:
on slides, say that slides have no primer — their broad lecture is the entry —
and stop.
`--kind` and `--course` are `fetch.py` flags you add yourself when Step 0 asks for
them; the user never types them.

## Step 0: Fetch and choose the mode

```bash
python3 ~/.claude/skills/ppread/fetch.py "<source>"
```

A local file goes through the same script — do not skip it. `fetch.py` reads the
file's own metadata for a title, creates `<slug>/` **in the directory the file is
already in**, and **moves** the file in, so a paper that arrived by hand ends up
shaped exactly like one that was fetched. A local file is never relocated into the
configured library, and for the same reason it never triggers the output-location
question below.

The script prints one JSON object. Read `route` and act:

| `route` | What happened | What to do |
|---|---|---|
| `latex` | arXiv source obtained (tier 1) | Read `source_path`. This is the good case. |
| `needs-html` | No LaTeX; an HTML full text may exist | Fetch `html_url` (or `page_url`) with Firecrawl `firecrawl_scrape`. |
| `needs-pdf` | Only a PDF exists | Paper: convert to text — see "The PDF route" below. **Slides** (`docs.kind: slides`): do not convert — `slides.md` reads the pages as images. |
| `unresolved` | Nothing identified the reference | Stop. Tell the user what was tried and ask for an arXiv ID, a DOI, or a direct URL. Do not guess at which paper was meant. |
| `needs-output-config` | No output location has ever been chosen | Ask (see below), save the answer, re-run Step 0. |
| `conflict` | The folder this paper wants already holds a lecture for another paper | Stop and ask the user — see "When two papers want one folder". Nothing was downloaded or moved. |
| `needs-title` | Local file: its metadata has no title, or a title with no ASCII in it. Network: metadata lookup returned no title, or the title it returned has no ASCII in it | **Slides** (`meta.kind: slides`): `reason` names what is missing — see "Naming: course and chapter" in `slides.md`. The file was **not** moved. Otherwise: **Local**: read its first page (`pdftotext -f 1 -l 1 <file> -`), take the **English** title — a paper written in another language usually prints one on page 1; translate it if it does not — and re-run with `--title "<title>"`. The file was **not** moved. **Network**: check `reason` — a metadata lookup failure is often transient (the same call can succeed a minute later), so **retry the fetch once, unchanged, before asking the user for a title**; only if it still comes back `needs-title` should you ask the user for the paper's English title and re-run with `--title "<title>"`. Nothing was downloaded or created. |
| `needs-kind` | Local PDF whose page size could not be read, so paper vs. slides is unknown | Look at page 1 (Read with `pages: "1"`). Landscape lecture slides → re-run with `--kind slides`; otherwise `--kind paper`. The file was **not** moved. |
| `local` | A local non-PDF source (e.g. `.tex`) already in place | Read `source_path` directly. |

### Choosing the mode

Every non-conflict route that has a `workdir` also carries `docs`:

```json
"docs": {"kind": "paper", "primer": "read", "broad": "partial", "deep": "absent", "legacy": false}
```

`docs.kind` is `paper` or `slides` and fixes the **mode sequence**: paper =
primer, broad, deep; slides = broad, deep, research. `docs` carries one state per mode in
the sequence, each `absent`, `partial` (being written, or interrupted), `unread`
or `read`. A mode is **finished** when its state is `unread` or `read`; `absent`
and `partial` are not finished. The table below is illustrative only and covers
papers; the rule that actually decides, for every combination of either kind, is:

1. **No flag**: the mode to act on is the first in the sequence that is not
   finished. If all are finished, stop and report every path.
2. **`--primer`, `--broad`, `--deep` or `--research`**: the named mode is the mode
   to act on (`--research` on a paper, `--primer` on slides: see Invocation).
3. Whatever mode was selected by 1 or 2: `absent` → write it; `partial` →
   resume it (bullet below), without asking; finished → report the file's path
   and stop.

| finished in `docs` | no flag | `--primer` | `--broad` | `--deep` |
|---|---|---|---|---|
| none | write primer | write primer | write broad | write deep |
| primer | write broad | exists — stop | write broad | write deep |
| primer, broad | write deep | exists — stop | exists — stop | write deep |
| broad only (a folder from before primer existed) | write primer | write primer | exists — stop | write deep |
| all three | stop | stop | stop | stop |

- **exists — stop**: report the file's path. Regenerate only when the user
  explicitly asks: delete the old file, write afresh, and say that `lecture_read`
  was reset to `false`. An old `broad.md` written to the earlier contract
  (abstract, introduction, conclusion, core method) is a finished lecture like any
  other; it is not rewritten.
- **`partial`**: always resume — never ask.
  - `<workdir>/.<mode>.parts/` exists → resume the orchestrated run (Step 3,
    "Resume").
  - Only `<mode>.part.md` exists (導讀, slides, or an older interruption) →
    delete everything from the file's last `##` heading onward and rewrite that
    section, then continue — sections are written one per pass, so only the last
    can be incomplete.
  - Restart only when the user explicitly asks: delete `<mode>.part.md` and
    `.<mode>.parts/`, then begin at Step 1.
- **`legacy: true`**: a `lecture.md` from ppread 0.1 is in the folder. It does not
  block anything; mention it once in the Step 1 status block.

### The PDF route: getting readable text out

Detect what this machine has and use the first that works. Do not ask the user to
install anything until every option has been tried.

1. **MarkItDown MCP** — `convert_to_markdown`. Best structure (headings, tables,
   lists survive). Available only when the session has that MCP server.
2. **`markitdown` CLI** — same engine, no MCP needed:
   ```bash
   command -v markitdown && markitdown "<file.pdf>"
   ```
3. **`pdftotext -layout`** — Poppler, present on most Linux installs. `-layout`
   preserves column geometry, which decides whether a two-column paper comes out
   readable or interleaved:
   ```bash
   command -v pdftotext && pdftotext -layout "<file.pdf>" -
   ```
4. **Nothing available** — stop and say so, with the install line:
   `pip install 'markitdown[pdf]'`, or the distribution's `poppler-utils`.

**None of these recover formulas, and saying otherwise would be misleading.** A
PDF stores glyph positions, not structure; whether a `2` was a superscript, a
subscript or a literal digit is information that stopped existing before any tool
opened the file. MarkItDown makes tier 6 more *readable*, never more *correct*.
The Discipline rules below apply in full on this route. The real fix is always to
climb back to tier 1.

### First run: ask where lectures go

`needs-output-config` means this machine has never been told where papers
belong. **Nothing was downloaded and no directory was created** — the check runs
before any network call precisely so the question comes first. Only network routes
reach it; a local file answers the question by its own location.

Ask the user, offering the two shapes an answer can take (the JSON carries `cwd`
and `suggested_cwd_mode` to fill in concrete paths):

- **One fixed library, always** — every paper lands in the same place no matter
  where the agent was started. Save with:
  ```bash
  python3 ~/.claude/skills/ppread/fetch.py --set-output "fixed:/absolute/path"
  ```
- **`papers/` under whatever directory I am in** — a separate library per
  project. Save with:
  ```bash
  python3 ~/.claude/skills/ppread/fetch.py --set-output "cwd:papers"
  ```

Then re-run Step 0. The answer lives in `~/.config/ppread/config.json` and is
never asked again. `--show-config` prints what is remembered and where it
currently resolves to; re-running `--set-output` changes it; `--out <dir>`
overrides it for one run without changing it.

**Never choose on the user's behalf.** Defaulting to `./papers` would mean
creating a directory tree inside whatever repo or home directory the session
happened to start in. That is the one mistake this gate exists to prevent.

### When two papers want one folder

The folder name comes from the title, so two papers can ask for the same one.
`fetch.py` returns `route: conflict` and writes nothing. It decides by reading the
front matter of **every** lecture already in the folder (`primer.md`, `broad.md`,
`deep.md`, their `.part.md` forms, and a legacy `lecture.md`) — the arXiv ID settles it, then
the DOI, then the title. `occupant.file` names the lecture that disagreed. A folder
holding a source file but no lecture cannot be identified at all, so that is
reported too.

A conflict with no `occupant` comes from a check that runs before any title is
compared — a second file beside a lecture's source, or a `--kind` that
contradicts the folder's lecture. `--title` cannot resolve those; follow the
result's `resolve` field. Every conflict's `resolve` says what actually works.

**Do not resolve this alone, and never work around it by renaming the folder.**
Show the user both papers — `occupant` is the resident one, `meta` the incoming
one — and ask which case it is:

- **The same paper** (a re-download, a newer version) — the user deletes or
  renames the old folder, then Step 0 runs again.
- **Genuinely different papers** — re-run with `--title "<a title that tells the
  two apart>"`. `--out <dir>` works too, but puts the paper outside the library.

### Where things go

```
<library>/
    papers.base                     # Obsidian Bases view, written once, never overwritten
    attention-is-all-you-need/      # network route: the configured library
        source.tex                  # only on the latex route
        src/                        # unpacked e-print tree — figures live here
        primer.md                   # what you write (導讀)
        broad.md                    # what you write (通讀)
        deep.md                     # what you write (精讀)
        .deep.parts/                # hidden work directory while 通讀/精讀 is in progress
~/Downloads/attention-is-all-you-need/   # local route: beside the file itself
        1706.03762.pdf              # the file, moved in
```

The folder is named by the `slug` field — ASCII, lowercase, hyphenated. Do not
rename it. On a network route with no LaTeX, `fetch.py` creates nothing — make the
folder yourself at `workdir`.

**Report the tier to the user before starting**, in one line — tier 1 means
formulas and citations are exact; tier 5–6 means they were reconstructed from a
PDF and may be wrong.

## Slides: switch to slides.md

When Step 0's `docs.kind` is `slides`, read `slides.md` (same directory) and
follow its Steps 1–4 **in place of** Steps 1–4 below. Step 5, Listing and
Discipline in this file still apply in full.

## Step 1: Survey, then say what will happen

Read the whole source first, not just the abstract. Then print a short status
block and **carry on without waiting** — it informs; it does not ask:

- The mode, and why (flag, or which table row); `resuming` if it was `partial`
- What the paper claims, in two sentences
- Its section structure, with a rough passage count per section
- Anything the fetch lost (missing figures, a garbled section); a legacy `lecture.md`, if any
- The plan for the mode, below

**Primer**:

- Which paragraphs go under〈論文全貌〉(Abstract, Introduction, Conclusion — name
  the section numbers)
- Which passage, figure and formula〈方法速覽〉builds its one worked example from
- The list for〈讀懂它需要先知道的〉, each with a one-line depth limit
- Where each of the five〈一頁看懂〉rows comes from (section, table or figure)

**Broad and deep**:

- The part split: 3–6 contiguous parts of the paper's sections, of similar
  source length, each with its section range
- The term-owner list: every background term the paper needs, each with one
  owner — the prerequisites when it is needed before or across parts, else the
  single part where it first appears. When a lower lecture owns the prerequisites,
  a term it does not cover goes to the first part where it appears; never link to
  a section that lacks it. The paper's own concepts (what it defines or proposes,
  e.g. residual learning) are not prerequisite terms: the defining part owns them
- Who owns〈讀懂它需要先知道的〉(see "Prerequisites live once" in Step 3)
- Deep: the whole paper, unless the invocation itself named certain sections

## Step 2: Gather everything from outside before writing

Every network call happens here, in this session, before any lecture text is
written: writers never touch the network, so parallel writers cannot multiply
rate-limit refusals, and a resumed run repeats no call.

**Broad and deep** keep the results in the hidden work directory:

- Create `<workdir>/.<mode>.parts/`. On `needs-html` and `needs-pdf`, where
  `fetch.py` leaves no text on disk, save the converted text there as
  `source.md` — the writers and `--limitations` read it.
- Save every raw JSON result below in `.<mode>.parts/context.json`, as one object
  keyed `graph`, `verify` (a list of results) and `limitations`. If `context.json`
  already exists (a resumed run), read it and make no call it already answers.

**Primer** has no work directory; keep the results in the conversation.

### The citation graph (broad)

```bash
python3 ~/.claude/skills/ppread/fetch.py --graph "<arXiv ID, else DOI, else English title>"
```

Pass the identifier from Step 0's `meta` (`arxiv_id`, else `doi`, else `title`),
not a file path.

- **`route: graph`** — choose「繼承的工作」from `references` (prefer
  `influential: true` or `methodology` in `intents`) and「後續發展」from `citations`.
  Note `citations_complete`, `citations_scanned` and `fetched_on` for the caveat line.
  A present `citations_error` means the citation list was cut short by a failure,
  not by the three-page cap — say so in「後續發展」rather than treating it as a
  clean stop.
- **`route: graph-unavailable`** — when `reason` names a 429 or another transient
  failure (not `not found`), wait about a minute and retry once or twice: `--graph`
  gives up on the first refusal, so a retry often succeeds. `PPREAD_S2_API_KEY`
  removes the throttling; mention it if retries keep failing. Only then fall back
  to the paper's own bibliography (on the latex route the `.bib` entries in `src/`
  are exact) and `--verify` every chosen title — `lecture-format.md`'s「後續發展」
  shows how. If `--verify` also fails, write its single "無法查證" line and list no
  outside papers at all.

### Verifying every other outside paper (all modes)

Papers from your own knowledge — rival approaches, prerequisite sources, further
reading not in the graph, a conflicting result a critique will cite — are checked
now, for the whole lecture; writers cannot check later. Send batches of about
eight titles (25 at most): results arrive only when the call finishes, so a call
cut off loses all of them.

```bash
python3 ~/.claude/skills/ppread/fetch.py --verify "<title>" "<title>" ...
```

Only `status: exact` may appear in the lecture. `mismatch` carries a `candidate`:
**do not use it**, even if it looks like the paper you meant. `not-found` and
`error` are both left out; tell the user how many titles were dropped and which
kind of failure it was.

There is no path by which a paper recalled from memory reaches the lecture without
an `exact` verification.

### The authors' own limitations (broad)

```bash
python3 ~/.claude/skills/ppread/fetch.py --limitations "<workdir>"
```

Offline. `limitations` carries `source` and `hits` (`sentence`, `section`,
`file`, `line`; from `source.tex` also `origin`, the e-print file the line came
from); a hit may begin mid-sentence, and `source: pdf` hits are lower
fidelity — say so. `limitations-unavailable` → the section says the text could
not be scanned. Never add a limitation the scan did not return.

## Step 3: Write the lecture

Read `lecture-format.md` (same directory): the「共通規則」part, plus「導讀文件」,
「通讀文件」or「精讀文件」for the mode being written. Follow it literally.

**Prerequisites live once.** The lowest finished lecture in primer → broad → deep
owns〈讀懂它需要先知道的〉; higher ones link to it with a relative link — but only
if that file actually has the section (an old-contract `broad.md` may not). With
no such lecture, the lecture writes its own.

### 導讀 — single writer

- Write to **`<workdir>/primer.part.md`**: front matter first (`mode: primer`,
  `lecture_read: false`), then **one `##` section per pass**, appending, in the
  skeleton's order. Never emit the whole lecture in one response — quality
  collapses near the end. After each section, state what was done and continue.
- Paragraph-unit 解說 point back to〈讀懂它需要先知道的〉, never re-explain it.
  Then Step 4.

### 通讀 and 精讀 — orchestrator and parallel writers

This session orchestrates. Work in progress lives in `<workdir>/.<mode>.parts/`,
hidden from `--list` and the folder checks; part numbers are two digits, 01–99.

1. **Header.** Write `00-header.md`: front matter (`mode` set, `lecture_read:
   false`), the header block, and〈讀懂它需要先知道的〉when this lecture owns it —
   else the one line linking to the lecture that does.
2. **Briefs.** For each part of the Step 1 plan write `brief-NN.tmp.md`: the section
   range; the source path (`source_path`, or `.<mode>.parts/source.md`); which
   `lecture-format.md` parts to read; the terms it owns (explain fully); the terms
   owned elsewhere, with where (link, never re-explain); its unit budget under
   `lecture-format.md`'s 通讀 caps; the verified outside papers it may cite,
   copied from `context.json` (nothing else); the figure paths for its sections;
   its output name `NN-<slug>.md`. Only when every brief is
   written, rename them all to `brief-NN.md` — that set of renames marks the plan
   complete, and `--assemble` counts only `brief-NN.md`.
3. **Writers.** Dispatch one writer per brief with the Agent tool, all in a single
   message so they run in parallel, with no model override so they run on this
   session's model. Each writer's prompt says: read this file's Discipline,
   `lecture-format.md`'s「共通規則」and the parts its brief names, its brief and its
   source range; write `NN-<slug>.tmp.md` one `##` section per pass; never touch the
   network or any web tool and never run `fetch.py`; name no
   outside paper the brief does not list; write no front matter, whole-paper
   sections or questions; when its last unit is written, rename the file to
   `NN-<slug>.md` — that rename is the part's completion signal.
4. **Checker.** When every writer has returned, dispatch one checker agent: it
   re-computes every numbered trace and checks every load-bearing number and its
   provenance against the source, may only correct arithmetic and provenance in
   place, never touches the network or runs `fetch.py`, and reports what it
   changed and any section over its unit cap — relay that in one line.
5. **Assemble.**
   ```bash
   python3 ~/.claude/skills/ppread/fetch.py --assemble "<workdir>" <mode>
   ```
   `assembled` → `<mode>.part.md` holds the header and every part in order.
   `assemble-incomplete` → re-dispatch the writers of the briefs in `missing`,
   then redo steps 4–5; a part missing a second time you write yourself (the
   fallback below). `duplicates` → keep one finished file per number and delete
   the rest; `reason` (no briefs) → redo step 2. `assemble-unavailable` → report
   `reason` and stop.
6. **Whole-paper sections.** Append to `<mode>.part.md`, one `##` per pass, the
   sections that need the whole paper, reading `context.json`: 通讀 —
   〈作者自述的限制〉,〈它在研究脈絡中的位置〉,〈延伸閱讀〉; 精讀 —〈論證鏈〉,
   〈主張與證據〉,〈設計決策〉. Then Step 4.

**Resume** (`.<mode>.parts/` exists): Steps 1–2 still run, Step 2 making only the
calls `context.json` lacks; then continue here from the first orchestration step
whose output is missing. No `00-header.md` → orchestration step 1. Any
`brief-*.tmp.md`, or no `brief-NN.md` → delete the tmp briefs and redo
orchestration step 2; otherwise the existing briefs are the plan of record. Then
delete any leftover part `.tmp.md`, re-dispatch only the briefs with no finished
part, and redo orchestration steps 4–6. Re-assembling overwrites
`<mode>.part.md`, discarding the interrupted run's whole-paper sections; step 6
rewrites them from `context.json`. No network call is repeated.

**Without the Agent tool**, write each brief's part yourself, sequentially, into
the same files, and do the checker's pass yourself; nothing else changes.

## Step 4: Questions, then finish the file

Read `questions.md` (same directory). Append the「問題」section to
`<mode>.part.md`: the five fixed questions for the mode (questions.md's 導讀 set
P1–P5, 通讀 set B1–B5, 精讀 set D1–D5), verbatim and in order, then at most three
custom questions from `Q6`, each with a folded reference answer.

When the questions are written, the lecture is complete. Finish it:

```bash
python3 ~/.claude/skills/ppread/fetch.py --finish "<workdir>" <mode>
```

`finished` → `path` is the lecture; `<mode>.part.md` was renamed to `<mode>.md`
and `.<mode>.parts/` removed. A `leftover` field means that directory could not
be removed: delete it yourself, or the lecture reads as partial. `finish-unavailable` → report `reason`. Only this
rename marks the lecture as finished — `--list` and the next run rely on it.

## Step 5: Stop

Report where the file is and how long it is, and remind the user that ticking
`lecture_read` in the file's properties marks it read.

**Do not write literature notes, permanent notes, or a summary of the user's
own takeaways.** The lecture is processed source material, not a note. In a
Zettelkasten the value comes from the user restating ideas in their own
words — generating that on their behalf destroys the only thing the method is
for.

The reference answers do not cross this line: they are comparison material, folded
so the user meets them only after answering, and marked `generated: claude` like the
rest of the file. If the user pastes their answers into the conversation, discuss
the gap — but do not turn their answers into notes or write them to any file.

## Listing

```bash
python3 ~/.claude/skills/ppread/fetch.py --list            # the configured library
python3 ~/.claude/skills/ppread/fetch.py --list <dir>      # any other directory
```

Render `papers` as a table — title, kind, year, primer, broad, deep, research —
using `✓` for `read`, `○` for `unread`, `…` for `partial`, `—` for `absent` or for
a mode the kind does not have (a paper has no research, slides have no primer), and a footnote for rows with
`legacy: true`. A slides row's `slug` is `<course>/<chapter>`. When `title` is
empty (a folder holding only a source file, no lecture yet) show the `slug`
instead, so the row is still identifiable. Filter or sort only as the user asks. Papers built beside local files live outside the
library; `--list <dir>` reaches them. A `needs-output-config` result means no
library is set: handle it as in Step 0.

The same state is visible in Obsidian through `papers.base` at the library root.

## Discipline

These are the rules that decide whether a lecture is worth reading. They bind
every agent that writes or checks any part of it. Only the orchestrator touches
the network.

**Never reconstruct a formula you cannot actually see.** On the PDF route,
extraction routinely destroys superscripts, fractions and summation limits —
`x²` arrives as `x2`, and the information is genuinely gone. The tempting failure
is to infer a plausible formula from context. That produces a lecture that reads
perfectly and is wrong. Write `⚠️ 此處公式從 PDF 抽取受損，無法確認原式` and move
on. The same applies to garbled tables and to citation numbers with no resolvable
target.

**Never name an outside paper that was not grounded.** Every paper other than the
one being read — in context sections, further reading, prerequisite sources, a
critique that cites a conflicting result, or a reference answer — comes from
`--graph` output, `--search` output (slides research) or an `exact` `--verify`.
A list recalled from memory gets an author, a year or a title wrong, or names a
paper that does not exist, and reads exactly as convincingly as a correct one; a
reader will go looking for it.

**Author comments are not the paper.** On the LaTeX route, text after an
unescaped `%` is an author comment: never quote, translate or take a number from it.

**Translate and explain as separate acts.** The translation renders what the
authors wrote, including where they were vague. The explanation is where context,
criticism and missing background belong. The translation is one paragraph under
`**中文翻譯**`; the explanation is always bold-titled bullets.

**Keep the authors' reasons apart from yours.** When a paper does not say why it
made a choice, write `論文未說明` and put any guess on its own line marked
`**推測**`, with how strong its support is. An unexplained decision is a finding;
a plausible reason supplied in its place hides it.

**Criticise at an address.** Every criticism points at a paragraph, table or
formula, with the numbers. "The sample is small" is not a criticism; "Table 2 runs
one seed per setting and the largest gap is 0.3 BLEU" is.

**Explain what the paper assumes, not what it says.** Restating a paragraph in
easier words is not explanation. Useful explanation answers: why this step and not
the obvious alternative, what breaks without it, which earlier work it is arguing
against, what the authors took for granted. Explain a mechanism from its parts and a
step-by-step trace with real values — never with an "X is a tool for Y" definition,
and never by dropping the term. `lecture-format.md` and `slides-format.md` 〈解說的具體度〉 have the full rule. Values not taken from the source are labelled as such, and a learned model is traced as data, never with invented numbers.

**Every load-bearing number carries its provenance inline.** A number that
supports an explanation, a critique or an answer is followed by where it came
from — `（§4.3）`, `（Table 2）`, `（Figure 5 目測，約）`. A critique that rests only on
a value read off a figure is marked `**推測**`.

**Trace the argument before judging its links.** In 精讀,〈論證鏈〉(question →
design → data → method → analysis → interpretation → conclusion → title, each
break located) comes before the item-by-item critique of〈主張與證據〉.

**Every technical term gets 中英並列 on first use** — `注意力機制（attention
mechanism）` — then the English alone afterwards.

**Cite by name, not number.** On the LaTeX route `\citep{vaswani2017}` tells you
exactly who is being cited — resolve it from the bibliography and name the work.

**Figures**: `fetch.py` lists `figures` and `figures_dir`. When a passage turns on
a figure, look at it — Read the file directly if it is `.png`/`.jpg`, then copy it
to `assets/<slug>/` and embed with `![[...]]`. For `.pdf`/`.eps` figures, say
plainly that the figure could not be viewed and explain from the caption and
surrounding text instead.

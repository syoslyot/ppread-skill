---
name: ppread
description: "Bilingual research-paper lectures in two modes — invoke with /ppread [--broad | --deep] <arXiv ID | DOI | URL | title | PDF path>, or /ppread --list [dir]. --broad writes broad.md: the abstract, introduction and conclusion paragraph by paragraph (English original, Traditional Chinese translation, explanation), the outside knowledge the paper assumes and how deep to go, a quick pass over the core method, and the paper's place in the literature grounded in the Semantic Scholar citation graph. --deep writes deep.md: the whole paper paragraph by paragraph with critical analysis, a claims-versus-evidence table and a design-decision breakdown. Both end with reader questions and folded reference answers. Fetches the highest-fidelity full text available (arXiv LaTeX first). --list shows every paper's lectures and whether each has been read. Stops at the lecture and never writes the user's own notes."
---

# /ppread — Paper Lectures, Broad and Deep

Turn one paper into a lecture the user can read straight through. There are two
kinds, written to two files, for two different jobs:

- **broad** (`broad.md`) — place the paper: what it answers, what it assumes, what
  its core idea is, where it sits among other work, what to read next.
- **deep** (`deep.md`) — judge the paper: does the argument hold, why was each
  design decision made, does the evidence carry the claims.

Fetching and every other step with a right answer lives in `fetch.py`; reading,
translating, explaining and questioning are judgment and live here.

## Invocation

| Command | Does |
|---|---|
| `/ppread <source>` | Picks the mode from what already exists (table in Step 0) |
| `/ppread --broad <source>` | Broad lecture |
| `/ppread --deep <source>` | Deep lecture |
| `/ppread --list [dir]` | Lists papers and lecture state — see "Listing" |

`<source>` may be an arXiv ID or URL, a DOI, a publisher URL, a paper title, or a
local PDF path. The mode is a flag, never a bare word: a title such as
`deep residual learning for image recognition` would otherwise lose its first word
to the mode and resolve to the wrong paper. Strip `--broad`/`--deep` before passing
the source to `fetch.py`; `fetch.py` does not accept them.

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
| `needs-pdf` | Only a PDF exists | Convert to text — see "The PDF route" below. |
| `unresolved` | Nothing identified the reference | Stop. Tell the user what was tried and ask for an arXiv ID, a DOI, or a direct URL. Do not guess at which paper was meant. |
| `needs-output-config` | No output location has ever been chosen | Ask (see below), save the answer, re-run Step 0. |
| `conflict` | The folder this paper wants already holds a lecture for another paper | Stop and ask the user — see "When two papers want one folder". Nothing was downloaded or moved. |
| `needs-title` | Local file: its metadata has no title, or a title with no ASCII in it. Network: metadata lookup returned no title, or the title it returned has no ASCII in it | **Local**: read its first page (`pdftotext -f 1 -l 1 <file> -`), take the **English** title — a paper written in another language usually prints one on page 1; translate it if it does not — and re-run with `--title "<title>"`. The file was **not** moved. **Network**: check `reason` — a metadata lookup failure is often transient (the same call can succeed a minute later), so **retry the fetch once, unchanged, before asking the user for a title**; only if it still comes back `needs-title` should you ask the user for the paper's English title and re-run with `--title "<title>"`. Nothing was downloaded or created. |
| `local` | A local non-PDF source (e.g. `.tex`) already in place | Read `source_path` directly. |

### Choosing the mode

Every non-conflict route that has a `workdir` also carries `docs`:

```json
"docs": {"broad": "read", "deep": "absent", "legacy": false}
```

`broad`/`deep` are each `absent`, `partial` (being written, or interrupted),
`unread` or `read`. A mode is **finished** when its state is `unread` or `read`;
`absent` and `partial` are not finished. The table below is illustrative only —
it does not cover every reachable combination (in particular it has no row for
`partial`). The rule that actually decides, and that covers all sixteen
combinations, is:

1. **No flag**: the mode to act on is the first of broad, then deep, that is not
   finished. If both are finished, stop and report both paths.
2. **`--broad` or `--deep`**: the named mode is the mode to act on.
3. Whatever mode was selected by 1 or 2: `absent` → write it; `partial` → ask
   the user whether to resume or restart (see the bullet below); finished →
   report the file's path and stop.

| `docs` | no flag | `--broad` | `--deep` |
|---|---|---|---|
| both `absent` | write broad | write broad | write deep |
| broad exists, deep `absent` | write deep | exists — stop | write deep |
| deep exists, broad `absent` | write broad | write broad | exists — stop |
| both exist | stop | stop | stop |

- **exists — stop**: report the file's path. Regenerate only when the user
  explicitly asks: delete the old file, write afresh, and say that `lecture_read`
  was reset to `false`.
- **`partial`**: `<mode>.part.md` is there. Ask whether to **resume** or **restart**.
  Resume: delete everything from the file's last `##` heading onward and rewrite that
  section, then continue — sections are written one per pass, so only the last can be
  incomplete. Restart: delete the `.part.md` and begin at Step 1.
- **`legacy: true`**: a `lecture.md` from ppread 0.1 is in the folder. It does not
  block anything; mention it once in the Step 1 survey.

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
front matter of **every** lecture already in the folder (`broad.md`, `deep.md`,
their `.part.md` forms, and a legacy `lecture.md`) — the arXiv ID settles it, then
the DOI, then the title. `occupant.file` names the lecture that disagreed. A folder
holding a source file but no lecture cannot be identified at all, so that is
reported too.

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
        broad.md                    # what you write (broad)
        deep.md                     # what you write (deep)
~/Downloads/attention-is-all-you-need/   # local route: beside the file itself
        1706.03762.pdf              # the file, moved in
```

The folder is named by the `slug` field — ASCII, lowercase, hyphenated. Do not
rename it. On a network route with no LaTeX, `fetch.py` creates nothing — make the
folder yourself at `workdir`.

**Report the tier to the user before starting**, in one line — tier 1 means
formulas and citations are exact; tier 5–6 means they were reconstructed from a
PDF and may be wrong.

## Step 1: Survey before writing

Read the whole source first. Do not start writing after skimming the abstract.

Then tell the user, in a short block:

- The mode that will be written, and why (flag given, or which row of the table)
- What the paper claims, in two sentences
- Its section structure, with a rough passage count per section
- Anything the fetch lost (missing figures, a garbled section); a legacy `lecture.md`, if any

**Broad** — add the plan:

- Which paragraphs go under「論文全貌」(Abstract, Introduction, Conclusion — name
  the section numbers)
- Which paragraphs, figure and formula go under「核心方法速覽」, and why these are
  the ones the abstract's claim depends on
- The draft list for「讀懂它需要先知道的」, each with a one-line depth limit

**Deep** — confirm:

- Whether `broad.md` exists (if not, say the deep lecture will explain background
  only where a passage cannot be read without it, and that `--broad` can be run
  separately)
- Whole paper, or only certain sections

Wait for the user to confirm or adjust before Step 2.

## Step 2: Ground the literature (broad only)

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
- **Papers from your own knowledge** — rival approaches, prerequisite sources,
  further reading not in the graph — must be checked, up to 25 titles per call,
  but send them in small batches of about eight titles rather than one 25-title
  call: results only arrive once the whole call finishes, so a long call that
  gets cut off loses every result in it, not just the last one.
  ```bash
  python3 ~/.claude/skills/ppread/fetch.py --verify "<title>" "<title>" ...
  ```
  Only `status: exact` may appear in the lecture. `mismatch` carries a `candidate`:
  **do not use it**, even if it looks like the paper you meant. `not-found` and
  `error` are both left out; tell the user how many titles were dropped and which
  kind of failure it was.
- **`route: graph-unavailable`** — check `reason` first. When it names a 429 or
  another transient network failure (as opposed to `not found`), wait roughly a
  minute and retry the same `--graph` call once or twice before accepting the
  fallback: `--graph` is one call chain that gives up on the first refusal, while
  `--verify` succeeds against the same throttled pool because it retries per
  title — a retry here often succeeds too. Setting `PPREAD_S2_API_KEY` is what
  actually removes the throttling; mention it to the user if retries keep failing.
  Only once retries are exhausted (or `reason` is `not found`), fall back to the
  paper's own bibliography (on the latex route the `.bib` entries in `src/` are
  exact) and run every chosen title through `--verify` — see `lecture-format.md`'s
  「後續發展」 for how this fallback plays out when `--verify` still works. If
  `--verify` also fails, write the single "無法查證" line that `lecture-format.md`
  specifies and list no outside papers at all.

There is no path by which a paper recalled from memory reaches the lecture without
an `exact` verification.

## Step 3: Write the lecture, section by section

Read `lecture-format.md` (same directory): the「共通規則」part, plus「廣讀文件」或
「精讀文件」for the mode being written. Follow it literally.

- Write to **`<workdir>/<mode>.part.md`** — `broad.part.md` or `deep.part.md`.
- Front matter first, with `mode` set and `lecture_read: false`.
- **One `##` section per pass**, appending to the file. Never emit the whole lecture
  in a single response — long papers overflow and quality collapses near the end.
  After each section, state what was completed and continue.
- For deep: write the paper's own sections, then「主張與證據」, then「設計決策」.

## Step 4: Questions, then finish the file

Read `questions.md` (same directory). Append the「問題」section: the five fixed
questions for the mode, verbatim and in order, then at most three custom questions
from `Q6`, each with a folded reference answer.

When the questions are written, the lecture is complete. Rename it:

```bash
mv "<workdir>/<mode>.part.md" "<workdir>/<mode>.md"
```

Only this rename marks the lecture as finished — `--list` and the next run rely on it.

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

Render `papers` as a table — title, year, broad, deep — using `✓` for `read`, `○`
for `unread`, `…` for `partial`, `—` for `absent`, and a footnote for rows with
`legacy: true`. When `title` is empty (a folder holding only a source file, no
lecture yet) show the `slug` instead, so the row is still identifiable. Filter or
sort only as the user asks. Papers built beside local files live outside the
library; `--list <dir>` reaches them. A `needs-output-config` result means no
library is set: handle it as in Step 0.

The same state is visible in Obsidian through `papers.base` at the library root.

## Discipline

These are the rules that decide whether a lecture is worth reading.

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
`--graph` output or an `exact` `--verify`. A list recalled from memory gets an
author, a year or a title wrong, or names a paper that does not exist, and reads
exactly as convincingly as a correct one; a reader will go looking for it.

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
against, what the authors took for granted.

**Every technical term gets 中英並列 on first use** — `注意力機制（attention
mechanism）` — then the English alone afterwards.

**Cite by name, not number.** On the LaTeX route `\citep{vaswani2017}` tells you
exactly who is being cited — resolve it from the bibliography and name the work.

**Figures**: `fetch.py` lists `figures` and `figures_dir`. When a passage turns on
a figure, look at it — Read the file directly if it is `.png`/`.jpg`, then copy it
to `assets/<slug>/` and embed with `![[...]]`. For `.pdf`/`.eps` figures, say
plainly that the figure could not be viewed and explain from the caption and
surrounding text instead.

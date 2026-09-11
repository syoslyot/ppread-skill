---
name: ppread
description: "Paragraph-by-paragraph bilingual close reading of a research paper — invoke with /ppread <arXiv ID | DOI | URL | PDF path>. Fetches the highest-fidelity full text available (arXiv LaTeX source first, falling back through HTML to PDF), then writes a Traditional Chinese lecture to reading/<title>.md: for each passage, the English original, a translation, and an explanation covering background, prior work, experimental rationale and formula breakdown. Stops at the lecture and never writes the user's own notes."
---

# /ppread — Paper Close Reading

Turn one paper into a paragraph-level bilingual lecture the user can read
straight through. Fetching is mechanical and lives in `fetch.py`; reading,
translating and explaining are judgment and live here.

**Runs when the user types `/ppread <source>`.** `<source>` may be an arXiv ID
or URL, a DOI, a publisher URL, a paper title, or a local PDF path.

## Step 0: Fetch

```bash
python3 ~/.claude/skills/ppread/fetch.py "<source>" --out .ppread
```

For a local PDF path, skip the script entirely and go straight to the PDF route
in Step 1.

The script prints one JSON object. Read `route` and act:

| `route` | What happened | What to do |
|---|---|---|
| `latex` | arXiv source obtained (tier 1) | Read `source_path`. This is the good case. |
| `needs-html` | No LaTeX; an HTML full text may exist | Fetch `html_url` (or `page_url`) with Firecrawl `firecrawl_scrape`. |
| `needs-pdf` | Only a PDF exists | Convert with MarkItDown MCP `convert_to_markdown`. |
| `unresolved` | Nothing identified the reference | Stop. Tell the user what was tried and ask for an arXiv ID, a DOI, or a direct URL. Do not guess at which paper was meant. |

`meta.json` in the workdir holds title, authors, year, DOI, arXiv ID and abstract.

**Report the tier to the user before starting**, in one line — tier 1 means
formulas and citations are exact; tier 5–6 means they were reconstructed from a
PDF and may be wrong. The user deserves to know which they are reading.

## Step 1: Survey before writing

Read the whole source first. Do not start writing after skimming the abstract.

Then tell the user, in a short block:

- What the paper claims, in two sentences
- Its section structure, with a rough passage count per section
- Which background knowledge the paper assumes but never states — this is
  usually the real reason a paper feels unreadable, and naming it up front
  changes how the rest lands
- Anything the fetch lost (missing figures, a garbled section)

Then ask whether to cover the whole paper or only certain sections. A full
lecture on a 10-page paper is long; the user may only want the method.

## Step 2: Write the lecture, section by section

Read `lecture-format.md` (same directory) for the exact output format. Follow
it literally.

Write **one section per pass**, appending to the file. Never try to emit the
whole paper in a single response — long papers overflow and quality collapses
near the end. After each section, state what was completed and continue.

Output path: `reading/<paper title>.md`, relative to the current directory.
Create `reading/` if absent. Use the paper's real title as the filename so
Obsidian `[[wikilinks]]` resolve naturally; strip characters illegal in
filenames (`/ \ : * ? " < > |`).

## Step 3: Stop

When the lecture is done, stop. Report where the file is and how long it is.

**Do not write literature notes, permanent notes, or a summary of the user's
own takeaways.** The lecture is processed source material, not a note. In a
Zettelkasten the value comes from the user restating ideas in their own
words — generating that on their behalf destroys the only thing the method is
for. Say the lecture is ready and leave the notes to them.

## Discipline

These are the rules that decide whether the lecture is worth reading.

**Never reconstruct a formula you cannot actually see.** On the PDF route,
extraction routinely destroys superscripts, fractions and summation limits —
`x²` arrives as `x2`, and the information is genuinely gone, not merely
obscured. The tempting failure is to infer a plausible formula from context.
That produces a lecture that reads perfectly and is wrong, which is worse than
one that admits a gap. Write `⚠️ 此處公式從 PDF 抽取受損，無法確認原式` and move on.
The same applies to garbled tables and to citation numbers with no resolvable
target.

**Translate and explain as separate acts.** The translation renders what the
authors wrote, including where they were vague. The explanation is where
context, criticism and missing background belong. Smuggling explanation into
the translation makes it impossible to tell author from commentator.

**Explain what the paper assumes, not what it says.** Restating a paragraph in
easier words is not explanation. Useful explanation answers: why this step and
not the obvious alternative, what breaks without it, which earlier work it is
arguing against, what the authors took for granted.

**Every technical term gets 中英並列 on first use** — `注意力機制（attention
mechanism）` — then the English alone afterwards. The user will meet these terms
in English for the rest of their career; a Chinese-only rendering is a
disservice.

**Cite by name, not number.** On the LaTeX route `\citep{vaswani2017}` tells you
exactly who is being cited — resolve it from the bibliography and name the work.
`[12]` is useless to a reader who does not have the reference list open.

**Figures**: `fetch.py` lists `figures` and `figures_dir`. When a passage turns
on a figure, look at it — Read the file directly if it is `.png`/`.jpg`, then
copy it to `assets/<slug>/` and embed with `![[...]]`. For `.pdf`/`.eps`
figures, say plainly that the figure could not be viewed and explain from the
caption and surrounding text instead.

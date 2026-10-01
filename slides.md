# Slides — workflow for course slide decks

Read this when Step 0 returned `docs.kind: slides`. It replaces SKILL.md's
Steps 1–4; SKILL.md's Step 5, Listing and Discipline still apply in full.

A slide deck is not a paper. It makes no claims to judge — the reader wants to
learn it — and its hardest obstacle is vocabulary: a survey slide names ten
techniques and explains none. It is also an incomplete record of a talk, and the
PDF often carries the student's own annotations on top. Three lectures follow:

- **broad** (`broad.md`) — map the chapter and explain every term on it.
- **deep** (`deep.md`) — work through each technical unit until the reader can do it.
- **research** (`research.md`) — link the chapter's topics to foundational and
  recent papers.

## Naming: course and chapter

`needs-title` for slides means `--course` or `--title` is missing — a deck's own
title metadata is never used. Read the cover and the running headers and footers
(pages 1–3 are usually enough) and re-run:

```bash
python3 ~/.claude/skills/ppread/fetch.py "<pdf>" --kind slides --course "<course>" --title "Ch<NN> <chapter title>"
```

- `--course`: the course's English name as the deck shows it (`VLSI DSP`) — not
  the institution, not the lecturer. A deck that shows only a course code uses the
  code. A running-header label is often a template carried over from another
  course; when it disagrees with the name the slides themselves use, take the
  slides' name and say so in the Step 1 survey.
- `--title`: `Ch`, the two-digit chapter number, then the chapter's English title
  — `Ch01 Introduction`. Zero-padding keeps chapters in order in a listing. A deck
  with no chapter number uses its English title alone.
- Keep `--kind slides` on every re-run if Step 0 needed it once.
- The folder becomes `<course-slug>/<title-slug>/` beside the PDF; re-running on
  the moved file reuses it.

Fill the front matter's `authors` (the lecturer) and `institution` from the same
pages; `pages` and `year` come from Step 0's `meta`.

## Reading the deck

**Look at every page.** Read the PDF with the Read tool's `pages` parameter, at
most 20 pages per call, until the whole deck has been seen. Slides carry their
meaning in diagrams, layout and arrows that text extraction flattens. Use
`pdftotext -layout -f <N> -l <N> "<pdf>" -` only to copy exact strings — a
term's spelling, a long formula's symbols — never as the primary reading.

**Separate four layers.**

| Layer | How to tell |
|---|---|
| Slide original | inside the template frame, in the deck's fonts and colours, usually English |
| Typed note | outside or overlapping the frame, a different font or size, often Chinese |
| Handwriting | pen strokes; whole handwritten pages inserted between slides |
| Highlight | marker strokes over slide text |

Typed notes and handwriting are the student's; a highlight marks what the
lecturer stressed. When a mark's layer cannot be decided, say so in the lecture
instead of picking one.

**Page numbers.** The printed slide number and the PDF page drift apart as soon
as one handwritten page is inserted. Cite both: `投影片 9（PDF p.10）`. A page with
no printed number: `PDF p.9（手寫插頁）`.

**Formulas.** A rendered formula on a slide can be seen, so transcribe it into
LaTeX and mark it `（自投影片圖像轉寫）`. One that cannot be read with confidence —
low resolution, overlapped by a note, ambiguous handwriting — gets
`⚠️ 此處公式無法從投影片圖像確認` and is not reconstructed from context.

**Units.** The unit of explanation is a run of slides on one subject, not a page:
`DSP Algorithm 2: DCT (1)–(3)` is one unit. Classify each:

- **term list** — names techniques without explaining them (a survey slide)
- **technical** — a derivation, an algorithm, a method, a worked example, or a
  handwritten derivation the student added

## Step 1: Survey before writing

Read the whole deck first. Then tell the user, in a short block:

- The mode that will be written, and why (flag given, or first unfinished in the sequence)
- The question the chapter answers, in one or two sentences
- Its structure as page ranges
- How many units are term lists and how many technical
- The note layer: how dense it is, where the inserted pages are
- That this is tier 6 and formulas are transcribed from page images

Add the plan for the mode:

- **broad** — the draft term list in two tiers (core / mentioned) with counts;
  the prerequisites, each with a one-line depth limit; the notes to be quoted and checked
- **deep** — the technical units, the worked example planned for each, the notes to check
- **research** — 4–6 topics, each with its source slides and the queries
  planned; the estimated number of Semantic Scholar requests and time (keyless:
  about 25 requests and several minutes of backoff — mention that
  `PPREAD_S2_API_KEY` removes it)

Wait for the user to confirm or adjust.

## Step 2: Research queries (research only)

For each topic, in order, one request at a time:

```bash
python3 ~/.claude/skills/ppread/fetch.py --search '"<topic phrase>"'
python3 ~/.claude/skills/ppread/fetch.py --search '"<topic phrase>"' --since <this year minus 3>
python3 ~/.claude/skills/ppread/fetch.py --graph "<arXiv ID, else DOI, else title of the anchor>"
```

- Quote multi-word phrases inside the query: bulk search matches keywords, and an
  unquoted `systolic array` matches either word.
- **Filter every result list.** Sorting by citations surfaces papers that merely
  mention the phrase, and keyword search collects namesakes from other fields
  ("systolic" is also a cardiology term). Judge from `title`, `fields` and
  `abstract` (often empty). Drop what does not fit, and tell the user how many
  were dropped per topic.
- The `--graph` anchor is the most foundational relevant paper from the first
  search. Handle `graph-unavailable` as SKILL.md Step 2 does.
- `search-unavailable` with a 429 or a network reason: wait about a minute and
  retry once or twice. If it still fails, that layer of that topic is written as
  unavailable (see `slides-format.md`), never filled from memory.
- `--verify` remains open for a paper you specifically know belongs; only
  `status: exact` may appear.

## Step 3: Write the lecture, section by section

Read `slides-format.md` (same directory): its「共通規則」plus the part for the
mode. Follow it literally.

- Write to `<workdir>/<mode>.part.md`, front matter first, `lecture_read: false`.
- One `##` section per pass, appended. Never the whole lecture in one response.
- deep: when a unit turns on a diagram and `pdftoppm` exists, render that page
  and embed it as `slides-format.md` shows:
  ```bash
  mkdir -p "<workdir>/assets"
  pdftoppm -png -r 110 -f <N> -l <N> -singlefile "<pdf>" "<workdir>/assets/pdf-p<NNN>"
  ```
  `<N>` is the PDF page, `<NNN>` the same number zero-padded to three digits.
  Without `pdftoppm`, cite the page only.

## Step 4: Questions, then finish the file

Read `questions.md`, part「簡報」. Append the「問題」section: the fixed questions
for the mode, verbatim and in order, then the custom questions it allows. Then:

```bash
mv "<workdir>/<mode>.part.md" "<workdir>/<mode>.md"
```

Only this rename marks the lecture as finished.

## Discipline for slides

SKILL.md's Discipline applies in full — above all, no outside paper that did not
come from `--search`, `--graph` or an `exact` `--verify`. Three more:

**Never blur the student's notes into the slides, or the slides into the notes.**
Presenting a note as slide text puts words in the lecturer's mouth; presenting
slide text as a note erases the student's own trace. Every quoted note carries its
layer and page.

**"The slides do not say" is not "the lecturer did not do".** A deck is a lossy
record of a talk. What you add goes under「補完」as your explanation, never as
what the lecturer meant.

**Do not translate bullets one by one.** Slide bullets are fragments; translating
them line by line adds nothing. Bilingual treatment belongs to the term section of
`broad.md`; elsewhere a term's first use is still `中文（English）`.

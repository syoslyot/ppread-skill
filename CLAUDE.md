# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Source-of-truth repo for the **`/ppread`** Claude Code skill (a personal global skill, like `gitf` and `p2issue`). The directory is named `ppread-skill`; the deployed skill name and its invocation are both `ppread`. The skill turns one research paper into bilingual lectures in two modes: `broad.md` places the paper (abstract/introduction/conclusion paragraph by paragraph, assumed outside knowledge, core idea, literature context grounded in the citation graph) and `deep.md` judges it (every paragraph with critical analysis, claims versus evidence, design decisions). Both end with reader questions and folded reference answers.

## Deploy model (source vs. deployment target)

This repo is the **source of truth**. The live skill lives at `~/.claude/skills/ppread/`. Editing files here does nothing until deployed.

```bash
./deploy.sh   # copies SKILL.md + lecture-format.md + questions.md + fetch.py -> ~/.claude/skills/ppread/
```

Only those four files are deployable. `deploy.sh`, `VERSION`, `tests/`, `docs/` and this file are development-only and must never be copied to the skill dir.

## Architecture: two layers, split by determinism

- **`fetch.py`** — pure mechanics. Source identification, arXiv twin lookup, e-print download, tar extraction, `\input` expansion, lecture state (`docs`), citation graph (`--graph`), title verification (`--verify`), library listing (`--list`), the `papers.base` file. Every step is deterministic and must stay testable from the shell. No judgment, no LLM assumptions. Standard library only — no third-party dependencies, so it runs anywhere `python3` exists.
- **`SKILL.md`** — orchestration and judgment, executed by the agent. Chooses the mode, plans coverage, splits passages, translates, explains, writes questions, enforces the honesty rules.
- **`lecture-format.md`** — the output contract for `broad.md` and `deep.md`, loaded in Step 3. Written in Chinese because it governs Chinese output and its worked examples must be in the target language.
- **`questions.md`** — what to ask and how to answer, loaded in Step 4. Kept apart from `lecture-format.md` because what to ask is a different concern from how the page looks.

Rule of thumb: anything with a right answer belongs in `fetch.py`; anything requiring judgment belongs in `SKILL.md`.

## The fidelity ladder

`fetch.py` returns a `tier` and a `route`. The whole design exists to climb as high as possible:

| tier | route | source |
|---|---|---|
| 1 | `latex` | arXiv e-print LaTeX — formulas and `\cite` keys exact |
| 4 | `needs-html` | arXiv LaTeXML HTML — MathML formulas |
| 5 | `needs-html` / `needs-pdf` | publisher HTML or OA PDF |
| 6 | `needs-pdf` | PDF only — formulas unreliable |

**Tier 2 is the highest-value step and must not be removed**: given a DOI or publisher URL, Semantic Scholar's `externalIds` is queried for an `ArXiv` id. A large share of paywalled CS papers have an arXiv preprint of the same work, which promotes the whole run back to tier 1. Verified working against `10.1109/CVPR.2016.90` → `1512.03385` and `10.1145/3292500.3330701` → `1907.10902`.

## Non-obvious decisions

- **No pandoc, no Markdown conversion.** LaTeX is handed to the agent as-is. Conversion loses `\label`/`\ref`/`\cite` structure, breaks on the custom `\newcommand` macros nearly every arXiv paper defines, and buys nothing — the agent reads LaTeX at least as well as Markdown. This also keeps the dependency set empty.
- **Whole-line `%` comments are stripped by default** because authors leave large commented-out passages that the agent would otherwise read as body text. Inline `%` is left alone (it may be an escaped `\%` or part of a URL). `fetch.py`'s own `% [ppread] >>>` provenance markers are explicitly exempted from stripping via negative lookahead — without that exemption the agent cannot tell which source file a passage came from.
- **Figures are not converted.** `.png`/`.jpg` can be read directly by the agent; `.pdf`/`.eps` cannot, and SKILL.md requires saying so rather than inventing a description.
- **The skill stops at the lecture.** It must never generate literature or permanent notes. The user's Zettelkasten at `~/computer-science/research/research-notes/` derives its value from the user restating ideas in their own words; auto-generating notes would hollow it out. This is a deliberate product boundary, not an unimplemented feature.
- **The contact email is not hardcoded.** `PPREAD_CONTACT`, when set, is appended to the User-Agent as `mailto:`, which admits requests to Crossref's polite pool — a separate, faster resource pool granted to contactable clients. The address is never verified; it exists so Crossref can reach whoever is responsible for runaway traffic instead of banning an IP range. Everything works without it. Do not reintroduce a literal address: this repo is public.
- **One folder per paper, named by an ASCII slug**, holding the source and its lectures together. `slugify` deliberately drops everything with no ASCII form rather than keeping CJK or Cyrillic: the path is pasted into shell commands and Markdown links, where spaces and non-ASCII both need escaping, and a title that yields an empty slug returns `needs-title` so the agent supplies the English one instead of the code inventing a name.
- **A folder belongs to one paper, and `fetch.py` proves it before writing.** Each lecture's front matter is the only on-disk record of which paper a folder holds — there is deliberately no `meta.json` — so `front_matter()` scans every file in `DOC_FILES` as plain `key: value` lines (its keys are fixed by `lecture-format.md`, which is why no YAML parser is needed) and `same_paper()` compares arXiv ID, then DOI, then a normalised title. A mismatch returns `route: conflict` before any download or `mkdir`. Deliberately **not** auto-suffixed to `<slug>-2`: a silent suffix turns a case that needs a human decision into a second folder nobody knows the meaning of. The escape hatches are `--title` (both routes now) and `--out`.
- **A local file's folder is created beside the file, not in the configured library.** The file already sits where the user put it; relocating it across the filesystem is an action nobody requested. Consequently the `needs-output-config` gate applies to network routes only — `identify()` runs before it, and the `file` branch returns without ever calling `resolve_out`. Re-running on an already-adopted file detects `src.parent.name == slug` and reuses that folder rather than nesting a second one.
- **Two lectures, not one layered file.** Broad is mostly about the paper's surroundings — prerequisites, rival approaches, what came after — while deep is only about the paper itself. They are different documents, not a shallow and a deep half of one, so they live in `broad.md` and `deep.md`, each with full front matter. Both are regenerable machine output, which is why duplicating the metadata does not reopen the `meta.json` objection (that one was about a generated file drifting from a hand-edited one).
- **No outside paper reaches a lecture from memory.** A remembered reading list reads as convincingly as a correct one while getting authors, years or titles wrong — the same failure as inferring a PDF-damaged formula, and worse in a further-reading table the user will act on. Outside papers come from `--graph` or an exact `--verify`. `search/match` always returns its best candidate however poor, so a score proves nothing; only an exact normalised title counts, and the resulting false negatives are accepted.
- **Citations: three pages, newest first.** The citations endpoint cannot sort by impact and caps `offset+limit` below 10000. Keyless requests hit 429 by the third quick call in testing, so scanning further costs minutes of backoff for more recent, rarely-cited papers. `citations_complete` tells the agent when the list is a sample, and the lecture says so with the fetch date.
- **Read state lives in front matter, not in folder names.** `lecture_read` is a checkbox property per lecture. Encoding state as a folder prefix was rejected: every state change would rename the folder and break image embeds and the user's own links (Obsidian only rewrites links for renames it performs); `[` `]` are glob syntax in the shell and reserved link characters in Obsidian; and the state would exist twice. The key is snake_case because Bases formulas cannot read hyphenated property keys.
- **`<mode>.part.md` until the last section is written.** "The lecture exists" must mean "the lecture is finished", or an interrupted run looks complete to `--list` and to the next run. The rename is the single completion signal, and `fetch.py` reads it from the filename rather than parsing content.
- **`papers.base` is written once and never overwritten.** The reader may customise the view. It filters on `type` and `generated` rather than on a folder, so lectures built beside local files elsewhere in the vault appear too.

## Testing

No test framework. Two layers:

- `python3 tests/offline_checks.py` — network-free assertions on `fetch.py` functions (lecture state, conflicts, verify matching, graph ranking and paging with a stubbed `s2_get`, listing, `papers.base`). Standard library only; run it after every change to `fetch.py`.
- Live runs against real sources from the shell. Verified cases: an arXiv ID (`1706.03762`, multi-file `\input` structure), an IEEE DOI (`10.1109/CVPR.2016.90` → `1512.03385`), an ACM URL; `--graph 1706.03762` (incomplete citations), `--graph 1905.02175` (complete in three pages); `--verify` on a real, a fabricated and a re-cased title. Semantic Scholar rate-limits keyless clients hard — space live runs out, or set `PPREAD_S2_API_KEY`.

Use `--out` to write somewhere disposable when testing; for local-file cases point at a throwaway copy instead, since the file is moved in place. `CLAUDE_SKILLS_DIR=<tmp> ./deploy.sh` deploys somewhere other than the live skill.

## Git

Git Flow, two trunks. `main` is the release line; `develop` is the integration branch and the base for all topic work. Branch `feature/*` or `fix/*` off `develop`, never off `main`, and never commit directly to either trunk. A release goes `develop` → `release/*` → `main`, is tagged there, then back-merges to `develop`; `/gitf` drives the whole cycle.

Everything up to `v0.1.0` landed on `main` directly — `develop` did not exist yet. That is history, not precedent.

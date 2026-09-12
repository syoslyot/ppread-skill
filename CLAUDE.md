# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Source-of-truth repo for the **`/ppread`** Claude Code skill (a personal global skill, like `gitf` and `p2issue`). The directory is named `ppread-skill`; the deployed skill name and its invocation are both `ppread`. The skill turns one research paper into a paragraph-level bilingual lecture: English original, Traditional Chinese translation, and an explanation covering background, prior work, experimental rationale and formula breakdown.

## Deploy model (source vs. deployment target)

This repo is the **source of truth**. The live skill lives at `~/.claude/skills/ppread/`. Editing files here does nothing until deployed.

```bash
./deploy.sh   # copies SKILL.md + lecture-format.md + fetch.py -> ~/.claude/skills/ppread/
```

Only those three files are deployable. `deploy.sh`, `VERSION` and this file are development-only and must never be copied to the skill dir.

## Architecture: two layers, split by determinism

- **`fetch.py`** — pure mechanics. Source identification, arXiv twin lookup, e-print download, tar extraction, `\input` expansion. Every step is deterministic and must stay testable from the shell. No judgment, no LLM assumptions. Standard library only — no third-party dependencies, so it runs anywhere `python3` exists.
- **`SKILL.md`** — orchestration and judgment, executed by the agent. Decides coverage, splits passages, translates, explains, enforces the honesty rules.
- **`lecture-format.md`** — the output contract, loaded by the agent in Step 2. Written in Chinese because it governs Chinese output and its worked examples must be in the target language.

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
- **One folder per paper, named by an ASCII slug**, holding the source and `lecture.md` together. `slugify` deliberately drops everything with no ASCII form rather than keeping CJK or Cyrillic: the path is pasted into shell commands and Markdown links, where spaces and non-ASCII both need escaping, and a title that yields an empty slug returns `needs-title` so the agent supplies the English one instead of the code inventing a name.
- **A folder belongs to one paper, and `fetch.py` proves it before writing.** `lecture.md`'s front matter is the only on-disk record of which paper a folder holds — there is deliberately no `meta.json` — so `lecture_identity()` scans it as plain `key: value` lines (its keys are fixed by `lecture-format.md`, which is why no YAML parser is needed) and `same_paper()` compares arXiv ID, then DOI, then a normalised title. A mismatch returns `route: conflict` before any download or `mkdir`. Deliberately **not** auto-suffixed to `<slug>-2`: a silent suffix turns a case that needs a human decision into a second folder nobody knows the meaning of. The escape hatches are `--title` (both routes now) and `--out`.
- **A local file's folder is created beside the file, not in the configured library.** The file already sits where the user put it; relocating it across the filesystem is an action nobody requested. Consequently the `needs-output-config` gate applies to network routes only — `identify()` runs before it, and the `file` branch returns without ever calling `resolve_out`. Re-running on an already-adopted file detects `src.parent.name == slug` and reuses that folder rather than nesting a second one.

## Testing

No test framework. `fetch.py` is exercised from the shell against real sources; the three verified cases are an arXiv ID (`1706.03762`, multi-file `\input` structure), an IEEE DOI, and an ACM URL. Use `--out` to write somewhere disposable when testing; for local-file cases point at a throwaway copy instead, since the file is moved in place.

## Git

Default branch is `main`. Develop on `feature/*` or `fix/*` branches; do not commit directly to `main`.

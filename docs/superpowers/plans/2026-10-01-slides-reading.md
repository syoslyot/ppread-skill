# Course-Slides Reading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `/ppread` read a local course slide deck (landscape PDF) into three lectures — `broad.md`, `deep.md`, `research.md` — alongside the existing paper lectures.

**Architecture:** `fetch.py` classifies a local PDF as `paper` or `slides` by page orientation, files slides under `<course-slug>/<title-slug>/`, reports a per-kind lecture state, and gains `--search` (Semantic Scholar bulk search) as research mode's source. `SKILL.md` keeps the shared parts and hands slides to a new `slides.md` workflow; the output contract lives in a new `slides-format.md`; `questions.md` gains a slides part.

**Tech Stack:** Python 3 standard library only; `pdfinfo` / `pdftoppm` (Poppler) when present; Semantic Scholar Graph API.

**Spec:** `docs/superpowers/specs/2026-10-01-slides-reading-design.md`

## Global Constraints

- `fetch.py` stays standard-library only. `pdfinfo` and `pdftoppm` are optional: every code path must work without them.
- Network routes (arXiv ID, DOI, URL, title) are always `paper`. `--kind` and `--course` are rejected with exit code 2 on a network source.
- Slides never trust PDF `/Title` metadata; only `--title` names a slides folder.
- No outside paper reaches any lecture except from `--search`, `--graph`, or an `exact` `--verify`.
- Deployable files are exactly: `SKILL.md`, `lecture-format.md`, `questions.md`, `fetch.py`, `slides.md`, `slides-format.md`.
- Commits: Conventional Commits subject; body = technical bullets, a blank line, then `問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展`; then the `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` line.
- Work happens on `feature/slides-reading`. Never commit `VLSI_Design_1_Introduction.pdf` (course material with the user's notes; the repo is public).
- Run `python3 tests/offline_checks.py` after every change to `fetch.py`; all checks must print `ok`.

## Review Focus

1. **Re-running on an adopted portrait deck without `--kind`** — once a lecture records `kind: slides`, the run must stay `slides` and leave the file where it is, not reclassify it as a paper and move it into a new nested folder. Pinned in Task 3 (`check_adopt_kind`).
2. **Rotated pages** — a portrait page with `Page rot: 90` displays landscape and must classify as `slides`. Pinned in Task 1 (`check_pdf_kind`).
3. **The same course spelled two ways across runs** (`VLSI DSP` vs `vlsi-dsp`) — must be the same folder and must not raise a conflict. Pinned in Task 2 (`check_same_paper_course`).
4. **Zero search results vs. a failed search** — `papers: []` under `route: search` must stay distinguishable from `search-unavailable`, or research writes "no papers exist" when the truth is "could not ask". Pinned in Task 5 (`check_search`).
5. **A library holding course containers next to `assets/` and empty folders** — `--list` must list chapters as `course/chapter`, must not descend into `assets/`, and must not crash on an empty course folder. Pinned in Task 4 (`check_list_library`).

---

### Task 1: Page-orientation classifier

**Files:**
- Modify: `fetch.py` (`pdf_title`, ~line 549; add `pdfinfo`, `pdf_kind`, `_MEDIABOX` just above it)
- Test: `tests/offline_checks.py`

**Interfaces:**
- Produces: `pdfinfo(path: Path) -> dict` (pdfinfo's `Key: value` lines; `{}` when missing or failing); `pdf_title(path: Path, info: dict | None = None) -> tuple[str, str, str]`; `pdf_kind(path: Path, info: dict | None = None) -> str` returning `"slides"`, `"paper"` or `""`.

- [ ] **Step 1: Write the failing test**

Add to `tests/offline_checks.py` above `CHECKS`, and append `check_pdf_kind` to `CHECKS`:

```python
def check_pdf_kind() -> None:
    d = Path(tempfile.mkdtemp())
    f = d / "x.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    orig = fetch.pdfinfo
    try:
        fetch.pdfinfo = lambda p: {"Page size": "720 x 540 pts", "Page rot": "0"}
        assert fetch.pdf_kind(f) == "slides"
        fetch.pdfinfo = lambda p: {"Page size": "595.276 x 841.89 pts (A4)", "Page rot": "0"}
        assert fetch.pdf_kind(f) == "paper"
        # Rotated portrait page displays landscape.
        fetch.pdfinfo = lambda p: {"Page size": "612 x 792 pts (letter)", "Page rot": "90"}
        assert fetch.pdf_kind(f) == "slides"
        # No pdfinfo: fall back to the first /MediaBox in the raw bytes.
        fetch.pdfinfo = lambda p: {}
        f.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Page /MediaBox [ 0 0 960 540 ] >>\nendobj\n")
        assert fetch.pdf_kind(f) == "slides"
        f.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Page /MediaBox [0 0 612 792] >>\nendobj\n")
        assert fetch.pdf_kind(f) == "paper"
        # MediaBox hidden in a compressed object stream: undecidable.
        f.write_bytes(b"%PDF-1.5\n1 0 obj\n<< /Type /ObjStm /Filter /FlateDecode >>\nendobj\n")
        assert fetch.pdf_kind(f) == ""
        assert fetch.pdf_kind(d / "missing.pdf") == ""
    finally:
        fetch.pdfinfo = orig
    # An explicit info dict is used as-is.
    assert fetch.pdf_kind(f, {"Page size": "720 x 540 pts"}) == "slides"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: FAIL with `AttributeError: module 'fetch' has no attribute 'pdfinfo'`

- [ ] **Step 3: Write minimal implementation**

In `fetch.py`, replace the whole `pdf_title` function with:

```python
def pdfinfo(path: Path) -> dict:
    """pdfinfo's 'Key: value' lines, or {} when pdfinfo is missing or fails."""
    if not shutil.which("pdfinfo"):
        return {}
    try:
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True,
                             text=True, timeout=20).stdout
    except Exception as e:
        log(f"  pdfinfo: {e}")
        return {}
    fields = {}
    for line in out.splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    return fields


def pdf_title(path: Path, info: dict | None = None) -> tuple[str, str, str]:
    """(title, author, year) from the PDF's own metadata. LaTeX-produced PDFs
    almost always carry a usable /Title."""
    fields = pdfinfo(path) if info is None else info
    m = re.search(r"\b(19|20)\d{2}\b", fields.get("CreationDate", ""))
    return fields.get("Title", ""), fields.get("Author", ""), m.group(0) if m else ""


_MEDIABOX = re.compile(rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]")


def pdf_kind(path: Path, info: dict | None = None) -> str:
    """'slides' when the first page displays landscape, 'paper' otherwise, '' when
    the page size cannot be read. Orientation is the one signal every deck shares
    and almost no paper does. The byte scan is the fallback for machines without
    pdfinfo; it misses a MediaBox packed into a compressed object stream, and the
    caller then asks rather than guesses."""
    info = pdfinfo(path) if info is None else info
    m = re.match(r"([\d.]+) x ([\d.]+)", info.get("Page size", ""))
    if m:
        w, h = float(m[1]), float(m[2])
        if info.get("Page rot", "0") in ("90", "270"):
            w, h = h, w
    else:
        try:
            box = _MEDIABOX.search(path.read_bytes())
        except OSError as e:
            log(f"  {path.name}: {e}")
            return ""
        if not box:
            return ""
        x0, y0, x1, y1 = map(float, box.groups())
        w, h = abs(x1 - x0), abs(y1 - y0)
    return "slides" if w > h else "paper"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: every line `ok  check_...`, including `ok  check_pdf_kind`

- [ ] **Step 5: Smoke-test against the real sample**

Run: `python3 -c "import fetch; from pathlib import Path; print(fetch.pdf_kind(Path('VLSI_Design_1_Introduction.pdf')))"`
Expected: `slides`

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): classify a local PDF as paper or slides by page orientation

- pdfinfo() 抽出共用；pdf_title() 可接收已讀取的 info
- pdf_kind()：pdfinfo 的 Page size（含 Page rot），無 pdfinfo 時掃 /MediaBox，判不出回空字串

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 2: Kind-aware lecture state and folder identity

**Files:**
- Modify: `fetch.py` (`DOC_FILES` ~line 580, `lecture_docs` ~line 606, `same_paper` ~line 632)
- Test: `tests/offline_checks.py` (`check_lecture_docs_and_conflicts` plus two new checks)

**Interfaces:**
- Consumes: `pdf_kind(path, info=None)` from Task 1.
- Produces: `MODES: dict[str, tuple[str, ...]]` = `{"paper": ("broad", "deep"), "slides": ("broad", "deep", "research")}`; `doc_kind(workdir: Path) -> str`; `source_kind(workdir: Path) -> str`; `lecture_docs(workdir: Path, kind: str = "") -> dict` returning `{"kind", "legacy", <mode>: state for each mode in MODES[kind]}`; `same_paper(ident, meta)` now also compares `course`.

- [ ] **Step 1: Update existing assertions and write the failing tests**

In `check_lecture_docs_and_conflicts`, change the four whole-dict assertions to:

```python
    assert fetch.lecture_docs(d) == {"kind": "paper", "legacy": False,
                                     "broad": "absent", "deep": "absent"}
```
```python
    assert fetch.lecture_docs(d) == {"kind": "paper", "legacy": False,
                                     "broad": "read", "deep": "partial"}
```
```python
    assert fetch.lecture_docs(e) == {"kind": "paper", "legacy": False,
                                     "broad": "unread", "deep": "unread"}
```
```python
    assert fetch.lecture_docs(f) == {"kind": "paper", "legacy": True,
                                     "broad": "absent", "deep": "absent"}
```

Add these checks and append both to `CHECKS`:

```python
S = {"title": "Ch01 Introduction", "course": "VLSI DSP", "kind": "slides"}


def check_slides_lecture_state() -> None:
    d = Path(tempfile.mkdtemp())
    assert fetch.lecture_docs(d, "slides") == {"kind": "slides", "legacy": False, "broad": "absent",
                                               "deep": "absent", "research": "absent"}
    write_doc(d / "broad.md", {**S, "mode": "broad", "lecture_read": "true"})
    write_doc(d / "research.part.md", {**S, "mode": "research", "lecture_read": "false"})
    # Kind read back from front matter when the caller does not know it.
    assert fetch.lecture_docs(d) == {"kind": "slides", "legacy": False, "broad": "read",
                                     "deep": "absent", "research": "partial"}
    c = fetch.folder_conflict(d, {"title": "Ch02 Pipelining", "course": "VLSI DSP"}, "s")
    assert c and c["occupant"]["file"] == "broad.md", c

    # An unknown kind in front matter is ignored, not trusted.
    e = Path(tempfile.mkdtemp())
    write_doc(e / "broad.md", {**A, "kind": "poster", "mode": "broad"})
    assert fetch.lecture_docs(e)["kind"] == "paper"

    # No lecture yet: the source PDF decides.
    g = Path(tempfile.mkdtemp())
    (g / "deck.pdf").write_bytes(b"%PDF-1.4\n<< /MediaBox [0 0 720 540] >>\n")
    orig = fetch.pdfinfo
    fetch.pdfinfo = lambda p: {}
    try:
        assert fetch.lecture_docs(g)["kind"] == "slides"
    finally:
        fetch.pdfinfo = orig


def check_same_paper_course() -> None:
    fm = {"title": "Ch01 Introduction", "course": "VLSI DSP"}
    assert fetch.same_paper(fm, {"title": "Ch01 Introduction", "course": "vlsi-dsp"})
    assert not fetch.same_paper(fm, {"title": "Ch01 Introduction", "course": "Computer Architecture"})
    assert fetch.same_paper(fm, {"title": "Ch01 Introduction"})
    assert fetch.same_paper({"title": "Ch01 Introduction"},
                            {"title": "ch01 introduction", "course": "VLSI DSP"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: FAIL at the first updated assertion in `check_lecture_docs_and_conflicts` (no `kind` key yet)

- [ ] **Step 3: Write minimal implementation**

Replace the `DOC_FILES` line with:

```python
DOC_FILES = ("broad.md", "deep.md", "research.md", "broad.part.md", "deep.part.md",
             "research.part.md", "lecture.md")
MODES = {"paper": ("broad", "deep"), "slides": ("broad", "deep", "research")}
```

Replace the whole `lecture_docs` function with:

```python
def doc_kind(workdir: Path) -> str:
    """The kind a lecture in this folder records, '' when none records a known one."""
    for name in DOC_FILES:
        kind = (front_matter(workdir / name) or {}).get("kind", "")
        if kind in MODES:
            return kind
    return ""


def source_kind(workdir: Path) -> str:
    """For a folder with no lecture yet: slides if any PDF in it is landscape."""
    return "slides" if any(pdf_kind(p) == "slides" for p in sorted(workdir.glob("*.pdf"))) else "paper"


def lecture_docs(workdir: Path, kind: str = "") -> dict:
    """Which lectures a folder holds and how far each has got. A lecture is written
    as <mode>.part.md and renamed only once its last section is done, so a .part
    file means unfinished even when a finished file of that mode also exists — a
    regeneration in progress is not done. Which modes exist depends on the kind:
    a caller that already decided it passes it, otherwise the folder says."""
    if kind not in MODES:
        kind = doc_kind(workdir) or source_kind(workdir)
    docs = {"kind": kind, "legacy": (workdir / "lecture.md").is_file()}
    for mode in MODES[kind]:
        if (workdir / f"{mode}.part.md").is_file():
            docs[mode] = "partial"
            continue
        fields = front_matter(workdir / f"{mode}.md")
        if fields is None:
            docs[mode] = "absent"
        else:
            docs[mode] = "read" if fields.get("lecture_read", "").lower() == "true" else "unread"
    return docs
```

In `same_paper`, insert as the function body's first lines (before the arXiv comparison), and extend the docstring's first sentence:

```python
    """Strongest available identifier wins, within one course: two decks share
    a chapter title far more often than two papers share a title, so differing
    courses settle it first. An arXiv id or a DOI settles it outright; only when
    one side lacks both does the comparison fall back to the title, normalised so
    that casing and punctuation do not fake a conflict."""
    c1, c2 = _norm_title(ident.get("course", "")), _norm_title(meta.get("course", ""))
    if c1 and c2 and c1 != c2:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: all `ok`, including `check_slides_lecture_state` and `check_same_paper_course`. (`check_list_library` still passes: neither its rows nor its expectations carry `kind` yet.)

- [ ] **Step 5: Bring check_list_library's expectations in line now**

So the suite is green at this commit, add `"kind": "paper",` to each of the four expected row dicts in `check_list_library`, e.g.:

```python
        {"slug": "a-read", "kind": "paper", "title": "Paper A", "year": "2017", "tier": "1",
         "broad": "read", "deep": "unread", "legacy": False},
```

and in `list_library` change the appended row to include the kind:

```python
        papers.append({"slug": d.name, "kind": docs["kind"], "title": fields.get("title", ""),
                       "year": fields.get("year", ""), "tier": fields.get("tier", ""),
                       "broad": docs["broad"], "deep": docs["deep"],
                       "legacy": docs["legacy"]})
```

Run: `python3 tests/offline_checks.py`
Expected: all `ok` (`--list` rows now carry `kind`; Task 4 restructures the function)

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): report lecture state per kind and compare courses in folder identity

- MODES：paper = broad/deep，slides = broad/deep/research；DOC_FILES 納入 research
- lecture_docs(workdir, kind)：呼叫端給定 > front matter 的 kind > 資料夾內 PDF 方向
- same_paper：兩邊都有 course 且不同時直接判定不同

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 3: Adopt a slide deck into `<course>/<chapter>/`

**Files:**
- Modify: `fetch.py` (`adopt_local` ~line 672 split into `adopt_local`, `adopt_slides`, `place`; `main` argument parsing and the `kind == "file"` branch)
- Test: `tests/offline_checks.py`

**Interfaces:**
- Consumes: `pdfinfo`, `pdf_title(path, info)`, `pdf_kind(path, info)` (Task 1); `doc_kind`, `lecture_docs(workdir, kind)`, `folder_conflict` (Task 2).
- Produces: `adopt_local(src: Path, out_override: Path | None, title_override: str, kind_override: str = "", course: str = "") -> dict`; `adopt_slides(src, out_override, title, course, info) -> dict`; `place(src: Path, workdir: Path, meta: dict, slug: str, kind: str) -> dict`; new route `needs-kind`; `meta["kind"]` on every local result; slides `meta` keys `kind, title, course, authors, year, pages, input`. CLI: `--kind {paper,slides}`, `--course TEXT`.

- [ ] **Step 1: Write the failing tests**

Add and append all three to `CHECKS`:

```python
DECK_INFO = {"Page size": "720 x 540 pts", "Pages": "79", "Title": "Slide 1",
             "CreationDate": "Wed Sep 16 15:42:45 2026 CST"}


def _adopt(src: Path, info: dict, out: Path | None = None, title: str = "",
           kind: str = "", course: str = "") -> dict:
    orig = fetch.pdfinfo
    fetch.pdfinfo = lambda p: info
    try:
        return fetch.adopt_local(src, out, title, kind, course)
    finally:
        fetch.pdfinfo = orig


def check_adopt_slides() -> None:
    root = Path(tempfile.mkdtemp())
    src = root / "VLSI_Design_1_Introduction.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    r = _adopt(src, DECK_INFO)
    assert r["route"] == "needs-title" and r["reason"].startswith("slides need --course and --title"), r
    assert r["meta"]["title"] == "", r  # "Slide 1" from metadata is not trusted
    assert src.exists()
    r = _adopt(src, DECK_INFO, course="VLSI DSP")
    assert r["reason"].startswith("slides need --title:"), r

    r = _adopt(src, DECK_INFO, course="VLSI DSP", title="Ch01 Introduction")
    wd = root / "vlsi-dsp" / "ch01-introduction"
    assert r["route"] == "needs-pdf" and r["workdir"] == str(wd) and r["tier"] == 6, r
    assert r["slug"] == "ch01-introduction"
    assert r["meta"] == {"kind": "slides", "title": "Ch01 Introduction", "course": "VLSI DSP",
                         "authors": [], "year": "2026", "pages": 79, "input": str(src)}, r["meta"]
    assert r["docs"] == {"kind": "slides", "legacy": False, "broad": "absent",
                         "deep": "absent", "research": "absent"}, r["docs"]
    moved = wd / src.name
    assert moved.exists() and not src.exists()

    # Re-run on the moved file: same folder, no nesting.
    r = _adopt(moved, DECK_INFO, course="VLSI DSP", title="Ch01 Introduction")
    assert r["workdir"] == str(wd) and moved.exists(), r

    # PDF already inside the course folder: only the chapter level is created.
    src2 = root / "vlsi-dsp" / "ch2.pdf"
    src2.write_bytes(b"%PDF-1.4\n")
    r = _adopt(src2, DECK_INFO, course="VLSI DSP", title="Ch02 Pipelining")
    assert r["workdir"] == str(root / "vlsi-dsp" / "ch02-pipelining"), r

    out = Path(tempfile.mkdtemp())
    src3 = root / "ch3.pdf"
    src3.write_bytes(b"%PDF-1.4\n")
    r = _adopt(src3, DECK_INFO, out=out, course="VLSI DSP", title="Ch03 Retiming")
    assert r["workdir"] == str(out / "vlsi-dsp" / "ch03-retiming"), r

    src4 = root / "ch4.pdf"
    src4.write_bytes(b"%PDF-1.4\n")
    r = _adopt(src4, DECK_INFO, course="超大型積體電路", title="Ch04")
    assert r["route"] == "needs-title" and "no ASCII" in r["reason"] and src4.exists(), r


def check_adopt_kind() -> None:
    root = Path(tempfile.mkdtemp())
    src = root / "unknown.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    r = _adopt(src, {})
    assert r["route"] == "needs-kind" and src.exists(), r

    # --kind forces slides on a deck whose size could not be read.
    r = _adopt(src, {}, title="Ch01 Intro", kind="slides", course="Course")
    assert r["route"] == "needs-pdf" and r["docs"]["kind"] == "slides", r
    wd = Path(r["workdir"])

    # Once a lecture records kind: slides, a re-run without --kind stays put.
    write_doc(wd / "broad.md", {"kind": "slides", "title": "Ch01 Intro", "course": "Course",
                                "mode": "broad", "lecture_read": "false"})
    portrait = {"Page size": "612 x 792 pts", "Title": "Something Else"}
    r = _adopt(wd / "unknown.pdf", portrait, title="Ch01 Intro", course="Course")
    assert r["workdir"] == str(wd) and r["docs"]["kind"] == "slides", r
    assert (wd / "unknown.pdf").exists()

    # A portrait PDF with a title is still a paper, beside the file.
    p = root / "paper.pdf"
    p.write_bytes(b"%PDF-1.4\n")
    r = _adopt(p, {"Page size": "612 x 792 pts", "Title": "A Paper Title"})
    assert r["workdir"] == str(root / "a-paper-title") and r["meta"]["kind"] == "paper", r
    assert r["docs"]["kind"] == "paper" and "research" not in r["docs"], r


def check_kind_flags_rejected_on_network_source() -> None:
    orig_argv, orig_stdout = sys.argv, sys.stdout
    for extra in (["--kind", "slides"], ["--course", "VLSI DSP"]):
        sys.argv = ["fetch.py", "1706.03762", *extra]
        sys.stdout = io.StringIO()
        try:
            rc = fetch.main()
        finally:
            sys.stdout, sys.argv = orig_stdout, orig_argv
        assert rc == 2, extra
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: FAIL in `check_adopt_slides` with `TypeError: adopt_local() takes 3 positional arguments but 5 were given`

- [ ] **Step 3: Write minimal implementation**

Replace the whole `adopt_local` function with these three functions:

```python
def adopt_local(src: Path, out_override: Path | None, title_override: str,
                kind_override: str = "", course: str = "") -> dict:
    """Give a local file the same shape every other route produces: one folder per
    paper, holding the source and (later) the lecture. The folder is created BESIDE
    the file: the file already sits where the user put it, and hauling it off to the
    configured library would relocate something nobody asked to have moved. Into
    that folder the file is MOVED, not copied — two copies of a 10 MB thesis in the
    same tree is not a library.

    The kind is decided before anything else, because it decides the folder's
    shape. A lecture already beside the file outranks the page size: a portrait
    deck adopted with --kind slides must not turn back into a paper on a re-run
    and be moved into a second, nested folder."""
    is_pdf = src.suffix.lower() == ".pdf"
    info = pdfinfo(src) if is_pdf else {}
    kind = kind_override or doc_kind(src.parent) or (pdf_kind(src, info) if is_pdf else "paper")
    if not kind:
        return {"route": "needs-kind", "path": str(src),
                "reason": "the page size could not be read, so it is unknown whether "
                          "this PDF is a paper or slides; look at its first page, then "
                          "re-run with --kind paper or --kind slides"}
    if kind == "slides":
        return adopt_slides(src, out_override, title_override, course, info)

    title, author, year = pdf_title(src, info)
    if title_override:
        title = title_override
    meta = {"kind": "paper", "title": title, "authors": [author] if author else [],
            "year": year, "doi": "", "arxiv_id": "", "abstract": "", "venue": "",
            "input": str(src)}

    if not title:
        return {"route": "needs-title", "meta": meta, "path": str(src),
                "reason": "the file carries no title metadata; read its first page, "
                          "then re-run with --title \"<the paper's title>\""}

    # No filename fallback here: a title exists by this point, and falling back to
    # the stem would name a folder "thesis-final-v3" while a real title was in hand.
    slug = slugify(title, "")
    if not slug:
        return {"route": "needs-title", "meta": meta, "path": str(src),
                "reason": f"the title {title!r} leaves no ASCII characters to name a "
                          "folder with; re-run with --title \"<the paper's English "
                          "title>\""}

    # A second run on an already-adopted file must land on the same folder, not
    # nest a <slug>/<slug>/ inside it.
    if out_override is not None:
        workdir = out_override / slug
    elif src.parent.name == slug:
        workdir = src.parent
    else:
        workdir = src.parent / slug
    return place(src, workdir, meta, slug, "paper")


def adopt_slides(src: Path, out_override: Path | None, title: str, course: str,
                 info: dict) -> dict:
    """Slides go under <course>/<chapter>/ so a course's chapters sit together.
    Both names come from the agent, read off the cover and the running headers:
    deck exports carry /Title values like "Slide 1" or "PowerPoint Presentation",
    and trusting one would mint a wrong folder name with nothing to flag it."""
    pages = info.get("Pages", "")
    meta = {"kind": "slides", "title": title, "course": course, "authors": [],
            "year": pdf_title(src, info)[2], "pages": int(pages) if pages.isdigit() else 0,
            "input": str(src)}
    missing = [flag for flag, value in (("--course", course), ("--title", title)) if not value]
    if missing:
        return {"route": "needs-title", "meta": meta, "path": str(src),
                "reason": f"slides need {' and '.join(missing)}: read the cover and the "
                          "running headers and footers, then re-run with --kind slides "
                          "--course \"<course>\" --title \"Ch<NN> <chapter title>\""}
    course_slug, slug = slugify(course, ""), slugify(title, "")
    if not course_slug or not slug:
        return {"route": "needs-title", "meta": meta, "path": str(src),
                "reason": "the course or the title leaves no ASCII characters to name "
                          "a folder with; re-run with the English --course and --title"}

    if out_override is not None:
        workdir = out_override / course_slug / slug
    elif src.parent.name == slug and src.parent.parent.name == course_slug:
        workdir = src.parent
    elif src.parent.name == course_slug:
        workdir = src.parent / slug
    else:
        workdir = src.parent / course_slug / slug
    return place(src, workdir, meta, slug, "slides")


def place(src: Path, workdir: Path, meta: dict, slug: str, kind: str) -> dict:
    """Move a local source into its folder, after proving the folder is its own."""
    dest = workdir / src.name

    conflict = folder_conflict(workdir, meta, slug)
    if conflict:
        return conflict | {"path": str(src)}

    if dest.resolve() == src.resolve():
        log("  already in place")
    elif dest.exists():
        return {"route": "conflict", "slug": slug, "workdir": str(workdir),
                "meta": meta, "path": str(src),
                "reason": f"{dest} already exists; refusing to overwrite it",
                "resolve": RESOLVE}
    else:
        # No lecture to identify the folder by, but something is already in it.
        # Whether that is this same paper under another filename or a different
        # paper entirely, nothing here can tell — and both leave two sources in a
        # folder meant for one, so say so instead of quietly adding to the pile.
        others = sorted(p.name for p in workdir.glob("*")
                        if p.is_file() and p.name not in DOC_FILES)
        if others:
            return {"route": "conflict", "slug": slug, "workdir": str(workdir),
                    "meta": meta, "path": str(src), "occupant": {"files": others},
                    "reason": f"{workdir} already holds {', '.join(others)} and no "
                              "lecture saying which paper that is",
                    "resolve": RESOLVE}
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        log(f"  moved {src.name} -> {dest}")

    ext = dest.suffix.lower()
    return {"slug": slug, "workdir": str(workdir), "meta": meta,
            "docs": lecture_docs(workdir, kind),
            "route": "needs-pdf" if ext == ".pdf" else "local",
            "tier": 6 if ext == ".pdf" else 1,
            "pdf_path": str(dest) if ext == ".pdf" else "",
            "source_path": str(dest),
            "reason": "local file; no LaTeX source available"}
```

In `main`, after the `--title` argument, add:

```python
    ap.add_argument("--kind", choices=("paper", "slides"),
                    help="local PDF only: force the kind when the page size cannot be "
                         "read or misleads (a portrait slide deck)")
    ap.add_argument("--course", default=None,
                    help="local slides only: the course name; with --title it names "
                         "the <course>/<chapter> folder")
```

Replace the `if kind == "file":` block in `main` with:

```python
    if kind == "file":
        override = Path(args.out).expanduser() if args.out else None
        result = adopt_local(Path(value), override, args.title or "",
                             args.kind or "", args.course or "")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.kind or args.course:
        log("--kind and --course apply to a local PDF only; a network source is always a paper")
        return 2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: all `ok`, including `check_adopt_slides`, `check_adopt_kind`, `check_kind_flags_rejected_on_network_source`

- [ ] **Step 5: Smoke-test the CLI on a throwaway copy of the sample**

```bash
T=$(mktemp -d) && cp VLSI_Design_1_Introduction.pdf "$T/"
python3 fetch.py "$T/VLSI_Design_1_Introduction.pdf"
python3 fetch.py "$T/VLSI_Design_1_Introduction.pdf" --course "VLSI DSP" --title "Ch01 Introduction"
find "$T"
```
Expected: first call `"route": "needs-title"` with reason starting `slides need --course and --title`; second call `"route": "needs-pdf"`, `"pages": 79`, `"docs"` with `"research": "absent"`; `find` shows `$T/vlsi-dsp/ch01-introduction/VLSI_Design_1_Introduction.pdf`.

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): adopt slide decks into course/chapter folders

- adopt_local 先判定種類：--kind > 資料夾講義的 kind > 頁面方向；判不出回 needs-kind
- adopt_slides：需 --course 與 --title，不採信 metadata Title；三種重跑情況不重複巢狀
- place()：抽出論文與簡報共用的衝突檢查與搬移
- --kind／--course 只限本機檔案，用於網路來源時 exit 2

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 4: `--list` sees course containers

**Files:**
- Modify: `fetch.py` (`list_library` ~line 748)
- Test: `tests/offline_checks.py` (`check_list_library`)

**Interfaces:**
- Consumes: `lecture_docs(workdir)` (Task 2).
- Produces: `list_library(root) -> {"route": "list", "library": str, "papers": [row]}` where each row has `slug, kind, title, year, tier, broad, deep, legacy` and, for slides, `research`. A chapter's `slug` is `"<course-slug>/<title-slug>"`.

- [ ] **Step 1: Write the failing test**

In `check_list_library`, before `r = fetch.list_library(lib)`, add:

```python
    (lib / "assets" / "a-read" / "fig.png").write_bytes(b"png")
    write_doc(lib / "vlsi-dsp" / "ch01-introduction" / "broad.md",
              {"kind": "slides", "title": "Ch01 Introduction", "course": "VLSI DSP",
               "year": "2026", "tier": "6", "mode": "broad", "lecture_read": "false"})
    (lib / "empty-course").mkdir()
```

and append this row as the last element of the expected `r["papers"]` list:

```python
        {"slug": "vlsi-dsp/ch01-introduction", "kind": "slides", "title": "Ch01 Introduction",
         "year": "2026", "tier": "6", "broad": "unread", "deep": "absent",
         "research": "absent", "legacy": False},
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: FAIL in `check_list_library` — the chapter row is missing

- [ ] **Step 3: Write minimal implementation**

Replace the whole `list_library` function with:

```python
def _subdirs(d: Path) -> list[Path]:
    try:
        return sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError as e:
        log(f"  {d}: {e}")
        return []


def _holds_file(d: Path) -> bool:
    try:
        return any(p.is_file() for p in d.iterdir())
    except OSError as e:
        log(f"  {d}: {e}")
        return False


def library_row(d: Path, slug: str) -> dict:
    fields = next((fm for fm in (front_matter(d / n) for n in DOC_FILES) if fm), {})
    docs = lecture_docs(d)
    return {"slug": slug, "title": fields.get("title", ""), "year": fields.get("year", ""),
            "tier": fields.get("tier", ""), **docs}


def list_library(root: Path) -> dict:
    """Every paper or chapter folder under root with the state of its lectures. A
    lecture folder is a non-hidden directory holding at least one file directly.
    A directory holding only directories is a container: a course, whose chapters
    are listed one level down as course/chapter — except assets/, whose
    subdirectories hold figures, not sources."""
    papers = []
    for d in _subdirs(root) if root.is_dir() else []:
        if _holds_file(d):
            papers.append(library_row(d, d.name))
        elif d.name != "assets":
            papers += [library_row(c, f"{d.name}/{c.name}")
                       for c in _subdirs(d) if _holds_file(c)]
    return {"route": "list", "library": str(root), "papers": papers}
```

(`**docs` spreads `kind`, `legacy` and one state per mode, so paper rows carry `broad`/`deep` and slides rows also `research`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: all `ok`, including `check_list_library` and `check_list_library_unreadable_dir`

- [ ] **Step 5: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): list slide chapters inside course folders

- 只含子資料夾的非隱藏資料夾（assets 除外）往下看一層，章節列為 course/chapter
- 每列帶 kind；簡報列多 research 狀態

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 5: `--search` through Semantic Scholar bulk search

**Files:**
- Modify: `fetch.py` (add constants and `search` after `graph`, ~line 395; `main` arguments and dispatch)
- Test: `tests/offline_checks.py`

**Interfaces:**
- Consumes: `s2_get(path) -> dict`, `s2_ids(rec) -> dict`, `clean_authors(names) -> list[str]` (existing).
- Produces: `search(query: str, since: int | None = None, limit: int = SEARCH_LIMIT) -> dict`; constants `SEARCH_LIMIT = 10`, `SEARCH_MAX = 1000`, `ABSTRACT_MAX = 300`. Success: `{"route": "search", "query", "since", "total", "papers": [{"title", "year", "arxiv", "doi", "authors", "venue", "citations", "fields", "abstract"}], "fetched_on"}`. Failure: `{"route": "search-unavailable", "query", "reason"}`. CLI: `--search QUERY [--since YEAR] [--limit N]`.

- [ ] **Step 1: Write the failing test**

Add and append to `CHECKS`:

```python
def check_search() -> None:
    long_abs = "word " * 100
    records = [
        {"title": "Systolic Arrays for (VLSI).", "year": 1978, "citationCount": 1064,
         "externalIds": {"CorpusId": 1}, "authors": [{"name": "H. Kung"}, {"name": ":"}],
         "venue": "", "abstract": None, "fieldsOfStudy": ["Computer Science"]},
        {"title": "SIGMA", "year": 2020, "citationCount": 541,
         "externalIds": {"DOI": "10.1109/x", "ArXiv": "2001.00001"}, "authors": [],
         "venue": "HPCA", "abstract": long_abs, "fieldsOfStudy": None},
        {"title": "third", "year": 2021, "citationCount": 1, "externalIds": {},
         "authors": [], "abstract": "short"},
    ]
    calls: list[str] = []

    def fake(path: str) -> dict:
        calls.append(path)
        return {"total": 3, "data": records}

    orig = fetch.s2_get
    fetch.s2_get = fake
    try:
        r = fetch.search('"systolic array"', since=2023, limit=2)
        no_year = fetch.search("dct")
        fetch.s2_get = lambda path: {"total": 0}
        empty = fetch.search("nothing matches this")
        def refuse(path: str) -> dict:
            raise fetch.urllib.error.HTTPError(path, 429, "Too Many Requests", {}, None)
        fetch.s2_get = refuse
        failed = fetch.search("dct")
    finally:
        fetch.s2_get = orig

    assert r["route"] == "search" and r["total"] == 3 and r["since"] == 2023, r
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["fetched_on"])
    p0, p1 = r["papers"]  # cut to limit client-side: the endpoint ignores limit
    assert p0 == {"title": "Systolic Arrays for (VLSI).", "year": 1978, "arxiv": "", "doi": "",
                  "authors": ["H. Kung"], "venue": "", "citations": 1064,
                  "fields": ["Computer Science"], "abstract": ""}, p0
    assert p1["arxiv"] == "2001.00001" and p1["doi"] == "10.1109/x" and p1["fields"] == []
    assert len(p1["abstract"]) <= fetch.ABSTRACT_MAX + 1 and p1["abstract"].endswith("…"), p1

    q = calls[0]
    assert q.startswith("/paper/search/bulk?"), q
    assert "query=%22systolic%20array%22" in q and "sort=citationCount%3Adesc" in q, q
    assert "year=2023-" in q, q
    assert "year=" not in calls[1] and len(no_year["papers"]) == 3

    assert empty == {"route": "search", "query": "nothing matches this", "since": None,
                     "total": 0, "papers": [], "fetched_on": empty["fetched_on"]}, empty
    assert failed == {"route": "search-unavailable", "query": "dct", "reason": "HTTP 429"}, failed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: FAIL with `AttributeError: module 'fetch' has no attribute 'search'`

- [ ] **Step 3: Write minimal implementation**

After the `graph` function, add:

```python
SEARCH_FIELDS = "title,year,authors,venue,citationCount,externalIds,abstract,fieldsOfStudy"
SEARCH_LIMIT = 10
SEARCH_MAX = 1000
ABSTRACT_MAX = 300


def search(query: str, since: int | None = None, limit: int = SEARCH_LIMIT) -> dict:
    """Papers on a topic, most-cited first — research mode's only source for a
    deck, which cites almost nothing a citation graph could start from. The bulk
    endpoint is the one search that sorts by citation count. It ignores `limit`
    and returns up to 1000 records, so the cut happens here. Abstracts are often
    null; fieldsOfStudy is returned so the agent can still drop namesakes from
    other fields. Zero results is a search that worked, distinct from one that
    could not be made."""
    params = {"query": query, "sort": "citationCount:desc", "fields": SEARCH_FIELDS}
    if since:
        params["year"] = f"{since}-"
    try:
        data = s2_get("/paper/search/bulk?"
                      + urllib.parse.urlencode(params, quote_via=urllib.parse.quote))
    except urllib.error.HTTPError as e:
        return {"route": "search-unavailable", "query": query, "reason": f"HTTP {e.code}"}
    except Exception as e:
        return {"route": "search-unavailable", "query": query, "reason": str(e)}

    papers = []
    for p in (data.get("data") or [])[:limit]:
        abstract = (p.get("abstract") or "").strip()
        if len(abstract) > ABSTRACT_MAX:
            abstract = abstract[:ABSTRACT_MAX].rsplit(" ", 1)[0] + "…"
        papers.append({**s2_ids(p),
                       "authors": clean_authors([a.get("name", "") for a in p.get("authors") or []]),
                       "venue": p.get("venue") or "", "citations": p.get("citationCount") or 0,
                       "fields": p.get("fieldsOfStudy") or [], "abstract": abstract})
    return {"route": "search", "query": query, "since": since,
            "total": data.get("total") or 0, "papers": papers,
            "fetched_on": time.strftime("%Y-%m-%d")}
```

In `main`, after the `--graph` argument, add:

```python
    ap.add_argument("--search", metavar="QUERY",
                    help="papers on a topic from Semantic Scholar, most-cited first; "
                         "quote phrases inside the query: '\"systolic array\"'")
    ap.add_argument("--since", type=int, metavar="YEAR",
                    help="with --search: only papers from YEAR onward")
    ap.add_argument("--limit", type=int, default=SEARCH_LIMIT, metavar="N",
                    help=f"with --search: at most N papers (default {SEARCH_LIMIT}, "
                         f"max {SEARCH_MAX})")
```

After the `if args.graph:` block, add:

```python
    if args.search:
        if not 1 <= args.limit <= SEARCH_MAX:
            log(f"--limit must be between 1 and {SEARCH_MAX}")
            return 2
        print(json.dumps(search(args.search, args.since, args.limit),
                         ensure_ascii=False, indent=2))
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/offline_checks.py`
Expected: all `ok`, including `check_search`

- [ ] **Step 5: Live check against the real endpoint**

Run: `python3 fetch.py --search '"systolic array"' --since 2023 --limit 3`
Expected: `"route": "search"`, `"total"` in the hundreds, three papers all with `year` ≥ 2023, sorted by `citations` descending. A `search-unavailable` with `HTTP 429` means rate limiting — wait a minute and retry once; it is not a code failure.

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): add --search over Semantic Scholar bulk search

- search()：依 citationCount 排序、--since 年份篩選、本地截斷至 --limit（端點忽略 limit）
- 回傳 fieldsOfStudy 與截斷的 abstract 供相關性過濾；零筆與失敗分屬 search／search-unavailable

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 6: `SKILL.md` and `lecture-format.md` route slides to their workflow

**Files:**
- Modify: `SKILL.md`
- Modify: `lecture-format.md` (檔頭 section)

**Interfaces:**
- Consumes: routes `needs-kind`, slides `needs-title`, `docs.kind`, `docs.research`, list rows with `kind`/`research` (Tasks 2–5).
- Produces: the hand-over sentence "read `slides.md`" that Task 7's file must satisfy; `--research` flag semantics.

- [ ] **Step 1: Replace the front-matter `description` line in `SKILL.md`**

```yaml
description: "Bilingual lectures from research papers and course slides — invoke with /ppread [--broad | --deep | --research] <arXiv ID | DOI | URL | title | PDF path>, or /ppread --list [dir]. Papers: --broad writes broad.md (abstract, introduction and conclusion paragraph by paragraph — English original, Traditional Chinese translation, explanation — the outside knowledge the paper assumes, a quick pass over the core method, and its place in the literature from the Semantic Scholar citation graph); --deep writes deep.md (the whole paper with critical analysis, a claims-versus-evidence table and design decisions). Course slides (a landscape PDF lecture deck, often carrying the student's own annotations): --broad maps the chapter and explains every technical term in both languages; --deep works through each technical unit with filled-in derivations, worked examples and a check of the student's notes; --research links the chapter's topics to foundational and recent papers found through Semantic Scholar search. Every lecture ends with questions and folded reference answers. --list shows every paper's and chapter's lectures and whether each has been read. Stops at the lecture and never writes the user's own notes."
```

- [ ] **Step 2: Replace the H1 and the intro paragraph that follows it**

Replace from `# /ppread — Paper Lectures, Broad and Deep` through the line `translating, explaining and questioning are judgment and live here.` with:

```markdown
# /ppread — Lectures from Papers and Course Slides

Turn one paper into a lecture the user can read straight through. There are two
kinds, written to two files, for two different jobs:

- **broad** (`broad.md`) — place the paper: what it answers, what it assumes, what
  its core idea is, where it sits among other work, what to read next.
- **deep** (`deep.md`) — judge the paper: does the argument hold, why was each
  design decision made, does the evidence carry the claims.

A local PDF can also be a **course slide deck**. Slides get three lectures —
broad, deep and research — and their own workflow in `slides.md`; Step 0 below
says when to switch to it.

Fetching and every other step with a right answer lives in `fetch.py`; reading,
translating, explaining and questioning are judgment and live here.
```

- [ ] **Step 3: Extend the Invocation table and the paragraph under it**

Add this row after the `--deep` row:

```markdown
| `/ppread --research <slides PDF>` | Research lecture — slides only |
```

Replace the last sentence of the paragraph under the table (`Strip \`--broad\`/\`--deep\` before passing the source to \`fetch.py\`; \`fetch.py\` does not accept them.`) with:

```markdown
Strip `--broad`/`--deep`/`--research` before passing the source to `fetch.py`;
`fetch.py` does not accept them. `--research` exists only for slides: on a paper,
say that a paper's broad lecture already places it in the literature, and stop.
`--kind` and `--course` are `fetch.py` flags you add yourself when Step 0 asks for
them; the user never types them.
```

- [ ] **Step 4: Update the Step 0 route table**

Change the `needs-pdf` row's third cell to:

```markdown
Paper: convert to text — see "The PDF route" below. **Slides** (`docs.kind: slides`): do not convert — `slides.md` reads the pages as images.
```

Add this row after the `conflict` row:

```markdown
| `needs-kind` | Local PDF whose page size could not be read, so paper vs. slides is unknown | Look at page 1 (Read with `pages: "1"`). Landscape lecture slides → re-run with `--kind slides`; otherwise `--kind paper`. The file was **not** moved. |
```

In the `needs-title` row's third cell, prepend:

```markdown
**Slides** (`meta.kind: slides`): `reason` names what is missing — see "Naming: course and chapter" in `slides.md`. The file was **not** moved. Otherwise:
```

- [ ] **Step 5: Generalise "Choosing the mode"**

Replace the paragraph starting `` `broad`/`deep` are each `absent`, `` through the end of rule 3 (`report the file's path and stop.`) with:

```markdown
`docs.kind` is `paper` or `slides` and fixes the **mode sequence**: paper =
broad, deep; slides = broad, deep, research. `docs` carries one state per mode in
the sequence, each `absent`, `partial` (being written, or interrupted), `unread`
or `read`. A mode is **finished** when its state is `unread` or `read`; `absent`
and `partial` are not finished. The table below is illustrative only and covers
papers; the rule that actually decides, for every combination of either kind, is:

1. **No flag**: the mode to act on is the first in the sequence that is not
   finished. If all are finished, stop and report every path.
2. **`--broad`, `--deep` or `--research`**: the named mode is the mode to act on
   (`--research` on a paper: see Invocation).
3. Whatever mode was selected by 1 or 2: `absent` → write it; `partial` → ask
   the user whether to resume or restart (see the bullet below); finished →
   report the file's path and stop.
```

- [ ] **Step 6: Insert the hand-over section**

Immediately before `## Step 1: Survey before writing`, insert:

```markdown
## Slides: switch to slides.md

When Step 0's `docs.kind` is `slides`, read `slides.md` (same directory) and
follow its Steps 1–4 **in place of** Steps 1–4 below. Step 5, Listing and
Discipline in this file still apply in full.
```

- [ ] **Step 7: Update Listing**

Replace the sentence starting `Render \`papers\` as a table — title, year, broad, deep —` up to `` `legacy: true`. `` with:

```markdown
Render `papers` as a table — title, kind, year, broad, deep, research — using `✓`
for `read`, `○` for `unread`, `…` for `partial`, `—` for `absent` or for a mode
the kind does not have (a paper has no research), and a footnote for rows with
`legacy: true`. A slides row's `slug` is `<course>/<chapter>`.
```

- [ ] **Step 8: Record `kind` in the paper front matter (`lecture-format.md`)**

In the 檔頭 example, add `kind: paper` as the line after `type: reading`. After the bullet starting `- \`mode\` 為`, add:

```markdown
- `kind` 一律寫 `paper`。課程簡報的講義格式不在這份檔案，見 `slides-format.md`。
```

- [ ] **Step 9: Verify**

Run: `grep -c "slides.md" SKILL.md && grep -n "needs-kind\|--research\|mode sequence" SKILL.md && grep -n "kind: paper" lecture-format.md`
Expected: a count ≥ 3; matches for all three patterns in SKILL.md; one or more matches in lecture-format.md.

Read SKILL.md top to bottom once and confirm no sentence still says the skill has only two modes or only reads papers (the deep/broad paper wording inside Steps 1–4 is correct as is).

- [ ] **Step 10: Commit**

```bash
git add SKILL.md lecture-format.md
git commit -F - <<'EOF'
docs(skill): route slides to slides.md and generalise mode selection by kind

- description、Invocation 加入課程簡報與 --research
- Step 0：needs-kind、簡報 needs-title、簡報不走 PDF 文字轉換
- 模式序列依 docs.kind；Listing 加 kind 與 research 欄
- lecture-format.md：論文 front matter 記錄 kind: paper

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 7: `slides.md` — the slides workflow

**Files:**
- Create: `slides.md`

**Interfaces:**
- Consumes: `fetch.py --kind/--course/--title`, `--search`, `--graph`, `--verify` (Tasks 3, 5); `slides-format.md` and `questions.md`「簡報」(Task 8).
- Produces: the workflow SKILL.md's hand-over points to.

- [ ] **Step 1: Write `slides.md`**

````markdown
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
  code.
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
````

- [ ] **Step 2: Verify consistency with fetch.py**

Every `fetch.py` flag that `slides.md` names must exist.

Run: `python3 fetch.py --help | grep -E -- "--(kind|course|search|since|limit)"`
Expected: five lines.

- [ ] **Step 3: Commit**

```bash
git add slides.md
git commit -F - <<'EOF'
docs(skill): add slides.md workflow for course slide decks

- 命名（--course／--title ChNN）、以看圖為主的閱讀、四層內容分辨、頁碼雙標、公式轉寫規則
- Step 1 總覽與分模式計畫；Step 2 research 查詢與過濾；Step 3–4 寫作與收尾；簡報專屬紀律

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 8: `slides-format.md` and the slides part of `questions.md`

**Files:**
- Create: `slides-format.md`
- Modify: `questions.md` (append a「簡報」part; adjust the opening line)

**Interfaces:**
- Consumes: front matter keys produced by Task 3's `meta` (`kind, title, course, authors, year, pages`).
- Produces: the output contract `slides.md` Step 3 loads; the fixed question IDs `SB1–SB5`, `SD1–SD5`, `SR1–SR3`.

- [ ] **Step 1: Write `slides-format.md`**

````markdown
# 簡報講義輸出格式

逐字遵守。一份課程簡報最多三份講義：`broad.md`（廣讀）、`deep.md`（深讀）、
`research.md`（研究延伸），格式各自在下方定義，三者共用「共通規則」。

問題區塊的出題與格式見 `questions.md` 的「簡報」部分。

---

# 共通規則

## 檔頭

```markdown
---
type: reading
kind: slides
mode: broad
lecture_read: false
generated: claude
title: Ch01 Introduction
course: VLSI DSP
authors: [M. D. Shieh]
institution: NCKU EE
year: 2026
pages: 79
tier: 6
created: 2026-10-01
---
```

- `kind` 一律 `slides`；`mode` 為 `broad`、`deep`、`research`，與檔名一致。
- `title`、`course` 必須與 `fetch.py` 的 `--title`、`--course` 一字不差——資料夾身分靠它們比對。
- `authors` 填講者，`institution` 填開課單位，都從封面與頁首頁尾讀出；讀不到就留空，不要猜。
- `lecture_read`、`generated`、`tier` 的規則與 `lecture-format.md` 相同。
- 同一份簡報的三份講義，front matter 除了 `mode`、`lecture_read`、`created` 以外必須一致。

## 開頭

檔頭之後，三份講義都以這兩行開始：

```markdown
# VLSI DSP — Ch01 Introduction

> **來源**　VLSI_Design_1_Introduction.pdf（79 頁，含課堂筆記與 1 頁手寫插頁）｜ **保真度**　tier 6（公式自投影片圖像轉寫）
```

deep 與 research 在標題後加上模式名稱：`# VLSI DSP — Ch01 Introduction（深讀）`、`（研究延伸）`。

## 頁碼

一律雙標：`投影片 9（PDF p.10）`。沒有印頁碼的插頁：`PDF p.9（手寫插頁）`。範圍：`投影片 34–37（PDF p.35–38）`。

## 投影片原文與課堂筆記

投影片原文用引用塊，第一行標出頁碼；條列照投影片的層級：

```markdown
> **投影片 8（PDF p.8）**
> - System design is often a tradeoff among
>   - Cost (hardwired)
>   - Time to market (programmable processor)
>   - Area/power (hardwired)
```

課堂筆記用 `[!note]` callout，標題寫明是打字還是手寫、在哪一頁，內容照錄、不修字：

```markdown
> [!note] 課堂筆記（打字，PDF p.8）
> 上述設計，是使用 floding（把那個面積大的折起來的概念）, upfloding 技巧。
```

手寫內容只轉寫看得清的部分；看不清的寫 `〔無法辨識〕`。

兩種區塊不可混用：投影片沒有的字不進引用塊，筆記裡的字不寫成投影片的話。

## 外部論文的寫法

與 `lecture-format.md` 相同：「作者 et al. (年份)」並附連結，連結優先
`https://arxiv.org/abs/<id>`，其次 `https://doi.org/<doi>`，兩者皆無就只寫標題與年份。
論文只能來自 `fetch.py --search`、`--graph` 或 `exact` 的 `--verify`。

## 反例（三份皆適用）

- **逐條翻譯投影片條列**——「Cost (hardwired)：成本（硬接線）」。條列是片段，翻譯沒有增加資訊；名詞的意思屬於術語段。
- **把筆記寫成老師的話**——「老師指出這是 folding 技巧」，實際上那是學生的打字筆記，而且原文拼錯。
- **把補完寫成投影片的意思**——「投影片的意思是 FIR 沒有回授」。投影片沒寫的，標為補完。
- **腦補看不清的公式**——圖像模糊或被筆記蓋住時，寫 `⚠️ 此處公式無法從投影片圖像確認`。
- **單標頁碼**——只寫「p.10」，讀者分不出是投影片頁碼還是 PDF 頁碼。
- **憑記憶列文獻**——research 或任何一處出現沒有經過 `--search`／`--graph`／`--verify` 的論文。

---

# 廣讀 `broad.md`

目的：把整章串成一張地圖，並讓讀者看懂投影片上的每一個專有名詞。**不處理推導**——那是深讀的事。

## 骨架

```markdown
## 章節地圖

## 術語

### （主題群組）

## 先備知識

## 老師強調的重點

## 問題
```

## 章節地圖

```markdown
## 章節地圖

**這章回答**　為什麼 DSP 演算法要做成專用硬體，以及從演算法走到硬體架構要經過哪些步驟。

| 頁碼 | 內容 | 在論證中的角色 |
|---|---|---|
| 投影片 2–13（PDF p.2–14） | 通訊與多媒體系統實例、hardwired 與 programmable 的取捨 | 動機：運算量與功耗需求逼出專用硬體 |
| 投影片 19–33（PDF p.20–34） | 演算法、架構、電路三個層面的設計議題 | 問題空間：設計者能在哪些層面動手、各能換到多少效能 |

- **結構觀察**　（章節結構上值得一提的事，例如後半段的記號與例子自成一套、像是另一份講義接上；沒有就不寫這一條）
```

「這章回答」一句話。表格的每一列是一段連續頁碼，「在論證中的角色」講它推進了什麼，不是重述標題。

## 術語

投影片上出現的每一個專有名詞都收，依**主題**分組（每組一個 `###`），不照字母排。分兩級：

**本章核心**——出現在技術單元、在多張投影片反覆出現、或本身就是設計流程的一步。每個一個 `####`：

```markdown
### 演算法表示法

#### 資料流圖（data flow graph, DFG）

- **定義**　A directed graph whose nodes are computations and whose edges carry data from producer to consumer, each edge labelled with the number of delay elements on it.
- **中文解釋**　節點是運算，邊是資料從誰流向誰，邊上的數字是那條路徑上暫存器的個數。它只說「誰的輸出餵給誰」，不決定什麼時候、用哪一個硬體執行——那是 scheduling 與 allocation 的工作。
- **出現在**　投影片 45–48（PDF p.46–49）、58–61（PDF p.59–62）
- **在本章的角色**　從演算法走到架構的中介表示；本章後半的 pipelining、retiming、scheduling 都是在 DFG 上做的變換。
```

- 「定義」用英文，力求精確；「中文解釋」不是定義的翻譯，而是補上直覺與它**不是**什麼。
- 「在本章的角色」不可省略：少了它，術語段只是一本字典。

**點到即可**——只在清單中被點名一次的名詞。每個主題群組末尾一張表：

```markdown
#### 點到即可

| 術語 | 是什麼 | 出現在 |
|---|---|---|
| 格狀編碼調變（trellis coded modulation, TCM） | 把通道編碼與調變合併設計，不增加頻寬就提高抗雜訊能力的技術 | 投影片 16（PDF p.17） |
| 卡爾曼濾波（Kalman filter） | 以狀態空間模型遞迴估計非平穩訊號狀態的濾波器 | 投影片 20（PDF p.21） |
```

「是什麼」一句話，讓讀者看到名詞時不卡住就好，不展開。

## 先備知識

這章沒講、但讀者不會就會卡住的東西。每項一個 `###`，格式與 `lecture-format.md`「讀懂它需要先知道的」相同（**卡在哪裡**／**要懂到什麼程度**／**去哪裡補**）。「去哪裡補」可以指向一般教科書的章節類型（例如「訊號與系統教科書的 z 轉換章」）；指向特定論文時，那篇論文同樣要經過查證。

## 老師強調的重點

從課堂筆記與螢光筆挑出投影片沒寫、但講課時強調的論點。每點一個粗體小標題：

```markdown
- **架構沒有最佳解**
  > [!note] 課堂筆記（打字，PDF p.8）
  > 老師說：架構沒有最佳解，只有比上次更好的解

  這句話是投影片 8 的 trade-off 清單沒說出口的結論：cost、time to market、area/power、flexibility、performance 互相牽制，所以設計目標是寫出一個 cost function 再去改善它，而不是找一個全域最佳。
```

引用的筆記若有錯（術語拼錯、概念錯置），在說明中直接指出並給正確版本。

## 問題

見 `questions.md`「簡報」。

---

# 深讀 `deep.md`

目的：讓讀者能自己做出本章的推導與方法。只處理**技術單元**。

## 骨架

```markdown
# VLSI DSP — Ch01 Introduction（深讀）

> **來源**　…｜ **保真度**　…
> **廣讀**　[broad.md](./broad.md)
> **範圍**　技術單元 9 個（投影片 34–78）；術語清單頁見廣讀〈術語〉

## 數位濾波器的表示法（投影片 34，PDF p.35）

## DSP Algorithm 2: DCT（投影片 35–37，PDF p.36–38）

…

## 問題
```

- `broad.md` 不存在時，「廣讀」一行寫 `無（可另跑 /ppread --broad）`，並在需要時就地補術語。
- 連回廣讀用相對路徑 `[broad.md](./broad.md)`，原因同 `lecture-format.md`。
- 術語清單頁不重講。範圍行交代它們由廣讀負責即可。

## 技術單元

每個單元一個 `##`，標題是單元主題與頁碼。內容依序：投影片原文、補完、實作例、筆記核對。用粗體標籤，不用標題——Obsidian 大綱只該有單元。

```markdown
## 數位濾波器的表示法（投影片 34，PDF p.35）

> **投影片 34（PDF p.35）**
> $$y(n)=\sum_{k=1}^{p}a_k\,y(n-k)+\sum_{k=0}^{q}b_k\,x(n-k)$$
> $$\Rightarrow Y(z)=H(z)\,X(z),\quad H(z)=\frac{B(z)}{A(z)},\quad B(z)=\sum_{k=0}^{q}b_kz^{-k},\ A(z)=1-\sum_{k=1}^{p}a_kz^{-k}$$
> - Moving average (MA) filter ⇒ FIR filter: $H(z)=B(z)$
>
> （公式自投影片圖像轉寫）

**補完**

- **從差分方程到 $H(z)$**　投影片跳過了一步：z 轉換的時移性質把 $x(n-k)$ 變成 $z^{-k}X(z)$，對 $y$ 同理。兩邊取 z 轉換後，把含 $Y(z)$ 的項移到左邊，得到 $Y(z)\,(1-\sum a_kz^{-k})=X(z)\sum b_kz^{-k}$，相除即 $H(z)=B(z)/A(z)$。
- **FIR 與 IIR 的分界**　所有 $a_k=0$ 時沒有回授，輸出只依賴有限個輸入，脈衝響應長度有限——FIR。任一 $a_k\neq0$ 就有回授——IIR。這條分界在硬體上的意義是：回授迴路決定了 pipelining 能切多細，後續章節的 iteration bound 就是從這裡來的。

**實作例**　3-tap FIR：$y(n)=b_0x(n)+b_1x(n-1)+b_2x(n-2)$。

1. $p=0$、$q=2$，所以 $H(z)=b_0+b_1z^{-1}+b_2z^{-2}$。
2. 脈衝響應：輸入 $\delta(n)$，輸出依序是 $b_0, b_1, b_2, 0, 0, \dots$——三個係數就是脈衝響應本身。
3. 直接型實作需要 2 個延遲元件、3 個乘法器、2 個加法器；最長路徑是一個乘法加兩個加法，$T_M+2T_A$。

**筆記核對**　本單元沒有課堂筆記。
```

**補完**的面向依單元挑用，用不上的不寫：

| 面向 | 回答什麼 |
|---|---|
| 跳過的步驟 | 投影片從 A 直接到 B，中間缺了什麼 |
| 為什麼成立 | 這一步依賴什麼性質或假設 |
| 與前面的關係 | 這個單元用到前面哪個單元的結果 |
| 硬體意義 | 數學上的性質在面積、時間、功耗上換成什麼 |
| 何時不適用 | 方法的前提在什麼情況下不成立 |

**實作例**用投影片自己給的例子（或投影片點名但沒做完的例子）實際算一遍，步驟編號。投影片沒有例子時，自己設計一個最小的例子，並寫明「此例非投影片所有」。

**筆記核對**對本單元每一則筆記給判定：

```markdown
**筆記核對**

> [!note] 課堂筆記（打字，PDF p.8）
> 上述設計，是使用 floding（把那個面積大的折起來的概念）, upfloding 技巧。

- **判定：有誤，需更正**　術語應為 folding 與 unfolding。folding 把多個運算分時共用到較少的硬體上，省面積、付出時間；unfolding 反過來把一次迭代展開成多份平行處理，付出面積、換取 throughput。筆記「把面積大的折起來」抓到 folding 的方向，但把兩者寫成同一件事。
```

判定只有三種：`正確`、`需補充`、`有誤，需更正`。後兩者必須給出正確版本與理由。

依賴圖表的單元，有 `pdftoppm` 時嵌入該頁：

```markdown
![投影片 26（PDF p.27）](./assets/pdf-p027.png)
```

用相對路徑而非 `![[...]]`：每個章節資料夾都有自己的 `pdf-p027.png`，wikilink 無法唯一解析。

## 問題

見 `questions.md`「簡報」。

---

# 研究延伸 `research.md`

目的：從這一章的主題出發，找到奠基的論文、發展脈絡與目前的研究進展，讓讀者知道課堂內容通往哪裡。

## 骨架

```markdown
# VLSI DSP — Ch01 Introduction（研究延伸）

> **來源**　…｜ **查詢日期**　2026-10-01 ｜ **剔除**　共 14 筆不相關檢索結果
> **廣讀**　[broad.md](./broad.md)

## 主題總覽

## （主題一）

### 奠基

### 發展脈絡

### 近期進展

## （主題二）

…

## 建議閱讀順序

## 問題
```

## 主題總覽

```markdown
| 主題 | 來源投影片 | 為什麼值得延伸 |
|---|---|---|
| Systolic array | 投影片 26–27（PDF p.27–28） | 本章只給出架構示意；同一個概念是今日 DNN 加速器的主流資料流 |
```

主題 4–6 個。「為什麼值得延伸」講課堂內容與研究現況的落差，不是重述主題。

## 每個主題

`##` 主題名稱，第一段是粗體標籤 **與本章的關係**，一兩句指出投影片上的哪個概念、哪一頁。接著三個 `###`，每篇論文一條：

```markdown
### 奠基

- [<title>](https://arxiv.org/abs/<id>)（<第一作者> et al., <年>）——<這篇對該主題的貢獻，一句>；接本章 <概念>（投影片 <N>）。`/ppread <id>`
```

- 標題、作者、年份一律取自 `fetch.py` 的輸出，不改寫。
- 有 arXiv ID 的論文在行尾附 `/ppread <id>`，讓讀者直接接回論文模式。
- **奠基** 取自依引用數排序的 `--search`；**發展脈絡** 取自核心奠基論文的 `--graph`（引用它、且延伸了它的論文）；**近期進展** 取自 `--since` 的 `--search`。
- 每層 1–4 篇。寧缺勿濫：過濾後只剩一篇就只寫一篇。

某一層查不到時不留白，寫一行原因：

```markdown
> 本次無法取得近期進展（原因：HTTP 429），此層從缺。
```

過濾後沒有相關論文時：

```markdown
> 檢索到 37 筆，皆與本主題無關，此層從缺。
```

## 建議閱讀順序

編號清單，只能引用上方已列出的論文。每項一句說明為什麼排在這裡（先備關係、難度、或與課程進度的對應）。

## 問題

見 `questions.md`「簡報」。
````

- [ ] **Step 2: Update the opening line of `questions.md`**

Replace the first paragraph under `# 問題區塊` (`每份講義（\`broad.md\`、\`deep.md\`）的最後一個 \`##\` 區塊。…`) so its first sentence reads:

```markdown
每份講義的最後一個 `##` 區塊。論文的兩份講義用以下各節；課程簡報的三份講義用文末「簡報」部分的固定題與題數，其餘規則共用。
```

(keep the rest of that paragraph unchanged).

- [ ] **Step 3: Append the「簡報」part to `questions.md`**

```markdown
---

# 簡報

`kind: slides` 的三份講義用這一部分的固定題與題數。「客製題」的四條判準、「參考答案」「格式」「邊界」沿用上方論文的規則，只有兩處不同：原文位置寫成 `投影片 N（PDF p.M）`；固定題由本專案設計，沒有外部出處。

## 題數

| 講義 | 固定題 | 客製題 |
|---|---|---|
| `broad.md` | SB1–SB5 | SB6 起，最多 3 題 |
| `deep.md` | SD1–SD5 | SD6 起，最多 3 題 |
| `research.md` | SR1–SR3 | SR4 起，最多 2 題 |

## 廣讀

| # | 題目 |
|---|---|
| SB1 | 這一章要回答什麼問題？用一段話串起整章的論證。 |
| SB2 | 本章最核心的三個術語各是什麼？各用一句話定義，並說明三者的關係。 |
| SB3 | 這一章依賴哪些先備知識？各從哪一頁開始用到？ |
| SB4 | 本章的方法在完整的設計流程中負責哪一段？上游輸入什麼、向下游交出什麼？ |
| SB5 | 深讀時最該花時間在哪幾個單元？理由是什麼？ |

SB5 是廣讀的出口，參考答案必須點名單元與頁碼。

## 深讀

| # | 題目 |
|---|---|
| SD1 | 不看投影片，重現本章最核心的推導或演算法步驟。 |
| SD2 | 用一個不在投影片上的新例子，把本章的方法走一遍。 |
| SD3 | 本章的方法在什麼條件下不適用，或會失效？ |
| SD4 | 投影片省略了哪一步？少了它，會讓人誤解什麼？ |
| SD5 | 本章哪兩個概念最容易混淆？差別在哪裡？ |

深讀的客製題是**考題形式**：給定條件，要求算出或推導出結果（例如「給定這個 DFG 與各運算的延遲，排出 ASAP 與 ALAP schedule，並指出哪些運算有 mobility」）。必須只用本章與先備知識就能解。參考答案寫出完整步驟，不只給最後答案；此時「3–6 句」的長度限制不適用。

## 研究

| # | 題目 |
|---|---|
| SR1 | 這些主題中，哪一條離目前的研究前沿最近？從本章走到那裡，中間缺哪些知識？ |
| SR2 | 選一篇近期論文：它在本章的哪個概念上做了延伸？延伸的方向是什麼？ |
| SR3 | 本章教的方法中，哪一個在近期研究中已經被取代或大幅修改？證據來自哪一篇？ |

SR2、SR3 的參考答案只能引用 `research.md` 已列出的論文。
```

- [ ] **Step 4: Verify**

Run: `grep -c "^| S[BDR][0-9]" questions.md && grep -n "^# " slides-format.md`
Expected: `13`; the H1s `# 簡報講義輸出格式`, `# 共通規則`, `# 廣讀 \`broad.md\``, `# 深讀 \`deep.md\``, `# 研究延伸 \`research.md\`` (plus H1 lines inside code fences, which are examples).

Run: `grep -n "pdf-p\|PPREAD\|--search" slides.md slides-format.md`
Expected: the asset name pattern `pdf-p<NNN>` / `pdf-p027` is consistent across both files.

- [ ] **Step 5: Commit**

```bash
git add slides-format.md questions.md
git commit -F - <<'EOF'
docs(skill): add slides lecture format and slides question sets

- slides-format.md：共通規則（檔頭、頁碼雙標、投影片引用與筆記 callout、反例）與三份講義的骨架與範例
- questions.md：簡報題數、SB1–SB5、SD1–SD5（客製題為考題形式）、SR1–SR3

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 9: Deploy list and `CLAUDE.md`

**Files:**
- Modify: `deploy.sh`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `slides.md`, `slides-format.md` (Tasks 7–8).
- Produces: a deploy that ships six files.

- [ ] **Step 1: Add the two files to `deploy.sh`**

After the `questions.md` install line, add:

```bash
install -m 0644 "$SRC/slides.md"         "$DEST/slides.md"
install -m 0644 "$SRC/slides-format.md"  "$DEST/slides-format.md"
```

- [ ] **Step 2: Verify the deploy into a scratch directory**

Run: `T=$(mktemp -d) && CLAUDE_SKILLS_DIR="$T" ./deploy.sh && ls "$T/ppread"`
Expected: `deployed -> <T>/ppread` and exactly `SKILL.md  fetch.py  lecture-format.md  questions.md  slides-format.md  slides.md`

- [ ] **Step 3: Update `CLAUDE.md`**

1. In「What this is」, replace the sentence starting `The skill turns one research paper into bilingual lectures in two modes:` through the end of that paragraph with:

```markdown
The skill turns one research paper into bilingual lectures in two modes: `broad.md` places the paper (abstract/introduction/conclusion paragraph by paragraph, assumed outside knowledge, core idea, literature context grounded in the citation graph) and `deep.md` judges it (every paragraph with critical analysis, claims versus evidence, design decisions). A local course slide deck gets three: `broad.md` maps the chapter and explains every term, `deep.md` works through each technical unit (derivations, worked examples, a check of the student's notes), `research.md` links its topics to foundational and recent papers. Every lecture ends with reader questions and folded reference answers.
```

2. Replace the deploy comment line with `./deploy.sh   # copies SKILL.md + lecture-format.md + questions.md + slides.md + slides-format.md + fetch.py -> ~/.claude/skills/ppread/` and `Only those four files are deployable.` with `Only those six files are deployable.`

3. In「Architecture」, after the `questions.md` bullet, add:

```markdown
- **`slides.md`** — the workflow for `kind: slides`, loaded after Step 0 in place of SKILL.md's Steps 1–4. Separate so that a paper run never reads slide rules and a slide run never wades through paper rules.
- **`slides-format.md`** — the output contract for the three slide lectures, in Chinese for the same reason as `lecture-format.md`.
```

4. In「Non-obvious decisions」, append:

```markdown
- **A local PDF is `slides` when its first page displays landscape.** Orientation is the one signal every deck shares and almost no paper does. `pdfinfo`'s page size (with rotation) first, a raw `/MediaBox` scan without it, `route: needs-kind` when neither can read it (a MediaBox inside a compressed object stream). A lecture's recorded `kind` outranks the page size on re-runs, so a portrait deck adopted with `--kind slides` is never reclassified and moved again.
- **Slides never trust `/Title`.** Deck exports default it to "Slide 1" or "PowerPoint Presentation"; using it would mint a wrong folder name with nothing to flag it. `--course` and `--title` are both required, read off the cover by the agent.
- **Slides live under `<course-slug>/<title-slug>/`.** A course's chapters sit together. `same_paper` refuses a match across differing courses, because two courses sharing a chapter title is far more likely than two papers sharing a title. `--list` descends one level into a directory that holds only directories (except `assets/`) to find them.
- **The student's annotations are a separate layer, never merged.** Exported note PDFs carry typed notes, handwriting and whole inserted pages over the slides. Lectures quote them in their own callout and check them; presenting a note as slide text would put words in the lecturer's mouth. Inserted pages are also why every page reference carries both the printed slide number and the PDF page.
- **Research mode searches; it does not recall.** A deck cites almost nothing, so there is no citation graph to start from. `--search` uses Semantic Scholar's bulk endpoint, the only search that sorts by citation count; it ignores `limit` (returns up to 1000) so the cut is local, and abstracts are often null so `fieldsOfStudy` is returned for filtering. Verified 2026-10-01 against `"systolic array"`.
```

5. In「Testing」→ live runs, append to the verified-cases sentence: `; a 79-page landscape course deck with typed and handwritten notes (adopted into `vlsi-dsp/ch01-introduction/`); `--search '"systolic array"' --since 2023``.

- [ ] **Step 4: Verify**

Run: `grep -n "six files\|slides.md\|needs-kind\|bulk endpoint" CLAUDE.md`
Expected: matches for each pattern.

- [ ] **Step 5: Commit**

```bash
git add deploy.sh CLAUDE.md
git commit -F - <<'EOF'
chore(deploy): ship slides.md and slides-format.md; document slides decisions

- deploy.sh 部署 6 個檔案
- CLAUDE.md：架構、部署清單與簡報相關的非顯而易見決策

問題：skill 目前只支援閱讀 paper，想讓它也支援閱讀課程簡報（PDF），一樣分廣讀與深讀，並延伸到相關論文與研究進展

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

---

### Task 10: End-to-end acceptance on the sample deck

**Files:**
- No source changes expected. Lectures are written to a scratch directory, never into the repo.

**Interfaces:**
- Consumes: everything above, deployed to a scratch skills directory.

- [ ] **Step 1: Deploy to scratch and stage a throwaway copy**

```bash
S=$(mktemp -d) && CLAUDE_SKILLS_DIR="$S" ./deploy.sh
W=$(mktemp -d) && cp VLSI_Design_1_Introduction.pdf "$W/"
echo "skills=$S work=$W"
```

- [ ] **Step 2: Run the three modes by following the deployed files**

Act as the skill: read `$S/ppread/SKILL.md`, run its Step 0 with `python3 $S/ppread/fetch.py "$W/VLSI_Design_1_Introduction.pdf"` (substituting `$S/ppread/` wherever the files say `~/.claude/skills/ppread/`), resolve `needs-title` as `slides.md` says, then follow `slides.md` for broad, then deep, then research (no flag each time — the mode sequence should pick them in order). Present each Step 1 survey to the user and wait for confirmation, as the workflow requires.

- [ ] **Step 3: Check the results**

Run: `find "$W" -type f | sort && python3 fetch.py --list "$W"`
Expected: `$W/vlsi-dsp/ch01-introduction/` holds the PDF, `broad.md`, `deep.md`, `research.md` (no `.part.md` left), and `assets/pdf-p*.png` if `pdftoppm` exists; `--list` shows one row with slug `vlsi-dsp/ch01-introduction`, kind `slides`, all three modes `unread`.

Check by reading the files:
- every page reference is double (`投影片 N（PDF p.M）`), and pages after the inserted p.9 are offset by one
- `broad.md`'s term section covers the names on PDF p.21–24 (Wiener, Kalman, LMS/RLS, SVD, bitonic sort, DFT/FFT, DCT/MDCT, wavelet, Hadamard, Schur, Levinson–Durbin, look-ahead transform)
- the note on PDF p.8 (`floding`/`upfloding`) is quoted in a `[!note]` callout and corrected to folding/unfolding
- no note text appears inside a `> **投影片` quote block
- every paper in `research.md` appears in the `--search` or `--graph` output captured during Step 2 (keep those outputs in `$W/../research-log.json` while running)
- each lecture ends with its fixed questions verbatim (SB1–SB5, SD1–SD5, SR1–SR3)

- [ ] **Step 4: Fix or file what failed**

A failure in `fetch.py` → fix with a test in `tests/offline_checks.py`, commit with `fix(...)`. A failure in the workflow or format docs → edit the doc, commit with `docs(skill): ...`. Anything verified only partly, or not at all (for example how Obsidian renders `./assets/` relative embeds, or an old `papers.base` lacking a `kind` column), → `gh issue create` now, with: the problem, why it was not done here, the consequence of leaving it, what to do, and how to tell it is done, linking this plan and the relevant commit SHA.

- [ ] **Step 5: Report**

Tell the user: the scratch path of the three lectures (so they can read them), what passed, what was fixed, and the issue numbers filed. Do not copy lectures into the repo and do not deploy to the live `~/.claude/skills/ppread/` — deployment happens after the user approves the branch.

# Broad / Deep Reading Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ppread's single linear `lecture.md` with two independent lectures — `broad.md` (orientation + literature context grounded in the citation graph) and `deep.md` (critical paragraph-level reading) — each ending in reader questions with folded reference answers, plus a per-lecture read marker surfaced by `--list` and an Obsidian Bases view.

**Architecture:** Deterministic work goes into `fetch.py` (front-matter state scanning, Semantic Scholar citation graph and title verification, library listing, the `.base` file). Judgment goes into `SKILL.md` (mode choice, survey, writing, question design), with the output contract in `lecture-format.md` and question design rules in a new `questions.md`.

**Tech Stack:** Python 3.10+ standard library only; Semantic Scholar Graph API v1; Obsidian Markdown (callouts, properties, Bases).

**Spec:** `docs/superpowers/specs/2026-09-15-broad-deep-reading-design.md`

## Global Constraints

- `fetch.py` uses the Python standard library only; must run on Python 3.10 (the dev machine has 3.10.12).
- `fetch.py` writes exactly one JSON object to stdout per invocation; diagnostics go to stderr via `log()`. Usage errors exit 2; every route (including failures such as `graph-unavailable`) exits 0.
- Deployable files are exactly: `SKILL.md`, `lecture-format.md`, `questions.md`, `fetch.py`.
- Lecture file names: `broad.md`, `deep.md`; while being written: `broad.part.md`, `deep.part.md`. Legacy file: `lecture.md`.
- Front matter keys added: `mode` (`broad` | `deep`), `lecture_read` (`true` | `false`). Property name is exactly `lecture_read`.
- `docs` state values: `absent` | `partial` | `unread` | `read`; plus `legacy: bool`.
- Semantic Scholar limits: citations page size 1000, at most 3 pages, top 50 citations returned; `--verify` at most 25 titles; ≥1 s between S2 requests; optional env `PPREAD_S2_API_KEY` sent as `x-api-key`.
- Passage translation label is exactly `**中文翻譯**`; no `**譯**` / `**解**` labels anywhere.
- Code style: comments only where logic is non-obvious; match the existing docstring voice in `fetch.py`.
- Commits: Conventional Commits subject; body = technical bullets, blank line, `問題：…` line, blank line, then the attribution lines below. Stay on `feature/broad-deep-reading`; never merge, never open a PR.
- Offline checks live in `tests/offline_checks.py` (standard library, no network, no framework — run as a script). Live network checks are shell commands in this plan and are not committed, matching the repo's "exercise against real sources" convention.

**Deviations from the spec, decided while planning:**

- The spec's §13 lists only shell-driven tests. This plan adds a committed `tests/offline_checks.py` so the network-free logic (state scanning, conflicts, graph paging, listing) can be re-checked after every change without spending Semantic Scholar quota. It is still a plain script with no framework or dependency.
- The spec's §8.5 writes `papers.base` "when the library first gets a workdir". On the `needs-html`/`needs-pdf` network routes `fetch.py` creates no workdir (the agent does), so the plan writes `papers.base` on every network route except `unresolved` — the intent (the library has a paper in it) is the same.

Attribution block for every commit body:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
```

The `問題` line for every commit in this plan:

```
問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差
```

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `fetch.py` | Deterministic mechanics: lecture state, conflict detection, S2 graph/verify, listing, `.base` file | 1–5 |
| `tests/offline_checks.py` (new) | Network-free assertions on `fetch.py` functions; run `python3 tests/offline_checks.py` | 1–5 |
| `lecture-format.md` | Output contract for `broad.md` / `deep.md` | 6 |
| `questions.md` (new) | Question design guide and callout format | 7 |
| `deploy.sh` | Copies the four deployable files | 7 |
| `SKILL.md` | Orchestration: invocation, mode table, steps, discipline | 8 |
| `CLAUDE.md`, `README.md`, `VERSION` | Developer and user docs, version | 9 |

---

### Task 1: Lecture state and multi-file conflict detection

**Files:**
- Modify: `fetch.py` — replace `lecture_identity()` (currently lines 424–445) and `folder_conflict()` (lines 474–487); modify `adopt_local()` "others" check (lines 546–547) and its return dict (lines 558–564); modify `main()` result dict (line 717)
- Create: `tests/offline_checks.py`

**Interfaces:**
- Consumes: existing `same_paper(ident: dict, meta: dict) -> bool`, `RESOLVE: str`, `log(msg: str)`
- Produces:
  - `DOC_FILES: tuple[str, ...] = ("broad.md", "deep.md", "broad.part.md", "deep.part.md", "lecture.md")`
  - `front_matter(f: Path) -> dict | None` — `None` if file missing, `{}` if unreadable or no front matter, else `{key: value}` strings
  - `lecture_docs(workdir: Path) -> dict` — `{"broad": state, "deep": state, "legacy": bool}`
  - `folder_conflict(workdir: Path, meta: dict, slug: str) -> dict | None` — conflict dict with `occupant["file"]`
  - `docs` key present in every non-conflict result that has a `workdir`
  - `tests/offline_checks.py` with `write_doc(path: Path, fields: dict) -> None` helper and a `CHECKS` list

- [ ] **Step 1: Write the failing check**

Create `tests/offline_checks.py`:

```python
#!/usr/bin/env python3
"""Network-free checks for fetch.py. Standard library only; run from anywhere:

    python3 tests/offline_checks.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch  # noqa: E402

A = {"title": "Paper A", "arxiv": "1111.11111"}
A_META = {"title": "Paper A", "arxiv_id": "1111.11111", "doi": ""}
B_META = {"title": "Paper B", "arxiv_id": "2222.22222", "doi": ""}


def write_doc(path: Path, fields: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{k}: {v}\n" for k, v in fields.items())
    path.write_text(f"---\n{body}---\n\n# body\n", "utf-8")


def check_lecture_docs_and_conflicts() -> None:
    d = Path(tempfile.mkdtemp())
    assert fetch.lecture_docs(d) == {"legacy": False, "broad": "absent", "deep": "absent"}

    write_doc(d / "broad.md", {**A, "mode": "broad", "lecture_read": "true"})
    write_doc(d / "deep.part.md", {**A, "mode": "deep", "lecture_read": "false"})
    assert fetch.lecture_docs(d) == {"legacy": False, "broad": "read", "deep": "partial"}
    assert fetch.folder_conflict(d, A_META, "s") is None
    c = fetch.folder_conflict(d, B_META, "s")
    assert c["route"] == "conflict" and c["occupant"]["file"] == "broad.md", c

    # A partial file wins over a finished one of the same mode.
    write_doc(d / "deep.md", {**A, "mode": "deep", "lecture_read": "true"})
    assert fetch.lecture_docs(d)["deep"] == "partial"

    e = Path(tempfile.mkdtemp())
    write_doc(e / "broad.md", {**A, "mode": "broad", "lecture_read": "false"})
    write_doc(e / "deep.md", {"title": "Paper B", "arxiv": "2222.22222",
                              "mode": "deep", "lecture_read": "false"})
    assert fetch.lecture_docs(e) == {"legacy": False, "broad": "unread", "deep": "unread"}
    c = fetch.folder_conflict(e, A_META, "s")
    assert c and c["occupant"]["file"] == "deep.md", c

    f = Path(tempfile.mkdtemp())
    write_doc(f / "lecture.md", A)
    assert fetch.lecture_docs(f) == {"legacy": True, "broad": "absent", "deep": "absent"}
    assert fetch.folder_conflict(f, A_META, "s") is None
    assert fetch.folder_conflict(f, B_META, "s")["occupant"]["file"] == "lecture.md"

    assert fetch.front_matter(f / "missing.md") is None
    (f / "plain.md").write_text("no front matter\n", "utf-8")
    assert fetch.front_matter(f / "plain.md") == {}
    assert fetch.front_matter(f / "lecture.md") == {"title": "Paper A", "arxiv": "1111.11111"}


CHECKS = [
    check_lecture_docs_and_conflicts,
]

if __name__ == "__main__":
    for check in CHECKS:
        check()
        print(f"ok  {check.__name__}")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 tests/offline_checks.py`
Expected: FAIL with `AttributeError: module 'fetch' has no attribute 'lecture_docs'`

- [ ] **Step 3: Implement**

In `fetch.py`, replace the whole `lecture_identity()` function with:

```python
DOC_FILES = ("broad.md", "deep.md", "broad.part.md", "deep.part.md", "lecture.md")


def front_matter(f: Path) -> dict | None:
    """The 'key: value' lines of a Markdown file's YAML front matter. The keys
    ppread reads are fixed by lecture-format.md and never nested, so a plain scan
    is exact and needs no YAML parser. None means no such file; an empty dict
    means one exists but says nothing."""
    if not f.is_file():
        return None
    try:
        text = f.read_text("utf-8", errors="replace")
    except OSError as e:
        log(f"  {f.name}: {e}")
        return {}
    if not text.startswith("---"):
        return {}
    body = text.partition("\n")[2].partition("\n---")[0]
    fields = {}
    for line in body.splitlines():
        k, sep, v = line.partition(":")
        if sep:
            fields[k.strip()] = v.strip().strip("\"'")
    return fields


def lecture_docs(workdir: Path) -> dict:
    """Which lectures a folder holds and how far each has got. A lecture is written
    as <mode>.part.md and renamed only once its last section is done, so a .part
    file means unfinished even when a finished file of that mode also exists — a
    regeneration in progress is not done."""
    docs = {"legacy": (workdir / "lecture.md").is_file()}
    for mode in ("broad", "deep"):
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

Replace the whole `folder_conflict()` function with:

```python
def folder_conflict(workdir: Path, meta: dict, slug: str) -> dict | None:
    """A conflict result, or None when every lecture in the folder is this paper's.
    Every file is checked, not just the first: a broad.md that matches says nothing
    about a deep.md written for another paper whose title landed on the same slug."""
    for name in DOC_FILES:
        ident = front_matter(workdir / name)
        if ident is None or same_paper(ident, meta):
            continue
        held = ident.get("title") or ident.get("arxiv") or ident.get("doi")
        return {"route": "conflict", "slug": slug, "workdir": str(workdir), "meta": meta,
                "occupant": {"file": name,
                             **{k: ident.get(k, "") for k in ("title", "doi", "arxiv")}},
                "reason": f"{workdir / name} is a lecture for "
                          + (f"a different paper ({held})" if held
                             else "a paper it does not identify")
                          + "; refusing to put a second paper in one folder",
                "resolve": RESOLVE}
    return None
```

Update the module comment block above `DOC_FILES` (the `# --- folder identity ---` block) — replace its last sentence `Left unchecked the damage is silent — lecture.md ends up describing a different paper than the source lying next to it, and nothing in either file says so.` with:

```python
# Left unchecked the damage is silent — a lecture ends up describing a different
# paper than the source lying next to it, and nothing in either file says so.
```

In `adopt_local()`, change the "others" comprehension:

```python
        others = sorted(p.name for p in workdir.glob("*")
                        if p.is_file() and p.name not in DOC_FILES)
```

and its reason string from `"lecture.md saying which paper that is"` to `"lecture saying which paper that is"`.

In `adopt_local()`'s final return dict, add `"docs": lecture_docs(workdir),` after `"meta": meta,`:

```python
    return {"slug": slug, "workdir": str(workdir), "meta": meta,
            "docs": lecture_docs(workdir),
            "route": "needs-pdf" if ext == ".pdf" else "local",
```

In `main()`, change

```python
    result = {"slug": slug, "workdir": str(workdir), "meta": meta}
```

to

```python
    result = {"slug": slug, "workdir": str(workdir), "meta": meta,
              "docs": lecture_docs(workdir)}
```

- [ ] **Step 4: Run checks to verify they pass**

Run: `python3 tests/offline_checks.py && grep -n "lecture_identity" fetch.py`
Expected: `ok  check_lecture_docs_and_conflicts`, and grep prints nothing.

- [ ] **Step 5: Live regression (spec §13 case 1 and 11)**

Run (network; writes only to a throwaway dir):

```bash
T=$(mktemp -d) && python3 fetch.py 1706.03762 --out "$T" | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['route'], r['docs'])"
```

Expected: `latex {'legacy': False, 'broad': 'absent', 'deep': 'absent'}`

```bash
T=$(mktemp -d) && printf '\\documentclass{article}\n' > "$T/local.tex" \
  && python3 fetch.py "$T/local.tex" --title "Local Regression Paper" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['route'], r['slug'], r['docs'])" \
  && ls "$T/local-regression-paper"
```

Expected: `local local-regression-paper {'legacy': False, 'broad': 'absent', 'deep': 'absent'}`, then `local.tex` listed inside the new folder (the file was moved beside itself into `<slug>/`, as in v0.1.0). A `.tex` with `--title` exercises `adopt_local()` without depending on `pdfinfo`.

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): track broad/deep lecture state and check every lecture for conflicts

- lecture_identity() 泛化為 front_matter()，新增 lecture_docs() 回報 absent/partial/unread/read
- folder_conflict() 逐一檢查 broad、deep、.part 與舊版 lecture.md，任一不符即 conflict
- 所有帶 workdir 的結果加上 docs 欄位
- 新增 tests/offline_checks.py（標準函式庫、無網路）

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 2: Semantic Scholar request helper and `--verify`

**Files:**
- Modify: `fetch.py` — `get()` (lines 45–72), `s2_lookup()` (lines 196–225), `main()` argparse and dispatch
- Modify: `tests/offline_checks.py`

**Interfaces:**
- Consumes: `get()`, `_norm_title(v: str) -> str`, `identify()`
- Produces:
  - `get(url, accept=None, retries=3, timeout=TIMEOUT, headers: dict | None = None) -> bytes`
  - `S2: str = "https://api.semanticscholar.org/graph/v1"`, module globals `_S2_KEY: str`, `_s2_last: float`
  - `s2_get(path: str) -> dict` — path starts with `/`; raises `urllib.error.HTTPError` and others like `get()`
  - `s2_ids(rec: dict) -> dict` — `{"title", "year", "arxiv", "doi"}`
  - `title_match(query: str) -> dict | None` — raw S2 record (includes `paperId`), `None` on 404 or no hit; raises on other errors
  - `match_status(query: str, rec: dict | None) -> dict`
  - `verify_title(query: str) -> dict` — `status` ∈ `exact` | `mismatch` | `not-found` | `error`
  - `VERIFY_MAX: int = 25`; CLI `--verify TITLE [TITLE ...]`

- [ ] **Step 1: Write the failing checks**

Add to `tests/offline_checks.py` above `CHECKS`:

```python
def check_verify_matching() -> None:
    rec = {"paperId": "p", "title": "Neural Machine Translation by Jointly Learning to Align and Translate",
           "year": 2014, "externalIds": {"ArXiv": "1409.0473"}}
    r = fetch.match_status("neural machine translation by jointly learning to align and translate", rec)
    assert r == {"query": "neural machine translation by jointly learning to align and translate",
                 "status": "exact", "title": rec["title"], "year": 2014,
                 "arxiv": "1409.0473", "doi": ""}, r
    r = fetch.match_status("Attention Mechanisms Are All You Need for Vision", rec)
    assert r["status"] == "mismatch" and r["candidate"] == rec["title"], r
    assert fetch.match_status("x", None) == {"query": "x", "status": "not-found"}


def check_s2_key_header() -> None:
    seen = {}
    orig_get, orig_key = fetch.get, fetch._S2_KEY

    def fake_get(url, **kw):
        seen.clear()
        seen.update(url=url, **kw)
        return b"{}"

    fetch.get = fake_get
    try:
        fetch._S2_KEY = "k"
        fetch.s2_get("/paper/x")
        assert seen["url"] == "https://api.semanticscholar.org/graph/v1/paper/x", seen
        assert seen["headers"] == {"x-api-key": "k"}, seen
        fetch._S2_KEY = ""
        fetch.s2_get("/paper/x")
        assert seen["headers"] is None, seen
    finally:
        fetch.get, fetch._S2_KEY = orig_get, orig_key
```

and extend the list:

```python
CHECKS = [
    check_lecture_docs_and_conflicts,
    check_verify_matching,
    check_s2_key_header,
]
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 tests/offline_checks.py`
Expected: first check `ok`, then FAIL with `AttributeError: module 'fetch' has no attribute 'match_status'`

- [ ] **Step 3: Implement**

Replace `get()`'s signature and request line:

```python
def get(url: str, accept: str | None = None, retries: int = 3,
        timeout: int = TIMEOUT, headers: dict | None = None) -> bytes:
```

```python
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
```

(the rest of `get()` is unchanged).

Directly above `def s2_lookup`, add:

```python
S2 = "https://api.semanticscholar.org/graph/v1"
# Optional: a key gets its own quota instead of the shared keyless pool, which
# answered 429 by the third quick request in testing. Everything works without it.
_S2_KEY = os.environ.get("PPREAD_S2_API_KEY", "").strip()
_s2_last = 0.0


def s2_get(path: str) -> dict:
    """One Semantic Scholar Graph API call, spaced at least a second after the
    previous one — cheaper than the backoff a 429 would cost."""
    global _s2_last
    wait = _s2_last + 1.0 - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    try:
        return json.loads(get(S2 + path, headers={"x-api-key": _S2_KEY} if _S2_KEY else None))
    finally:
        _s2_last = time.monotonic()


def s2_ids(rec: dict) -> dict:
    ext = rec.get("externalIds") or {}
    return {"title": rec.get("title") or "", "year": rec.get("year"),
            "arxiv": ext.get("ArXiv") or "", "doi": ext.get("DOI") or ""}
```

Replace the body of `s2_lookup()` from `fields = ...` through the `except Exception` block with:

```python
    fields = "title,abstract,year,authors,externalIds,openAccessPdf,venue"
    if ident.startswith("search:"):
        path = f"/paper/search?query={urllib.parse.quote(value)}&limit=1&fields={fields}"
    else:
        path = f"/paper/{urllib.parse.quote(ident, safe=':/')}?fields={fields}"

    try:
        data = s2_get(path)
    except urllib.error.HTTPError as e:
        log(f"  semantic scholar: HTTP {e.code}")
        return None
    except Exception as e:  # network, JSON, anything
        log(f"  semantic scholar: {e}")
        return None
```

(the trailing `if "data" in data:` block is unchanged).

Add a new section directly after `arxiv_meta()` (the end of the metadata sources section, before `# --- arXiv e-print ---`):

```python
# --- literature grounding -------------------------------------------------
#
# A broad lecture names papers outside the one being read. A list of such papers
# produced from memory gets an author, a year or a title wrong, or names a paper
# that does not exist, and reads exactly as convincingly as a correct one. So every
# outside paper must come from the citation graph or pass an exact title match.

VERIFY_MAX = 25


def title_match(query: str) -> dict | None:
    """Semantic Scholar's best title match, or None when it has none. Other
    failures raise, so callers can tell 'no such paper' from 'could not ask'."""
    path = f"/paper/search/match?query={urllib.parse.quote(query)}&fields=title,year,externalIds"
    try:
        data = s2_get(path)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    hits = data.get("data") or []
    return hits[0] if hits else None


def match_status(query: str, rec: dict | None) -> dict:
    """search/match always returns its best candidate, however poor, so a high
    score proves nothing; only an exact normalised title does. A near miss is
    reported with its candidate but never counts as verified."""
    if not rec:
        return {"query": query, "status": "not-found"}
    if _norm_title(rec.get("title", "")) == _norm_title(query):
        return {"query": query, "status": "exact", **s2_ids(rec)}
    return {"query": query, "status": "mismatch", "candidate": rec.get("title") or ""}


def verify_title(query: str) -> dict:
    try:
        return match_status(query, title_match(query))
    except urllib.error.HTTPError as e:
        return {"query": query, "status": "error", "reason": f"HTTP {e.code}"}
    except Exception as e:
        return {"query": query, "status": "error", "reason": str(e)}
```

`_norm_title` is defined later in the file (folder identity section); that is fine because it is only looked up at call time.

In `main()`, add after the `--keep-comments` argument:

```python
    ap.add_argument("--verify", nargs="+", metavar="TITLE",
                    help=f"check up to {VERIFY_MAX} paper titles against Semantic "
                         "Scholar; only an exact normalised title match counts")
```

and add right after `args = ap.parse_args()`:

```python
    if args.verify:
        if len(args.verify) > VERIFY_MAX:
            log(f"--verify takes at most {VERIFY_MAX} titles per call")
            return 2
        print(json.dumps({"route": "verify",
                          "results": [verify_title(t) for t in args.verify]},
                         ensure_ascii=False, indent=2))
        return 0
```

- [ ] **Step 4: Run offline checks**

Run: `python3 tests/offline_checks.py`
Expected: three `ok` lines.

- [ ] **Step 5: Live checks (spec §13 cases 5 and 6)**

```bash
python3 fetch.py --verify $(for i in $(seq 26); do printf 't%s ' "$i"; done); echo "exit=$?"
```

Expected: stderr `--verify takes at most 25 titles per call`, `exit=2`, no network traffic.

```bash
python3 fetch.py --verify \
  "Neural Machine Translation by Jointly Learning to Align and Translate" \
  "Attention Mechanisms Are All You Need for Vision Transformers in Low Resource Settings" \
  "neural machine translation by JOINTLY learning to align and translate" \
  | python3 -c "import json,sys; [print(r['status'], r.get('arxiv', r.get('candidate', r.get('reason','')))) for r in json.load(sys.stdin)['results']]"
```

Expected: line 1 `exact 1409.0473`; line 2 `not-found` or `mismatch <some other title>`; line 3 `exact 1409.0473`. If any line is `error HTTP 429`, wait 60 s and rerun once; persistent 429 means the shared keyless pool is saturated — rerun with `PPREAD_S2_API_KEY` set if one is available, otherwise record the result and continue.

Also confirm the S2-dependent main route still works:

```bash
T=$(mktemp -d) && python3 fetch.py 10.1109/CVPR.2016.90 --out "$T" | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['route'], r['meta']['arxiv_id'])"
```

Expected: `latex 1512.03385`

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): verify paper titles against Semantic Scholar

- 新增 s2_get()：請求間隔至少 1 秒，選用 PPREAD_S2_API_KEY 作為 x-api-key
- get() 接受額外 headers；s2_lookup() 改走 s2_get()
- 新增 --verify：search/match 結果以正規化標題完全相等才算 exact，mismatch 附 candidate 但不算查證通過
- 單次上限 25 個標題，超過 exit 2

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 3: `--graph`

**Files:**
- Modify: `fetch.py` — literature grounding section (added in Task 2), `main()`
- Modify: `tests/offline_checks.py`

**Interfaces:**
- Consumes: `s2_get()`, `s2_ids()`, `title_match()`, `_norm_title()`, `identify()`
- Produces:
  - `GRAPH_FIELDS: str`, `GRAPH_PAGE = 1000`, `GRAPH_PAGES = 3`, `GRAPH_TOP_CITATIONS = 50`
  - `graph_node(edge: dict, side: str) -> dict` — `side` is `"citedPaper"` or `"citingPaper"`; returns `{"title","year","arxiv","doi","citations","influential","intents"}`
  - `rank(nodes: list[dict]) -> list[dict]` — influential first, then citations descending
  - `graph(source: str) -> dict` — route `graph` or `graph-unavailable`
  - CLI `--graph ID_OR_TITLE`

- [ ] **Step 1: Write the failing check**

Add to `tests/offline_checks.py`:

```python
def _edge(side: str, title: str, cites: int, influential: bool) -> dict:
    return {side: {"title": title, "year": 2020, "externalIds": {}, "citationCount": cites},
            "isInfluential": influential, "intents": ["methodology"] if influential else []}


def _run_graph(citation_pages: dict, total: int, fail_at: int | None = None) -> dict:
    def fake(path: str) -> dict:
        if "/references" in path:
            return {"data": [_edge("citedPaper", "r-low", 1, False),
                             _edge("citedPaper", "r-infl", 0, True),
                             _edge("citedPaper", "r-high", 50, False)]}
        if "/citations" in path:
            off = int(re.search(r"offset=(\d+)", path).group(1))
            if off == fail_at:
                raise OSError("boom")
            data, more = citation_pages[off]
            return {"data": data, **({"next": off + len(data)} if more else {})}
        return {"title": "P", "year": 2020, "externalIds": {"ArXiv": "2001.00001"},
                "citationCount": total}

    orig = fetch.s2_get
    fetch.s2_get = fake
    try:
        return fetch.graph("2001.00001")
    finally:
        fetch.s2_get = orig


def check_graph() -> None:
    full = [_edge("citingPaper", f"c{i}", i, i == 5) for i in range(1000)]
    g = _run_graph({0: (full, True), 1000: ([_edge("citingPaper", "late", 99999, False)], False)},
                   total=1001)
    assert g["route"] == "graph" and g["paper"]["arxiv"] == "2001.00001", g
    assert [r["title"] for r in g["references"]] == ["r-infl", "r-high", "r-low"]
    assert g["references"][0]["intents"] == ["methodology"]
    assert [c["title"] for c in g["citations"][:2]] == ["c5", "late"]
    assert len(g["citations"]) == 50
    assert g["citations_scanned"] == 1001 and g["citations_complete"] is True
    assert g["citation_count"] == 1001 and "citations_error" not in g
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", g["fetched_on"])

    g = _run_graph({0: (full, True), 1000: (full, True), 2000: (full, True)}, total=170000)
    assert g["citations_scanned"] == 3000 and g["citations_complete"] is False

    g = _run_graph({0: (full, True)}, total=5000, fail_at=1000)
    assert g["citations_scanned"] == 1000 and g["citations_complete"] is False
    assert g["citations_error"] == "boom"

    assert fetch.graph(__file__)["route"] == "graph-unavailable"
```

and append `check_graph,` to `CHECKS`.

- [ ] **Step 2: Run to verify failure**

Run: `python3 tests/offline_checks.py`
Expected: FAIL with `AttributeError: module 'fetch' has no attribute 'graph'`

- [ ] **Step 3: Implement**

Append to the literature grounding section in `fetch.py`:

```python
GRAPH_FIELDS = "title,year,externalIds,citationCount,isInfluential,intents"
GRAPH_PAGE = 1000
# Citations come newest-first and the API cannot sort them by impact; offset+limit
# is capped below 10000. Past three pages a keyless run spends minutes in backoff
# only to collect more recent, rarely-cited papers, so three is where it stops.
GRAPH_PAGES = 3
GRAPH_TOP_CITATIONS = 50


def graph_node(edge: dict, side: str) -> dict:
    p = edge.get(side) or {}
    return {**s2_ids(p), "citations": p.get("citationCount") or 0,
            "influential": bool(edge.get("isInfluential")),
            "intents": edge.get("intents") or []}


def rank(nodes: list[dict]) -> list[dict]:
    return sorted(nodes, key=lambda n: (not n["influential"], -n["citations"]))


def graph(source: str) -> dict:
    """The paper's neighbourhood in the citation graph, ranked locally.
    citations_complete is true only when the citation list was read to its end."""
    kind, value = identify(source)
    if kind == "file":
        return {"route": "graph-unavailable",
                "reason": "pass the paper's arXiv ID, DOI or title, not a file path"}
    try:
        if kind == "query":
            rec = title_match(value)
            if not rec or _norm_title(rec.get("title", "")) != _norm_title(value):
                return {"route": "graph-unavailable", "reason": "not found"}
            pid = rec["paperId"]
        else:
            prefix = {"arxiv": "ARXIV:", "doi": "DOI:", "url": "URL:"}[kind]
            pid = urllib.parse.quote(prefix + value, safe=":/")
        paper = s2_get(f"/paper/{pid}?fields=title,year,externalIds,citationCount,referenceCount")
        refs = s2_get(f"/paper/{pid}/references?limit={GRAPH_PAGE}&fields={GRAPH_FIELDS}")
    except urllib.error.HTTPError as e:
        return {"route": "graph-unavailable",
                "reason": "not found" if e.code == 404 else f"HTTP {e.code}"}
    except Exception as e:
        return {"route": "graph-unavailable", "reason": str(e)}

    cites: list[dict] = []
    error, exhausted = "", False
    for page in range(GRAPH_PAGES):
        try:
            data = s2_get(f"/paper/{pid}/citations?limit={GRAPH_PAGE}"
                          f"&offset={page * GRAPH_PAGE}&fields={GRAPH_FIELDS}")
        except Exception as e:
            error = str(e)
            break
        cites += [graph_node(x, "citingPaper") for x in data.get("data") or []]
        if data.get("next") is None:
            exhausted = True
            break

    result = {"route": "graph", "paper": s2_ids(paper),
              "references": rank([graph_node(x, "citedPaper") for x in refs.get("data") or []]),
              "citations": rank(cites)[:GRAPH_TOP_CITATIONS],
              "citation_count": paper.get("citationCount") or 0,
              "citations_scanned": len(cites),
              "citations_complete": exhausted and not error,
              "fetched_on": time.strftime("%Y-%m-%d")}
    if error:
        result["citations_error"] = error
    return result
```

In `main()`, add after the `--verify` argument:

```python
    ap.add_argument("--graph", metavar="ID_OR_TITLE",
                    help="references and citations of a paper from Semantic Scholar, "
                         "ranked by influence then citation count")
```

and after the `--verify` dispatch block:

```python
    if args.graph:
        print(json.dumps(graph(args.graph), ensure_ascii=False, indent=2))
        return 0
```

- [ ] **Step 4: Run offline checks**

Run: `python3 tests/offline_checks.py`
Expected: four `ok` lines.

- [ ] **Step 5: Live checks (spec §13 cases 2–4)**

Run each with a pause between them to respect the shared rate limit:

```bash
summ='import json,sys; g=json.load(sys.stdin); print(g["route"], g.get("paper",{}).get("arxiv"), g.get("citation_count"), g.get("citations_scanned"), g.get("citations_complete"), sum(r["influential"] for r in g.get("references",[])), g.get("reason",""))'
python3 fetch.py --graph 1706.03762 | python3 -c "$summ"; sleep 20
python3 fetch.py --graph 1905.02175 | python3 -c "$summ"; sleep 20
python3 fetch.py --graph 10.1109/CVPR.2016.90 | python3 -c "$summ"
```

Expected:
- `graph 1706.03762 <≈170000> 3000 False <≥1>`
- `graph 1905.02175 <≈2173> <≈2173> True <n>`
- `graph 1512.03385 <large> 3000 False <n>`

A `graph-unavailable HTTP 429` line: wait 60 s, rerun that line once; if it persists, record it (the code path is covered offline) and continue.

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): expose a paper's citation graph for literature grounding

- 新增 --graph：references 一頁全取，citations 最多 3 頁（每頁 1000），本機依 isInfluential 再依被引數排序
- citations 回傳前 50 筆，附 citation_count、citations_scanned、citations_complete、fetched_on
- 解析不到或網路失敗回 graph-unavailable；citations 中途失敗保留已取得部分並加 citations_error

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 4: `--list`

**Files:**
- Modify: `fetch.py` — add `list_library()` after `adopt_local()`; extract `needs_output_config()`; `main()`
- Modify: `tests/offline_checks.py`

**Interfaces:**
- Consumes: `DOC_FILES`, `front_matter()`, `lecture_docs()`, `resolve_out()`, `CONFIG_PATH`
- Produces:
  - `list_library(root: Path) -> dict` — `{"route": "list", "library": str, "papers": [{"slug","title","year","tier","broad","deep","legacy"}]}`
  - `needs_output_config() -> dict`
  - CLI `--list [DIR]`

- [ ] **Step 1: Write the failing check**

Add to `tests/offline_checks.py`:

```python
def check_list_library() -> None:
    lib = Path(tempfile.mkdtemp())
    write_doc(lib / "a-read" / "broad.md",
              {**A, "year": "2017", "tier": "1", "mode": "broad", "lecture_read": "true"})
    write_doc(lib / "a-read" / "deep.md",
              {**A, "year": "2017", "tier": "1", "mode": "deep", "lecture_read": "false"})
    write_doc(lib / "b-legacy" / "lecture.md", {"title": "Legacy", "year": "2016", "tier": "6"})
    (lib / "c-source-only").mkdir()
    (lib / "c-source-only" / "paper.pdf").write_bytes(b"%PDF")
    write_doc(lib / "d-partial" / "broad.part.md", {"title": "Partial", "mode": "broad"})
    (lib / "assets" / "a-read").mkdir(parents=True)
    (lib / ".obsidian").mkdir()
    (lib / ".obsidian" / "app.json").write_text("{}", "utf-8")
    (lib / "papers.base").write_text("", "utf-8")

    r = fetch.list_library(lib)
    assert r["route"] == "list" and r["library"] == str(lib)
    assert r["papers"] == [
        {"slug": "a-read", "title": "Paper A", "year": "2017", "tier": "1",
         "broad": "read", "deep": "unread", "legacy": False},
        {"slug": "b-legacy", "title": "Legacy", "year": "2016", "tier": "6",
         "broad": "absent", "deep": "absent", "legacy": True},
        {"slug": "c-source-only", "title": "", "year": "", "tier": "",
         "broad": "absent", "deep": "absent", "legacy": False},
        {"slug": "d-partial", "title": "Partial", "year": "", "tier": "",
         "broad": "partial", "deep": "absent", "legacy": False},
    ], r["papers"]

    assert fetch.list_library(lib / "nope") == {"route": "list", "library": str(lib / "nope"),
                                                 "papers": []}
```

and append `check_list_library,` to `CHECKS`.

- [ ] **Step 2: Run to verify failure**

Run: `python3 tests/offline_checks.py`
Expected: FAIL with `AttributeError: module 'fetch' has no attribute 'list_library'`

- [ ] **Step 3: Implement**

Add after `adopt_local()`:

```python
def list_library(root: Path) -> dict:
    """Every paper folder under root with the state of its lectures. A paper folder
    is a non-hidden directory holding at least one file directly: that admits a
    folder with only a source in it and skips containers such as assets/, whose
    contents are all subdirectories."""
    papers = []
    dirs = sorted(p for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith(".")) if root.is_dir() else []
    for d in dirs:
        if not any(p.is_file() for p in d.iterdir()):
            continue
        fields = next((fm for fm in (front_matter(d / n) for n in DOC_FILES) if fm), {})
        docs = lecture_docs(d)
        papers.append({"slug": d.name, "title": fields.get("title", ""),
                       "year": fields.get("year", ""), "tier": fields.get("tier", ""),
                       "broad": docs["broad"], "deep": docs["deep"],
                       "legacy": docs["legacy"]})
    return {"route": "list", "library": str(root), "papers": papers}
```

Add near `resolve_out()` (output location config section):

```python
def needs_output_config() -> dict:
    return {
        "route": "needs-output-config",
        "cwd": str(Path.cwd()),
        "suggested_cwd_mode": str(Path.cwd() / "papers"),
        "config_path": str(CONFIG_PATH),
        "reason": "no output location has been chosen yet; ask the user, then "
                  "re-run with --set-output 'fixed:/abs/path' or 'cwd:papers'",
    }
```

In `main()`, replace the inline `needs-output-config` dict:

```python
    out_root, _cfg = resolve_out(args.out)
    if out_root is None:
        print(json.dumps(needs_output_config(), ensure_ascii=False, indent=2))
        return 0
```

Add the argument after `--graph`:

```python
    ap.add_argument("--list", nargs="?", const="", metavar="DIR",
                    help="list paper folders and the state of their lectures; "
                         "defaults to the configured library")
```

and the dispatch after the `--graph` dispatch:

```python
    if args.list is not None:
        root = Path(args.list).expanduser() if args.list else resolve_out(None)[0]
        out = needs_output_config() if root is None else list_library(root)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
```

- [ ] **Step 4: Run offline checks**

Run: `python3 tests/offline_checks.py`
Expected: five `ok` lines.

- [ ] **Step 5: CLI smoke check (spec §13 case 7)**

```bash
L=$(mktemp -d) && mkdir -p "$L/x" && printf -- '---\ntitle: X\nmode: deep\nlecture_read: true\n---\n' > "$L/x/deep.md" && python3 fetch.py --list "$L"
XDG_CONFIG_HOME=$(mktemp -d) python3 fetch.py --list | python3 -c "import json,sys; print(json.load(sys.stdin)['route'])"
```

Expected: first command prints a `list` JSON whose single paper has `"deep": "read"`; second prints `needs-output-config` (an empty `XDG_CONFIG_HOME` means no remembered library).

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): list paper folders with their lecture state

- 新增 --list [DIR]：掃描一層子資料夾，回報 title、year、tier 與 broad/deep/legacy 狀態
- 只把「直接含有檔案」的非隱藏資料夾視為論文資料夾，略過 assets/ 這類容器
- 抽出 needs_output_config()，未設定 library 時 --list 與主流程共用

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 5: `papers.base`

**Files:**
- Modify: `fetch.py` — add `PAPERS_BASE` and `ensure_base()` in the output section; call from `main()`
- Modify: `tests/offline_checks.py`

**Interfaces:**
- Consumes: `log()`
- Produces: `PAPERS_BASE: str`, `ensure_base(library: Path) -> None`

- [ ] **Step 1: Write the failing check**

Add to `tests/offline_checks.py`:

```python
def check_papers_base() -> None:
    lib = Path(tempfile.mkdtemp()) / "papers"
    fetch.ensure_base(lib)
    f = lib / "papers.base"
    text = f.read_text("utf-8")
    assert text == fetch.PAPERS_BASE
    for needle in ("'type == \"reading\"'", "'generated == \"claude\"'",
                   "'lecture_read != true'", "property: note.mode"):
        assert needle in text, needle
    f.write_text("custom\n", "utf-8")
    fetch.ensure_base(lib)
    assert f.read_text("utf-8") == "custom\n"
```

and append `check_papers_base,` to `CHECKS`.

- [ ] **Step 2: Run to verify failure**

Run: `python3 tests/offline_checks.py`
Expected: FAIL with `AttributeError: module 'fetch' has no attribute 'ensure_base'`

- [ ] **Step 3: Implement**

Add in the `# --- output ---` section, before `slugify()`:

```python
# Filtered by properties rather than folder, so lectures built beside local files
# elsewhere in the vault show up too, and a reader's own `type: reading` notes do not.
PAPERS_BASE = """\
filters:
  and:
    - 'type == "reading"'
    - 'generated == "claude"'
views:
  - type: table
    name: 未讀講義
    filters:
      and:
        - 'lecture_read != true'
    order:
      - title
      - mode
      - year
      - lecture_read
  - type: table
    name: 全部講義
    order:
      - title
      - mode
      - year
      - lecture_read
    groupBy:
      property: note.mode
      direction: ASC
"""


def ensure_base(library: Path) -> None:
    """Place an Obsidian Bases view at the library root, once. Never overwritten:
    the reader may have customised its columns and filters since."""
    f = library / "papers.base"
    if f.exists():
        return
    try:
        library.mkdir(parents=True, exist_ok=True)
        f.write_text(PAPERS_BASE, "utf-8")
        log(f"  wrote {f}")
    except OSError as e:
        log(f"  papers.base: {e}")
```

In `main()`, immediately before the final `print(json.dumps(result, ...))` of the network route, add:

```python
    if result["route"] != "unresolved":
        ensure_base(out_root)
```

- [ ] **Step 4: Run offline checks**

Run: `python3 tests/offline_checks.py`
Expected: six `ok` lines.

- [ ] **Step 5: Live check (spec §13 case 10)**

```bash
T=$(mktemp -d) && python3 fetch.py 1706.03762 --out "$T" >/dev/null && ls "$T" && echo custom > "$T/papers.base" && python3 fetch.py 1706.03762 --out "$T" >/dev/null && cat "$T/papers.base"
```

Expected: `ls` shows `attention-is-all-you-need  papers.base`; final `cat` prints `custom`.

- [ ] **Step 6: Commit**

```bash
git add fetch.py tests/offline_checks.py
git commit -F - <<'EOF'
feat(fetch): drop an Obsidian Bases view of lectures into the library

- 新增 ensure_base()：library 根目錄沒有 papers.base 時寫入一份，已存在永不覆寫
- 視圖以 type 與 generated 屬性篩選，含「未讀講義」與依 mode 分組的「全部講義」
- 網路路線除 unresolved 外皆確保 papers.base 存在

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 6: Rewrite `lecture-format.md`

**Files:**
- Modify (full rewrite): `lecture-format.md`

**Interfaces:**
- Consumes: spec §4, §5, §6
- Produces: the output contract `SKILL.md` (Task 8) tells the agent to load in Step 3. Section names referenced by `SKILL.md`: 「共通規則」「廣讀文件」「精讀文件」.

- [ ] **Step 1: Write the file**

Replace the entire contents of `lecture-format.md` with:

````markdown
# 講義輸出格式

逐字遵守。這份檔案決定讀者實際讀到的東西長什麼樣。一篇論文最多兩份講義：
`broad.md`（廣讀）與 `deep.md`（精讀），格式各自在下方定義；兩者共用「共通規則」。

問題區塊的出題與格式另見 `questions.md`。

---

# 共通規則

## 檔頭

front matter 是這份講義的 metadata 來源——不另寫 meta.json。欄位全部來自
`fetch.py` 輸出的 `meta`，缺的留空不要刪。

```markdown
---
type: reading
mode: broad
lecture_read: false
generated: claude
title: Attention Is All You Need
authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin]
year: 2017
venue:
doi:
arxiv: 1706.03762
url: https://arxiv.org/abs/1706.03762
tier: 1
created: 2026-09-15
---
```

- `mode` 為 `broad` 或 `deep`，與檔名一致。
- `lecture_read` 一律寫 `false`。讀者讀完後自己勾選；Obsidian 會把它顯示成核取方塊。
  重新產生講義時也重設為 `false`——內容換了，原本的「讀完」指的是舊內容。
- `generated: claude` 不可省略。它明示這是機器產物、可重生，與讀者自己寫的卡片不同。
- `tier` 不可省略：tier 1 代表公式與引用取自 LaTeX 原始碼、精確；tier 5–6 代表是從
  PDF 還原的，可能有誤。讀者有權知道自己在讀哪一種。
- 同一篇論文的兩份講義，front matter 除了 `mode`、`lecture_read`、`created` 以外必須一致。

**講義中不出現「第一層」「第二層」之類的層級字樣。** 章節骨架本身就是閱讀順序。

## 段落單元

```markdown
### 3.2.1　Scaled Dot-Product Attention

> We call our particular attention "Scaled Dot-Product Attention". The input
> consists of queries and keys of dimension $d_k$, and values of dimension
> $d_v$. We compute the dot products of the query with all keys, divide each
> by $\sqrt{d_k}$, and apply a softmax function to obtain the weights on the
> values.

**中文翻譯**　本文把採用的注意力機制稱為 Scaled Dot-Product Attention。輸入包含維度為
$d_k$ 的 query 與 key，以及維度為 $d_v$ 的 value。計算方式是把 query 與所有 key
做點積，各除以 $\sqrt{d_k}$，再經過 softmax 函數得到 value 的權重。

- **為什麼要除以 $\sqrt{d_k}$**　這是整段唯一不顯然的設計。點積的變異數隨 $d_k$
  線性成長，$d_k$ 大時點積會落在 softmax 的飽和區——梯度趨近於零，訓練停滯。除以
  $\sqrt{d_k}$ 把變異數壓回 $O(1)$。論文在腳註才提這件事，但它是這個機制能 work
  的前提。
- **與前人工作的關係**　Bahdanau et al. (2014) 的 additive attention 用一層
  前饋網路算相容性分數。理論複雜度相同，但點積能直接呼叫高度最佳化的矩陣乘法
  核心，實務上快得多。作者選點積是工程考量而非理論優勢。
```

| 部分 | 內容 | 紀律 |
|---|---|---|
| `> ` 引用塊 | 英文原文，逐字 | 不改寫、不節錄成摘要。原文長就整段放。 |
| `**中文翻譯**　` | 繁體中文翻譯 | 忠於原文，包括原文含糊之處。不補充、不解釋、不評論。 |
| 條列解說 | 每條以粗體小標題開頭 | 補上原文沒說的東西。 |

解說**一律**寫成「粗體小標題＋條列」，不加「解」之類的總標籤。翻譯是一整段文字、
解說是條列——排版本身區分兩者，所以「翻譯裡不夾解釋」才守得住。某段不需要解說時，
翻譯之後直接接下一個段落單元。

用粗體標籤而非標題，是為了不污染 Obsidian 大綱——大綱只該有章節。

## 解說面向不是必填欄位

各文件列出的解說面向，依段落性質挑用得上的，用不上的整條不寫。寫死成模板的後果是
一整排「本段無」——純雜訊，會把真正有東西的段落淹掉。寧可某段只有一條，也不要湊滿。

## 分段單位

以**論文的自然段落**為單位。兩個調整：

- 連續的短過場段（一兩句話、只做承接）合併成一個單元
- 單一段落塞了多個獨立論點時可以拆開，但拆點要落在句號，不可切斷句子

判準是「這個單元值不值得配一份獨立的解說」。不值得就合併。

## 圖表單元

```markdown
### Figure 2　Scaled Dot-Product Attention 與 Multi-Head Attention

![[attention-is-all-you-need/ModalNet-19.png]]

> (left) Scaled Dot-Product Attention. (right) Multi-Head Attention consists of
> several attention layers running in parallel.

**中文翻譯**　（左）Scaled Dot-Product Attention。（右）Multi-Head Attention 由數個
平行運行的注意力層組成。

- **怎麼讀**　左圖由下往上是資料流：Q 與 K 進 MatMul，Scale 即除以 $\sqrt{d_k}$，
  Mask 只在 decoder 用到⋯⋯
- **這張圖在證明什麼**　（或：這張圖不證明任何事，只是架構示意）
```

數據圖（折線、長條、散佈）的解說必須額外交代：兩軸各是什麼、哪一條線是本文方法、
差距多大才算有意義、以及這張圖有沒有被挑過（例如只報最好的一次跑）。

無法檢視的圖（`.pdf`／`.eps`）照實說明，改由 caption 與上下文解釋，不要假裝看過。

## 外部論文的寫法

講義中提到本篇以外的論文時，一律「作者 et al. (年份)」並附連結，例如
[Bahdanau et al. (2014)](https://arxiv.org/abs/1409.0473)。這些論文必須來自
`fetch.py --graph` 或通過 `fetch.py --verify`（見 SKILL.md〈Discipline〉），
查證不過的不寫。

## 反例（兩種文件皆適用）

- **翻譯裡夾解釋**——「⋯⋯再經過 softmax（一種把向量正規化成機率分布的函數）⋯⋯」。
  括號內容屬於解說。
- **解說只是把翻譯換句話說**——「這段在說注意力機制的計算方式」。沒有增加任何資訊。
- **出現「譯」「解」標籤或層級字樣**——已廢止。
- **腦補公式**——PDF 路線讀到 `x2` 就寫成 $x^2$。必須標 `⚠️ 此處公式從 PDF 抽取受損，無法確認原式`。
- **引用寫成編號**——「如 [12] 所示」。應寫成「如 Bahdanau et al. (2014) 所示」。
- **摘要式跳躍**——把三段原文併成一段翻譯。逐段對照的價值就在於逐段。
- **憑記憶列文獻**——延伸閱讀或脈絡區塊出現沒有經過 `--graph`／`--verify` 的論文。

---

# 廣讀文件 `broad.md`

目的：定位這篇論文——它回答什麼問題、讀懂它要先知道什麼、它的核心想法、它在研究
脈絡中的位置、接著該讀什麼。**深度以「能定位這篇論文」為限**，不處理推導與實驗細節。

## 骨架

```markdown
# Attention Is All You Need

> **來源**　arXiv:1706.03762 ｜ **保真度**　tier 1（LaTeX 原始碼，公式與引用為原文）
> **本篇在做什麼**　（兩句話，不是摘要的翻譯，是判斷）

## 論文全貌

### Abstract
### 1 Introduction
### 7 Conclusion

## 讀懂它需要先知道的

## 核心方法速覽

## 它在研究脈絡中的位置

### 繼承的工作
### 其他路線
### 後續發展

## 延伸閱讀

## 問題
```

「論文全貌」下的小節標題沿用論文自己的編號與名稱。

## 論文全貌

Abstract、Introduction、Conclusion 逐段做段落單元。解說聚焦**論證結構**：

- **在論文中的位置**——這段在論證鏈的哪一環
- **問題設定**——作者認為要解決的是什麼、為什麼現有方法不夠
- **宣稱的貢獻**——每項貢獻在正文哪一節被證明（只指路，不評斷證據強弱，那是精讀的事）
- **術語**——首次出現的術語，中英並列：`注意力機制（attention mechanism）`

## 讀懂它需要先知道的

論文沒寫、讀者不知道就會卡住的論文外知識。每項一個 `###` 小節：

```markdown
### BLEU 與 COMET

- **卡在哪裡**　§5 主結果只報 BLEU 與 COMET，兩者差距的解讀方向相反時不知道該信誰。
- **要懂到什麼程度**　知道 BLEU 是 n-gram 重疊率、對同義改寫不敏感；COMET 是以
  人工評分訓練的神經網路評分器。不必會算。
- **去哪裡補**　[Papineni et al. (2002)](https://aclanthology.org/P02-1040) §2；
  [Rei et al. (2020)](https://arxiv.org/abs/2009.09025) §1–2。
```

「要懂到什麼程度」不可省略：少了它，這一區會膨脹成一門課。

## 核心方法速覽

不逐段講。只挑**摘要主張直接依賴**的段落——通常是方法總覽段、主架構圖、那一條
核心公式——做段落單元。解說面向：

- **它做了什麼**——一句話講清楚機制
- **與對手差在哪**——跟最直接的替代做法比，關鍵差異是哪一個
- **看圖的方法**——主架構圖怎麼讀

推導、超參數、ablation 一律不講。

## 它在研究脈絡中的位置

**以這篇論文為中心**，不描繪整個研究領域。這一區沒有原文可引，以條列解說為主。

- **繼承的工作**　取自 `--graph` 的 `references` 中 `influential: true` 或 `intents`
  含 `methodology` 者。每篇說明本篇借用或改良了什麼。
- **其他路線**　解決同一問題的其他派別。每派一個粗體小標題，交代：核心主張、
  至少一篇查證過的代表論文、與本篇分歧在哪個假設上。派別的歸納屬評論，句子寫成
  「可歸為⋯⋯」而非事實陳述。
- **後續發展**　取自 `citations`。`citations_complete` 為 `false` 時，本小節第一行寫：

  ```markdown
  > 以下取自最新的 3000 篇引用（查詢日期 2026-09-15），不代表影響力排序。
  ```

  數字與日期取自 `citations_scanned` 與 `fetched_on`。

`--graph` 與 `--verify` 都無法使用時，整個「它在研究脈絡中的位置」只寫一行：

```markdown
> 本次無法查證外部文獻（Semantic Scholar 無法連線），此區從缺。
```

## 延伸閱讀

```markdown
| 論文 | 為什麼讀 | 本篇之前或之後 | 建議 |
|---|---|---|---|
| [Neural Machine Translation by Jointly Learning to Align and Translate](https://arxiv.org/abs/1409.0473)（Bahdanau et al., 2014） | additive attention 的原型，本篇 §3.2 的比較對象 | 之前 | 廣讀 |
```

- 「建議」只有 `廣讀`／`精讀` 兩值。
- 連結優先 arXiv（`https://arxiv.org/abs/<id>`），其次 DOI（`https://doi.org/<doi>`）。
- 查證失敗者不列，不以警告標記代替。

## 問題

見 `questions.md`。

---

# 精讀文件 `deep.md`

目的：只談這篇論文。論述是否成立、每個設計決策為何如此、證據撐不撐得起主張。

## 骨架

```markdown
# Attention Is All You Need

> **來源**　arXiv:1706.03762 ｜ **保真度**　tier 1（LaTeX 原始碼，公式與引用為原文）
> **廣讀**　[broad.md](./broad.md)
> **核心主張**　（一句話）
> **最值得懷疑的地方**　（一句話——讀之前先立一個靶子）

## Abstract

## 1 Introduction

…（論文自己的章節，依原順序）

## 主張與證據

## 設計決策

## 問題
```

- `broad.md` 不存在時，「廣讀」一行寫 `無（可另跑 /ppread --broad）`。
- 連回廣讀用相對路徑 Markdown 連結 `[broad.md](./broad.md)`，不用 `[[broad]]`：
  每個論文資料夾都有同名的 `broad.md`，wikilink 無法唯一解析。
- 章節標題沿用論文自己的編號與名稱；Step 1 若縮小範圍，只寫選定的章節，
  「主張與證據」「設計決策」「問題」三區仍然要寫。

## 與 `broad.md` 的關係

- **`broad.md` 存在**：它講過的前置知識與研究脈絡不重講，需要時寫
  「見廣讀〈讀懂它需要先知道的〉」。
- **`broad.md` 不存在**：只在某段確實依賴某背景才讀得懂時，在該段補到該段所需的程度。
- 兩種情況下 Abstract 與 Introduction 都要重新做段落單元：「本文貢獻有三點」在精讀
  中是被檢驗的對象，不是導讀。

## 解說面向

| 面向 | 回答什麼 |
|---|---|
| **論證位置** | 這段支撐哪個主張，是前提、推論還是證據 |
| **設計動機** | 為什麼這樣做，不這樣做會壞在哪 |
| **替代方案** | 顯而易見的其他做法是什麼、為何未採用 |
| **公式拆解** | 每個符號是什麼、整體在算什麼、哪一項是關鍵 |
| **實驗設計** | 為什麼這樣切資料、這樣設 baseline，這個設計能／不能支持什麼結論 |
| **隱含假設** | 作者沒寫出來、結論卻依賴的前提 |
| **存疑之處** | 推論跳躍、證據不足、與已知結果衝突 |
| 術語、背景知識 | 輔助面向，只在 §「與 broad.md 的關係」允許時使用 |

## 批判的底線

- 每條批判指向具體位置（段落、表格、公式）。
  - ✗「樣本數偏少。」
  - ✓「Table 2 每個設定只跑一個 seed，最大差距 0.3 BLEU，不足以排除隨機波動。」
- 以「與某篇論文的結果衝突」為據時，那篇論文同樣要經過 `--graph`／`--verify`。

## 本節收束

每個 `##` 層級的論文章節結束時補一句：

```markdown
> **本節收束**　（這一節確立了什麼，下一節要用它做什麼）
```

## 主張與證據

把 Abstract 與 Introduction 裡的每一條主張，對應到正文的證據：

```markdown
| 主張 | 原文位置 | 證據 | 強度 | 落差 |
|---|---|---|---|---|
| 在 WMT 2014 英德翻譯上達到新的 state of the art | Abstract | Table 2 | 支持 | — |
| 訓練成本只有既有最佳模型的一小部分 | Abstract | Table 2 訓練成本欄 | 部分支持 | 成本以 FLOPs 估算，未報實際硬體時數的變異 |
```

「強度」只有四個值：`支持`／`部分支持`／`未支持`／`無對應證據`。
`支持` 時「落差」寫 `—`。

## 設計決策

每個決策一個 `###` 小節，依重要性排序：

```markdown
### D1　用 scaled dot-product attention 而非 additive attention

- **選擇**　相容性分數用點積並除以 $\sqrt{d_k}$。
- **放棄的替代方案**　additive attention（Bahdanau et al., 2014）；不縮放的點積。
- **作者的理由**　§3.2.1：「dot-product attention is much faster and more space-efficient in practice」。
- **證據**　§3.2.1 腳註的變異數論證；未見直接比較兩者翻譯品質的實驗。
- **撐不撐得起**　速度論點成立；「$d_k$ 大時不縮放會變差」只引用 Britz et al. (2017)
  的觀察，本篇沒有自己的 ablation。
```

作者沒說明理由時：

```markdown
- **作者的理由**　論文未說明。
- **推測**　⋯⋯（並交代這個推測的根據有多強）
```

一篇論文沒解釋自己的設計決策，本身就是精讀要挖出的資訊，不可被合理的補述掩蓋。

## 問題

見 `questions.md`。
````

- [ ] **Step 2: Verify the contract**

Run:

```bash
grep -nE '\*\*(譯|解)\*\*' lecture-format.md ; grep -c '中文翻譯' lecture-format.md ; grep -nE '^# ' lecture-format.md
```

Expected: first grep prints nothing; count ≥ 3; the `# ` lines are `講義輸出格式`, `共通規則`, `廣讀文件 \`broad.md\``, `精讀文件 \`deep.md\``, plus two `# Attention Is All You Need` lines that sit inside the skeleton code fences.

Also check every external-paper example link in the file with `--verify` so the contract does not model an unverified citation:

```bash
python3 fetch.py --verify \
  "BLEU: a Method for Automatic Evaluation of Machine Translation" \
  "COMET: A Neural Framework for MT Evaluation" \
  "Neural Machine Translation by Jointly Learning to Align and Translate" \
  "Massive Exploration of Neural Machine Translation Architectures" \
  | python3 -c "import json,sys; [print(r['status'], r.get('arxiv') or r.get('doi') or r.get('candidate','')) for r in json.load(sys.stdin)['results']]"
```

Expected: four `exact` lines; COMET should show arXiv `2009.09025`, Bahdanau `1409.0473`. If BLEU returns no arXiv/DOI that is expected (ACL Anthology paper); keep the aclanthology link. If any line is not `exact`, replace that example in `lecture-format.md` with one that verifies, and rerun.

- [ ] **Step 3: Commit**

```bash
git add lecture-format.md
git commit -F - <<'EOF'
docs(format): define the broad and deep lecture contracts

- lecture-format.md 分為共通規則、廣讀文件、精讀文件三部分
- 段落單元改用「中文翻譯」標籤，解說一律粗體小標題條列，廢除「譯」「解」與層級字樣
- front matter 新增 mode、lecture_read
- 廣讀骨架：論文全貌、前置知識（含懂到什麼程度）、核心方法速覽、研究脈絡、延伸閱讀
- 精讀骨架：逐段批判、主張與證據表、設計決策（作者理由與推測分開）

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 7: `questions.md` and deploy

**Files:**
- Create: `questions.md`
- Modify: `deploy.sh`

**Interfaces:**
- Consumes: spec §9
- Produces: the question guide `SKILL.md` Step 4 loads; fixed IDs `B1`–`B5`, `D1`–`D5`; custom IDs from `Q6`.

- [ ] **Step 1: Write `questions.md`**

````markdown
# 問題區塊

每份講義（`broad.md`、`deep.md`）的最後一個 `##` 區塊。目的是讓讀者先自己作答，
再展開參考答案對照，量出自己的思考與參考答案的落差。

## 結構

- **固定題在前**：題號與題目每篇論文完全相同，一字不改。讀者因此能跨論文回顧同一題。
- **客製題在後**：題號從 `Q6` 起接續。
- **總題數 ≤ 8**：固定 5 題，客製最多 3 題。題目太多，讀者會整批跳過。

## 固定題

依 S. Keshav, "How to Read a Paper," *ACM SIGCOMM Computer Communication Review*
37(3):83–84, 2007。該文的三遍閱讀法中，第一遍的目的是決定要不要繼續讀，第三遍是在
腦中重新實作並挑戰每一個假設——分別對應廣讀與精讀。

### 廣讀

| # | 題目 |
|---|---|
| B1 | 這篇論文要解決什麼問題？為什麼這個問題值得解決？ |
| B2 | 用一段話說明它的核心想法與宣稱的貢獻。 |
| B3 | 它屬於哪一類研究（新方法、分析、benchmark、系統、理論）？該用什麼標準評價這一類研究？ |
| B4 | 它繼承了哪些工作、與哪條路線立場相對？分歧點在哪個假設上？ |
| B5 | 這篇值得精讀嗎？理由是什麼？精讀時最該檢查哪個地方？ |

B3 決定後續的評價標準：benchmark 論文該問資料集建構有沒有偏差，方法論文該問
baseline 公不公平。B5 是廣讀的出口，參考答案必須給出「值得／不值得」的明確判斷。

### 精讀

| # | 題目 |
|---|---|
| D1 | 不看論文，說出方法的完整流程，以及每一步為什麼必要。 |
| D2 | 最弱的主張是哪一條？證據缺了什麼？ |
| D3 | 哪一個設計決策最關鍵？換成替代方案，預期會發生什麼？ |
| D4 | 結論依賴哪些沒有明說的假設？在什麼條件下會不成立？ |
| D5 | 要接續這篇做研究，第一個實驗會做什麼？ |

D2 的參考答案取材自「主張與證據」表，D3 取材自「設計決策」區塊。

## 客製題

每題必須全部通過：

1. **沒讀過這篇就答不出來。** 能套用到任何論文的題目，要嘛該升為固定題，要嘛是空泛題——兩者都不是客製題。
2. **瞄準這篇的關鍵點**：特定的設計決策、特定圖表、出乎意料的結果、與對立路線的衝突。
3. **不考查表題。** 「Table 2 最高分是多少」翻原文就有答案，測不出思考。
4. **題型依模式**：廣讀偏理解與定位（能否說明 X、X 在脈絡中的位置）；精讀偏評估與推演（Y 是否合理、換成 Z 會怎樣）。

反例：

- ✗「這篇論文的優缺點是什麼？」——任何論文都能問。
- ✗「本文使用了哪些資料集？」——查表題。
- ✓「作者只用 COMET 挑選 checkpoint，卻同時回報 BLEU。若改用 BLEU 挑選，Table 2 的排名可能怎麼變？」

## 參考答案

- **表態。** 開放題給明確立場與理由，不寫「兩者皆有道理」。確實沒有唯一正解時，先給一個立場，再用一句帶出另一個站得住的立場。
- **事實附原文位置**（§、Table、Figure）。推測標 `**推測**`。
- **3–6 句。** 與讀者實際會寫的長度相當，才對照得起來。
- **關鍵點 2–3 條。** 好答案必須涵蓋的要點，供讀者逐條自評。
- **外部論文**同樣受 SKILL.md〈Discipline〉的查證規則約束。

## 格式

```markdown
## 問題

> [!question] B1　這篇論文要解決什麼問題？為什麼這個問題值得解決？

> [!answer]- 參考答案（先作答再展開）
> 本文處理序列轉換模型無法平行化訓練的問題⋯⋯（§1 第 2 段）
>
> **關鍵點**
> - 問題的具體範圍：⋯⋯
> - 為什麼既有方法不夠：⋯⋯

> [!question] Q6　作者為什麼⋯⋯？

> [!answer]- 參考答案（先作答再展開）
> ⋯⋯
>
> **關鍵點**
> - ⋯⋯
```

- 每題是一對 callout：`[!question]` 不摺疊，`[!answer]-` 摺疊（`-` 代表預設收起）。
- **相鄰 callout 之間必須空一行**，否則 Obsidian 會把它們併成同一個區塊。
- 參考答案一律摺疊：先看到答案會錨定讀者的思考，對照就失效。

## 邊界

參考答案是對照材料，不是讀者的筆記。不要把讀者在對話中貼出的作答整理成筆記、
寫進講義或寫進任何檔案。
````

- [ ] **Step 2: Update `deploy.sh`**

Add after the `lecture-format.md` install line:

```bash
install -m 0644 "$SRC/questions.md"      "$DEST/questions.md"
```

- [ ] **Step 3: Verify**

Run:

```bash
grep -cE '^\| (B[1-5]|D[1-5]) \|' questions.md
D=$(mktemp -d) && CLAUDE_SKILLS_DIR="$D" ./deploy.sh && ls "$D/ppread"
```

Expected: `10`; the final `ls` lists exactly `SKILL.md  fetch.py  lecture-format.md  questions.md`. (`CLAUDE_SKILLS_DIR` points the deploy at a throwaway directory, so the live skill is untouched.)

- [ ] **Step 4: Commit**

```bash
git add questions.md deploy.sh
git commit -F - <<'EOF'
docs(questions): add the question guide for broad and deep lectures

- 新增 questions.md：固定題 B1–B5、D1–D5（依 Keshav 三遍閱讀法），客製題判準與反例，參考答案紀律
- 問題與參考答案以 [!question] 與摺疊的 [!answer]- callout 呈現
- deploy.sh 增部署 questions.md

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 8: Rewrite `SKILL.md`

**Files:**
- Modify (full rewrite): `SKILL.md`

**Interfaces:**
- Consumes: `fetch.py` routes and flags from Tasks 1–5 (`docs`, `--graph`, `--verify`, `--list`, `graph-unavailable`, `verify` statuses); `lecture-format.md` sections from Task 6; `questions.md` from Task 7
- Produces: the deployed orchestration

- [ ] **Step 1: Write the file**

Replace the entire contents of `SKILL.md` with:

````markdown
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
| `needs-title` | A local file whose metadata has no title, or a title with no ASCII in it | Read its first page (`pdftotext -f 1 -l 1 <file> -`), take the **English** title — a paper written in another language usually prints one on page 1; translate it if it does not — and re-run with `--title "<title>"`. The file was **not** moved. |
| `local` | A local non-PDF source (e.g. `.tex`) already in place | Read `source_path` directly. |

### Choosing the mode

Every route that has a `workdir` also carries `docs`:

```json
"docs": {"broad": "read", "deep": "absent", "legacy": false}
```

`broad`/`deep` are each `absent`, `partial` (being written, or interrupted),
`unread` or `read`. Decide:

| `docs` | no flag | `--broad` | `--deep` |
|---|---|---|---|
| both `absent` | write broad | write broad | write deep |
| broad exists, deep `absent` | write deep | exists — stop | write deep |
| deep exists, broad `absent` | write broad | write broad | exists — stop |
| both exist | stop | stop | stop |
| the chosen mode is `partial` | ask | ask | ask |

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
- **Papers from your own knowledge** — rival approaches, prerequisite sources,
  further reading not in the graph — must be checked, up to 25 titles per call:
  ```bash
  python3 ~/.claude/skills/ppread/fetch.py --verify "<title>" "<title>" ...
  ```
  Only `status: exact` may appear in the lecture. `mismatch` carries a `candidate`:
  **do not use it**, even if it looks like the paper you meant. `not-found` and
  `error` are both left out; tell the user how many titles were dropped and which
  kind of failure it was.
- **`route: graph-unavailable`** — fall back to the paper's own bibliography (on the
  latex route the `.bib` entries in `src/` are exact) and run every chosen title
  through `--verify`. If `--verify` also fails, write the single "無法查證" line
  that `lecture-format.md` specifies and list no outside papers at all.

There is no path by which a paper recalled from memory reaches the lecture without
an `exact` verification.

## Step 3: Write the lecture, section by section

Read `lecture-format.md` (same directory): the「共通規則」part, plus「廣讀文件」or
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
`legacy: true`. Filter or sort only as the user asks. Papers built beside local files
live outside the library; `--list <dir>` reaches them. A `needs-output-config` result
means no library is set: handle it as in Step 0.

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
````

- [ ] **Step 2: Verify references between files**

Run:

```bash
for r in latex needs-html needs-pdf unresolved needs-output-config conflict needs-title local graph graph-unavailable list verify; do
  grep -q "\"$r\"" fetch.py && grep -q "$r" SKILL.md || echo "missing: $r"
done
for s in 共通規則 廣讀文件 精讀文件; do grep -q "^# $s" lecture-format.md || echo "missing section: $s"; done
grep -n 'lecture_identity\|\*\*譯\*\*\|\*\*解\*\*' SKILL.md
```

Expected: no output at all — every route is both produced by `fetch.py` and named in `SKILL.md`, the three section names `SKILL.md` Step 3 cites exist in `lecture-format.md`, and no stale identifiers or labels remain.

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -F - <<'EOF'
feat(skill): orchestrate broad and deep lectures

- 新增 --broad／--deep／--list 呼叫方式，依 docs 狀態表決定模式，partial 時詢問續寫或重寫
- Step 1 依模式提出規劃；Step 2（僅廣讀）以 --graph 與 --verify 取得外部文獻
- 寫入 <mode>.part.md，一次一個 ## 區塊，出完題後改名為正式檔名
- Discipline 新增：外部文獻必須查證、作者理由與推測分開、批判指向具體位置
- Step 5 補述參考答案與卡片盒邊界的關係

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 9: Developer docs, README, version

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `VERSION`, `fetch.py` (User-Agent version string, line 32)

**Interfaces:**
- Consumes: everything above
- Produces: docs consistent with v0.2.0

- [ ] **Step 1: `VERSION` and User-Agent**

Set `VERSION` to:

```
0.2.0
```

In `fetch.py` change `"ppread/0.1 (+https://github.com/syoslyot/ppread-skill"` to `"ppread/0.2 (+https://github.com/syoslyot/ppread-skill"`.

- [ ] **Step 2: `CLAUDE.md`**

Apply these edits.

In **What this is**, replace the sentence `The skill turns one research paper into a paragraph-level bilingual lecture: English original, Traditional Chinese translation, and an explanation covering background, prior work, experimental rationale and formula breakdown.` with:

```markdown
The skill turns one research paper into bilingual lectures in two modes: `broad.md` places the paper (abstract/introduction/conclusion paragraph by paragraph, assumed outside knowledge, core idea, literature context grounded in the citation graph) and `deep.md` judges it (every paragraph with critical analysis, claims versus evidence, design decisions). Both end with reader questions and folded reference answers.
```

In **Deploy model**, replace the deploy code comment and the following sentence:

```markdown
./deploy.sh   # copies SKILL.md + lecture-format.md + questions.md + fetch.py -> ~/.claude/skills/ppread/
```

```markdown
Only those four files are deployable. `deploy.sh`, `VERSION`, `tests/`, `docs/` and this file are development-only and must never be copied to the skill dir.
```

In **Architecture**, change the first bullet's description to include the new mechanics and add a bullet for `questions.md`:

```markdown
- **`fetch.py`** — pure mechanics. Source identification, arXiv twin lookup, e-print download, tar extraction, `\input` expansion, lecture state (`docs`), citation graph (`--graph`), title verification (`--verify`), library listing (`--list`), the `papers.base` file. Every step is deterministic and must stay testable from the shell. No judgment, no LLM assumptions. Standard library only — no third-party dependencies, so it runs anywhere `python3` exists.
- **`SKILL.md`** — orchestration and judgment, executed by the agent. Chooses the mode, plans coverage, splits passages, translates, explains, writes questions, enforces the honesty rules.
- **`lecture-format.md`** — the output contract for `broad.md` and `deep.md`, loaded in Step 3. Written in Chinese because it governs Chinese output and its worked examples must be in the target language.
- **`questions.md`** — what to ask and how to answer, loaded in Step 4. Kept apart from `lecture-format.md` because what to ask is a different concern from how the page looks.
```

In **Non-obvious decisions**, append these bullets at the end of the list:

```markdown
- **Two lectures, not one layered file.** Broad is mostly about the paper's surroundings — prerequisites, rival approaches, what came after — while deep is only about the paper itself. They are different documents, not a shallow and a deep half of one, so they live in `broad.md` and `deep.md`, each with full front matter. Both are regenerable machine output, which is why duplicating the metadata does not reopen the `meta.json` objection (that one was about a generated file drifting from a hand-edited one).
- **No outside paper reaches a lecture from memory.** A remembered reading list reads as convincingly as a correct one while getting authors, years or titles wrong — the same failure as inferring a PDF-damaged formula, and worse in a further-reading table the user will act on. Outside papers come from `--graph` or an exact `--verify`. `search/match` always returns its best candidate however poor, so a score proves nothing; only an exact normalised title counts, and the resulting false negatives are accepted.
- **Citations: three pages, newest first.** The citations endpoint cannot sort by impact and caps `offset+limit` below 10000. Keyless requests hit 429 by the third quick call in testing, so scanning further costs minutes of backoff for more recent, rarely-cited papers. `citations_complete` tells the agent when the list is a sample, and the lecture says so with the fetch date.
- **Read state lives in front matter, not in folder names.** `lecture_read` is a checkbox property per lecture. Encoding state as a folder prefix was rejected: every state change would rename the folder and break image embeds and the user's own links (Obsidian only rewrites links for renames it performs); `[` `]` are glob syntax in the shell and reserved link characters in Obsidian; and the state would exist twice. The key is snake_case because Bases formulas cannot read hyphenated property keys.
- **`<mode>.part.md` until the last section is written.** "The lecture exists" must mean "the lecture is finished", or an interrupted run looks complete to `--list` and to the next run. The rename is the single completion signal, and `fetch.py` reads it from the filename rather than parsing content.
- **`papers.base` is written once and never overwritten.** The reader may customise the view. It filters on `type` and `generated` rather than on a folder, so lectures built beside local files elsewhere in the vault appear too.
```

Replace the whole **Testing** section body with:

```markdown
No test framework. Two layers:

- `python3 tests/offline_checks.py` — network-free assertions on `fetch.py` functions (lecture state, conflicts, verify matching, graph ranking and paging with a stubbed `s2_get`, listing, `papers.base`). Standard library only; run it after every change to `fetch.py`.
- Live runs against real sources from the shell. Verified cases: an arXiv ID (`1706.03762`, multi-file `\input` structure), an IEEE DOI (`10.1109/CVPR.2016.90` → `1512.03385`), an ACM URL; `--graph 1706.03762` (incomplete citations), `--graph 1905.02175` (complete in three pages); `--verify` on a real, a fabricated and a re-cased title. Semantic Scholar rate-limits keyless clients hard — space live runs out, or set `PPREAD_S2_API_KEY`.

Use `--out` to write somewhere disposable when testing; for local-file cases point at a throwaway copy instead, since the file is moved in place. `CLAUDE_SKILLS_DIR=<tmp> ./deploy.sh` deploys somewhere other than the live skill.
```

- [ ] **Step 3: `README.md`**

Replace the opening two paragraphs (from `A Claude Code skill that turns` through `給讀英文論文還很慢的人。`) with:

```markdown
A Claude Code skill that turns one research paper into bilingual lectures in two
modes: a **broad** lecture that places the paper in its field, and a **deep**
lecture that takes it apart. Both translate the paper paragraph by paragraph into
Traditional Chinese and end with questions for the reader.

把一篇論文變成兩種講義：**廣讀**幫忙定位這篇論文，**精讀**逐段拆解與批判。
兩者都逐段對照原文與中譯，最後附上問題與摺疊的參考答案。
```

In **這不是翻譯工具**, replace the example block's two labels: `**譯**　計算方式是` → `**中文翻譯**　計算方式是`, and delete the line `**解**` together with the blank line after it. Replace the paragraph after the block (`翻譯與解釋嚴格分離：…`) with:

```markdown
翻譯與解說嚴格分離：翻譯是一整段、忠於原文（包括原文含糊之處），評論與補充一律寫成
粗體小標題的條列。
```

Insert a new section directly after **這不是翻譯工具**:

```markdown
## 兩種講義

| | 廣讀 `broad.md` | 精讀 `deep.md` |
|---|---|---|
| 回答 | 這篇在研究脈絡的哪裡、值不值得精讀 | 論述成不成立、每個設計為什麼這樣做 |
| 逐段對照 | Abstract、Introduction、Conclusion，加上核心方法的關鍵段落 | 全文 |
| 論文以外 | 前置知識（含「懂到什麼程度」）、繼承的工作、其他路線、後續發展、延伸閱讀 | 只談這篇 |
| 彙整 | — | 主張與證據對照表、設計決策拆解 |
| 問題 | 固定題 B1–B5 ＋ 客製題 | 固定題 D1–D5 ＋ 客製題 |

固定題每篇論文一字不改，讀過一批論文後可以回頭比較同一題的作答；參考答案預設摺疊，
先作答再展開。

**廣讀裡出現的每一篇外部論文都經過查證**：來自 Semantic Scholar 的引用網路，或標題
完全吻合的查詢結果。憑記憶列出的文獻清單常常作者、年份或標題錯一項，甚至整篇不存在，
而讀起來跟正確的一樣可信——所以查證不過的論文不會出現在講義裡。
```

In **安裝**, after the `PPREAD_CONTACT` paragraph, add:

```markdown
選用：`export PPREAD_S2_API_KEY=<key>` 讓引用網路與標題查證使用自己的 Semantic Scholar
配額。不帶 key 時共用公開配額，連續查詢容易被限流；不設也能用，只是可能要等。
```

Replace the **用法** code block and the file tree that follows it with:

````markdown
```
/ppread 1706.03762                  # 沒有講義 → 廣讀；已有廣讀 → 精讀
/ppread --broad 10.1109/CVPR.2016.90
/ppread --deep https://dl.acm.org/doi/10.1145/3292500.3330701
/ppread --deep ./papers/某篇論文.pdf
/ppread --list                      # 每篇論文的講義與閱讀狀態
```

一篇論文一個資料夾，原始檔與講義放在一起：

```
<資料庫>/
    papers.base                          # Obsidian Bases 視圖
    attention-is-all-you-need/           # 網路來源：進設定好的資料庫
        source.tex       # 只有走 LaTeX 路線才有
        src/             # 解壓出的 e-print 樹，圖檔在這裡
        broad.md         # 廣讀講義
        deep.md          # 精讀講義
~/Downloads/attention-is-all-you-need/   # 本機檔案：就建在該檔案旁邊
        1706.03762.pdf   # 被移進來的原檔
```
````

In the paragraph that begins `metadata（標題、作者、年份、DOI、arXiv ID、保真度 tier）全部寫在 \`lecture.md\``, replace `` `lecture.md` `` with `每份講義`.

In the conflict paragraph, replace `判斷依據是該資料夾裡\n\`lecture.md\` 的 front matter` with `判斷依據是該資料夾裡每一份講義的 front matter`.

Insert a new section before **它刻意不做的事**:

```markdown
## 閱讀進度

每份講義的 front matter 有一個 `lecture_read`，產生時是 `false`。讀完在 Obsidian 的
屬性欄勾選即可（不用 Obsidian 就把 `false` 改成 `true`）。

- `/ppread --list` 列出資料庫裡每篇論文的廣讀、精讀狀態：已讀、未讀、寫到一半、未產生。
- 資料庫根目錄的 `papers.base` 在 Obsidian 裡是一張表格，預設視圖就是「未讀講義」。
  這個檔案只在第一次寫入，之後怎麼改都不會被覆蓋。

狀態刻意不寫進資料夾名稱：狀態一變就得改名，講義裡的圖片嵌入與自己筆記裡的連結會跟著斷。

寫到一半中斷的講義叫 `broad.part.md`／`deep.part.md`，完成時才改成正式檔名；
下次執行會問要續寫還是重寫。
```

In **它刻意不做的事**, append after the Zettelkasten paragraph:

```markdown
講義最後的參考答案也不是筆記：它預設摺疊，是作答之後拿來對照的材料。把自己的答案
貼進對話可以討論落差，但 skill 不會把答案整理成筆記或寫進任何檔案。
```

- [ ] **Step 4: Verify**

Run:

```bash
grep -n 'lecture\.md' README.md CLAUDE.md SKILL.md | grep -v -i 'legacy\|舊版\|0\.1'
grep -nE '\*\*(譯|解)\*\*' README.md
python3 tests/offline_checks.py
```

Expected: the first grep prints only lines that describe `lecture.md` as the legacy/0.1 file (inspect each; any other hit is a missed edit — fix it); the second prints nothing; offline checks print six `ok` lines.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md VERSION fetch.py
git commit -F - <<'EOF'
docs: describe broad and deep lectures and bump to 0.2.0

- CLAUDE.md：可部署檔改為四份，Architecture 補 questions.md，新增六條 non-obvious decisions，Testing 改為 offline checks 加 live runs
- README.md：兩種講義比較表、外部文獻查證說明、新用法與檔案樹、閱讀進度、PPREAD_S2_API_KEY
- VERSION 與 User-Agent 升為 0.2

問題：現在閱讀論文的方式都是線性的，希望改成廣讀與精讀兩種模式（皆需翻譯），並對每篇論文出題、附參考答案以對照思考落差

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014hB82hU52RU64Ltd26Bghy
EOF
```

---

### Task 10: End-to-end run and manual Obsidian checks

**Files:** none modified unless a check fails (then fix in the file the failure points to and commit with a `fix(...)` subject in the same format).

**Interfaces:**
- Consumes: the deployed skill

- [ ] **Step 1: Ask before deploying**

`./deploy.sh` overwrites the live `~/.claude/skills/ppread/`. Stop and get an explicit yes from the user before running it. Also confirm which short paper to use; propose `1905.02175` (already used in live checks, moderate length).

- [ ] **Step 2: Deploy**

Run: `./deploy.sh && ls ~/.claude/skills/ppread`
Expected: `deployed -> /home/wassup/.claude/skills/ppread` and the four files.

- [ ] **Step 3: Broad run**

Run `python3 ~/.claude/skills/ppread/fetch.py --show-config` and ask the user whether the test paper may land in that library. If not, pick a scratch directory and, when invoking `/ppread --broad 1905.02175`, instruct the agent to append `--out <scratch dir>` to its Step 0 `fetch.py` call (and to use the same `--out` for Step 4's `/ppread 1905.02175`). `<workdir>` below is the `workdir` field from that Step 0 output.

Check the resulting `broad.md`:

```bash
F=<workdir>/broad.md
test -f "$F" && ! test -f "${F%.md}.part.md" && echo renamed
grep -c '^> \[!question\] B[1-5]' "$F"            # expect 5
grep -c '^> \[!answer\]-' "$F"                    # expect = number of questions
grep -nE '\*\*(譯|解)\*\*|第.層' "$F"              # expect nothing
grep -n '^lecture_read: false$' "$F"               # expect one line
grep -oE '\(https://(arxiv\.org/abs|doi\.org)/[^)]+\)' "$F" | sort -u | wc -l
```

Then extract every outside-paper title from「它在研究脈絡中的位置」and「延伸閱讀」and rerun them through `fetch.py --verify`; every one must be `exact` or appear in a fresh `--graph 1905.02175`. Any that fails is a Discipline violation — record it and fix the `SKILL.md` wording that allowed it.

- [ ] **Step 4: Deep run**

Run `/ppread 1905.02175` with no flag. Expected: Step 1 announces deep (row "broad exists, deep absent"). Check `deep.md`:

```bash
F=<workdir>/deep.md
grep -c '^> \[!question\] D[1-5]' "$F"            # expect 5
grep -n '^## 主張與證據$\|^## 設計決策$\|^## 問題$' "$F"   # expect three, in this order
grep -n '\[broad.md\](./broad.md)' "$F"            # expect one
grep -nE '\*\*(譯|解)\*\*' "$F"                     # expect nothing
```

- [ ] **Step 5: State checks**

```bash
python3 ~/.claude/skills/ppread/fetch.py --list <library or scratch dir>
```

Expected: the paper shows `"broad": "unread", "deep": "unread"`. Edit `broad.md` front matter to `lecture_read: true`, rerun, expect `"broad": "read"`. Then run `/ppread --broad 1905.02175` again: expect "exists — stop" without writing.

- [ ] **Step 6: Manual Obsidian checks (user)**

Ask the user to open the library in Obsidian and confirm:

1. `papers.base` opens as a table; the「未讀講義」view lists `deep.md` and not the now-read `broad.md`. If the filter `'lecture_read != true'` shows nothing or errors, change `PAPERS_BASE` in `fetch.py` and `tests/offline_checks.py`'s needle to use `not: ['lecture_read == true']` form:
   ```yaml
       filters:
         not:
           - 'lecture_read == true'
   ```
   rerun `python3 tests/offline_checks.py`, delete the test library's `papers.base`, regenerate, and have the user recheck.
2. `lecture_read` renders as a checkbox and ticking it flips the Bases row.
3. `[!answer]-` callouts are collapsed by default and expand on click.

- [ ] **Step 7: Report**

Report to the user: every check's result, anything fixed, and anything still unverified. Do not merge or open a PR; the user drives the release with `/gitf`.

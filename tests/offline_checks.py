#!/usr/bin/env python3
"""Network-free checks for fetch.py. Standard library only; run from anywhere:

    python3 tests/offline_checks.py
"""

from __future__ import annotations

import os
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


def check_list_library_unreadable_dir() -> None:
    """A permission-denied subdirectory must be logged and skipped, not raise —
    fetch.py has to print its one JSON object no matter what a stray directory
    under the library looks like."""
    lib = Path(tempfile.mkdtemp())
    write_doc(lib / "readable" / "broad.md",
              {**A, "year": "2017", "tier": "1", "mode": "broad", "lecture_read": "true"})
    blocked = lib / "blocked"
    (blocked).mkdir()
    (blocked / "paper.pdf").write_bytes(b"%PDF")
    blocked.chmod(0o000)
    try:
        if os.access(blocked, os.R_OK):
            print("skip check_list_library_unreadable_dir "
                  "(chmod 0o000 does not deny read in this environment)")
            return
        r = fetch.list_library(lib)
        assert r["route"] == "list", r
        slugs = [p["slug"] for p in r["papers"]]
        assert "readable" in slugs, slugs
        assert "blocked" not in slugs, slugs
    finally:
        blocked.chmod(0o755)


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


def check_slugify_length() -> None:
    # An ordinary long title survives whole; only a title past SLUG_MAX is cut,
    # and then at a hyphen so the last word is never left as a fragment.
    bert = ("BERT: Pre-training of Deep Bidirectional Transformers for "
            "Language Understanding")
    assert fetch.slugify(bert, "x") == (
        "bert-pre-training-of-deep-bidirectional-transformers-for-language-understanding")

    long_title = " ".join(["alpha"] * 40)  # 40 * 6 - 1 = 239 chars slugified
    s = fetch.slugify(long_title, "x")
    assert len(s) <= fetch.SLUG_MAX, len(s)
    assert s.endswith("alpha") and "--" not in s, s
    assert fetch.slugify("x" * (fetch.SLUG_MAX + 10), "f") == "x" * fetch.SLUG_MAX
    assert fetch.slugify("——", "fallback") == "fallback"


CHECKS = [
    check_lecture_docs_and_conflicts,
    check_slugify_length,
    check_verify_matching,
    check_s2_key_header,
    check_graph,
    check_list_library,
    check_list_library_unreadable_dir,
    check_papers_base,
]

if __name__ == "__main__":
    for check in CHECKS:
        check()
        print(f"ok  {check.__name__}")

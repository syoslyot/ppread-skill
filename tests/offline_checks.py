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

#!/usr/bin/env python3
"""ppread fetch — resolve a paper reference to the highest-fidelity full text available.

Emits one JSON object on stdout describing what was obtained and which route the
agent should take next. Diagnostics go to stderr. Standard library only.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import sys
import tarfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Crossref's "polite pool" gives contactable clients a separate, faster resource
# pool; the address is for accountability, never verified, and entirely optional.
# arXiv only requires that the agent be identifiable at all.
_CONTACT = os.environ.get("PPREAD_CONTACT", "").strip()
UA = ("ppread/0.1 (+https://github.com/syoslyot/ppread-skill" +
      (f"; mailto:{_CONTACT})" if _CONTACT else ")"))
TIMEOUT = 45

ARXIV_NEW = r"\d{4}\.\d{4,5}"
ARXIV_OLD = r"[a-z-]+(?:\.[A-Z]{2})?/\d{7}"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>&]+")


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def get(url: str, accept: str | None = None, retries: int = 3,
        timeout: int = TIMEOUT) -> bytes:
    """Keyless Semantic Scholar rate-limits hard and arXiv's search endpoint is slow
    enough to time out, so both classes of failure are retried with backoff."""
    delay = 3.0
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        if accept:
            req.add_header("Accept", accept)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and attempt < retries - 1:
                log(f"  rate limited ({e.code}), retrying in {delay:.0f}s")
                time.sleep(delay)
                delay *= 3
                continue
            raise
        except (TimeoutError, urllib.error.URLError) as e:
            if attempt < retries - 1:
                log(f"  transient network failure ({e}), retrying in {delay:.0f}s")
                time.sleep(delay)
                delay *= 3
                continue
            raise
    raise RuntimeError("unreachable")


# --- source identification ------------------------------------------------


def identify(raw: str) -> tuple[str, str]:
    """Classify a user-supplied reference into (kind, value)."""
    s = raw.strip()

    m = re.fullmatch(rf"(?:arxiv:)?({ARXIV_NEW}|{ARXIV_OLD})(v\d+)?", s, re.I)
    if m:
        return "arxiv", m.group(1)

    if "arxiv.org" in s:
        m = re.search(rf"(?:abs|pdf|html|e-print)/({ARXIV_NEW}|{ARXIV_OLD})", s)
        if m:
            return "arxiv", m.group(1)

    if "doi.org" in s:
        m = DOI_RE.search(urllib.parse.unquote(s))
        if m:
            return "doi", m.group(0).rstrip(".")

    if s.lower().startswith("doi:"):
        return "doi", s[4:].strip()

    m = DOI_RE.fullmatch(s)
    if m:
        return "doi", m.group(0)

    if s.startswith(("http://", "https://")):
        # Publisher URLs very often carry the DOI in the path.
        m = DOI_RE.search(urllib.parse.unquote(s))
        if m:
            return "doi", m.group(0).rstrip(".")
        return "url", s

    return "query", s


# --- metadata sources -----------------------------------------------------


def crossref_meta(doi: str) -> dict:
    """Crossref covers every registered DOI and has no punitive rate limit, so it is
    the reliable metadata source. Semantic Scholar is reserved for finding arXiv twins."""
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    try:
        m = json.loads(get(url)).get("message", {})
    except Exception as e:
        log(f"  crossref: {e}")
        return {}
    parts = ((m.get("issued") or {}).get("date-parts") or [[]])[0]
    return {
        "title": (m.get("title") or [""])[0],
        "authors": [
            " ".join(x for x in (a.get("given"), a.get("family")) if x)
            for a in (m.get("author") or [])
        ],
        "year": str(parts[0]) if parts else "",
        "venue": (m.get("container-title") or [""])[0],
        # Crossref abstracts arrive as a JATS XML fragment.
        "abstract": " ".join(re.sub(r"<[^>]+>", " ", m.get("abstract") or "").split()),
    }


def arxiv_search(title: str) -> str:
    """Title search against arXiv itself. Preferred over Semantic Scholar for bare
    titles because the goal is an arXiv ID and arXiv does not rate-limit like S2."""
    q = urllib.parse.quote(f'ti:"{title}"', safe=':')
    url = f"https://export.arxiv.org/api/query?search_query={q}&max_results=1"
    try:
        root = ET.fromstring(get(url, timeout=90))
    except Exception as e:
        log(f"  arxiv search: {e}")
        return ""
    el = root.find("a:entry/a:id", {"a": "http://www.w3.org/2005/Atom"})
    if el is None or not el.text:
        return ""
    m = re.search(rf"abs/({ARXIV_NEW}|{ARXIV_OLD})", el.text)
    return m.group(1) if m else ""


def s2_lookup(kind: str, value: str) -> dict | None:
    """Ask Semantic Scholar for cross-IDs. This is what finds an arXiv twin of a
    paywalled paper, which is the single highest-value step in the whole ladder."""
    prefix = {"doi": "DOI:", "arxiv": "ARXIV:", "url": "URL:"}.get(kind)
    if prefix is None:
        ident = "search:" + value
    else:
        ident = prefix + value

    fields = "title,abstract,year,authors,externalIds,openAccessPdf,venue"
    if ident.startswith("search:"):
        url = ("https://api.semanticscholar.org/graph/v1/paper/search"
               f"?query={urllib.parse.quote(value)}&limit=1&fields={fields}")
    else:
        url = ("https://api.semanticscholar.org/graph/v1/paper/"
               f"{urllib.parse.quote(ident, safe=':/')}?fields={fields}")

    try:
        data = json.loads(get(url))
    except urllib.error.HTTPError as e:
        log(f"  semantic scholar: HTTP {e.code}")
        return None
    except Exception as e:  # network, JSON, anything
        log(f"  semantic scholar: {e}")
        return None

    if "data" in data:
        hits = data.get("data") or []
        return hits[0] if hits else None
    return data or None


def arxiv_meta(arxiv_id: str) -> dict:
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(get(url))
    except Exception as e:
        log(f"  arxiv api: {e}")
        return {}
    entry = root.find("a:entry", ns)
    if entry is None:
        return {}

    def text(tag: str) -> str:
        el = entry.find(f"a:{tag}", ns)
        return " ".join(el.text.split()) if el is not None and el.text else ""

    published = text("published")
    return {
        "title": text("title"),
        "abstract": text("summary"),
        "year": published[:4] if published else "",
        "authors": [
            " ".join(a.text.split())
            for a in entry.findall("a:author/a:name", ns)
            if a.text
        ],
    }


# --- arXiv e-print --------------------------------------------------------


def safe_extract(tf: tarfile.TarFile, dest: Path) -> None:
    dest = dest.resolve()
    for m in tf.getmembers():
        target = (dest / m.name).resolve()
        if not str(target).startswith(str(dest)):
            raise RuntimeError(f"unsafe path in archive: {m.name}")
        if m.issym() or m.islnk():
            continue
    tf.extractall(dest)


def fetch_eprint(arxiv_id: str, dest: Path) -> tuple[str, Path | None]:
    """Download and unpack arXiv source. Returns (kind, path) where kind is one of
    'latex' (source tree unpacked), 'pdf' (author uploaded PDF only), 'none'."""
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    log(f"  fetching e-print: {url}")
    try:
        blob = get(url)
    except Exception as e:
        log(f"  e-print unavailable: {e}")
        return "none", None

    if blob[:4] == b"%PDF":
        pdf = dest / "source.pdf"
        pdf.write_bytes(blob)
        return "pdf", pdf

    if blob[:2] == b"\x1f\x8b":
        try:
            inner = gzip.decompress(blob)
        except Exception as e:
            log(f"  gunzip failed: {e}")
            return "none", None
    else:
        inner = blob

    src = dest / "src"
    src.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(inner)) as tf:
            safe_extract(tf, src)
        return "latex", src
    except tarfile.ReadError:
        pass  # single-file submission: the gunzipped blob IS the .tex

    if inner[:4] == b"%PDF":
        pdf = dest / "source.pdf"
        pdf.write_bytes(inner)
        return "pdf", pdf

    single = src / "main.tex"
    single.write_bytes(inner)
    return "latex", src


# --- LaTeX assembly -------------------------------------------------------

INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
# Whole-line comments are stripped (authors often leave large commented-out
# passages that would otherwise be read as body text), but ppread's own
# provenance markers must survive so the agent can tell files apart.
COMMENT_LINE_RE = re.compile(r"^[ \t]*%(?! \[ppread\]).*$", re.M)


def find_main_tex(root: Path) -> Path | None:
    """The main file is the one that opens the document. Prefer a file having both
    \\documentclass and \\begin{document}; fall back to either signal alone."""
    both, decl, begun = [], [], []
    for p in sorted(root.rglob("*.tex")):
        try:
            t = p.read_text("utf-8", errors="replace")
        except OSError:
            continue
        has_decl = "\\documentclass" in t
        has_begin = "\\begin{document}" in t
        if has_decl and has_begin:
            both.append(p)
        elif has_decl:
            decl.append(p)
        elif has_begin:
            begun.append(p)
    for bucket in (both, begun, decl):
        if bucket:
            # Shallowest path wins; ties broken by size (the real main file is
            # usually the larger of same-depth candidates).
            return sorted(bucket, key=lambda p: (len(p.parts), -p.stat().st_size))[0]
    return None


def resolve_input(name: str, base: Path, root: Path) -> Path | None:
    name = name.strip()
    cands = [name, name + ".tex"] if not name.endswith(".tex") else [name]
    for c in cands:
        for parent in (base, root):
            p = (parent / c)
            if p.is_file():
                return p
    return None


def expand(path: Path, root: Path, seen: set[Path], depth: int = 0) -> str:
    rp = path.resolve()
    if rp in seen or depth > 12:
        return f"% [ppread] skipped recursive include: {path.name}\n"
    seen.add(rp)
    text = path.read_text("utf-8", errors="replace")

    def sub(m: re.Match[str]) -> str:
        target = resolve_input(m.group(1), path.parent, root)
        if target is None:
            return f"% [ppread] missing include: {m.group(1)}\n"
        return (f"\n% [ppread] >>> {target.relative_to(root)}\n"
                + expand(target, root, seen, depth + 1)
                + f"\n% [ppread] <<< {target.relative_to(root)}\n")

    return INPUT_RE.sub(sub, text)


def assemble(root: Path, strip_comments: bool) -> str | None:
    main = find_main_tex(root)
    if main is None:
        return None
    log(f"  main tex: {main.relative_to(root)}")
    text = expand(main, root, set())
    if strip_comments:
        text = COMMENT_LINE_RE.sub("", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# --- output ---------------------------------------------------------------


def slugify(title: str, fallback: str) -> str:
    if not title:
        return fallback
    t = unicodedata.normalize("NFKD", title)
    t = re.sub(r"[^\w\s-]", "", t, flags=re.U).strip().lower()
    t = re.sub(r"[\s_]+", "-", t)
    return t[:60].strip("-") or fallback


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve a paper to its best available full text.")
    ap.add_argument("source", help="arXiv ID/URL, DOI, publisher URL, or a title to search")
    ap.add_argument("--out", default=".ppread", help="working directory (default: .ppread)")
    ap.add_argument("--keep-comments", action="store_true",
                    help="keep whole-line LaTeX comments (stripped by default)")
    args = ap.parse_args()

    kind, value = identify(args.source)
    log(f"identified as {kind}: {value}")

    meta: dict = {"title": "", "authors": [], "year": "", "doi": "", "arxiv_id": "",
                  "abstract": "", "venue": "", "input": args.source}
    pdf_url = ""

    if kind == "arxiv":
        meta["arxiv_id"] = value
    else:
        # Metadata first, from the source that actually covers this kind of id.
        if kind == "doi":
            meta["doi"] = value
            for k, v in crossref_meta(value).items():
                if v:
                    meta[k] = v
        elif kind == "query":
            aid = arxiv_search(value)
            if aid:
                meta["arxiv_id"] = aid
                log(f"  arxiv title match: {aid}")

        # Semantic Scholar is consulted only to find an arXiv twin we do not have.
        if not meta["arxiv_id"]:
            rec = s2_lookup(kind, value)
            if rec:
                ext = rec.get("externalIds") or {}
                meta["arxiv_id"] = ext.get("ArXiv", "") or ""
                meta["doi"] = meta["doi"] or ext.get("DOI", "")
                for field in ("title", "abstract", "venue"):
                    if not meta[field] and rec.get(field):
                        meta[field] = rec[field]
                if not meta["year"] and rec.get("year"):
                    meta["year"] = str(rec["year"])
                if not meta["authors"]:
                    meta["authors"] = [a.get("name", "")
                                       for a in (rec.get("authors") or [])]
                pdf_url = ((rec.get("openAccessPdf") or {}).get("url")) or ""
                if meta["arxiv_id"]:
                    log(f"  found arXiv twin: {meta['arxiv_id']}")

    if meta["arxiv_id"]:
        am = arxiv_meta(meta["arxiv_id"])
        for k, v in am.items():
            if v and not meta.get(k):
                meta[k] = v

    slug = slugify(meta["title"], meta["arxiv_id"] or "paper")
    workdir = Path(args.out) / slug
    workdir.mkdir(parents=True, exist_ok=True)

    result = {"slug": slug, "workdir": str(workdir), "meta": meta}

    if meta["arxiv_id"]:
        kind2, path = fetch_eprint(meta["arxiv_id"], workdir)
        if kind2 == "latex" and path is not None:
            text = assemble(path, strip_comments=not args.keep_comments)
            if text:
                out = workdir / "source.tex"
                out.write_text(text, "utf-8")
                figs = sorted(
                    str(p.relative_to(path))
                    for ext in ("*.png", "*.jpg", "*.jpeg", "*.pdf", "*.eps")
                    for p in path.rglob(ext)
                )
                result |= {"route": "latex", "tier": 1,
                           "source_path": str(out),
                           "chars": len(text),
                           "figures_dir": str(path),
                           "figures": figs[:80]}
            else:
                result |= {"route": "needs-pdf", "tier": 6,
                           "pdf_url": f"https://arxiv.org/pdf/{meta['arxiv_id']}",
                           "reason": "e-print unpacked but no main .tex found"}
        elif kind2 == "pdf":
            result |= {"route": "needs-pdf", "tier": 6, "pdf_path": str(path),
                       "reason": "author submitted PDF only, no LaTeX source"}
        else:
            result |= {"route": "needs-html", "tier": 4,
                       "html_url": f"https://arxiv.org/html/{meta['arxiv_id']}",
                       "pdf_url": f"https://arxiv.org/pdf/{meta['arxiv_id']}",
                       "reason": "e-print not available"}
    elif pdf_url or meta["doi"] or kind == "url":
        result |= {"route": "needs-pdf" if pdf_url else "needs-html",
                   "tier": 5,
                   "pdf_url": pdf_url,
                   "page_url": value if kind == "url" else (
                       f"https://doi.org/{meta['doi']}" if meta["doi"] else ""),
                   "reason": "no arXiv source exists for this paper"}
    else:
        # Nothing identified it and nothing retrievable was found. Say so loudly:
        # a silent tier-5 with no URL leaves the agent with nothing to act on.
        result |= {"route": "unresolved", "tier": 0,
                   "reason": "could not resolve this reference to any retrievable "
                             "source (lookup services unreachable or no match); "
                             "ask the user for an arXiv ID, a DOI, or a direct URL"}

    (workdir / "meta.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

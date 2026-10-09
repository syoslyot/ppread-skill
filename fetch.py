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
import shutil
import subprocess
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
UA = ("ppread/0.2 (+https://github.com/syoslyot/ppread-skill" +
      (f"; mailto:{_CONTACT})" if _CONTACT else ")"))
TIMEOUT = 45

ARXIV_NEW = r"\d{4}\.\d{4,5}"
ARXIV_OLD = r"[a-z-]+(?:\.[A-Z]{2})?/\d{7}"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>&]+")


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def get(url: str, accept: str | None = None, retries: int = 3,
        timeout: int = TIMEOUT, headers: dict | None = None) -> bytes:
    """Keyless Semantic Scholar rate-limits hard and arXiv's search endpoint is slow
    enough to time out, so both classes of failure are retried with backoff."""
    delay = 3.0
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
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


# --- output location config ---
#
# Where lectures land is the one thing this tool cannot infer. Guessing means
# writing into whatever directory the agent happened to start in — someone
# else's repo, a home directory. So the location is asked once and remembered.

CONFIG_PATH = (Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
               / "ppread" / "config.json")


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text("utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", "utf-8")


def resolve_out(cli_out: str | None) -> tuple[Path | None, dict]:
    """(destination, config). A None destination means nothing is configured yet
    and the caller must ask before touching the network or the filesystem."""
    cfg = load_config()
    if cli_out:
        return Path(cli_out).expanduser(), cfg
    mode = cfg.get("mode")
    if mode == "fixed" and cfg.get("path"):
        return Path(cfg["path"]).expanduser(), cfg
    if mode == "cwd":
        return Path.cwd() / (cfg.get("dir") or "papers"), cfg
    return None, cfg


def needs_output_config() -> dict:
    return {
        "route": "needs-output-config",
        "cwd": str(Path.cwd()),
        "suggested_cwd_mode": str(Path.cwd() / "papers"),
        "config_path": str(CONFIG_PATH),
        "reason": "no output location has been chosen yet; ask the user, then "
                  "re-run with --set-output 'fixed:/abs/path' or 'cwd:papers'",
    }


# --- source identification ------------------------------------------------


def identify(raw: str) -> tuple[str, str]:
    """Classify a user-supplied reference into (kind, value)."""
    s = raw.strip()

    # A path that exists wins over every pattern below: a local file is not
    # something to look up, and a filename can otherwise look like anything.
    if Path(s).expanduser().is_file():
        return "file", str(Path(s).expanduser().resolve())

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


def clean_authors(names: list[str]) -> list[str]:
    """Drop punctuation-only fragments: the "\\\\" line breaks inside a LaTeX
    \\author{...} block can survive extraction as standalone entries (a bare ":"),
    and those are never names."""
    return [n for n in names if any(c.isalnum() for c in n)]


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
        "authors": clean_authors([
            " ".join(x for x in (a.get("given"), a.get("family")) if x)
            for a in (m.get("author") or [])
        ]),
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
        "authors": clean_authors([
            " ".join(a.text.split())
            for a in entry.findall("a:author/a:name", ns)
            if a.text
        ]),
    }


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
    path = f"/paper/search/match?query={urllib.parse.quote(query)}&fields=title,year,externalIds,authors"
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
        return {"query": query, "status": "exact", **s2_ids(rec),
                "authors": clean_authors([a.get("name", "") for a in rec.get("authors") or []])}
    return {"query": query, "status": "mismatch", "candidate": rec.get("title") or ""}


def verify_title(query: str) -> dict:
    try:
        return match_status(query, title_match(query))
    except urllib.error.HTTPError as e:
        return {"query": query, "status": "error", "reason": f"HTTP {e.code}"}
    except Exception as e:
        return {"query": query, "status": "error", "reason": str(e)}


GRAPH_FIELDS = "title,year,authors,externalIds,citationCount,isInfluential,intents"
GRAPH_PAGE = 1000
# Citations come newest-first and the API cannot sort them by impact; offset+limit
# is capped below 10000. Past three pages a keyless run spends minutes in backoff
# only to collect more recent, rarely-cited papers, so three is where it stops.
GRAPH_PAGES = 3
GRAPH_TOP_CITATIONS = 50


def graph_node(edge: dict, side: str) -> dict:
    p = edge.get(side) or {}
    return {**s2_ids(p),
            "authors": clean_authors([a.get("name", "") for a in p.get("authors") or []]),
            "citations": p.get("citationCount") or 0,
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
        return {"route": "search-unavailable", "query": query,
                "reason": str(e) or type(e).__name__}

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


# --- local files ---


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


# --- folder identity ------------------------------------------------------
#
# One folder holds one paper. Two papers can still want the same folder: the slug
# comes from the title, and titles collide ("A Survey of ..." twice over, a
# workshop paper later reprinted, a 60-char truncation that erases the difference).
# Left unchecked the damage is silent — a lecture ends up describing a different
# paper than the source lying next to it, and nothing in either file says so.


DOC_FILES = ("broad.md", "deep.md", "research.md", "broad.part.md", "deep.part.md",
             "research.part.md", "lecture.md")
MODES = {"paper": ("broad", "deep"), "slides": ("broad", "deep", "research")}


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


def doc_kind(workdir: Path) -> str:
    """The kind a lecture in this folder records, or 'paper' when a lecture exists
    but doesn't record a kind—all lectures predate the kind field. Returns '' only
    when no lecture file exists at all. A file only counts when its front matter
    marks it as ppread's: broad.md or research.md are also natural names for the
    user's own notes, and one of those must not decide a deck's kind."""
    found_lecture = False
    for name in DOC_FILES:
        fields = front_matter(workdir / name)
        if fields and (fields.get("generated") == "claude"
                       or fields.get("type") == "reading" or "mode" in fields):
            found_lecture = True
            kind = fields.get("kind", "")
            if kind in MODES:
                return kind
    if found_lecture:
        return "paper"
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


def _norm_arxiv(v: str) -> str:
    return re.sub(r"^arxiv:|v\d+$", "", (v or "").strip().lower())


def _norm_title(v: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (v or "").lower()).strip()


def same_paper(ident: dict, meta: dict) -> bool:
    """Strongest available identifier wins, within one course: two decks share
    a chapter title far more often than two papers share a title, so differing
    courses settle it first. An arXiv id or a DOI settles it outright; only when
    one side lacks both does the comparison fall back to the title, normalised so
    that casing and punctuation do not fake a conflict."""
    c1, c2 = _norm_title(ident.get("course", "")), _norm_title(meta.get("course", ""))
    if c1 and c2 and c1 != c2:
        return False
    a1, a2 = _norm_arxiv(ident.get("arxiv", "")), _norm_arxiv(meta.get("arxiv_id", ""))
    if a1 and a2:
        return a1 == a2
    d1, d2 = (ident.get("doi", "") or "").strip().lower(), (meta.get("doi", "") or "").strip().lower()
    if d1 and d2:
        return d1 == d2
    t1, t2 = _norm_title(ident.get("title", "")), _norm_title(meta.get("title", ""))
    return bool(t1) and t1 == t2


RESOLVE = ("if it is the same paper, delete or rename the folder that is already "
           "there; if it is a different paper, re-run with --title \"<a title that "
           "tells the two apart>\" or --out <another directory>. Do not rename the "
           "folder by hand afterwards — fetch.py derives it from the title.")


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
    recorded = doc_kind(src.parent)
    # A lecture speaks for the folder's one source. A second file beside it is not
    # that document, and letting the lecture claim it would write a chapter's
    # deep.md from a downloaded paper, or nest a talk deck inside a paper.
    others = sorted(p.name for p in src.parent.glob("*") if p.is_file() and p != src
                    and p.name not in DOC_FILES and not p.name.startswith(".")) if recorded else []
    if others:
        return {"route": "conflict", "workdir": str(src.parent), "path": str(src),
                "reason": f"{src.parent} already holds a {recorded} lecture and its "
                          f"source ({', '.join(others)}); {src.name} is a different "
                          "file in that folder",
                "resolve": "move the file out of that folder and re-run on it there"}
    if kind_override and recorded and kind_override != recorded:
        return {"route": "conflict", "workdir": str(src.parent), "path": str(src),
                "reason": f"--kind {kind_override} contradicts the {recorded} lecture "
                          f"already in {src.parent}; re-running would move the file "
                          "into a second, nested folder",
                "resolve": "drop --kind to keep this folder's kind, or move the file "
                           "out of the folder first if it really is a different "
                           "document"}
    kind = kind_override or recorded or (pdf_kind(src, info) if is_pdf else "paper")
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
    # Re-run beside its own lecture: the lecture already names the deck, so omitted
    # names are read back from it, and differing ones must surface as a conflict
    # in this folder rather than mint a second one nested inside it.
    beside = doc_kind(src.parent) == "slides"
    if beside:
        fm = next((f for f in (front_matter(src.parent / n) for n in DOC_FILES) if f), {})
        course, title = course or fm.get("course", ""), title or fm.get("title", "")
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
    elif beside or (src.parent.name == slug and src.parent.parent.name == course_slug):
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


def _subdirs(d: Path) -> list[Path]:
    try:
        return sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError as e:
        log(f"  {d}: {e}")
        return []


def _holds_file(d: Path) -> bool:
    try:
        return any(p.is_file() and not p.name.startswith(".") for p in d.iterdir())
    except OSError as e:
        log(f"  {d}: {e}")
        return False


def _has_src(d: Path) -> bool:
    try:
        return (d / "src").is_dir()
    except OSError:
        return False  # _holds_file already logged the unreadable folder


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
    subdirectories hold figures, not sources. A course may also hold loose files
    (a deck not yet adopted, a syllabus): a folder with chapter subfolders and no
    lecture of its own is still a course. Only slides chapters make a course: a
    paper's own subfolder (figs/) must not turn the paper into one. A src/ marks a paper folder even
    with no file beside it: fetch_eprint unpacks there before source.tex exists,
    and an e-print with no main .tex never gets one."""
    papers = []
    for d in _subdirs(root) if root.is_dir() else []:
        if d.name == "assets":
            continue
        held, src = _holds_file(d), _has_src(d)
        # A lecture-less subfolder counts as a chapter only beside no loose file: a
        # paper's figs/ of landscape figure PDFs looks exactly like a new chapter.
        chapters = [c for c in _subdirs(d) if c.name not in ("src", "assets")
                    and _holds_file(c) and (doc_kind(c) == "slides" or not held
                                            and lecture_docs(c)["kind"] == "slides")]
        if not (held or src or chapters):
            continue
        if src or not chapters or doc_kind(d):
            papers.append(library_row(d, d.name))
        else:
            papers += [library_row(c, f"{d.name}/{c.name}") for c in chapters]
    return {"route": "list", "library": str(root), "papers": papers}


# --- output ---------------------------------------------------------------

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
      - kind
      - course
      - mode
      - year
      - lecture_read
  - type: table
    name: 全部講義
    order:
      - title
      - kind
      - course
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


# The limit is the filesystem's, not a matter of taste: a single path component
# is capped at 255 bytes on ext4, xfs and APFS, and the slug is pure ASCII so a
# character is a byte. 200 leaves room to spare while keeping every realistic
# title whole — the earlier 60 truncated ordinary ones (BERT's own title is 79).
# Changing this number re-derives the folder name of every paper already on disk,
# so it is a breaking change to how a paper is addressed, not a cosmetic tweak.
SLUG_MAX = 200


def resolve_slug(title_override: str, meta_title: str) -> tuple[str, str]:
    """The folder slug for a network route, or ("", reason) when none can be
    derived yet. Never falls back to an ID-shaped name: that would mint a
    workdir different from the one folder_conflict() checks, silently bypassing
    the duplicate-paper guard on every transient metadata failure."""
    title = title_override or meta_title
    if not title:
        return "", ("metadata lookup returned no title — this is often transient "
                     "(e.g. a temporary HTTP error); retry the fetch once before "
                     "asking the user for one")
    slug = slugify(title, "")
    if not slug:
        return "", (f"the title {title!r} leaves no ASCII characters to name a "
                     "folder with; re-run with --title \"<the paper's English "
                     "title>\"")
    return slug, ""


def slugify(title: str, fallback: str) -> str:
    """ASCII, lowercase, hyphen-separated. The folder name gets pasted into shell
    commands (pdftotext, markitdown) and into Markdown links, where a space has to
    be quoted in one and percent-escaped in the other. NFKD plus an ASCII round
    trip folds accents onto their base letters (Scholkopf, not Sch_lkopf) and drops
    what has no ASCII form at all, so a title in another script yields "" and the
    caller asks for an English one rather than inventing a name."""
    t = unicodedata.normalize("NFKD", title)
    t = t.encode("ascii", "ignore").decode()
    t = re.sub(r"[^\w\s-]", "", t).strip().lower()
    t = re.sub(r"[\s_]+", "-", t)
    if len(t) > SLUG_MAX:  # cut back to a word boundary, not "...netwo"
        t = t[:SLUG_MAX].rpartition("-")[0] or t[:SLUG_MAX]
    return t.strip("-") or fallback


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve a paper to its best available full text.")
    ap.add_argument("source", nargs="?",
                    help="arXiv ID/URL, DOI, publisher URL, or a title to search")
    ap.add_argument("--out", default=None,
                    help="one-off override of the output directory: the configured "
                         "library on a network route, or the input file's own "
                         "directory on a local one")
    ap.add_argument("--set-output", metavar="MODE:VALUE",
                    help="remember where lectures go: 'fixed:/abs/path' for one "
                         "location always, or 'cwd:papers' for <current dir>/papers")
    ap.add_argument("--title", default=None,
                    help="English title overriding the one found; decides the folder "
                         "name. Needed for a local file whose metadata has no title "
                         "or no ASCII in it, and to separate two papers whose titles "
                         "land on the same folder")
    ap.add_argument("--kind", choices=("paper", "slides"),
                    help="local PDF only: force the kind when the page size cannot be "
                         "read or misleads (a portrait slide deck)")
    ap.add_argument("--course", default=None,
                    help="local slides only: the course name; with --title it names "
                         "the <course>/<chapter> folder")
    ap.add_argument("--show-config", action="store_true",
                    help="print the remembered output location and exit")
    ap.add_argument("--keep-comments", action="store_true",
                    help="keep whole-line LaTeX comments (stripped by default)")
    ap.add_argument("--verify", nargs="+", metavar="TITLE",
                    help=f"check up to {VERIFY_MAX} paper titles against Semantic "
                         "Scholar; only an exact normalised title match counts")
    ap.add_argument("--graph", metavar="ID_OR_TITLE",
                    help="references and citations of a paper from Semantic Scholar, "
                         "ranked by influence then citation count")
    ap.add_argument("--search", metavar="QUERY",
                    help="papers on a topic from Semantic Scholar, most-cited first; "
                         "quote phrases inside the query: '\"systolic array\"'")
    ap.add_argument("--since", type=int, metavar="YEAR",
                    help="with --search: only papers from YEAR onward")
    ap.add_argument("--limit", type=int, default=SEARCH_LIMIT, metavar="N",
                    help=f"with --search: at most N papers (default {SEARCH_LIMIT}, "
                         f"max {SEARCH_MAX})")
    ap.add_argument("--list", nargs="?", const="", metavar="DIR",
                    help="list paper folders and the state of their lectures; "
                         "defaults to the configured library")
    args = ap.parse_args()

    if args.verify:
        if len(args.verify) > VERIFY_MAX:
            log(f"--verify takes at most {VERIFY_MAX} titles per call")
            return 2
        print(json.dumps({"route": "verify",
                          "results": [verify_title(t) for t in args.verify]},
                         ensure_ascii=False, indent=2))
        return 0

    if args.graph:
        print(json.dumps(graph(args.graph), ensure_ascii=False, indent=2))
        return 0

    if args.search:
        if not 1 <= args.limit <= SEARCH_MAX:
            log(f"--limit must be between 1 and {SEARCH_MAX}")
            return 2
        print(json.dumps(search(args.search, args.since, args.limit),
                         ensure_ascii=False, indent=2))
        return 0

    if args.list is not None:
        root = Path(args.list).expanduser() if args.list else resolve_out(None)[0]
        out = needs_output_config() if root is None else list_library(root)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.show_config:
        cfg = load_config()
        out, _ = resolve_out(None)
        print(json.dumps({"config_path": str(CONFIG_PATH), "config": cfg,
                          "resolves_to": str(out) if out else None},
                         ensure_ascii=False, indent=2))
        return 0

    if args.set_output:
        mode, _, val = args.set_output.partition(":")
        if mode == "fixed":
            if not val:
                log("fixed: needs a path"); return 2
            cfg = {"mode": "fixed", "path": str(Path(val).expanduser().resolve())}
        elif mode == "cwd":
            cfg = {"mode": "cwd", "dir": val or "papers"}
        else:
            log(f"unknown mode {mode!r}: use 'fixed:/abs/path' or 'cwd:papers'")
            return 2
        save_config(cfg)
        out, _ = resolve_out(None)
        print(json.dumps({"saved": str(CONFIG_PATH), "config": cfg,
                          "resolves_to": str(out)}, ensure_ascii=False, indent=2))
        return 0

    if not args.source:
        log("a source is required (arXiv ID, DOI, URL, or title)")
        return 2

    kind, value = identify(args.source)
    log(f"identified as {kind}: {value}")

    # A local file carries its own destination — the folder goes next to it — so
    # this route never has to ask the library question below.
    if kind == "file":
        override = Path(args.out).expanduser() if args.out else None
        result = adopt_local(Path(value), override, args.title or "",
                             args.kind or "", args.course or "")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.kind or args.course:
        log("--kind and --course apply to a local PDF only; a network source is always a paper")
        return 2

    # Gate before any network call or mkdir: never download into a directory the
    # user has not agreed to.
    out_root, _cfg = resolve_out(args.out)
    if out_root is None:
        print(json.dumps(needs_output_config(), ensure_ascii=False, indent=2))
        return 0

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
                    meta["authors"] = clean_authors([a.get("name", "")
                                                     for a in (rec.get("authors") or [])])
                pdf_url = ((rec.get("openAccessPdf") or {}).get("url")) or ""
                if meta["arxiv_id"]:
                    log(f"  found arXiv twin: {meta['arxiv_id']}")

    if meta["arxiv_id"]:
        am = arxiv_meta(meta["arxiv_id"])
        for k, v in am.items():
            if v and not meta.get(k):
                meta[k] = v

    if args.title and not meta["title"]:
        # --title disambiguates the folder name; it must not overwrite a title
        # the lookup actually verified, only fill one the lookup left empty.
        meta["title"] = args.title

    slug, title_reason = resolve_slug(args.title or "", meta["title"])
    if not slug:
        print(json.dumps({"route": "needs-title", "meta": meta, "reason": title_reason},
                         ensure_ascii=False, indent=2))
        return 0
    # One folder per paper: the source and the lecture the agent writes live
    # side by side. The folder is created only if there is something to put in
    # it — a failed lookup should not litter the tree with empty directories.
    workdir = out_root / slug

    # Before the download, not after: a folder that turns out to belong to another
    # paper makes the whole fetch pointless, and finding that out first costs one
    # stat instead of a 10 MB e-print.
    conflict = folder_conflict(workdir, meta, slug)
    if conflict:
        print(json.dumps(conflict, ensure_ascii=False, indent=2))
        return 0

    result = {"slug": slug, "workdir": str(workdir), "meta": meta,
              "docs": lecture_docs(workdir, "paper")}

    if meta["arxiv_id"]:
        workdir.mkdir(parents=True, exist_ok=True)
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

    # No meta.json: the metadata belongs in the lecture's front matter, where a
    # reader actually sees it. Writing it twice means two files to keep in sync.
    if result["route"] != "unresolved":
        ensure_base(out_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

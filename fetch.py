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


# --- local files ---


def pdf_title(path: Path) -> tuple[str, str, str]:
    """(title, author, year) from the PDF's own metadata via pdfinfo, when
    available. LaTeX-produced PDFs almost always carry a usable /Title."""
    if not shutil.which("pdfinfo"):
        return "", "", ""
    try:
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True,
                             text=True, timeout=20).stdout
    except Exception as e:
        log(f"  pdfinfo: {e}")
        return "", "", ""
    fields = {}
    for line in out.splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    year = ""
    m = re.search(r"\b(19|20)\d{2}\b", fields.get("CreationDate", ""))
    if m:
        year = m.group(0)
    return fields.get("Title", ""), fields.get("Author", ""), year


# --- folder identity ------------------------------------------------------
#
# One folder holds one paper. Two papers can still want the same folder: the slug
# comes from the title, and titles collide ("A Survey of ..." twice over, a
# workshop paper later reprinted, a 60-char truncation that erases the difference).
# Left unchecked the damage is silent — lecture.md ends up describing a different
# paper than the source lying next to it, and nothing in either file says so.


def lecture_identity(workdir: Path) -> dict | None:
    """Which paper a folder already holds, read from lecture.md's YAML front
    matter. That front matter is the only on-disk record of it — ppread writes no
    meta.json on purpose — and its keys are fixed by lecture-format.md, so a plain
    'key: value' scan is exact here and needs no YAML parser. None means no lecture
    yet; an empty dict means one exists but identifies nothing."""
    f = workdir / "lecture.md"
    if not f.is_file():
        return None
    try:
        text = f.read_text("utf-8", errors="replace")
    except OSError as e:
        log(f"  lecture.md: {e}")
        return {}
    if not text.startswith("---"):
        return {}
    body = text.partition("\n")[2].partition("\n---")[0]
    ident = {}
    for line in body.splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip() in ("title", "doi", "arxiv"):
            ident[k.strip()] = v.strip().strip("\"'")
    return ident


def _norm_arxiv(v: str) -> str:
    return re.sub(r"^arxiv:|v\d+$", "", (v or "").strip().lower())


def _norm_title(v: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (v or "").lower()).strip()


def same_paper(ident: dict, meta: dict) -> bool:
    """Strongest available identifier wins. An arXiv id or a DOI settles it
    outright; only when one side lacks both does the comparison fall back to the
    title, normalised so that casing and punctuation do not fake a conflict."""
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
    """A conflict result, or None when the folder is free or already this paper's."""
    ident = lecture_identity(workdir)
    if ident is None or same_paper(ident, meta):
        return None
    held = ident.get("title") or ident.get("arxiv") or ident.get("doi")
    return {"route": "conflict", "slug": slug, "workdir": str(workdir), "meta": meta,
            "occupant": {k: ident.get(k, "") for k in ("title", "doi", "arxiv")},
            "reason": f"{workdir} already holds a lecture for "
                      + (f"a different paper ({held})" if held
                         else "a paper it does not identify")
                      + "; refusing to put a second paper in one folder",
            "resolve": RESOLVE}


def adopt_local(src: Path, out_override: Path | None, title_override: str) -> dict:
    """Give a local file the same shape every other route produces: one folder per
    paper, holding the source and (later) the lecture. The folder is created BESIDE
    the file: the file already sits where the user put it, and hauling it off to the
    configured library would relocate something nobody asked to have moved. Into
    that folder the file is MOVED, not copied — two copies of a 10 MB thesis in the
    same tree is not a library."""
    title, author, year = pdf_title(src)
    if title_override:
        title = title_override
    meta = {"title": title, "authors": [author] if author else [], "year": year,
            "doi": "", "arxiv_id": "", "abstract": "", "venue": "",
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
                        if p.is_file() and p.name != "lecture.md")
        if others:
            return {"route": "conflict", "slug": slug, "workdir": str(workdir),
                    "meta": meta, "path": str(src), "occupant": {"files": others},
                    "reason": f"{workdir} already holds {', '.join(others)} and no "
                              "lecture.md saying which paper that is",
                    "resolve": RESOLVE}
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        log(f"  moved {src.name} -> {dest}")

    ext = dest.suffix.lower()
    return {"slug": slug, "workdir": str(workdir), "meta": meta,
            "route": "needs-pdf" if ext == ".pdf" else "local",
            "tier": 6 if ext == ".pdf" else 1,
            "pdf_path": str(dest) if ext == ".pdf" else "",
            "source_path": str(dest),
            "reason": "local file; no LaTeX source available"}


# --- output ---------------------------------------------------------------


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
    if len(t) > 60:  # cut back to a word boundary rather than leaving "...netwo"
        t = t[:60].rpartition("-")[0] or t[:60]
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
    ap.add_argument("--show-config", action="store_true",
                    help="print the remembered output location and exit")
    ap.add_argument("--keep-comments", action="store_true",
                    help="keep whole-line LaTeX comments (stripped by default)")
    args = ap.parse_args()

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
        result = adopt_local(Path(value), override, args.title or "")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Gate before any network call or mkdir: never download into a directory the
    # user has not agreed to.
    out_root, _cfg = resolve_out(args.out)
    if out_root is None:
        print(json.dumps({
            "route": "needs-output-config",
            "cwd": str(Path.cwd()),
            "suggested_cwd_mode": str(Path.cwd() / "papers"),
            "config_path": str(CONFIG_PATH),
            "reason": "no output location has been chosen yet; ask the user, then "
                      "re-run with --set-output 'fixed:/abs/path' or 'cwd:papers'",
        }, ensure_ascii=False, indent=2))
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

    slug = slugify(args.title or meta["title"], meta["arxiv_id"] or "paper")
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

    result = {"slug": slug, "workdir": str(workdir), "meta": meta}

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
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

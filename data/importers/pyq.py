#!/usr/bin/env python3
"""
Import Kerala PSC previous-year OMR question papers (PYQs) into the mocker
question-bank schema.

Source  : https://www.keralapsc.gov.in/answerkey_omrexams  (question booklet PDF
          + official answer key PDF, paired by question-paper code)
Licence : Kerala PSC permits reuse with accurate reproduction and prominent
          attribution.  Because "accurate reproduction" is a licence condition we
          never shuffle options -- the answer index is whatever the real paper had.
Output  : data/questions/pyq-<topic>.json   (never touches hand-authored banks)

Run:
    cd data/importers
    python3 pyq.py --limit 40
    python3 ../validate.py ../questions/pyq-*.json

Needs `pdftotext` (poppler-utils) on PATH.  Downloads and extracted text are
cached under cache/pyq/ (gitignored) so re-runs are resumable.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(HERE)                       # data/
PROJECT_DIR = os.path.dirname(DATA_DIR)                # repo root
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
CACHE_DIR = os.path.join(HERE, "cache", "pyq")
INDEX_CACHE = os.path.join(CACHE_DIR, "index")
PDF_CACHE = os.path.join(CACHE_DIR, "pdf")
TXT_CACHE = os.path.join(CACHE_DIR, "txt")
CLS_CACHE = os.path.join(CACHE_DIR, "cls")

BASE = "https://www.keralapsc.gov.in"
INDEX_URL = BASE + "/answerkey_omrexams?tid=All&page={page}"
INDEX_PAGES = 240                                      # page=0..239
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
POLITE_DELAY = 1.0                                     # seconds between requests
HTTP_RETRIES = 3

MIN_YEAR = 2019          # older PDFs are 100-dpi scans with junk text layers
MIN_TEXT_CHARS = 500     # below this the text layer is unusable
MIN_LETTER_RATIO = 0.60  # ASCII letters / non-space chars

# --- quality gates ---
MIN_STEM_WORDS = 15
MAX_STEM_WORDS = 60
# Match-the-following / multi-statement items are authentic Kerala PSC style and
# are kept when they are self-contained, so they get a longer word budget.
MAX_LIST_STEM_WORDS = 130
MAX_OPTION_LEN = 120
MAX_NON_ASCII_RATIO = 0.15

BAD_STEM_SUBSTRINGS = (
    "following table", "figure", "diagram", "passage", "underlined",
)

# pdftotext -layout sometimes glues a page footer onto the last option, e.g.
# option (D) of 13/2026 Q4 came out as "d c a b   A -3- 13/26".  Strip those.
FOOTER_RES = (
    re.compile(r"\[\s*P\.?\s*T\.?\s*O\.?\s*\.?\s*\]?", re.I),
    re.compile(r"SPACE\s+FOR\s+ROUGH\s+WORK", re.I),
    re.compile(r"\s+[A-D]\s+-\s*\d+\s*-\s*\d{1,3}/\d{2,4}\s*$"),
    re.compile(r"\s*-\s*\d+\s*-\s*$"),
    re.compile(r"\s+\d{1,3}/\d{2,4}\s*$"),
    re.compile(r"\s+[A-D]\s*$"),                     # bare alpha-code marker
)


def strip_footer(text: str) -> str:
    """Remove page-footer debris; repeat because footers arrive in pieces."""
    prev = None
    while prev != text:
        prev = text
        for rx in FOOTER_RES:
            text = rx.sub(" ", text)
        text = norm_ws(text)
    return text

# --- LLM ---
LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
LLM_MODEL = "qwen/qwen3.8-27b"
LLM_BATCH = 20
PROMPT_VERSION = "v2"              # bump to invalidate the classification cache
LLM_RPM = 30                       # hard ceiling: requests / minute
LLM_MIN_INTERVAL = 60.0 / LLM_RPM
LLM_429_SLEEP = 65
LLM_RETRIES = 3
# Groq also enforces a tokens-per-minute budget (8k TPM on the free tier for this
# model, i.e. ~4 batches/min).  We read x-ratelimit-remaining-tokens off every
# response and idle until the window resets rather than burning 429s.
LLM_TOKEN_HEADROOM = 3000
# Free-tier daily request cap is 1000; stop short of it and fall back to keywords
# rather than dying mid-run (the classification cache makes a resume cheap).
LLM_MAX_REQUESTS = 900

TOPICS = (
    "indian-history", "kerala", "indian-polity", "geography", "economy",
    "general-science", "arts-culture", "world-gk", "sports", "computers-tech",
    "environment",
)
DROP = "drop"
VALID_LABELS = set(TOPICS) | {DROP}

CLASSIFY_SYSTEM = (
    "You label Kerala PSC exam questions by subject for a General Knowledge quiz app. "
    "Reply with JSON only."
)
CLASSIFY_PROMPT = """Label each question with exactly one topic.

Topics:
- indian-history: Indian history, freedom struggle, dynasties, rulers, movements
- kerala: anything about Kerala -- its history, renaissance leaders, geography, districts, rivers, schemes, institutions
- indian-polity: Constitution, articles, parliament, judiciary, panchayati raj, acts, rights, commissions
- geography: physical/political geography of India and the world (not Kerala-specific)
- economy: economics, banking, budget, taxes, five-year plans, GDP, industry
- general-science: physics, chemistry, biology, human body, health, nutrition, diseases -- at school-syllabus level
- arts-culture: Indian art forms, dance, music, painting, architecture, festivals, heritage sites,
  awards (Jnanpith, Padma, Bharat Ratna, Oscars), Indian cinema, and Indian literature ONLY in the
  general-knowledge sense (who wrote a famous work, who won which prize)
- world-gk: world organisations, countries, capitals, world leaders, inventions, world history
- sports: sports, games, tournaments, players, trophies, venues
- computers-tech: computers, IT, internet, software, hardware, cyber law, e-governance
- environment: ecology, biodiversity, pollution, climate, wildlife, conservation, protected areas
- drop: NOT general knowledge.

Use "drop" for all of the following:
- maths / mental ability / reasoning / arithmetic / data interpretation
- English grammar, vocabulary, comprehension, figures of speech, phonetics, linguistics
- Malayalam, Tamil, Kannada, Hindi, Arabic or Sanskrit language questions
- post-specific technical content: surveying, civil / mechanical / electrical / electronics
  engineering, nursing, pharmacy, clinical medicine, veterinary, agriculture machinery,
  accountancy and audit procedure, law-exam section numbers, library science, printing
- pedagogy, teaching methodology, educational psychology, curriculum and evaluation theory
- DEGREE-LEVEL SUBJECT SPECIALISM of any kind, including literary criticism of specific poems,
  novels, plays or authors. These are asked in Higher Secondary School Teacher / Lecturer /
  Junior Instructor papers and are NOT general knowledge. Negative examples that must be "drop":
    * "In Mac Flecknoe, Dryden describes the streets ..."
    * "Which one among the following is not a Hyperbole used in 'To His Coy Mistress'?"
    * "Which statement(s) is/are true in the life Tess of the D'Urbervilles?"
    * "... guideline for poetry mentioned in the 'Preface to Lyrical Ballads'"
  A question about English/American literature, or close analysis of any single text, is "drop"
  even though it looks like "arts-culture".
- anything that needs a diagram, table, map or attached passage that is not in the text

KEEP (do not drop just for their shape): match-the-following, "List - I / List - II",
statement-and-reason and multi-statement questions. Those are normal Kerala PSC GK questions --
label them by their subject matter as long as the pairs or statements are printed in the stem.

When unsure between a GK topic and "drop", prefer "drop".

Return JSON exactly of this form, one entry per input id, no extra keys:
{"labels": [{"i": 1, "topic": "kerala"}, {"i": 2, "topic": "drop"}]}

Questions:
"""

# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

WS_RE = re.compile(r"\s+")


def norm_ws(s: str) -> str:
    """Collapse whitespace runs (incl. NBSP) to single spaces and strip."""
    return WS_RE.sub(" ", str(s).replace(" ", " ")).strip()


def norm_key(s: str) -> str:
    """Dedup key -- matches the normalisation used by data/validate.py."""
    return re.sub(r"\W+", " ", str(s).lower()).strip()


def slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0] or s[:maxlen]
    return s.strip("-")


def strip_tags(fragment: str) -> str:
    return norm_ws(html.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------- #
# Polite HTTP with retries + on-disk cache
# --------------------------------------------------------------------------- #

_last_request = [0.0]


def http_get(url: str, *, binary: bool = False):
    """GET with a browser UA, ~1 req/sec, and exponential-backoff retries."""
    for attempt in range(1, HTTP_RETRIES + 1):
        wait = POLITE_DELAY - (time.time() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
            return raw if binary else raw.decode("utf-8", "replace")
        except Exception as e:
            if attempt == HTTP_RETRIES:
                raise
            log(f"    [retry {attempt}/{HTTP_RETRIES - 1}] {type(e).__name__} {e} -- {url}")
            time.sleep(2 ** attempt)


def cached_get(url: str, path: str, *, binary: bool = False):
    """Fetch `url` unless `path` already holds it (resumability)."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        mode = "rb" if binary else "r"
        kw = {} if binary else {"encoding": "utf-8", "errors": "replace"}
        with open(path, mode, **kw) as fh:
            return fh.read(), True
    data = http_get(url, binary=binary)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if binary else "w"
    kw = {} if binary else {"encoding": "utf-8"}
    with open(path, mode, **kw) as fh:
        fh.write(data)
    return data, False


# --------------------------------------------------------------------------- #
# Index crawl
# --------------------------------------------------------------------------- #

# The details cell has been re-labelled several times over the years:
#   2024-2026  "Question Paper Code:079/2026"  "Question Paper Medium:English"  "Date Of Test:21-Aug-2026"
#   2023       "QUESTION CODE : 135/2023"      "MEDIUM OF QUESTION : MALAYALAM" "DATE OF TEST : 31/07/2023"
#   2019       "Question Paper Code: 037/2019" "Medium of Question: TAMIL"      "Date of Test: 02/08/2019"
#   2016       "Paper Code:-144/2016"          "Medium of question:- ENGLISH"   "Date of Test :- 03.11.2016"
#   2013       (no medium field at all)
# The separator inside the code itself also wobbles: "079/2026", "68-2026",
# "062-2026 - M/T/K", "115-2025 K".
# ...and the separator after a label is any of ":", "-", ".", "," or nothing
# ("Question Paper Code. 71/2024", "Medium of Question,English").
SEP = r"[\s:.,\-]*"
CODE_RE = re.compile(
    rf"(?:question\s+paper\s+code|question\s+code|paper\s+code){SEP}"
    r"(\d{1,4}\s*[/-]\s*\d{4}(?:\s*[-/ ]\s*[A-Za-z]{1,2}\b)?)", re.I)
LANGS = ("english", "malayalam", "tamil", "kannada", "hindi", "urdu", "arabic",
         "sanskrit", "malayalm", "tami")
MEDIUM_RE = re.compile(
    rf"(?:question\s+paper\s+medium|medium\s+of\s+questions?|medium){SEP}"
    r"([A-Za-z/,\s]+?)\s*"
    r"(?=(?:category|cat\b|name|department|post|paper|question|date|code|medium)\b|$)", re.I)
# Some rows write it the other way round: "Kannada Medium, Assistant Gr.II".
MEDIUM_SUFFIX_RE = re.compile(
    r"\b((?:" + "|".join(LANGS) + r")(?:\s*[/,]\s*(?:" + "|".join(LANGS) + r"))*)\s+medium\b",
    re.I)


def parse_medium(details: str) -> str:
    """Medium as a lowercase language list, or '' when the row does not state one."""
    m = MEDIUM_RE.search(details)
    if m:
        val = norm_ws(m.group(1)).lower().strip(" ,/")
        toks = [t for t in re.split(r"[/,\s]+", val) if t]
        lead = []
        for t in toks:                      # keep only the leading run of language names
            if t not in LANGS:
                break
            lead.append(t)
        if lead:
            return "/".join(lead)
    m = MEDIUM_SUFFIX_RE.search(details)
    return norm_ws(m.group(1)).lower() if m else ""
DATE_RE = re.compile(r"date\s*(?:of|Of)?\s*test\s*:?-?\s*([0-9A-Za-z][0-9A-Za-z./-]{5,})", re.I)
DATE_FALLBACK_RE = re.compile(r"\bdate\s*:?-?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", re.I)

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(raw: str) -> str | None:
    """'21-Aug-2026' | '02/08/2019' | '03.11.2016' -> ISO 'YYYY-MM-DD'."""
    if not raw:
        return None
    raw = raw.strip().rstrip(".")
    m = re.match(r"^(\d{1,2})[-/. ]([A-Za-z]{3,})[-/. ](\d{4})$", raw)
    if m and m.group(2)[:3].lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2)[:3].lower()]:02d}-{int(m.group(1)):02d}"
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", raw)
    if m:                                     # Kerala PSC writes day-first
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y}-{mo:02d}-{d:02d}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    return raw if m else None


def _split_code(raw: str | None):
    if not raw:
        return None
    m = re.match(r"\s*(\d{1,4})\s*[/-]\s*(\d{4})", raw)
    return (m.group(1), m.group(2)) if m else None


def norm_code(raw: str | None) -> str | None:
    """'079/2026' / '68-2026' / '080/2026/M' -> '79/2026' (padding + medium suffix dropped)."""
    parts = _split_code(raw)
    return f"{int(parts[0])}/{parts[1]}" if parts else None


def display_code(raw: str | None) -> str | None:
    """Canonical 'NNN/YYYY' the way Kerala PSC prints it on the booklet."""
    parts = _split_code(raw)
    return f"{parts[0]}/{parts[1]}" if parts else None


def parse_index_page(html_text: str) -> list[dict]:
    """One index page -> row dicts.  Cells: post | details | key-type | papers | keys | uploaded."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", html_text, re.S):
        tds = re.findall(r"<td[^>]*>.*?</td>", tr, re.S)
        if len(tds) < 6:
            continue                               # header / layout row
        post = strip_tags(tds[0])
        details = strip_tags(tds[1])
        keytype = strip_tags(tds[2])
        papers = re.findall(r'href="([^"]+\.pdf[^"]*)"', tds[3], re.I)
        keys = re.findall(r'href="([^"]+\.pdf[^"]*)"', tds[4], re.I)
        cm = CODE_RE.search(details)
        raw_code = cm.group(1) if cm else None
        med = parse_medium(details)
        dm = DATE_RE.search(details) or DATE_FALLBACK_RE.search(details)
        rows.append({
            "post": post,
            "details": details,
            "code": display_code(raw_code),
            "ncode": norm_code(raw_code),
            "medium": med,
            "date": parse_date(dm.group(1) if dm else ""),
            "final": "final" in keytype.lower(),
            "keytype": keytype or "Answer Key",
            "papers": [urllib.parse.urljoin(BASE, u) for u in papers],
            "keys": [urllib.parse.urljoin(BASE, u) for u in keys],
        })
    return rows


def crawl_index(pages: int, refresh: bool) -> list[dict]:
    all_rows: list[dict] = []
    for page in range(pages):
        path = os.path.join(INDEX_CACHE, f"page-{page:03d}.html")
        if refresh and os.path.exists(path):
            os.remove(path)
        try:
            body, hit = cached_get(INDEX_URL.format(page=page), path)
        except Exception as e:
            log(f"  [index] page {page} FAILED: {type(e).__name__} {e}")
            continue
        rows = parse_index_page(body)
        all_rows += rows
        if page % 20 == 0 or not rows:
            log(f"  [index] page {page:>3}: {len(rows)} rows{' (cached)' if hit else ''}")
        if not rows:
            break                                  # ran off the end of the listing
    return all_rows


def is_english(medium: str) -> bool:
    """Only pure-English papers.  'Malayalam/Tamil/Kannada' and 'Malayalam,Tamil,English'
    combined rows are skipped: their booklets use legacy Shree-Mal fonts that pdftotext
    cannot decode."""
    m = medium.strip().lower()
    if not m:
        return False
    parts = [p.strip() for p in re.split(r"[/,]", m) if p.strip()]
    return parts == ["english"]


# Common/general recruitment exams devote most of the paper to GK, so they are
# processed first.  Post-specific papers still get processed -- their trailing
# GK section yields good questions -- just later in the queue.
GENERAL_POST_RE = re.compile(
    r"\b(prelim\w*|degree level|10th level|plus two level|common\s+\w*exam|"
    r"l\.?d\.?\s*clerk|lower division clerk|ldc|l\.?g\.?s|last grade|"
    r"university assistant|secretariat assistant|company\s*/?\s*corporation|"
    r"clerk|cashier|typist|police constable|constable|civil police|excise|"
    r"sub inspector|si of police|special branch|"
    r"teacher|hsst|h\.?s\.?s\.?t|hst|full time junior language|"
    r"village extension officer|village field assistant|fireman|"
    r"junior co-?operative inspector|beat forest officer|forest)\b", re.I)
TECHNICAL_POST_RE = re.compile(
    r"\b(engineer|engineering|draftsman|draughtsman|overseer|tradesman|"
    r"instructor|surgeon|nurse|midwife|pharmacist|technician|mechanic|"
    r"electrician|lineman|operator|lecturer|laboratory|lab\b|radiographer|"
    r"physiotherapist|geologist|geophysicist|chemist|biochemist|analyst|"
    r"tracer|welder|fitter|turner|plumber|carpenter|blacksmith)\b", re.I)


def paper_priority(post: str) -> int:
    """0 = general/common exam (GK-heavy), 1 = post-specific/technical."""
    if TECHNICAL_POST_RE.search(post):
        return 1
    return 0 if GENERAL_POST_RE.search(post) else 1


ALPHA_FROM_NAME = re.compile(r"(?:set[-_ ]*|[-_ ])([A-D])\s*(?:\)|\.pdf|_|-)", re.I)


def alpha_from_url(url: str) -> str | None:
    name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
    m = ALPHA_FROM_NAME.search(name)
    return m.group(1).upper() if m else None


def select_papers(rows: list[dict]) -> tuple[list[dict], collections.Counter]:
    """Rows with BOTH a question paper and a key, English medium, test date >= MIN_YEAR.
    A Final Answer Key published as a separate row is matched back by paper code."""
    skips = collections.Counter()

    # Registry of every key URL we saw, so a final key filed on another page is reachable.
    finals: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r["final"] and r["ncode"] and r["keys"]:
            finals[(r["ncode"], r["medium"] or "?")].append(r)

    papers, seen_codes = [], {}
    for r in rows:
        if not r["papers"]:
            skips["no question paper (key-only row)"] += 1
            continue
        if not r["keys"]:
            skips["no answer key"] += 1
            continue
        if not is_english(r["medium"]):
            skips[f"non-English medium ({r['medium'] or 'unstated'})"] += 1
            continue
        if not r["date"]:
            skips["no test date"] += 1
            continue
        if int(r["date"][:4]) < MIN_YEAR:
            skips[f"pre-{MIN_YEAR} paper"] += 1
            continue
        code = r["ncode"] or f"url:{r['papers'][0]}"
        if code in seen_codes:
            skips["duplicate paper code"] += 1
            continue
        seen_codes[code] = True

        own_key_url, key_kind = r["keys"][0], r["keytype"]
        key_url = own_key_url
        if not r["final"] and r["ncode"]:
            # Prefer the Final Answer Key when one exists for this code + medium.
            cand = finals.get((r["ncode"], r["medium"])) or []
            if not cand:
                # medium sometimes missing on the final row; only trust an unambiguous match
                loose = [f for (c, _m), v in finals.items() if c == r["ncode"] for f in v]
                cand = loose if len(loose) == 1 else []
            if cand:
                key_url, key_kind = cand[0]["keys"][0], "Final Answer Key"

        paper_url = r["papers"][0]
        papers.append({
            "code": r["code"] or "?",
            "ncode": r["ncode"],
            "post": r["post"],
            "date": r["date"],
            "paper_url": paper_url,
            "key_url": key_url,
            "key_kind": key_kind,
            # the row's own key, used if the preferred final key turns out to be
            # for a different paper (the site occasionally mislabels a code)
            "own_key_url": own_key_url,
            "own_key_kind": r["keytype"],
            "alpha": alpha_from_url(paper_url),
            "priority": paper_priority(r["post"]),
        })
    # Stable sort: GK-heavy common exams first, newest-first within each band.
    papers.sort(key=lambda p: p["priority"])
    return papers, skips


# --------------------------------------------------------------------------- #
# PDF -> text
# --------------------------------------------------------------------------- #

def pdf_text(url: str, tag: str) -> str:
    """Download (cached) and run `pdftotext -layout` (cached)."""
    slug = f"{tag}-{hashlib.sha1(url.encode()).hexdigest()[:10]}"
    pdf_path = os.path.join(PDF_CACHE, slug + ".pdf")
    txt_path = os.path.join(TXT_CACHE, slug + ".txt")
    if os.path.exists(txt_path) and os.path.getsize(txt_path) > 0:
        with open(txt_path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    cached_get(url, pdf_path, binary=True)
    os.makedirs(TXT_CACHE, exist_ok=True)
    subprocess.run(["pdftotext", "-layout", pdf_path, txt_path],
                   check=True, capture_output=True, timeout=180)
    with open(txt_path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def text_usable(txt: str) -> tuple[bool, str]:
    """Reject 100-dpi scans and legacy-font booklets whose text layer is junk."""
    if len(txt) < MIN_TEXT_CHARS:
        return False, f"text layer too short ({len(txt)} chars)"
    dense = [c for c in txt if not c.isspace()]
    letters = sum(1 for c in dense if "a" <= c.lower() <= "z")
    ratio = letters / max(1, len(dense))
    if ratio < MIN_LETTER_RATIO:
        return False, f"junk text layer ({ratio:.0%} ASCII letters)"
    return True, ""


# --------------------------------------------------------------------------- #
# Parsing (verified at ~99.5% on modern booklets)
# --------------------------------------------------------------------------- #

KEYCELL = r'(?:[A-D]|X|\*|Del(?:eted)?)'
KEYROW = re.compile(rf'\b(\d{{1,3}})\s+({KEYCELL})\s+({KEYCELL})\s+({KEYCELL})\s+({KEYCELL})(?!\w)')
DROPPED_KEY = re.compile(r'^(?:X|\*|Del(?:eted)?)$', re.I)


def parse_key(txt):
    """Answer-key PDF text -> {alpha_code: {qno: letter}}.
    Rows sit in two side-by-side blocks (1-50 | 51-100), so scan each line for
    every (qno, A, B, C, D) tuple rather than anchoring to line start/end."""
    key = {}
    for line in txt.splitlines():
        for m in KEYROW.finditer(line):
            q = int(m.group(1))
            if not 1 <= q <= 200:
                continue
            for i, code in enumerate('ABCD'):
                key.setdefault(code, {})[q] = m.group(2 + i)
    return key


def parse_questions(txt):
    """Question-booklet text -> [{n, question, options{A..D}}]."""
    txt = re.sub(r'^\s*\d{3}/\d{4}(?:-[MTK])?\s+\d+\s+[A-D]\s*$', '', txt, flags=re.M)
    txt = re.sub(r'^\s*\d{3}/\d{4}(?:-[MTK])?\s*$', '', txt, flags=re.M)
    txt = re.sub(r'\[P\.T\.O\.\]|SPACE FOR ROUGH WORK', '', txt)
    # Cover pages carry a numbered INSTRUCTIONS list that also starts at "1.",
    # and booklet templates differ ("Maximum : 100 marks" vs "Maximum Marks : 100").
    # So try every candidate "1." start and keep whichever yields the most questions.
    return max((_scan(txt[m.start():]) for m in re.finditer(r'\n\s*1\.\s', '\n' + txt)),
               key=len, default=[])


def _scan(txt):
    parts = re.split(r'\n\s*(\d{1,3})\.\s', '\n' + txt)
    out, expect = [], 1
    for i in range(1, len(parts) - 1, 2):
        if int(parts[i]) != expect:
            continue                            # ignore stray numbering inside a stem
        # Templates vary: "(A) ..." and bare "A) ...", and some booklets render
        # the D marker in lowercase ("d)"), so accept both cases.
        chunks = re.split(r'(?:(?<=\s)|(?<=^))\(?([A-Da-d])\)\s', parts[i + 1])
        stem = strip_footer(' '.join(chunks[0].split()))
        if stem[:1].islower():                  # "match the following..." -> "Match ..."
            stem = stem[0].upper() + stem[1:]
        opts = {chunks[j].upper(): strip_footer(' '.join(chunks[j + 1].split()))
                for j in range(1, len(chunks) - 1, 2)}
        if stem and len(opts) == 4:
            out.append({"n": expect, "question": stem, "options": opts})
        expect += 1
    return out


BOOKLET_ALPHA_RE = re.compile(r"Alpha\s*Code\s*[:\-]?\s*([A-D])\b", re.I)
# Every page of a modern booklet is headed with its bare paper code, e.g. "079/2026".
BOOKLET_CODE_RE = re.compile(r"^\s*(\d{1,3}/\d{4})(?:-[MTK])?\s*$", re.M)


def booklet_alpha(txt: str, fallback: str | None) -> str:
    """The booklet's own cover states its alpha code; trust that over the filename."""
    m = BOOKLET_ALPHA_RE.search(txt[:4000])
    return (m.group(1).upper() if m else (fallback or "A"))


# --------------------------------------------------------------------------- #
# Quality gates
# --------------------------------------------------------------------------- #

ALL_NONE_RE = re.compile(r"(all|none|any) of (the above|these|those)|"
                         r"^\s*(all|none) of\b|all the above|above all", re.I)

# "List - I / List-II", "Column A/B", "Match the following" -- these are fine so
# long as the pairs themselves are in the stem.
LIST_CUE_RE = re.compile(
    r"list\s*[-–—]?\s*(?:i{1,3}|1|2)\b|column\s*[-–—]?\s*(?:i{1,3}|a|b|1|2)\b|"
    r"match the following|match list|matched pair", re.I)
# Pair/statement markers: "(i)", "i.", "(a)", "a)", "1." ...
LIST_MARKER_RE = re.compile(r"(?:^|\s)\(?(?:[ivx]{1,4}|[a-d]|[1-9])[.)]\s")


def gate(stem: str, options: list[str]) -> str | None:
    """Return a drop reason, or None if the question passes every gate."""
    # Match-the-following / multi-statement items are kept -- they are authentic
    # Kerala PSC style -- but only when the pairs themselves survived extraction.
    markers = len(LIST_MARKER_RE.findall(stem))
    listy = markers >= 3
    if LIST_CUE_RE.search(stem) and not listy:
        return "matching item not self-contained"
    words = len(stem.split())
    if words < MIN_STEM_WORDS:
        return "stem too short"
    if words > (MAX_LIST_STEM_WORDS if listy else MAX_STEM_WORDS):
        return "stem too long"
    low = stem.lower()
    for bad in BAD_STEM_SUBSTRINGS:
        if bad in low:
            return f"stem needs an attachment ('{bad}')"
    if len(options) < 4:
        return "fewer than 4 options"
    if any(not o.strip() for o in options):
        return "empty option"
    if any(re.fullmatch(r"[A-Da-d]", o.strip()) for o in options):
        return "option is a bare alpha-code marker"
    if any(len(o) > MAX_OPTION_LEN for o in options):
        return "option too long"
    if len({norm_key(o) for o in options}) != len(options):
        return "duplicate options"
    if any(ALL_NONE_RE.search(o) for o in options):
        return "'all/none of the above' option"
    blob = stem + " " + " ".join(options)
    dense = [c for c in blob if not c.isspace()]
    non_ascii = sum(1 for c in dense if ord(c) > 127)
    if dense and non_ascii / len(dense) > MAX_NON_ASCII_RATIO:
        return "OCR garbage (non-ASCII)"
    return None


def existing_question_keys() -> set[str]:
    """Every question already in the bank, normalised the way validate.py does."""
    keys: set[str] = set()
    if not os.path.isdir(QUESTIONS_DIR):
        return keys
    for fn in sorted(os.listdir(QUESTIONS_DIR)):
        if not fn.endswith(".json") or fn.startswith("pyq-"):
            continue
        try:
            with open(os.path.join(QUESTIONS_DIR, fn)) as fh:
                for q in json.load(fh):
                    keys.add(norm_key(q.get("question", "")))
        except Exception as e:
            log(f"  [warn] could not read {fn}: {e}")
    return keys


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

# Deterministic fallback, used when no LLM key is configured or a batch fails.
FALLBACK_DROP = [
    re.compile(r"\b(sin|cos|tan|theta|logarithm|integral|derivative)\b", re.I),
    re.compile(r"\b(simple|compound) interest\b|\bper annum\b|\bprofit and loss\b", re.I),
    re.compile(r"\bhow many (days|hours|minutes|men|women|workers|litres|kg)\b", re.I),
    re.compile(r"\b(ratio|percentage|average|LCM|HCF|probability)\b.*\b(is|are|of)\b", re.I),
    re.compile(r"\bRs\.?\s*[\d,]", re.I),
    re.compile(r"\b(synonym|antonym|spelling|spelt|idiom|phrase|proverb|preposition|"
               r"conjunction|adjective|adverb|tense|voice|narration|article)\b", re.I),
    re.compile(r"\bfill in the blank|\bcorrect(ly)? spel|\bone word substitut", re.I),
    re.compile(r"\b(surveying|theodolite|tacheometry|chainage|bearing capacity|"
               r"mouldboard|penstock|reinforcement|torque|bearing|welding|lathe|"
               r"transistor|amplifier|hydraulic|thresher|tractor|mortar|aggregate)\b", re.I),
    re.compile(r"\b(nursing|catheter|dosage|syringe|pharmacopoeia|anaesthesia|"
               r"prescription|ward)\b", re.I),
    re.compile(r"\b(hyperbole|metaphor|simile|sonnet|stanza|iambic|prosody|"
               r"soliloquy|protagonist|novella|verse|canto|elegy|ode to|"
               r"lyrical ballads|shakespeare|chaucer|milton|dryden|wordsworth|"
               r"keats|shelley|hardy|dickens|eliot)\b", re.I),
    re.compile(r"\b(pedagogy|pedagogical|curriculum|lesson plan|teaching method|"
               r"evaluation technique|bloom.s taxonomy|constructivis)\b", re.I),
    re.compile(r"[ഀ-ൿ஀-௿ಀ-೿]"),   # Malayalam/Tamil/Kannada
]

FALLBACK_TOPICS = [
    ("kerala", r"\b(kerala|malabar|travancore|cochin|kochi|thiruvananthapuram|trivandrum|"
               r"kozhikode|calicut|thrissur|kollam|alappuzha|kannur|kasaragod|palakkad|"
               r"idukki|wayanad|kottayam|pathanamthitta|malappuram|ernakulam|malayalam|"
               r"malayali|sree narayana|ayyankali|chattampi|vaikom|kudumbashree|periyar river|"
               r"onam|kathakali|theyyam)\b"),
    ("indian-polity", r"\b(constitution|article \d|amendment|parliament|lok sabha|rajya sabha|"
                      r"president of india|governor|supreme court|high court|panchayat|"
                      r"fundamental right|directive principle|election commission|preamble|"
                      r"chief justice|ordinance|schedule of the constitution|rti|human rights commission)\b"),
    ("indian-history", r"\b(mauryan|mughal|gupta|ashoka|akbar|shivaji|harappa|indus valley|"
                       r"freedom struggle|quit india|swaraj|gandhi|nehru|bhagat singh|"
                       r"revolt of 1857|non-cooperation|civil disobedience|dandi|"
                       r"indian national congress|sepoy|viceroy|dynasty|empire|sultanate)\b"),
    ("environment", r"\b(biodiversity|ecosystem|wildlife sanctuary|national park|tiger reserve|"
                    r"pollution|ozone|climate change|global warming|greenhouse|endangered|"
                    r"biosphere|deforestation|ramsar|conservation|renewable energy)\b"),
    ("computers-tech", r"\b(computer|software|hardware|internet|website|browser|keyboard|"
                       r"processor|memory|byte|operating system|algorithm|database|network|"
                       r"cyber|e-mail|email|artificial intelligence|programming language)\b"),
    ("sports", r"\b(olympic|cricket|football|hockey|badminton|tennis|athletics|world cup|"
               r"medal|tournament|trophy|stadium|player|championship|asian games)\b"),
    ("economy", r"\b(economy|economic|gdp|inflation|bank|rbi|reserve bank|budget|tax|gst|"
                r"five year plan|niti aayog|export|import|currency|stock exchange|"
                r"per capita income|poverty line|census)\b"),
    ("general-science", r"\b(atom|molecule|element|acid|alkali|vitamin|enzyme|hormone|blood|"
                        r"cell|dna|gene|bacteria|virus|disease|deficiency|velocity|energy|"
                        r"gravity|electron|proton|neutron|chemical|periodic table|"
                        r"photosynthesis|digestion|respiration|physics|chemistry|biology)\b"),
    ("geography", r"\b(river|mountain|plateau|desert|latitude|longitude|monsoon|soil|"
                  r"tropic|equator|ocean|strait|peninsula|volcano|earthquake|glacier|"
                  r"state of india|capital of|highest peak|largest state|climate)\b"),
    ("arts-culture", r"\b(literature|poet|novel|author|book|award|padma|jnanpith|dance|music|"
                     r"painting|festival|temple|architecture|film|cinema|sahitya|"
                     r"classical|folk|theatre|instrument)\b"),
    ("world-gk", r"\b(united nations|unesco|unicef|who\b|world bank|imf|nato|asean|saarc|"
                 r"nobel|capital of [a-z]+|president of [a-z]+|country|continent|"
                 r"headquarters|international)\b"),
]
FALLBACK_TOPICS = [(t, re.compile(p, re.I)) for t, p in FALLBACK_TOPICS]


def classify_fallback(stem: str, options: list[str]) -> str:
    blob = stem + " " + " ".join(options)
    if any(r.search(blob) for r in FALLBACK_DROP):
        return DROP
    for topic, rx in FALLBACK_TOPICS:
        if rx.search(blob):
            return topic
    return DROP           # unsure -> drop, per the brief


def load_api_key() -> str | None:
    """LLM_API_KEY from the project .env (or the environment).  Never printed."""
    key = os.environ.get("LLM_API_KEY")
    if key:
        return key.strip() or None
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.exists(env_path):
        return None
    for line in open(env_path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("LLM_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


class Classifier:
    """Batched LLM classification with an on-disk cache and a keyword fallback."""

    def __init__(self, api_key: str | None, use_llm: bool = True):
        self.api_key = api_key if use_llm else None
        self.enabled = bool(self.api_key)
        self.last_call = 0.0
        self.cooldown_until = 0.0          # set from the TPM headers
        self.tokens = 0
        self.requests = 0
        self.budget_spent = False
        self.exhausted = False
        self.consecutive_failures = 0
        self.stats = collections.Counter()
        os.makedirs(CLS_CACHE, exist_ok=True)

    # --- cache ---
    @staticmethod
    def _cache_path(stem: str) -> str:
        return os.path.join(CLS_CACHE, hashlib.sha1(
            (LLM_MODEL + "|" + PROMPT_VERSION + "|" + norm_key(stem)).encode()
        ).hexdigest()[:16] + ".json")

    def _cached(self, stem: str) -> str | None:
        p = self._cache_path(stem)
        if os.path.exists(p):
            try:
                lab = json.load(open(p)).get("topic")
                if lab in VALID_LABELS:
                    return lab
            except Exception:
                pass
        return None

    def _store(self, stem: str, topic: str):
        with open(self._cache_path(stem), "w") as fh:
            json.dump({"topic": topic}, fh)

    # --- llm ---
    def _post(self, payload: dict) -> tuple[dict, dict]:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(LLM_URL, data=body, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Groq sits behind Cloudflare, which 403s the default urllib UA.
            "User-Agent": "mocker-pyq-importer/1.0",
        })
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.load(resp), dict(resp.headers)

    @staticmethod
    def _duration(raw: str | None) -> float:
        """Groq writes reset windows as '2.437s' / '1m30s' / '10m4.8s'."""
        if not raw:
            return 0.0
        total = 0.0
        for val, unit in re.findall(r"([\d.]+)\s*(ms|m|s|h)", raw):
            total += float(val) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
        return total

    def _absorb_limits(self, headers: dict):
        h = {k.lower(): v for k, v in headers.items()}
        try:
            remaining = float(h.get("x-ratelimit-remaining-tokens", "1e9"))
        except ValueError:
            return
        if remaining < LLM_TOKEN_HEADROOM:
            reset = self._duration(h.get("x-ratelimit-reset-tokens")) + 1.0
            self.cooldown_until = time.time() + min(reset, 90.0)

    def _call(self, prompt: str) -> dict | None:
        for attempt in range(1, LLM_RETRIES + 1):
            wait = max(LLM_MIN_INTERVAL - (time.time() - self.last_call),
                       self.cooldown_until - time.time())
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.time()
            self.requests += 1
            try:
                data, headers = self._post({
                    "model": LLM_MODEL,
                    "messages": [{"role": "system", "content": CLASSIFY_SYSTEM},
                                 {"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                })
                self._absorb_limits(headers)
                self.tokens += (data.get("usage") or {}).get("total_tokens", 0)
                return json.loads(data["choices"][0]["message"]["content"])
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    raise SystemExit("[llm] 401 Unauthorized -- check LLM_API_KEY. Aborting.")
                if e.code == 429:
                    try:
                        body = e.read().decode("utf-8", "replace")[:400]
                    except Exception:
                        body = ""
                    if re.search(r"per\s*day|daily|TPD|RPD", body, re.I):
                        # Daily quota gone -- no amount of sleeping fixes that today.
                        log("    [llm] daily quota exhausted; switching to the "
                            "keyword fallback for the rest of the run")
                        self.exhausted = True
                        return None
                    log(f"    [llm] 429 rate-limited, sleeping {LLM_429_SLEEP}s")
                    time.sleep(LLM_429_SLEEP)
                    self.cooldown_until = 0.0
                    continue
                log(f"    [llm] HTTP {e.code} (attempt {attempt}/{LLM_RETRIES})")
                time.sleep(3 * attempt)
            except Exception as e:
                log(f"    [llm] {type(e).__name__} {e} (attempt {attempt}/{LLM_RETRIES})")
                time.sleep(3 * attempt)
        return None

    def _llm_batch(self, batch: list[dict]) -> dict[int, str]:
        lines = []
        for i, it in enumerate(batch, 1):
            # Only the stem plus a short option preview -- keeps the prompt cheap.
            preview = " | ".join(o[:26] for o in it["options"])
            lines.append(f'{i}. {it["question"][:220]}\n   opts: {preview[:130]}')
        out = self._call(CLASSIFY_PROMPT + "\n".join(lines))
        got: dict[int, str] = {}
        if not isinstance(out, dict):
            return got
        labels = out.get("labels")
        if not isinstance(labels, list):
            labels = next((v for v in out.values() if isinstance(v, list)), [])
        for entry in labels:
            if not isinstance(entry, dict):
                continue
            try:
                i = int(entry.get("i"))
            except (TypeError, ValueError):
                continue
            topic = str(entry.get("topic", "")).strip().lower()
            if 1 <= i <= len(batch) and topic in VALID_LABELS:
                got[i - 1] = topic
        return got

    # --- public ---
    def classify(self, items: list[dict]) -> list[str]:
        """items: [{question, options}] -> parallel list of labels."""
        labels: list[str | None] = [None] * len(items)
        pending = []
        for idx, it in enumerate(items):
            hit = self._cached(it["question"])
            if hit:
                labels[idx] = hit
                self.stats["cache"] += 1
            else:
                pending.append(idx)

        if self.enabled and pending:
            for start in range(0, len(pending), LLM_BATCH):
                if self.requests >= LLM_MAX_REQUESTS:
                    self.budget_spent = True
                    log(f"    [llm] hit the {LLM_MAX_REQUESTS}-request daily guard; "
                        f"remaining {len(pending) - start} questions use the keyword fallback")
                    break
                if self.exhausted or self.consecutive_failures >= 3:
                    self.budget_spent = True
                    log(f"    [llm] giving up on the API; remaining "
                        f"{len(pending) - start} questions use the keyword fallback")
                    break
                chunk = pending[start:start + LLM_BATCH]
                got = self._llm_batch([items[i] for i in chunk])
                self.consecutive_failures = 0 if got else self.consecutive_failures + 1
                for j, idx in enumerate(chunk):
                    if j in got:
                        labels[idx] = got[j]
                        self._store(items[idx]["question"], got[j])
                        self.stats["llm"] += 1
                if (start // LLM_BATCH) % 10 == 0 or start + LLM_BATCH >= len(pending):
                    log(f"    [llm] classified {min(start + LLM_BATCH, len(pending))}"
                        f"/{len(pending)} new questions "
                        f"({self.requests} reqs, {self.tokens:,} tokens)")

        for idx, it in enumerate(items):
            if labels[idx] is None:
                labels[idx] = classify_fallback(it["question"], it["options"])
                self.stats["fallback"] += 1
        return labels  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Per-paper ingest
# --------------------------------------------------------------------------- #

ROMAN_RE = re.compile(r"\b(I{1,3}|IV|VI{0,3}|IX|XI{0,2})\b", re.I)


def short_post(post: str) -> str:
    """'TRACER (Soil Survey and Soil Conservation )' -> 'Tracer' for the explanation.
    Splits only on real separators, so 'SUB-ENGINEER' survives intact."""
    s = re.split(r"\s+[-–/]\s+|[(,]|\s*/\s*(?=[A-Z])", norm_ws(post))[0]
    s = norm_ws(s).rstrip(" -–/,.")
    if s.isupper() or s.islower():
        s = s.title()
    # .title() mangles the Grade numerals Kerala PSC uses everywhere ("Gr.II" -> "Gr.Ii")
    s = ROMAN_RE.sub(lambda m: m.group(0).upper(), s)
    return s[:60].strip() or "Kerala PSC"


def pretty_date(iso: str) -> str:
    y, m, d = iso.split("-")
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(m) - 1]
    return f"{int(d)} {month} {y}"


def ingest_paper(p: dict, drops: collections.Counter) -> tuple[list[dict], dict]:
    """Download + parse one paper.  Returns (raw candidate questions, per-paper stats)."""
    stat = {"code": p["code"], "post": short_post(p["post"]), "date": p["date"],
            "key_kind": p["key_kind"], "parsed": 0, "gated": 0, "candidates": 0,
            "status": "ok", "reason": "", "priority": p["priority"]}

    qtxt = pdf_text(p["paper_url"], "q")
    ok, why = text_usable(qtxt)
    if not ok:
        stat.update(status="skipped", reason=why)
        return [], stat
    def load_key(url):
        """-> (text, error).  Modern key PDFs restate their paper code, so we can
        verify that the key we picked really belongs to this paper."""
        txt = pdf_text(url, "k")
        good, reason = text_usable(txt)
        if not good:
            return None, "answer key: " + reason
        km = CODE_RE.search(txt[:1500])
        kcode = norm_code(km.group(1)) if km else None
        if kcode and p["ncode"] and kcode != p["ncode"]:
            return None, f"key/paper code mismatch ({kcode} vs {p['ncode']})"
        return txt, ""

    ktxt, err = load_key(p["key_url"])
    if ktxt is None and p.get("own_key_url") and p["own_key_url"] != p["key_url"]:
        # The preferred Final Answer Key was wrong for this paper -- fall back to
        # the provisional key filed on the paper's own row.
        alt, alt_err = load_key(p["own_key_url"])
        if alt is not None:
            ktxt, err = alt, ""
            p["key_kind"] = p["own_key_kind"]
            stat["key_kind"] = p["own_key_kind"]
            stat["reason"] = "final key rejected, used the row's own key"
    if ktxt is None:
        stat.update(status="skipped", reason=err)
        return [], stat

    if p["code"] in (None, "?"):
        # A few index rows omit the code; the booklet prints it on every page.
        bm = BOOKLET_CODE_RE.search(qtxt[:6000])
        if bm:
            p["code"] = bm.group(1)
            p["ncode"] = p["ncode"] or norm_code(bm.group(1))
            stat["code"] = p["code"]

    alpha = booklet_alpha(qtxt, p["alpha"])
    key = parse_key(ktxt).get(alpha, {})
    questions = parse_questions(qtxt)
    stat["parsed"] = len(questions)
    stat["alpha"] = alpha
    if not questions:
        stat.update(status="skipped", reason="no questions parsed")
        return [], stat
    if not key:
        stat.update(status="skipped", reason=f"no key rows for alpha code {alpha}")
        return [], stat

    out = []
    for q in questions:
        letter = key.get(q["n"])
        if letter is None:
            drops["no key entry"] += 1
            continue
        if DROPPED_KEY.match(letter):
            drops["key marked deleted (X/*/Deleted)"] += 1
            continue
        options = [q["options"].get(c, "") for c in "ABCD"]
        reason = gate(q["question"], options)
        if reason:
            drops[reason] += 1
            stat["gated"] += 1
            continue
        out.append({
            "n": q["n"],
            "question": q["question"],
            "options": options,
            "answer": "ABCD".index(letter),
            "paper": p,
        })
    stat["candidates"] = len(out)
    return out, stat


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="Kerala PSC PYQ importer")
    ap.add_argument("--limit", type=int, default=40,
                    help="max number of papers to ingest (default 40)")
    ap.add_argument("--pages", type=int, default=INDEX_PAGES,
                    help=f"index pages to crawl (default {INDEX_PAGES})")
    ap.add_argument("--no-llm", action="store_true",
                    help="use only the deterministic keyword classifier")
    ap.add_argument("--refresh-index", action="store_true",
                    help="re-download index pages instead of using the cache")
    ap.add_argument("--dry-run", action="store_true",
                    help="do everything except write data/questions/pyq-*.json")
    args = ap.parse_args()

    for d in (INDEX_CACHE, PDF_CACHE, TXT_CACHE, CLS_CACHE):
        os.makedirs(d, exist_ok=True)

    log(f"=== Kerala PSC PYQ importer === limit={args.limit} pages={args.pages}")
    log("\n[1/5] crawling index")
    rows = crawl_index(args.pages, args.refresh_index)
    log(f"  {len(rows)} table rows across {args.pages} pages")

    papers, skips = select_papers(rows)
    log(f"\n[2/5] {len(papers)} ingestable papers (English, >= {MIN_YEAR}, paper + key)")
    for reason, n in skips.most_common(12):
        log(f"    skipped {n:>5}  {reason}")
    finals = sum(1 for p in papers if "final" in p["key_kind"].lower())
    log(f"  key type: {finals} final, {len(papers) - finals} provisional")

    n_ingestable = len(papers)
    papers = papers[:args.limit]
    log(f"\n[3/5] downloading + parsing {len(papers)} papers")

    drops: collections.Counter = collections.Counter()
    per_paper: list[dict] = []
    candidates: list[dict] = []
    for i, p in enumerate(papers, 1):
        try:
            got, stat = ingest_paper(p, drops)
        except Exception as e:
            stat = {"code": p["code"], "post": short_post(p["post"]), "date": p["date"],
                    "key_kind": p["key_kind"], "parsed": 0, "gated": 0, "candidates": 0,
                    "status": "error", "reason": f"{type(e).__name__}: {e}",
                    "priority": p["priority"]}
            got = []
        per_paper.append(stat)
        candidates += got
        flag = "" if stat["status"] == "ok" else f"  <-- {stat['status']}: {stat['reason']}"
        log(f"  [{i:>2}/{len(papers)}] {stat['code']:<12} {stat['post'][:34]:<34} "
            f"parsed={stat['parsed']:>3} kept={stat['candidates']:>3}{flag}")

    # --- dedup (against the existing bank and within this run) ---
    seen = existing_question_keys()
    log(f"\n[4/5] dedup against {len(seen)} existing questions, then classify")
    unique = []
    for c in candidates:
        k = norm_key(c["question"])
        if k in seen:
            drops["duplicate question"] += 1
            continue
        seen.add(k)
        unique.append(c)

    api_key = load_api_key()
    clf = Classifier(api_key, use_llm=not args.no_llm)
    log(f"  classifier: {'LLM ' + LLM_MODEL if clf.enabled else 'keyword fallback only'} "
        f"({len(unique)} questions)")
    labels = clf.classify(unique)
    log(f"  label source: {dict(clf.stats)}  (llm tokens used: {clf.tokens:,})")

    buckets: dict[str, list[dict]] = collections.defaultdict(list)
    for c, topic in zip(unique, labels):
        if topic == DROP:
            drops["classified as non-GK (drop)"] += 1
            continue
        p = c["paper"]
        answer_text = c["options"][c["answer"]]
        buckets[topic].append({
            "topic": topic,
            "question": c["question"],
            "options": c["options"],
            "answer": c["answer"],
            "explanation": (f"This question was asked in Kerala PSC exam {p['code']} "
                            f"({short_post(p['post'])}, {pretty_date(p['date'])}). "
                            f"The correct answer is {answer_text}."),
            "difficulty": 2,
            "tags": ["pyq", slugify(p["post"])],
            "source": "pyq",
            "source_ref": f"Kerala PSC {p['code']} · Q{c['n']}",
            "source_key": p["key_kind"],          # provisional vs final key used
            "source_url": p["paper_url"],
            "published_at": p["date"],
        })

    # --- write ---
    log(f"\n[5/5] writing {'(dry run)' if args.dry_run else ''}")
    # Regenerate from scratch so a topic that no longer qualifies leaves no stale file.
    if not args.dry_run:
        for fn in sorted(os.listdir(QUESTIONS_DIR)):
            if fn.startswith("pyq-") and fn.endswith(".json"):
                os.remove(os.path.join(QUESTIONS_DIR, fn))
    written = []
    for topic in sorted(buckets):
        items = buckets[topic]
        path = os.path.join(QUESTIONS_DIR, f"pyq-{topic}.json")
        if not args.dry_run:
            with open(path, "w") as fh:
                json.dump(items, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        written.append((topic, len(items), path))

    # ----------------------------------------------------------------- summary
    dist = collections.Counter(q["answer"] for items in buckets.values() for q in items)
    total_kept = sum(len(v) for v in buckets.values())
    ok_papers = [s for s in per_paper if s["status"] == "ok"]
    bad_papers = [s for s in per_paper if s["status"] != "ok"]

    log("\n" + "=" * 78)
    log("SUMMARY")
    log("=" * 78)
    log(f"  index rows crawled          {len(rows)}")
    log(f"  ingestable papers matched   {n_ingestable}  (--limit {args.limit} -> {len(papers)} attempted)")
    log(f"  papers parsed OK            {len(ok_papers)}")
    log(f"      general/common-exam     {sum(1 for s in ok_papers if s['priority'] == 0)}")
    log(f"      post-specific           {sum(1 for s in ok_papers if s['priority'] == 1)}")
    log(f"  papers skipped / errored    {len(bad_papers)}")
    for s in bad_papers:
        log(f"      {s['code']:<12} {s['status']}: {s['reason']}")
    log(f"  questions parsed            {sum(s['parsed'] for s in per_paper)}")
    log(f"  candidates after gates      {len(candidates)}")
    log(f"  kept after dedup + topics   {total_kept}")

    log("\n  --- dropped, by reason ---")
    for reason, n in drops.most_common():
        log(f"    {n:>6}  {reason}")

    log("\n  --- per paper ---")
    log(f"    {'code':<12} {'date':<11} {'key':<11} {'band':<8} {'post':<30} "
        f"{'parsed':>6} {'kept':>5}")
    for s in per_paper:
        log(f"    {s['code']:<12} {s['date'] or '?':<11} "
            f"{('final' if 'final' in s['key_kind'].lower() else 'provisional'):<11} "
            f"{('general' if s['priority'] == 0 else 'specific'):<8} "
            f"{s['post'][:30]:<30} {s['parsed']:>6} {s['candidates']:>5}")

    log("\n  --- kept per topic ---")
    for topic, n, path in written:
        log(f"    pyq-{topic:<16} {n:>5}   {os.path.relpath(path, PROJECT_DIR)}")
    log(f"    {'TOTAL':<20} {total_kept:>5}")

    log("\n  --- answer position distribution (NOT corrected: licence requires "
        "faithful reproduction) ---")
    for i in range(4):
        n = dist.get(i, 0)
        share = n / total_kept if total_kept else 0
        log(f"    index {i} ({'ABCD'[i]})  {n:>5}  {share:>6.1%}  {'#' * int(share * 60)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

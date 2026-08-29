#!/usr/bin/env python3
"""
Import the MILU (Multi-task Indic Language Understanding) English test split into
the mocker question-bank schema.

Dataset : murthyrudra/milu-cleaned  (English config, test split)
Licence : CC-BY-4.0 -- MILU, arXiv:2411.02538
Output  : data/questions/milu-<topic>.json   (never touches hand-authored banks)

Run:
    cd data/importers
    uv venv .venv && uv pip install --python .venv/bin/python pyarrow pandas requests
    ./.venv/bin/python milu.py
"""

from __future__ import annotations

import collections
import json
import os
import random
import re
import sys

import pandas as pd
import requests

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(HERE)                    # data/
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
CACHE_DIR = os.path.join(HERE, "cache")
PARQUET_PATH = os.path.join(CACHE_DIR, "milu-english-test-0.parquet")

PARQUET_URL = (
    "https://huggingface.co/api/datasets/murthyrudra/milu-cleaned"
    "/parquet/English/test/0.parquet"
)
PARQUET_INDEX_URL = (
    "https://huggingface.co/api/datasets/murthyrudra/milu-cleaned/parquet"
)

SEED = 20240817
CAP_PER_TOPIC = 600
MIN_PER_TOPIC = 20
MAX_QUESTION_LEN = 220
MIN_QUESTION_LEN = 15
MAX_OPTION_LEN = 80

# MILU `subject` -> our topic slug. Subjects absent from this map are dropped
# (pure maths/verbal reasoning, engineering, medicine, law-exam content,
# agriculture specifics, pedagogy, psychology -- none of which are PSC GK).
SUBJECT_TO_TOPIC = {
    # --- history ---
    "History": "indian-history",
    "Religion and Spirituality": "indian-history",
    # --- polity ---
    "Politics and Governance": "indian-polity",
    "Public Administration": "indian-polity",
    "Social Welfare and Development": "indian-polity",
    # --- geography ---
    "Geography": "geography",
    "Earth Sciences": "geography",
    "Anthropology": "geography",
    # --- economy ---
    "Economics": "economy",
    "Finance and Investment": "economy",
    "Business and Management": "economy",
    # --- science ---
    "Physics": "general-science",
    "Chemistry": "general-science",
    "Biology": "general-science",
    "Astronomy and Astrophysics": "general-science",
    # --- arts & culture ---
    "Arts and Culture": "arts-culture",
    "Literature and Linguistics": "arts-culture",
    "Music and Performing Arts": "arts-culture",
    "Architecture and Design": "arts-culture",
    "Media and Communication": "arts-culture",
    # --- world gk ---
    "International Relations": "world-gk",
    # --- sports ---
    "Sports and Recreation": "sports",
    # --- computers / tech ---
    "Computer Science": "computers-tech",
    "Information Technology": "computers-tech",
    "Technology and Innovation": "computers-tech",
    # --- environment ---
    "Environmental Science": "environment",
}

DROPPED_SUBJECTS_NOTE = {
    "Language Studies": "English grammar/vocabulary, not GK",
    "Education": "pedagogy + state-specific department trivia",
    "Logical Reasoning": "puzzles, not GK",
    "Sociology": "mostly reasoning puzzles / survey statistics",
    "Psychology": "academic psychology, not PSC GK",
    "Law and Ethics": "law-exam section-number content",
    "Ethics and Human Rights": "situational ethics, not factual GK",
    "Defense and Security": "time-sensitive current-affairs style",
    "Agriculture": "agriculture specifics",
    "Health and Medicine": "clinical medicine",
    "Food Science": "food technology specifics",
    "Engineering": "engineering syllabus",
    "Materials Science": "engineering syllabus",
    "Energy and Power": "engineering syllabus",
    "Transportation and Logistics": "logistics/engineering syllabus",
}

# Question text mentioning any of these is routed to `kerala` regardless of subject.
KERALA_RE = re.compile(
    r"\b(kerala|malabar|travancore|cochin|kochi|thiruvananthapuram|"
    r"trivandrum|kozhikode|calicut|malayalam|malayali)\b",
    re.I,
)

# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #

# Multi-statement / matching / assertion-reason / ordering constructs.
BAD_QUESTION_SUBSTRINGS = [
    "match the following",
    "match list",
    "consider the following",
    "assertion",
    "reason (r)",
    "list-i",
    "list i",
    "column",
    "which of the statements",
    "codes given below",
    "code given below",
    "given below are",
    "arrange",
    "chronological",
    "correctly matched",
    "odd man out",
    "odd one out",
    "read the following",
    "following statements",
    "statements are correct",
    "is/are correct",
    "directions:",
    "direction:",
    "select the correct alternative",
    "correct order",
    "pick the option",
]

# Verbal-ability / grammar / vocabulary artefacts that slipped into GK subjects.
BAD_QUESTION_RE = [
    re.compile(r"\bselect the most appropriate\b", re.I),
    re.compile(r"\bfill in the blank", re.I),
    re.compile(r"\bunderlined\b", re.I),
    re.compile(r"\bnarration\b", re.I),
    re.compile(r"\bidiom\b|\bproverb\b", re.I),
    re.compile(r"\bsynonym\b|\bantonym\b|\bspelt\b|\bspelling\b", re.I),
    re.compile(r"\bone word substitution\b", re.I),
    re.compile(r"\bjumbled\b", re.I),
    re.compile(r"\bactive voice\b|\bpassive voice\b", re.I),
    re.compile(r"\bcomplete the (following|sentence)\b", re.I),
    re.compile(r"\bsegment\b.*\bsentence\b", re.I),
    re.compile(r"\bwhich of the following sentence", re.I),
    # arithmetic word problems
    re.compile(r"\bRs\.?\s*[\d,]", re.I),
    re.compile(r"\bper annum\b", re.I),
    re.compile(r"\b(compound|simple) interest\b", re.I),
    re.compile(r"\bratio of\b.*\brespectively\b", re.I),
    re.compile(r"\bhow many (days|hours|minutes|men|women|workers)\b", re.I),
    # time-sensitive / current-affairs framing
    re.compile(r"\bas on\b|\bas of\b|\brecently\b|\bat present\b", re.I),
    re.compile(r"\b(currently|presently|nowadays)\b", re.I),
    re.compile(r"\bwho is the (present|current|new)\b", re.I),
    re.compile(r"\bin the news\b", re.I),
    # explicit enumerations: "1.", "(a)", "I.", "(i)" appearing inline
    re.compile(r"(?:^|\s)\(?[ivx]{1,4}\)\s", re.I),
    re.compile(r"(?:^|\s)\(?[a-d]\)\s", re.I),
    re.compile(r"(?:^|\s)[1-9]\.\s"),
    re.compile(r"(?:^|\s)[IVX]{1,4}\.\s"),
    re.compile(r"\b\d\s+and\s+\d\b"),
]

# Option-level rejects.
BAD_OPTION_RE = [
    re.compile(r"(all|none|any) of (the above|these|those)", re.I),
    re.compile(r"^\s*(all|none) of\b", re.I),
    re.compile(r"\bboth\b", re.I),
    re.compile(r"\bneither\b", re.I),
    re.compile(r"\bonly\b", re.I),
    re.compile(r"\b\d\s*(and|&|,)\s*\d\b"),
    re.compile(r"\b[ivx]{1,4}\s*(and|&|,)\s*[ivx]{1,4}\b", re.I),
    re.compile(r"^\s*[a-d]\s*$", re.I),          # bare "A" / "B" answer-key artefacts
    re.compile(r"^\s*[ivx]{1,4}\s*$", re.I),
    re.compile(r"all options are correct", re.I),
    re.compile(r"^\s*(true|false)\s*$", re.I),
    re.compile(r"cannot be determined|not determined|data inadequate", re.I),
]

WS_RE = re.compile(r"\s+")


def norm_ws(s: str) -> str:
    """Collapse all whitespace runs (incl. NBSP) to single spaces and strip."""
    return WS_RE.sub(" ", str(s).replace(" ", " ")).strip()


def norm_key(s: str) -> str:
    """Dedup key -- matches the normalisation used by data/validate.py."""
    return re.sub(r"\W+", " ", str(s).lower()).strip()


PREFIX_RE = re.compile(r"^\s*[\(\[]?\s*([a-dA-D]|[1-4]|[ivIV]{1,3})\s*[\)\].:]\s+")


def strip_option_prefixes(options: list[str]) -> list[str]:
    """
    Strip "(a)" / "A." / "1)" style labels -- but only when *all four* options
    carry a prefix and those prefixes form the expected a-b-c-d / 1-2-3-4 /
    i-ii-iii-iv sequence. This avoids mangling real answers such as
    "A. P. J. Abdul Kalam".
    """
    matches = [PREFIX_RE.match(o) for o in options]
    if not all(matches):
        return options
    labels = [m.group(1).lower() for m in matches]
    if labels not in (["a", "b", "c", "d"], ["1", "2", "3", "4"], ["i", "ii", "iii", "iv"]):
        return options
    return [norm_ws(o[m.end():]) for o, m in zip(options, matches)]


def question_ok(q: str) -> bool:
    if "\n" in q or "\r" in q:
        return False
    if not (MIN_QUESTION_LEN <= len(q) <= MAX_QUESTION_LEN):
        return False
    low = q.lower()
    if any(s in low for s in BAD_QUESTION_SUBSTRINGS):
        return False
    if any(r.search(q) for r in BAD_QUESTION_RE):
        return False
    # more than one fill-in blank -> usually a broken/translated stem
    if len(re.findall(r"_{2,}", q)) > 1:
        return False
    # stray CJK / Devanagari etc. = translation artefact
    if re.search(r"[ऀ-෿一-鿿]", q):
        return False
    return True


def options_ok(options: list[str]) -> bool:
    if len(options) != 4:
        return False
    for o in options:
        if not o or len(o) > MAX_OPTION_LEN:
            return False
        if "\n" in o:
            return False
        if any(r.search(o) for r in BAD_OPTION_RE):
            return False
        if re.search(r"[ऀ-෿一-鿿]", o):
            return False
    if len({norm_key(o) for o in options}) != 4:
        return False
    return True


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

def fetch_parquet() -> str:
    if os.path.exists(PARQUET_PATH) and os.path.getsize(PARQUET_PATH) > 100_000:
        print(f"[cache] using {PARQUET_PATH}")
        return PARQUET_PATH
    os.makedirs(CACHE_DIR, exist_ok=True)
    urls = [PARQUET_URL]
    try:
        idx = requests.get(PARQUET_INDEX_URL, timeout=60).json()
        found = idx.get("English", {}).get("test", []) if isinstance(idx, dict) else []
        urls += [u for u in found if isinstance(u, str)]
    except Exception as e:  # index is only a fallback
        print(f"[warn] could not read parquet index: {e}")
    for url in urls:
        try:
            print(f"[fetch] {url}")
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            with open(PARQUET_PATH, "wb") as fh:
                fh.write(r.content)
            print(f"[fetch] wrote {len(r.content):,} bytes")
            return PARQUET_PATH
        except Exception as e:
            print(f"[warn] {url} failed: {e}")
    raise SystemExit("could not download the MILU parquet")


# --------------------------------------------------------------------------- #
# Existing hand-authored banks (for cross-file dedup)
# --------------------------------------------------------------------------- #

def existing_question_keys() -> set[str]:
    keys: set[str] = set()
    if not os.path.isdir(QUESTIONS_DIR):
        return keys
    for fn in sorted(os.listdir(QUESTIONS_DIR)):
        if not fn.endswith(".json") or fn.startswith("milu-"):
            continue
        try:
            with open(os.path.join(QUESTIONS_DIR, fn)) as fh:
                for q in json.load(fh):
                    keys.add(norm_key(q.get("question", "")))
        except Exception as e:
            print(f"[warn] could not read {fn}: {e}")
    return keys


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    path = fetch_parquet()
    df = pd.read_parquet(path)
    print(f"[load] {len(df):,} rows, columns={list(df.columns)}")

    print("\n=== subject counts (raw) ===")
    counts = df.groupby(["domain", "subject"]).size().reset_index(name="n")
    for _, r in counts.sort_values(["domain", "n"], ascending=[True, False]).iterrows():
        topic = SUBJECT_TO_TOPIC.get(r["subject"])
        label = topic or f"DROP ({DROPPED_SUBJECTS_NOTE.get(r['subject'], 'not GK')})"
        print(f"  {r['domain']:<24} {r['subject']:<32} {r['n']:>5}  ->  {label}")

    seen = existing_question_keys()
    print(f"\n[dedup] {len(seen)} question keys loaded from hand-authored banks")

    buckets: dict[str, list[dict]] = collections.defaultdict(list)
    stats = collections.Counter()

    for row in df.itertuples(index=False):
        subject = row.subject
        topic = SUBJECT_TO_TOPIC.get(subject)
        if topic is None:
            stats["drop:subject"] += 1
            continue

        question = norm_ws(row.question)
        if not question_ok(question):
            stats["drop:question"] += 1
            continue

        raw_opts = [norm_ws(getattr(row, f"option{i}")) for i in range(1, 5)]
        opts = strip_option_prefixes(raw_opts)
        opts = [norm_ws(o) for o in opts]
        if not options_ok(opts):
            stats["drop:options"] += 1
            continue

        target = str(row.target).strip()
        if target not in ("option1", "option2", "option3", "option4"):
            stats["drop:target"] += 1
            continue
        answer_text = opts[int(target[-1]) - 1]

        key = norm_key(question)
        if key in seen:
            stats["drop:dup"] += 1
            continue
        seen.add(key)

        if KERALA_RE.search(question):
            topic = "kerala"
            stats["route:kerala"] += 1

        tag = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
        buckets[topic].append(
            {
                "topic": topic,
                "question": question,
                "_answer_text": answer_text,
                "_distractors": [o for o in opts if o != answer_text],
                "explanation": f"The correct answer is {answer_text}.",
                "difficulty": 2,
                "tags": [tag],
                "source": "milu",
            }
        )
        stats["kept"] += 1

    print("\n=== filter stats ===")
    for k, v in sorted(stats.items()):
        print(f"  {k:<18} {v:>6}")

    os.makedirs(QUESTIONS_DIR, exist_ok=True)
    written: list[tuple[str, int, dict]] = []
    skipped: list[tuple[str, int]] = []

    for topic in sorted(buckets):
        items = buckets[topic]
        rng = random.Random(f"{SEED}:{topic}")
        rng.shuffle(items)
        if len(items) > CAP_PER_TOPIC:
            items = items[:CAP_PER_TOPIC]
        if len(items) < MIN_PER_TOPIC:
            skipped.append((topic, len(items)))
            continue

        out = []
        for i, it in enumerate(items):
            distractors = list(it.pop("_distractors"))
            answer_text = it.pop("_answer_text")
            if len(distractors) != 3:            # safety net; options_ok makes this unreachable
                continue
            rng.shuffle(distractors)
            slot = i % 4                          # round-robin => exactly ~25% per index
            options = distractors[:slot] + [answer_text] + distractors[slot:]
            it["options"] = options
            it["answer"] = slot
            out.append(
                {
                    "topic": it["topic"],
                    "question": it["question"],
                    "options": it["options"],
                    "answer": it["answer"],
                    "explanation": it["explanation"],
                    "difficulty": it["difficulty"],
                    "tags": it["tags"],
                    "source": it["source"],
                }
            )

        dist = collections.Counter(q["answer"] for q in out)
        fn = os.path.join(QUESTIONS_DIR, f"milu-{topic}.json")
        with open(fn, "w") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        written.append((topic, len(out), dict(sorted(dist.items()))))

    print("\n=== written ===")
    print(f"  {'topic':<18} {'count':>6}  answer distribution")
    total = 0
    for topic, n, dist in written:
        total += n
        share = max(dist.values()) / n
        print(f"  milu-{topic:<13} {n:>6}  {dist}  (max {share:.0%})")
    print(f"  {'TOTAL':<18} {total:>6}")
    if skipped:
        print("\n  skipped (< %d questions): %s" % (MIN_PER_TOPIC, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())

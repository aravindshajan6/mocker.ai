"""Dependency-free fallback generator for current-affairs MCQs.

Used when no LLM key is configured. Instead of generic NER (which needs a model), this uses typed
gazetteers: a headline is usable only when exactly one entity of one type appears in it, so blanking
that entity leaves an unambiguous fill-in-the-blank stem whose distractors are same-type by construction.

    from .heuristic import generate_heuristic
    questions = generate_heuristic(fetch_items(), max_questions=20, seed=7)

Output dicts match the bank schema produced by current_affairs.generate_with_claude.
Self-test:  python3 backend/app/content/heuristic.py
"""
from __future__ import annotations

import random
import re
from datetime import date
from functools import lru_cache

BLANK = "______"


def _g(csv: str) -> list[str]:
    """Compact gazetteer literal: comma-separated names on one string."""
    return [n.strip() for n in csv.split(",") if n.strip()]


STATES = _g("""Andhra Pradesh, Arunachal Pradesh, Assam, Bihar, Chhattisgarh, Goa, Gujarat, Haryana,
Himachal Pradesh, Jharkhand, Karnataka, Kerala, Madhya Pradesh, Maharashtra, Manipur, Meghalaya, Mizoram,
Nagaland, Odisha, Punjab, Rajasthan, Sikkim, Tamil Nadu, Telangana, Tripura, Uttar Pradesh, Uttarakhand,
West Bengal, Delhi, Jammu and Kashmir, Ladakh, Puducherry, Chandigarh, Lakshadweep,
Andaman and Nicobar Islands""")
STATE_ALIASES = {
    "TN": "Tamil Nadu", "UP": "Uttar Pradesh", "MP": "Madhya Pradesh", "J&K": "Jammu and Kashmir",
    "Jammu & Kashmir": "Jammu and Kashmir", "Orissa": "Odisha", "Uttaranchal": "Uttarakhand",
    "Pondicherry": "Puducherry", "Bengal": "West Bengal",
    "Andaman and Nicobar": "Andaman and Nicobar Islands",
}
KERALA_DISTRICTS = _g("""Thiruvananthapuram, Kollam, Pathanamthitta, Alappuzha, Kottayam, Idukki, Ernakulam,
Thrissur, Palakkad, Malappuram, Kozhikode, Wayanad, Kannur, Kasaragod""")
DISTRICT_ALIASES = {
    "Trivandrum": "Thiruvananthapuram", "Quilon": "Kollam", "Alleppey": "Alappuzha", "Trichur": "Thrissur",
    "Calicut": "Kozhikode", "Cannanore": "Kannur", "Kasargod": "Kasaragod",
}
COUNTRIES = _g("""Afghanistan, Argentina, Australia, Austria, Bangladesh, Belgium, Bhutan, Brazil, Canada,
China, Denmark, Egypt, Ethiopia, Fiji, Finland, France, Germany, Ghana, Greece, Indonesia, Iran, Iraq,
Ireland, Israel, Italy, Japan, Kenya, Kuwait, Malaysia, Maldives, Mauritius, Mexico, Mongolia, Myanmar,
Nepal, Netherlands, New Zealand, Nigeria, North Korea, Norway, Oman, Pakistan, Philippines, Poland,
Portugal, Qatar, Russia, Saudi Arabia, Seychelles, Singapore, South Africa, South Korea, Spain, Sri Lanka,
Sweden, Switzerland, Thailand, Turkey, Ukraine, United Arab Emirates, United Kingdom, United States,
Vietnam, Zimbabwe""")
COUNTRY_ALIASES = {"UAE": "United Arab Emirates", "UK": "United Kingdom", "Britain": "United Kingdom",
                   "US": "United States", "USA": "United States", "Holland": "Netherlands", "Burma": "Myanmar"}
CITIES = _g("""Mumbai, New Delhi, Bengaluru, Hyderabad, Chennai, Kolkata, Pune, Ahmedabad, Surat, Jaipur,
Lucknow, Kanpur, Nagpur, Indore, Bhopal, Patna, Vadodara, Ludhiana, Agra, Varanasi, Nashik, Coimbatore,
Madurai, Visakhapatnam, Vijayawada, Mysuru, Mangaluru, Guwahati, Bhubaneswar, Ranchi, Raipur, Dehradun,
Shimla, Srinagar, Amritsar, Panaji, Kochi, Gandhinagar, Jodhpur, Aurangabad""")
CITY_ALIASES = {"Bangalore": "Bengaluru", "Bombay": "Mumbai", "Madras": "Chennai", "Calcutta": "Kolkata",
                "Mysore": "Mysuru", "Mangalore": "Mangaluru", "Cochin": "Kochi", "Benaras": "Varanasi"}
ORGS = _g("""RBI, SEBI, ISRO, DRDO, NITI Aayog, ECI, Election Commission of India, UPSC, Supreme Court, CBI,
NIA, AIIMS, IIT, IISc, CSIR, ICMR, ICAR, NDRF, NDMA, CAG, NHRC, TRAI, IRDAI, NABARD, SIDBI, LIC, SBI, ONGC,
BHEL, HAL, BEL, NTPC, Coal India, Indian Railways, Indian Navy, Indian Army, Indian Air Force, BSF, CRPF,
ITBP, CISF, NSE, BSE, EPFO, FSSAI, CBSE, NCERT, UGC, AICTE, NAAC, KSEB, KSRTC, Kerala PSC, BARC, IMD,
Enforcement Directorate, GST Council, Finance Commission, Law Commission, National Green Tribunal, Lokpal""")
INTL_BODIES = _g("""United Nations, WHO, IMF, World Bank, WTO, UNESCO, UNICEF, NATO, BRICS, SCO, ASEAN, G20,
OPEC, IAEA, UNHCR, ILO, OECD, SAARC, Interpol, European Union""")
MINISTRIES = ["Ministry of " + n for n in _g("""Home Affairs, Finance, External Affairs, Defence, Education,
Health and Family Welfare, Railways, Agriculture, Environment, Power, Civil Aviation, Culture, Tourism,
Road Transport and Highways, Commerce and Industry, Science and Technology, Rural Development, Coal,
Jal Shakti, Ayush, Textiles, Petroleum and Natural Gas, Labour and Employment, Mines, Steel,
Women and Child Development, Electronics and Information Technology""")]
SPORTS_BODIES = _g("""BCCI, ICC, FIFA, UEFA, AFC, AIFF, IOA, IOC, AFI, BAI, Hockey India, FIH, NADA, WADA,
SAI, WFI, BFI, TTFI, ATP, WTA, Kerala Cricket Association, Sports Authority of India, Asian Games,
Commonwealth Games""")
# "India" is ambient in Indian news: keep it as a possible distractor, never as an answer.
AMBIENT = {"India"}
# Acronym/expansion pairs that must never appear as two separate options.
CONCEPTS = {"SAI": "Sports Authority of India", "ECI": "Election Commission of India",
            "IOC": "International Olympic Committee", "BAI": "Badminton Association of India",
            "AFI": "Athletics Federation of India", "IOA": "Indian Olympic Association"}

GAZETTEERS: dict[str, tuple[list[str], dict[str, str]]] = {
    "kerala-district": (KERALA_DISTRICTS, DISTRICT_ALIASES), "state": (STATES, STATE_ALIASES),
    "sports-body": (SPORTS_BODIES, {}), "organisation": (ORGS, {}), "ministry": (MINISTRIES, {}),
    "international-body": (INTL_BODIES, {}), "country": (COUNTRIES + ["India"], COUNTRY_ALIASES),
    "city": (CITIES, CITY_ALIASES),
}
# Most specific / most examinable type wins when several have a unique match.
TYPE_PRIORITY = ["kerala-district", "state", "sports-body", "organisation", "ministry",
                 "international-body", "country", "city", "numeric"]

NUMERIC_PATTERNS = [
    ("money", re.compile(r"(?:Rs\.?|₹|INR)\s?([\d,]+(?:\.\d+)?)\s*(?:crore|lakh|billion|million)\b", re.I)),
    ("percent", re.compile(r"\b([\d,]+(?:\.\d+)?)\s*(?:per cent|percent|%)", re.I)),
    ("power", re.compile(r"\b([\d,]+(?:\.\d+)?)\s*(?:MW|GW|kW)\b")),
    ("distance", re.compile(r"\b([\d,]+(?:\.\d+)?)\s*(?:km|kilometres|kilometers|metres|meters)\b", re.I)),
    ("count", re.compile(r"\b([\d,]+(?:\.\d+)?)\s*(?:crore|lakh|million|billion)\b", re.I)),
    ("years", re.compile(r"\b([\d,]+)\s*(?:years|year)\b", re.I)),
]

# Headlines that cannot become clean stems: quoted speech, questions, colon-led opinion forms, first person.
BAD_TITLE = re.compile(r"[?\"“”‘’']|^[^:]{0,30}:")
FIRST_PERSON = re.compile(r"\b(I|We|My|Our|Me|we|my|our|me|us)\b")


@lru_cache(maxsize=4096)
def _pattern(term: str) -> re.Pattern:
    """Word-boundary matcher. Acronyms match case-sensitively so 'SAI'/'US' don't hit ordinary words."""
    flags = 0 if (term.isupper() and len(term) <= 5) or "&" in term else re.I
    body = re.escape(term).replace(r"\ ", r"\s+").replace(" ", r"\s+")
    return re.compile(r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])", flags)


_COMPILED: dict[str, list[tuple[str, str, re.Pattern]]] = {}
for _typ, (_names, _al) in GAZETTEERS.items():
    _entries = [(n, n) for n in _names] + [(c, a) for a, c in _al.items()]
    _COMPILED[_typ] = [(canon, surf, _pattern(surf)) for canon, surf in _entries]


def _find_entities(text: str) -> dict[str, dict[str, set[str]]]:
    """type -> canonical -> set of matched surface forms, after dropping nested matches."""
    raw: dict[str, dict[str, set[str]]] = {}
    surfaces: set[str] = set()
    for typ, entries in _COMPILED.items():
        for canon, surf, pat in entries:
            if pat.search(text):
                raw.setdefault(typ, {}).setdefault(canon, set()).add(surf)
                surfaces.add(surf)
    # An entity that is a substring of another matched surface ("Bengal" in "West Bengal") is spurious.
    def nested(s: str) -> bool:
        return any(s.lower() in o.lower() and s.lower() != o.lower() for o in surfaces)
    out: dict[str, dict[str, set[str]]] = {}
    for typ, cands in raw.items():
        keep = {c: {s for s in ss if not nested(s)} for c, ss in cands.items()}
        keep = {c: ss for c, ss in keep.items() if ss and c not in AMBIENT}
        if keep:
            out[typ] = keep
    return out


def _find_numbers(text: str) -> list[tuple[str, str]]:
    """Non-overlapping numeric phrases as (whole phrase, number substring)."""
    found: list[tuple[int, int, str, str]] = []
    for _kind, pat in NUMERIC_PATTERNS:
        for m in pat.finditer(text):
            if any(m.start() < e and s < m.end() for s, e, _, _ in found):
                continue
            found.append((m.start(), m.end(), re.sub(r"\s+", " ", m.group(0)).strip(), m.group(1)))
    return [(phrase, num) for _s, _e, phrase, num in sorted(found)]


def _fmt_number(value: float, sample: str) -> str:
    if "." in sample:
        s = f"{value:,.1f}"
    else:
        s = f"{round(value):,}"
    return s if "," in sample else s.replace(",", "")


def _numeric_distractors(phrase: str, num: str) -> list[str]:
    try:
        base = float(num.replace(",", ""))
    except ValueError:
        return []
    if base <= 0:
        return []
    out: list[str] = []
    for factor in (0.5, 2.0, 1.5, 3.0, 0.25):
        cand = phrase.replace(num, _fmt_number(base * factor, num), 1)
        if cand != phrase and cand not in out:
            out.append(cand)
        if len(out) == 3:
            break
    return out if len(out) == 3 else []


def _distractor_pool(names: list[str], answer: str, haystack: str, width: int = 12) -> list[str]:
    """Same-type candidates: absent from the item, one per concept, and of comparable length so the
    options cannot be ordered by length."""
    seen: set[str] = {CONCEPTS.get(answer, answer)}
    pool: list[str] = []
    for n in names:
        concept = CONCEPTS.get(n, n)
        if n in AMBIENT or concept in seen or _pattern(n).search(haystack):
            continue
        seen.add(concept)
        pool.append(n)
    pool.sort(key=lambda n: abs(len(n) - len(answer)))
    return pool[:max(width, 3)]


def _blank_out(text: str, surfaces: set[str]) -> str:
    out = text
    for s in sorted(surfaces, key=len, reverse=True):
        out = _pattern(s).sub(BLANK, out)
    out = re.sub(r"(?:%s[\s,]+){1,}%s" % (BLANK, BLANK), BLANK, out)
    return re.sub(r"\s+", " ", out).strip()


def _context_words(stem: str) -> int:
    return len([w for w in stem.split() if BLANK not in w])


# (topic slug, entity types that imply it, keyword regex) — first match wins, default "geography".
TOPIC_RULES: list[tuple[str, set[str], str]] = [
    ("sports", {"sports-body"}, r"cricket|football|hockey|olympi|medal|tournament|world cup|test series|"
                                r"athletics|badminton|kabaddi|chess|wrestl|squad|championship"),
    ("kerala", {"kerala-district"}, r"kerala|malayalam|kochi|kozhikode|thiruvananthapuram|ksrtc|kseb|onam|"
                                    r"sabarimala|backwater"),
    ("economy", set(), r"rbi|sebi|crore|lakh|gdp|inflation|repo rate|bank|budget|tax|gst|export|import|"
                       r"rupee|fiscal|investment|trade|nabard|market"),
    ("general-science", set(), r"isro|drdo|satellite|rocket|launch|vaccine|icmr|csir|aiims|barc|space|"
                               r"mission|telescope|genome|clinical|scientist"),
    ("computers-tech", set(), r"artificial intelligence|semiconductor|chip|software|internet|5g|6g|cyber|"
                              r"data centre|startup|digital"),
    ("environment", set(), r"forest|wildlife|tiger|elephant|climate|monsoon|pollution|emission|"
                           r"biodiversity|wetland|sanctuary|solar|renewable|cyclone"),
    ("indian-polity", {"ministry"}, r"ministry|minister|court|election|parliament|lok sabha|rajya sabha|"
                                    r"bill|amendment|governor|president|commission|verdict|ordinance|"
                                    r"cabinet|government|govt|assembly|stipend|welfare|scheme"),
    ("arts-culture", set(), r"festival|museum|heritage|temple|award|literature|film|dance|music|monument"),
    ("indian-history", set(), r"anniversary|freedom struggle|independence|dynasty|ancient|medieval|"
                              r"empire|colonial|centenary"),
    ("world-gk", {"country", "international-body"}, r"(?!x)x"),
]


def _topic_slug(text: str, typ: str) -> str:
    """Map an item to a substantive GK topic slug so the bank stays browsable by subject."""
    low = text.lower()
    for slug, types, keywords in TOPIC_RULES:
        if typ in types or re.search(r"\b(?:%s)\b" % keywords, low):
            return slug
    return "geography"


def _sentence_with(summary: str, surfaces: set[str]) -> str | None:
    for sent in re.split(r"(?<=[.!?])\s+", summary):
        if any(_pattern(s).search(sent) for s in surfaces):
            return sent.strip()
    return None


def generate_heuristic(items: list[dict], max_questions: int = 20, seed: int | None = None) -> list[dict]:
    """Build fill-in-the-blank MCQs from news items using typed gazetteers. Stdlib only."""
    rng = random.Random(seed)
    out: list[dict] = []
    seen_stems: set[str] = set()
    answer_counts = [0, 0, 0, 0]

    for item in items:
        if len(out) >= max_questions:
            break
        title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
        summary = re.sub(r"\s+", " ", str(item.get("summary") or "")).strip()
        if not title or BAD_TITLE.search(title) or FIRST_PERSON.search(title):
            continue
        haystack = title + " " + summary[:300]

        entities = _find_entities(haystack)
        unique = {t: next(iter(c)) for t, c in entities.items() if len(c) == 1}
        numbers = _find_numbers(haystack)

        answer = distractors = None
        chosen_type = surfaces = None
        for typ in TYPE_PRIORITY:
            if typ == "numeric":
                if len(numbers) != 1:
                    continue
                phrase, num = numbers[0]
                if phrase not in title:  # numeric stems are only built from the headline
                    continue
                d = _numeric_distractors(phrase, num)
                if not d:
                    continue
                chosen_type, answer, distractors, surfaces = "numeric", phrase, d, {phrase}
                break
            if typ not in unique:
                continue
            canon = unique[typ]
            surf = entities[typ][canon]
            pool = _distractor_pool(GAZETTEERS[typ][0], canon, haystack)
            if len(pool) < 3:
                continue
            chosen_type, answer, distractors, surfaces = typ, canon, rng.sample(pool, 3), surf
            break
        if not answer:
            continue

        # Prefer the headline; fall back to the summary sentence that carries the entity.
        stem_src = title if (chosen_type == "numeric" or any(_pattern(s).search(title) for s in surfaces)) \
            else (_sentence_with(summary[:300], surfaces) or "")
        if not stem_src:
            continue
        body = _blank_out(stem_src, surfaces)
        if BLANK not in body or answer.lower() in body.lower() or _context_words(body) < 7:
            continue
        stem = _date_prefix(item.get("published")) + body.rstrip(".") + "."
        if not 8 <= len(stem.split()) <= 30:
            continue
        key = re.sub(r"\W+", " ", stem.lower()).strip()
        if key in seen_stems:
            continue

        if any(d.lower() in stem.lower() for d in distractors):
            continue
        options = [answer] + list(distractors)
        rng.shuffle(options)
        # Spread the correct index evenly over 0-3 across the batch.
        target = min(range(4), key=lambda i: (answer_counts[i], i))
        correct = options.index(answer)
        options[correct], options[target] = options[target], options[correct]
        answer_counts[target] += 1
        seen_stems.add(key)

        expl = f"From {item.get('source', 'the news')}, {item.get('published', '')}: {title}."
        out.append({
            "topic": "current-affairs",
            "question": stem,
            "options": options,
            "answer": target,
            "explanation": expl[:240],
            "difficulty": 1,
            "tags": ["current-affairs", "heuristic", _topic_slug(haystack, chosen_type), chosen_type],
            "source": "news-heuristic",
            "published_at": item.get("published"),
            "source_url": item.get("link"),
        })
    return out


def _date_prefix(published) -> str:
    try:
        d = date.fromisoformat(str(published)[:10])
        return f"({d.strftime('%b %Y')}) "
    except (ValueError, TypeError):
        return ""


SAMPLE_ITEMS = [
    {"source": "The Hindu Kerala", "published": "2026-08-28", "link": "https://example.com/a",
     "title": "Peechi Dam in Thrissur to open four spillway shutters on August 31",
     "summary": "The irrigation department said the reservoir had crossed its rule curve level after heavy rain in the catchment area."},
    {"source": "Deccan Herald Science", "published": "2026-08-27", "link": "https://example.com/b",
     "title": "ISRO completes long-duration hot test of the semi-cryogenic engine at Mahendragiri",
     "summary": "The engine will power the heavier upper stage planned for future heavy-lift launches."},
    {"source": "Deccan Herald Sports", "published": "2026-08-26", "link": "https://example.com/c",
     "title": "BCCI names a 15-member squad for the limited-overs tour against Australia",
     "summary": "The selection committee brought back two fast bowlers who had recovered from injury."},
    {"source": "The Hindu National", "published": "2026-08-25", "link": "https://example.com/d",
     "title": "New maritime coastal shipping corridor will link Kochi with Singapore from October",
     "summary": "The route is expected to cut transit time for containerised cargo moving through the region."},
    {"source": "Deccan Herald Business", "published": "2026-08-24", "link": "https://example.com/e",
     "title": "Union Cabinet approves Rs 1,200 crore package for coastal shipping modernisation",
     "summary": "The outlay covers berth upgrades, dredging and a fleet support scheme for domestic operators."},
    {"source": "TOI Top Stories", "published": "2026-08-23", "link": "https://example.com/f",
     "title": "Opinion: why we must rethink our transport policy?",
     "summary": "A columnist argues for a change of approach."},
]


def run_tests() -> None:
    qs = generate_heuristic(SAMPLE_ITEMS, max_questions=20, seed=7)
    assert len(qs) >= 4, f"expected several questions, got {len(qs)}"
    for q in qs:
        assert set(q) >= {"topic", "question", "options", "answer", "explanation", "difficulty",
                          "tags", "source", "published_at", "source_url"}
        assert q["topic"] == "current-affairs" and q["source"] == "news-heuristic"
        assert len(q["options"]) == 4 and len(set(q["options"])) == 4
        assert 0 <= q["answer"] <= 3
        assert BLANK in q["question"]
        assert 8 <= len(q["question"].split()) <= 30
        assert q["options"][q["answer"]].lower() not in q["question"].lower()
        assert len(q["explanation"]) <= 240
        assert q["tags"][:2] == ["current-affairs", "heuristic"] and len(q["tags"]) == 4
        assert q["difficulty"] == 1
    assert not [q for q in qs if "rethink our transport" in q["question"]], "opinion/question title not skipped"
    assert generate_heuristic(SAMPLE_ITEMS, seed=7) == qs, "seeded output must be deterministic"
    assert len({q["answer"] for q in qs}) >= min(4, len(qs)) - 1, "answer index not spread"
    assert generate_heuristic(SAMPLE_ITEMS * 3, seed=7) == qs, "duplicate stems must be dropped"
    assert generate_heuristic(SAMPLE_ITEMS, max_questions=2, seed=7).__len__() == 2
    print(f"OK: {len(qs)} questions, all assertions passed.")


if __name__ == "__main__":
    for _i, _q in enumerate(generate_heuristic(SAMPLE_ITEMS, seed=7), 1):
        print(f"\n{_i}. {_q['question']}")
        for _j, _o in enumerate(_q["options"]):
            print(f"   {'ABCD'[_j]}) {_o}{'   <-- answer' if _j == _q['answer'] else ''}")
        print(f"   tags={_q['tags']}  expl={_q['explanation']}")
    print()
    run_tests()

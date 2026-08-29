#!/usr/bin/env python3
"""Validate question bank JSON files. Usage: python3 data/validate.py data/questions/<file>.json [...]"""
import json, sys, collections, re
ok = True
for path in sys.argv[1:]:
    try:
        qs = json.load(open(path))
    except Exception as e:
        print(f"{path}: INVALID JSON: {e}"); ok = False; continue
    seen = set(); dist = collections.Counter(); errs = []
    for i, q in enumerate(qs):
        for k in ("topic","question","options","answer","explanation","difficulty","tags","source"):
            if k not in q: errs.append(f"#{i}: missing {k}")
        if not isinstance(q.get("options"), list) or len(q.get("options", [])) != 4: errs.append(f"#{i}: need 4 options")
        elif len(set(map(str.strip, map(str, q["options"])))) != 4: errs.append(f"#{i}: duplicate options")
        elif any(re.search(r"(all|none) of the above", str(o), re.I) for o in q["options"]): errs.append(f"#{i}: 'all/none of the above'")
        if not isinstance(q.get("answer"), int) or not 0 <= q.get("answer", -1) <= 3: errs.append(f"#{i}: answer must be int 0-3")
        else: dist[q["answer"]] += 1
        if q.get("difficulty") not in (1,2,3): errs.append(f"#{i}: difficulty 1-3")
        key = re.sub(r"\W+", " ", str(q.get("question","")).lower()).strip()
        if key in seen: errs.append(f"#{i}: duplicate question")
        seen.add(key)
        if len(str(q.get("explanation",""))) < 20: errs.append(f"#{i}: explanation too short")
    n = len(qs)
    skew = max(dist.values()) / n if n else 0
    if skew > 0.36: errs.append(f"answer position skew: {dict(dist)} (max share {skew:.0%} > 36%)")
    print(f"{path}: {n} questions, answer dist {dict(sorted(dist.items()))}, {len(errs)} problems")
    for e in errs[:30]: print("   ", e)
    ok = ok and not errs
sys.exit(0 if ok else 1)

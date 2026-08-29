# Question bank JSON schema

Each file in `data/questions/` is a JSON array. One file per topic, named `<topic-slug>.json`.

```json
[
  {
    "topic": "indian-history",
    "question": "Who founded the Mauryan Empire?",
    "options": ["Ashoka", "Chandragupta Maurya", "Bindusara", "Chanakya"],
    "answer": 1,
    "explanation": "Chandragupta Maurya founded the Mauryan Empire in 321 BCE with the guidance of Chanakya, overthrowing the Nanda dynasty.",
    "difficulty": 1,
    "tags": ["ancient-india", "mauryan"],
    "source": "seed"
  }
]
```

Rules:
- `options`: exactly 4 distinct strings, plausible distractors, no "All of the above"/"None of the above".
- `answer`: 0-based index into options. Vary the position of the correct answer evenly (roughly 25% each index).
- `explanation`: 1-2 sentences, factual, teaches something (this is shown after the user answers).
- `difficulty`: 1 = easy (10th level), 2 = medium (degree level / LDC), 3 = hard (UPSC prelims level).
- `tags`: 1-3 lowercase kebab-case tags.
- `source`: "seed" for hand-authored.
- Questions must be exam-style for Indian PSC (Kerala PSC / SSC / UPSC prelims), factually verified, unambiguous, self-contained, no images, no time-sensitive "current" facts (e.g. "current chief minister") unless in current-affairs topic.
- Never repeat a question within a file. Avoid trivia that is disputed.

Topic slugs (phase 1, all under the "GK" umbrella):
- indian-history        Indian History (ancient, medieval, modern, freedom struggle)
- kerala                Kerala History, Renaissance, Culture, Geography & Facts
- indian-polity         Indian Constitution & Polity
- geography             Geography (India & World, physical & political)
- economy               Indian Economy & basic economics
- general-science       Physics, Chemistry, Biology basics
- arts-culture          Arts, Culture, Literature, Awards (India)
- world-gk              World GK: organisations, countries, famous personalities, inventions
- sports                Sports & Games (rules, venues, trophies, famous players)
- computers-tech        Basics of Computers & IT, Cyber laws
- environment           Environment, Ecology, Biodiversity, Climate
- current-affairs       Current affairs (generated from news; not hand-authored)

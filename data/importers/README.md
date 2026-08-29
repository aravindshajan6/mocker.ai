# Importers

## MILU (`milu.py`)

`milu.py` builds bulk question banks from the **MILU** benchmark (English config, `test`
split of the Hugging Face dataset `murthyrudra/milu-cleaned`, ~13.5k rows, 1.9 MB parquet).
It maps MILU's `subject` field onto our topic slugs, drops non-GK subjects (maths/verbal
reasoning, engineering, medicine, law-exam content, agriculture, pedagogy, psychology),
applies a strict quality filter (single-line stems 15-220 chars; no match-the-following /
assertion-reason / multi-statement / arithmetic / grammar items; 4 distinct clean options,
no "All of the above"-style choices), routes any Kerala-related stem to `kerala`, strips
`(a)`/`A.`/`1)` option labels, deduplicates against `data/questions/*.json`, then shuffles
options round-robin (fixed seed) so each answer index holds ~25%. Output: one
`data/questions/milu-<topic>.json` per topic, capped at 600, minimum 20. Hand-authored
banks are never modified.

### Licence

MILU: *A Multi-task Indic Language Understanding Benchmark* — **CC-BY-4.0**,
[arXiv:2411.02538](https://arxiv.org/abs/2411.02538). Attribute the MILU authors when
redistributing these derived files.

### Rerun

```sh
cd data/importers
uv venv .venv
uv pip install --python .venv/bin/python pyarrow pandas requests
./.venv/bin/python milu.py            # re-downloads unless cache/*.parquet exists
python3 ../validate.py ../questions/milu-*.json
```

Delete `cache/` to force a fresh download. Both `.venv/` and `cache/` are gitignored.
Output is deterministic: the seed lives in `SEED` at the top of `milu.py`, and the
subject→topic mapping in `SUBJECT_TO_TOPIC` (printed on every run).

---

## Kerala PSC previous-year questions (`pyq.py`)

`pyq.py` builds question banks from **real Kerala PSC OMR exam papers** — the question
booklet PDF plus the official answer key PDF — published at
<https://www.keralapsc.gov.in/answerkey_omrexams>. Output: one
`data/questions/pyq-<topic>.json` per topic. Hand-authored and `milu-*` banks are never
modified; every `pyq-*.json` is regenerated from scratch on each run.

### What it does

1. **Crawls the index** (`?tid=All&page=0..239`, ~4.8k rows) with a browser User-Agent at
   ~1 request/second. Each row gives the post name, question-paper code, medium, date of
   test, key type and the PDF links. Only rows carrying **both** a question paper and an
   answer key are ingestable. The site has relabelled these fields at least five times
   since 2013 (`Question Paper Code:079/2026` / `QUESTION CODE : 135/2023` /
   `Paper Code:-144/2016`, separators `:`, `-`, `.`, `,`), so the field parsers are
   deliberately tolerant.
2. **Filters** to English-medium papers with a test date of 2019 or later.
3. **Prefers the Final Answer Key.** Finals are usually published later as a separate,
   paper-less row, so they are matched back by normalised paper code (`079/2026`,
   `79/2026` and `68-2026` all normalise to `<n>/<year>`). Every key PDF restates its own
   paper code; if it disagrees with the paper, the final key is rejected and the paper's
   own provisional key is used instead. The key actually used is recorded per question in
   `source_key`.
4. **Extracts text** with `pdftotext -layout`, then rejects unusable text layers
   (< 500 chars, or < 60 % ASCII letters — old scans and legacy-font booklets).
5. **Parses** the booklet and the key. Answer keys print two side-by-side blocks
   (1–50 | 51–100), so every `(q, A, B, C, D)` tuple on a line is scanned rather than
   anchoring to line starts. Booklets carry a numbered *instructions* list that also
   starts at "1.", and templates differ between papers, so every candidate "1." start is
   tried and the one yielding the most questions wins. Each booklet's alpha code is read
   off its own cover page and used to pick the right key column. Page-footer debris that
   `-layout` glues onto options (`A -3- 13/26`, `[P.T.O.]`) is stripped.
6. **Quality-gates** each question (see below), drops answers keyed `X`/`*`/`Deleted`,
   and deduplicates against every existing `data/questions/*.json` plus the rest of the run.
7. **Classifies** the survivors into topic slugs with an LLM, dropping everything that is
   not general knowledge.

### Topic classification

Papers mix GK with maths, English grammar, regional language and post-specific technical
sections, so each surviving question is labelled by an LLM: OpenAI-compatible
`POST https://api.groq.com/openai/v1/chat/completions`, model `qwen/qwen3.8-27b`,
`response_format: json_object`, key read from `LLM_API_KEY` in the project `.env` (never
logged). Questions go out 20 per request as stem + a short option preview; pacing follows
the `x-ratelimit-remaining-tokens` header (the free tier allows 8 000 tokens/minute), 429s
sleep 65 s, 401 aborts the run. Labels are cached under `cache/pyq/cls/` keyed by question
text and `PROMPT_VERSION`, so re-runs cost nothing; bump `PROMPT_VERSION` after editing the
prompt. `--no-llm`, a missing key, or a failing API all fall back to a deterministic
keyword classifier.

Anything that is not GK is dropped: maths and mental ability, English grammar and
vocabulary, regional-language questions, post-specific technical content, pedagogy, and —
the biggest single source of false positives — **degree-level subject specialism**,
especially literary criticism of individual poems and novels from HSST/Lecturer papers,
which otherwise lands in `arts-culture`. Match-the-following, `List – I / List – II` and
multi-statement questions are **kept**: they are authentic Kerala PSC style, and are only
dropped when the pairs themselves did not survive text extraction.

Papers are processed with general/common recruitment exams (Preliminary, LDC/LGS, Clerk,
Assistant, Police Constable, Excise, Teacher/HSST, Fireman, …) ahead of post-specific ones,
since they carry far more GK — but technical papers are still processed for their trailing
GK sections.

### Quality gates

Stem 15–60 words (130 for a self-contained match-the-following / multi-statement item);
4 options, none empty, none over 120 characters, all distinct, no bare alpha-code markers,
no "All/None of the above"; no stem referring to a table, figure, diagram, passage or
underlined text it cannot show; no `List – I`/`Column` reference without at least three
pair markers in the stem; at most 15 % non-ASCII characters. Every drop is counted and the
counts are printed at the end of the run.

### Licence and attribution

Kerala Public Service Commission permits reuse of this material **provided it is reproduced
accurately and attributed prominently**. Two consequences for this importer:

- **Options are never shuffled.** The answer index is whatever the real paper used, so the
  answer-position distribution is skewed and is reported but not corrected. This is the one
  schema rule these files deliberately break, so **strict answer balance is off for
  `pyq-*.json`**: `data/validate.py` treats a file whose records all carry `"source": "pyq"`
  as verbatim and skips its answer-position skew check. Faithful reproduction is a licence
  condition, not a data-quality defect — do not "fix" the distribution by shuffling.
- Every record carries `source_ref` (`Kerala PSC 079/2026 · Q37`), `source_url` (the exact
  booklet PDF), `source_key` (provisional vs final answer key) and `published_at` (date of
  test). Any UI surfacing these questions must show the Kerala PSC attribution.

### Known limitation: Malayalam / Tamil / Kannada papers

Only papers whose medium is exactly **English** are imported. Malayalam, Tamil and Kannada
booklets — and bilingual `English/Malayalam` booklets — are skipped: they are typeset in
legacy ASCII-mapped Shree-Mal-style fonts, so `pdftotext` returns mojibake rather than
Unicode and the text cannot be recovered without font-specific remapping. Papers dated
before 2019 are also skipped: they are 100-dpi scans whose text layer is junk. Both classes
are detected and logged rather than silently dropped.

### Rerun

```sh
cd data/importers
python3 pyq.py --limit 40          # 40 papers; --limit 500 walks the whole index
python3 ../validate.py ../questions/pyq-*.json
```

Flags: `--limit N` (papers), `--pages N` (index pages), `--no-llm` (keyword classifier
only), `--refresh-index` (re-download the listing), `--dry-run` (parse and classify but
write nothing).

Everything is cached under `cache/pyq/` (gitignored): `index/` the listing HTML, `pdf/` the
downloaded PDFs, `txt/` the `pdftotext -layout` output, `cls/` the topic labels. Re-runs
skip anything already cached, so an interrupted run resumes cheaply; delete a subdirectory
to force that stage to redo its work. Requires `pdftotext` (poppler-utils) on `PATH`; no
Python dependencies beyond the standard library.

<!-- PYQ-STATS -->

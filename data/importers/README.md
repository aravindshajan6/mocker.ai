# Importers

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

## Licence

MILU: *A Multi-task Indic Language Understanding Benchmark* — **CC-BY-4.0**,
[arXiv:2411.02538](https://arxiv.org/abs/2411.02538). Attribute the MILU authors when
redistributing these derived files.

## Rerun

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

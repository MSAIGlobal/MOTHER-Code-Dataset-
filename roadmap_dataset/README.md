# MOTHER roadmap coding dataset

Build multi-turn coding supervised fine-tuning data from the ten roadmap PDFs.
The reference extraction produced **730 units from 242 pages** across ten PDFs.
The DSA PDF contains **507** numbered entries, including seven beyond its title count.
Each accepted candidate contains three to five question/answer pairs on one task.

## 1. Index the PDFs

Requires Python 3.10+ and Poppler's `pdftotext`. Run from the repository root.
Keep source PDFs, extracted text, credentials and generated corpora on your training
storage. This directory contains pipeline code only.

```bash
RUN_DIR="$PWD/roadmap-run"
python3 roadmap_dataset/build.py index /path/to/pdfs "$RUN_DIR/units.jsonl"
```

## 2. Generate candidates

Use an approved teacher serving the chat-completions JSON interface. Its endpoint
receives extracted source passages. Set `MOTHER_DATASET_API_KEY` if it uses bearer
authentication. Pilot across documents before running the full index.

```bash
TEACHER_ENDPOINT=http://127.0.0.1:8000/v1/chat/completions
TEACHER_MODEL=your-teacher-model
python3 roadmap_dataset/build.py generate "$RUN_DIR/units.jsonl" "$RUN_DIR/candidates" \
  --endpoint "$TEACHER_ENDPOINT" --model "$TEACHER_MODEL" --limit 10
```

Remove `--limit 10` for full generation. Reuse the same endpoint, model, index and
work directory to resume. Generation retries failed responses and checkpoints
accepted drafts and skips per source unit. Use one generator process per run
directory. The pilot limit counts cached units and skips.

## 3. Review and export

```bash
python3 roadmap_dataset/build.py review "$RUN_DIR/candidates" "$RUN_DIR/review.jsonl"
python3 roadmap_dataset/build.py export "$RUN_DIR/candidates" "$RUN_DIR/review.jsonl" \
  "$RUN_DIR/reviewed"
```

Between commands, set the review record's `decision` to `approve` or `reject`.
Review provenance and usage rights, semantic correctness, tests and edge cases.
Run solution checks in an isolated environment and use MOTHER's existing corpus
screen before training. The generator parses Python syntax and checks turn
structure. It never runs generated code. The approval fingerprint binds to the
original candidate. Edits to answer text in the review packet are ignored.

Export requires approved examples from at least three groups. It assigns whole
roadmap documents and DSA pattern groups to seeded train, validation and test
splits. Each training row uses `messages`. `provenance.jsonl` maps each row back
to its source PDF, page and hash. Deduplication at this stage uses normalized
first-question text.

## 4. Merge with the exact CORE baseline

Use the code shards referenced by the **active CORE 8B run manifest or
trainer configuration**, including existing held-out code sets when available.
Robotics' checked-in `training/midtraining/run_v4_7b.py` defaults to
`v12r_data/processed/mother_core_v7b_cleared.jsonl` and accepts the
`MOTHER_CORE_DATA_FILE` override. Its `training/midtraining/patch_code_pool.py`
references `v12r_data/generated/code_security_pool.jsonl` as a replay pool.
These are leads for finding the live run's inputs. Verify the actual launcher
log, checkpoint lineage, manifest and attached replay pools, then supply the
active code shards, including a code-only extract if materialized into a mixed
corpus. The Robotics repo's `training/midtraining/resume_guard.py` documents why
historical v6/v7/v7b names cannot identify the active corpus by themselves.
The Robotics `training/midtraining/CODE_POSTTRAIN.md` also identifies older
code corpora that were retired. Verify the run and use frozen copies or a
read-only snapshot. Keep the output separate from the active training run.

```bash
python3 roadmap_dataset/merge.py \
  --baseline-train /path/from/active-manifest/code-train.jsonl \
  --baseline-validation /path/from/active-manifest/code-validation.jsonl \
  --baseline-test /path/from/active-manifest/code-test.jsonl \
  --roadmap "$RUN_DIR/reviewed" --out "$RUN_DIR/merged"
```

Baseline flags can be repeated for multiple shards. Omit optional holdout flags
only when those splits are unavailable. The merger accepts chat messages, flat
CORE `Question:/Answer:` records, question/answer pairs and Alpaca records.
Baseline rows retain their schema. Roadmap rows carry both `messages` and the
CORE flat `text` field with `category=code_cot`, plus a source label for the
corpus screen. Confirm how the active loader selects its training fields and
register or review the new source label under your existing provenance policy.

The merge streams JSONL, checks schemas and hashes every input while using a
temporary on-disk SQLite index. It keeps the first normalized initial prompt
per corpus, processing existing test, validation and train before roadmap
records. The report counts identical examples, conflicting answers and
cross-split collisions. If train duplicates encode deliberate replay weights,
review those counts before adopting a deduplicated build. Unstructured
`text` requires explicit opt-in and receives only exact text deduplication.
The pass does not detect semantic paraphrases or code clones across different
prompts. `roadmap-lineage.jsonl` maps retained additions to their input rows.

Review `merge-report.json` and verify split sizes and source coverage before
pointing a new run at the result. Use a separate run with a fresh dataset
index when changing corpus order or content. An existing checkpoint's chunk
offset belongs to its original corpus.

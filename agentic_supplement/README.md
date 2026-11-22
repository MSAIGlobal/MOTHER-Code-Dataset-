# MOTHER CORE agentic supplement 2

This first-party pilot has 84 train, 21 validation and 21 test examples.
It covers calculator argument fidelity, clarification, planning, bounded
recovery, partial results and draft-only requests. The six domains share
task templates, so the held-out domains measure transfer across vocabulary.
Use independent operational cases to measure broader generalisation.

The records use CORE's flat `text/category/source` format and the W29
calculator trace syntax. The included pilot is a candidate for the active
agent corpus. The production tokenizer, loader and live shards were
unavailable when building this bundle.

## Screen against the active agent corpus

Use the exact agent training and evaluation shards from the active run,
including separate replay pools. Multiple flags are supported. Add v7b
as another baseline if the supplement also feeds CORE midtraining.

```bash
python3 agentic_supplement.py --out staged-agentic-v2 \
  --baseline-train /path/to/current-agent-train.jsonl \
  --holdout /path/to/current-agent-eval.jsonl
```

The streaming check removes candidate collisions using normalized complete
text and the first comparable prompt. It reports rows with opaque prompt
formats. It does not rewrite sources or remove intentional replay repeats.
Check the active corpus schema, sampler routing and source approval before
adding only the staged train file to a new agent corpus version. Keep both
evaluation files outside the recursive training-shard directory. Verify
that tokenization preserves the final tool result and answer under the
actual sequence cap. Use a fresh data index for the new corpus version.

## External source decisions

- Visionscaper Agentic LLM Pretraining 1.7B is a mixed pretraining blend
  under CC BY-SA 4.0. Consider only train-split, provenance-cleared,
  benign function-calling records for a separate pilot. Track constituent
  sources. Keep the supplied holdouts independent and tokenize with MOTHER's
  tokenizer. https://huggingface.co/datasets/visionscaper/agentic-llm-pretraining-1.7b
- NVIDIA Nemotron SFT Agentic v4 is the first external SFT candidate.
  Prefer benign examples from tool_calling, then evaluate knowledge_agent
  separately for policy-grounded retrieval. Review OpenMDW 1.1 terms and
  trace provenance. Preserve the tool definition, arguments and result-ID
  linkage during conversion. Remove reasoning_content and review a bounded
  slice before import. https://huggingface.co/datasets/nvidia/Nemotron-SFT-Agentic-v4
- NVIDIA ToolScale is a secondary orchestration evaluation candidate.
  Its synthetic RL environment format needs adaptation before it can be
  compared with native SFT trajectories. https://huggingface.co/datasets/nvidia/ToolScale
- InfiAlign Qwen 7B SFT is a reasoning checkpoint and a reference for
  sample selection. Use its quality-first data selection approach. Keep
  MOTHER as the base model. https://huggingface.co/InfiX-ai/InfiAlign-Qwen-7B-SFT

No third-party rows or model weights are bundled. Keep external ingestion
scoped to reviewed benign tool use and independently validated outputs.

## Training efficiency comparison

Compare existing corpus alone and existing corpus plus the curated add-on
at the same non-padding token budget, checkpoint, optimizer settings and
evaluation suite. Track tool selection, exact argument validity, tool-result
grounding, recovery and side-effect errors, plus tokens per second. Compare
score gain per GPU-hour. If the add-on beats existing agent rows, test a
targeted swap at the same token budget while retaining the old manifest for
reproducibility. Existing data should be retired only after a measured win.

## Full node run

From the repository root, provide the exact active **agent** training shards
and available held-out shards. Use a new output path with space for a copy
of the baseline corpus. Supply v7b only if it is the intended merge target.

```bash
python3 agentic_supplement/run.py \
  --baseline-train /path/to/agent-train.jsonl \
  --holdout /path/to/agent-eval.jsonl \
  --out "$HOME/mother-agentic-v2-release"
```

The runner generates the supplement, filters initial-prompt and normalized
text collisions, copies the baseline in input order, appends only the
screened training rows, then checks the merged line count, appended bytes
and SHA-256 before publishing the output directory. Existing baseline
duplicates and replay ordering are preserved. Point a new run at
`agent-corpus.train.jsonl` specifically. The output directory also contains
standalone and held-out shards, so do not use it as a recursive training input.

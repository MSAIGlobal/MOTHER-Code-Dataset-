"""Build and stage a deterministic, first-party MOTHER agent curriculum."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unicodedata


PROMPT = re.compile(r"^SYSTEM: .*?\nUSER: (.*?)\nASSISTANT: ", re.S)
QA = re.compile(r"^Question:\s*(.*?)\n\s*Answer:", re.S)
SYSTEM = "You are MOTHER. Available tool: calc(expression). Use confirmed tool results and respect the user's constraints."
SCENARIOS = {
    "compute": ("accelerator trays", "GPUs"),
    "archive": ("archive cartons", "folders"),
    "stock": ("spare-parts bins", "filters"),
    "training": ("classroom packs", "workbooks"),
    "retail": ("supply crates", "bottles"),
    "library": ("shelving units", "books"),
}


def key(value):
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def row(question, answer, bucket, call=False):
    return {
        "category": "calc_tool" if call else "agent_chain_2step",
        "source": f"mother_agentic_supplement_v2:{bucket}",
        "text": f"SYSTEM: {SYSTEM}\nUSER: {question}\nASSISTANT: {answer}",
    }


def curriculum(domains):
    for domain in domains:
        container, unit = SCENARIOS[domain]
        for count, each in ((7, 12), (11, 8), (13, 9), (18, 4), (22, 7), (27, 16)):
            total = count * each
            expression = f"{count}*{each}"
            yield row(
                f"Calculate the number of {unit} in {count} {container} with {each} in each.",
                f'TOOL_CALL calc(expression="{expression}")\nTOOL_RESULT {total}\nThere are {total} {unit}.',
                "argument_fidelity", True,
            )
            yield row(
                f"I need a count of {unit} across {count} {container}. The contents per container are missing. What should we do first?",
                f"How many {unit} are in each container, and do all {count} contain the same number? "
                "If the quantities differ, provide the individual counts.",
                "clarify",
            )
            yield row(
                f"Outline the checks you would do before reporting a total for {count} {container} of {unit}. These are estimates and I need a verified total.",
                "Match the inventory to the requested containers, check that every container has a verified count, "
                "and resolve missing or repeated records before adding the counts. Report any unresolved gaps.",
                "plan",
            )
        yield row(
            f"The approved calculator timed out while counting {unit} for our {container}. The job allows one retry and already used it. What now?",
            "Mark the total as unverified and report that the retry budget is exhausted. Ask whether the operator wants to restart the job.",
            "bounded_recovery",
        )
        yield row(
            f"One of our {container} has no recorded count of {unit}. The subtotal of 81 includes only the confirmed entries. What can I report?",
            f"Report a confirmed subtotal of 81 {unit}, with one container pending. Leave the overall total open until that count is verified.",
            "partial_result",
        )
        yield row(
            f"The inventory for the {container} shows an approved count of {unit}. Draft a note for the reviewer, but keep it private.",
            "Draft: The inventory count has been approved. Please review the supporting record and flag any discrepancy. "
            "This draft has not been shared.",
            "no_side_effect",
        )


def read_rows(path):
    with path.open(encoding="utf-8") as handle:
        for line, raw in enumerate(handle, 1):
            if not raw.strip():
                yield None
                continue
            try:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("expected an object")
                yield data
            except ValueError as error:
                raise ValueError(f"{path}:{line}: {error}") from error


def prompt_keys(record):
    result = set()
    text = record.get("text")
    if isinstance(text, str):
        match = PROMPT.match(text) or QA.match(text)
        if match:
            result.add(key(match.group(1)))
    messages = record.get("messages", [])
    if isinstance(messages, list):
        message = next((m for m in messages if isinstance(m, dict) and m.get("role") == "user"), {})
        if isinstance(message.get("content"), str):
            result.add(key(message["content"]))
    return result


def external_overlap(paths, candidates):
    matched = set()
    reports = []
    for path in paths:
        counts = Counter()
        before = path.stat()
        for record in read_rows(path):
            if record is None:
                counts["blank_lines"] += 1
                continue
            counts["rows"] += 1
            prompts = prompt_keys(record)
            if not prompts:
                counts["opaque_prompt"] += 1
            keys = prompts & candidates
            text = record.get("text")
            if isinstance(text, str):
                exact = key(text)
                if exact in candidates:
                    keys.add(exact)
            if keys:
                counts["rows_overlapping"] += 1
                matched.update(keys)
        after = path.stat()
        identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        if identity(before) != identity(after) or not counts["rows"]:
            raise ValueError(f"Input changed during scan or is empty: {path}")
        reports.append({"path": str(path.resolve()), "size": before.st_size,
                        "mtime_ns": before.st_mtime_ns, **counts})
    return matched, reports


def write(path, records):
    with path.open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline-train", action="append", type=Path, default=[])
    parser.add_argument("--holdout", action="append", type=Path, default=[])
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    paths = args.baseline_train + args.holdout
    if len(paths) != len({p.resolve() for p in paths}):
        parser.error("baseline and holdout paths must be distinct")
    train = list(curriculum(("compute", "archive", "stock", "training")))
    held = {"validation": list(curriculum(("retail",))), "test": list(curriculum(("library",)))}
    # Answer-only templates can collapse across scenarios. Keep one per
    # normalized prompt and complete trace, across all generated splits.
    seen = set()
    for record in train + held["validation"] + held["test"]:
        prompts = prompt_keys(record)
        if len(prompts) != 1 or prompts & seen:
            raise ValueError("missing or duplicate generated prompt")
        seen.update(prompts)
    candidates = seen | {key(record["text"]) for record in train + held["validation"] + held["test"]}
    collisions, reports = external_overlap(paths, candidates)

    def retain(records):
        return [record for record in records if not (
            (prompt_keys(record) | {key(record["text"])}) & collisions
        )]

    clean = {"train": retain(train), **{name: retain(rows) for name, rows in held.items()}}
    if not all(clean.values()):
        raise ValueError("baseline overlap removed an entire split")
    report = {
        "baseline_checked": bool(args.baseline_train), "holdouts_checked": bool(args.holdout),
        "inputs": reports, "matched_keys": len(collisions),
        "rows": {name: len(rows) for name, rows in clean.items()},
        "category_mix": {name: dict(Counter(r["category"] for r in rows))
                         for name, rows in clean.items()},
        "bytes": {name: sum(len(r["text"].encode()) for r in rows) for name, rows in clean.items()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as tmp:
        stage = Path(tmp) / "stage"
        stage.mkdir()
        for name, records in clean.items():
            write(stage / f"agentic.{name}.jsonl", records)
        (stage / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        stage.rename(args.out)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

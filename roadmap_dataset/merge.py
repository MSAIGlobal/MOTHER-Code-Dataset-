"""Merge reviewed roadmap conversations with explicit, immutable CORE JSONL shards."""

import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata

from build import json_text


SPLITS = ("test", "validation", "train")
FLAT_QA = re.compile(r"^\s*Question:\s*(.+?)\n\s*Answer:\s*(.+)$", re.S)


def unpack(row):
    if not isinstance(row, dict):
        raise ValueError("Expected a JSON object")
    if "messages" in row:
        messages = row["messages"]
        if not isinstance(messages, list) or not messages:
            raise ValueError("Expected a nonempty messages list")
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in {
                "system", "developer", "user", "assistant", "tool", "function"
            }:
                raise ValueError("Invalid message role")
            content = message.get("content")
            if content is None and message["role"] == "assistant" and message.get("tool_calls"):
                continue
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Expected nonempty text content")
        users = [m["content"] for m in messages if m["role"] == "user"]
        if not users or not any(m["role"] == "assistant" for m in messages):
            raise ValueError("Expected user and assistant messages")
        return users[0], messages
    if "text" in row:
        value = row["text"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Expected nonempty flat text")
        match = FLAT_QA.match(value)
        if not match:
            return None, value
        question, answer = match.groups()
    elif "question" in row and "answer" in row:
        question, answer = row["question"], row["answer"]
    elif "instruction" in row and "output" in row:
        question, answer = row["instruction"], row["output"]
        context = row.get("input", "")
        if context:
            if not isinstance(question, str) or not isinstance(context, str):
                raise ValueError("Expected text instruction and input")
            question = f"{question}\n\n{context}"
    else:
        raise ValueError("Unsupported baseline schema")
    if any(not isinstance(value, str) or not value.strip() for value in (question, answer)):
        raise ValueError("Expected nonempty question and answer")
    messages = [{"role": "user", "content": question.strip()},
                {"role": "assistant", "content": answer.strip()}]
    return question, messages


def key(value):
    return hashlib.sha256(value.encode("utf-8")).digest()


def merge(args):
    if args.out.exists():
        raise ValueError("Choose a new output directory")
    shards = {split: getattr(args, f"baseline_{split}") or [] for split in SPLITS}
    if not shards["train"]:
        raise ValueError("Supply the baseline train shards from the active run manifest")
    inputs = [
        (split, "baseline", path)
        for split in SPLITS for path in shards[split]
    ] + [(split, "roadmap", args.roadmap / f"{split}.jsonl") for split in SPLITS]
    if len({path.resolve() for _, _, path in inputs}) != len(inputs):
        raise ValueError("The same input file was assigned more than once")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as tmp:
        staging = Path(tmp) / "merged"
        staging.mkdir()
        report = {"inputs": [], "output_rows": Counter(),
                  "baseline_holdout_supplied": {s: bool(shards[s]) for s in SPLITS[:2]}}
        with ExitStack() as stack:
            db = sqlite3.connect(Path(tmp) / "dedup.sqlite")
            stack.callback(db.close)
            db.execute("CREATE TABLE seen (key BLOB PRIMARY KEY, body BLOB, split TEXT) WITHOUT ROWID")
            outputs = {
                split: stack.enter_context((staging / f"{split}.jsonl").open("w", encoding="utf-8"))
                for split in SPLITS
            }
            lineage = stack.enter_context(
                (staging / "roadmap-lineage.jsonl").open("w", encoding="utf-8")
            )
            for split, origin, path in inputs:
                counts = Counter()
                checksum = hashlib.sha256()
                with path.open("rb") as handle:
                    for line, raw in enumerate(handle, 1):
                        checksum.update(raw)
                        if not raw.strip():
                            continue
                        counts["input_rows"] += 1
                        try:
                            row = json.loads(raw.decode("utf-8"))
                            prompt, body = unpack(row)
                            if origin == "roadmap" and "messages" not in row:
                                raise ValueError("Expected roadmap chat row")
                        except (UnicodeError, ValueError) as error:
                            raise ValueError(f"{path}:{line}: {error}") from error
                        body_hash = key(json_text(body))
                        if prompt is None:
                            counts["opaque_text_rows"] += 1
                            if not args.allow_opaque_text:
                                raise ValueError(f"{path}:{line}: flat text has no comparable Q&A delimiter")
                            row_key = b"text:" + body_hash
                        else:
                            # Normalize presentation variance while retaining operators and punctuation.
                            canonical = " ".join(unicodedata.normalize("NFC", prompt).split())
                            row_key = b"prompt:" + key(canonical)
                        previous = db.execute(
                            "SELECT body, split FROM seen WHERE key = ?", (row_key,)
                        ).fetchone()
                        if previous:
                            counts["exact_duplicate" if previous[0] == body_hash else "prompt_conflict"] += 1
                            if previous[1] != split:
                                counts["cross_split_overlap"] += 1
                            continue
                        db.execute("INSERT INTO seen VALUES (?, ?, ?)", (row_key, body_hash, split))
                        if origin == "roadmap":
                            lineage.write(json_text({
                                "split": split, "roadmap_line": line,
                                "merged_line": report["output_rows"][split] + 1,
                            }) + "\n")
                            row = {
                                **row, "category": "code_cot", "source": "roadmap_pdf_sft",
                                "text": "\n\n".join(
                                    ("Question:\n\n" if m["role"] == "user" else "Answer: ") + m["content"]
                                    for m in body
                                ),
                            }
                        outputs[split].write(json_text(row) + "\n")
                        counts["retained"] += 1
                        report["output_rows"][split] += 1
                report["inputs"].append({
                    "path": str(path.resolve()), "sha256": checksum.hexdigest(),
                    "split": split, "origin": origin, "counts": dict(counts),
                })
                db.commit()
        if not any(entry["counts"].get("input_rows") for entry in report["inputs"]
                   if entry["origin"] == "baseline" and entry["split"] == "train"):
            raise ValueError("Baseline train input is empty")
        (staging / "merge-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        staging.rename(args.out)
    print(json_text(report["output_rows"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for split in SPLITS:
        parser.add_argument(f"--baseline-{split}", type=Path, action="append")
    parser.add_argument("--roadmap", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-opaque-text", action="store_true")
    args = parser.parse_args()
    try:
        merge(args)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()

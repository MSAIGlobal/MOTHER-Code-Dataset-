"""Stage a deduplicated supplement and a verified, versioned agent corpus."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def copy_baseline(report, output):
    path = Path(report["path"])
    with path.open("rb") as source:
        before = path.stat()
        if (before.st_size, before.st_mtime_ns) != (report["size"], report["mtime_ns"]):
            raise ValueError(f"Baseline changed after screening: {path}")
        last = b""
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            output.write(block)
            last = block[-1:]
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise ValueError(f"Baseline changed during copying: {path}")
        if last != b"\n":
            output.write(b"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-train", type=Path, action="append", required=True)
    parser.add_argument("--holdout", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a new output directory")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    builder = Path(__file__).with_name("agentic_supplement.py")

    with tempfile.TemporaryDirectory(dir=args.out.parent) as temporary:
        stage = Path(temporary) / "release"
        command = [sys.executable, str(builder), "--out", str(stage)]
        for flag, paths in (("--baseline-train", args.baseline_train), ("--holdout", args.holdout)):
            for path in paths:
                command.extend((flag, str(path)))
        subprocess.run(command, check=True)

        manifest_path = stage / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        additions = (stage / "agentic.train.jsonl").read_bytes()
        merged = stage / "agent-corpus.train.jsonl"
        with merged.open("xb") as output:
            for report in manifest["inputs"][:len(args.baseline_train)]:
                copy_baseline(report, output)
            offset = output.tell()
            output.write(additions)

        digest = hashlib.sha256()
        rows = 0
        with merged.open("rb") as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(block)
                rows += block.count(b"\n")
            source.seek(offset)
            if source.read() != additions:
                raise ValueError("Merged supplement differs from screened training rows")
        expected = sum(r["rows"] + r.get("blank_lines", 0)
                       for r in manifest["inputs"][:len(args.baseline_train)])
        expected += manifest["rows"]["train"]
        if rows != expected:
            raise ValueError(f"Merged line count {rows} differs from expected {expected}")
        manifest["merged"] = {"lines": rows, "sha256": digest.hexdigest(),
                              "supplement_byte_offset": offset}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        stage.rename(args.out)
    print(f"Verified {rows:,} merged lines. Output: {args.out}")


if __name__ == "__main__":
    main()

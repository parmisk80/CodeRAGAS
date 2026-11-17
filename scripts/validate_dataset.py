"""Validate a CodeEval JSONL file.

Usage: python validate_dataset.py codeeval_template.jsonl

Checks:
1. Every row has the required fields.
2. Every pair_id has exactly one label=1 row and one label=0 row.
3. Counts per category.
4. If a row has tests, runs code + tests (subprocess, 5 s timeout) and checks
   that the result agrees with the label:
     - correct rows must pass
     - 'bug' and 'hallucinated_api' flawed rows must FAIL
     - 'insecure' flawed rows must PASS (they are only insecure, not wrong)

Note: this runs the code in the file. Only use it on code you trust.
"""
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

REQUIRED = ["id", "pair_id", "category", "task", "code", "label", "tests"]
CATEGORIES = {"bug", "insecure", "hallucinated_api"}


def run_tests(code: str, tests: list) -> bool:
    program = code + "\n" + "\n".join(tests) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, timeout=5)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def main(path: str) -> None:
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    problems = []

    for r in rows:
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            problems.append(f"{r.get('id', '?')}: missing fields {missing}")
        if r.get("category") not in CATEGORIES:
            problems.append(f"{r.get('id', '?')}: unknown category {r.get('category')}")

    pairs = defaultdict(list)
    for r in rows:
        pairs[r["pair_id"]].append(r["label"])
    for pid, labels in pairs.items():
        if sorted(labels) != [0, 1]:
            problems.append(f"{pid}: needs exactly one label=1 and one label=0, got {labels}")

    cats = Counter(r["category"] for r in rows if r["label"] == 0)
    print("Pairs per category:", dict(cats))
    print("Total rows:", len(rows))

    for r in rows:
        if not r["tests"]:
            continue
        passed = run_tests(r["code"], r["tests"])
        if r["label"] == 1 or r["category"] == "insecure":
            expected = True
        else:
            expected = False
        if passed != expected:
            problems.append(
                f"{r['id']}: tests {'passed' if passed else 'failed'} "
                f"but expected {'pass' if expected else 'fail'}"
            )

    if problems:
        print("\nProblems found:")
        for p in problems:
            print(" -", p)
    else:
        print("\nAll checks passed.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "codeeval_template.jsonl")
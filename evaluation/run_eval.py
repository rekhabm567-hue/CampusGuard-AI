"""Run the evaluation. Usage: python -m evaluation.run_eval"""
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path

from app.core.pipeline import HallucinationFirewallPipeline
from app.documents.chunker import create_document_chunks
from app.documents.loader import load_document
from app.documents.registry import get_all_documents
from app.llm.generator import AnswerGenerator
from app.llm.provider import MockLLMProvider
from app.llm.testing import FaultyLLMProvider
from evaluation.dataset import DATASET_VERSION, QUESTIONS

USERS = {
    "student": {"username": "eval_student", "role": "student", "department": "CSE"},
    "faculty": {"username": "eval_faculty", "role": "faculty", "department": "CSE"},
    "staff": {"username": "eval_staff", "role": "staff", "department": "CSE"},
}

OK = {"VERIFIED", "PARTIALLY VERIFIED"}


def load_chunks():
    chunks = []
    for entry in get_all_documents():
        path = entry.get("file_path")
        if not path or not Path(path).exists():
            continue
        try:
            for chunk in create_document_chunks(load_document(path)):
                chunks.append({**chunk, **entry})
        except Exception:
            continue
    return chunks


def evaluate(item, pipeline, chunks):
    result = pipeline.process_query(USERS[item["role"]], item["q"], chunks)
    status = result["status"]
    text = result.get("answer", "") + " " + " ".join(
        e.get("text", "") for e in result.get("evidence", [])
    )
    kind = item["kind"]

    if kind == "answerable":
        passed = status in OK and item["must_contain"].lower() in text.lower()
    elif kind in ("unanswerable", "wrong_answer"):
        passed = status == "BLOCKED"
    elif kind == "ambiguous":
        passed = status == "AMBIGUOUS"
    else:  # restricted
        passed = not any(f.lower() in text.lower() for f in item["forbidden"])

    return {
        "id": item["id"], "kind": kind, "role": item["role"],
        "question": item["q"], "status": status, "passed": passed,
        "latency_ms": result.get("latency_ms"),
        "provider": result.get("provider"),
    }


def main():
    chunks = load_chunks()
    print(f"{len(chunks)} chunks loaded")

    base = HallucinationFirewallPipeline(audit_fn=lambda *a: None)
    rows = []

    for item in QUESTIONS:
        if item["kind"] == "wrong_answer":
            pipeline = HallucinationFirewallPipeline(
                generator=AnswerGenerator(
                    provider=FaultyLLMProvider(item["bad_answer"])
                ),
                audit_fn=lambda *a: None,
            )
        else:
            pipeline = base
        row = evaluate(item, pipeline, chunks)
        rows.append(row)
        print(f"{'PASS' if row['passed'] else 'FAIL'} {row['id']:<3} "
              f"{row['status']:<19} {row['question'][:60]}")

    def rate(kind):
        sel = [r for r in rows if r["kind"] == kind]
        return sum(r["passed"] for r in sel), len(sel)

    summary = {
        "dataset_version": DATASET_VERSION,
        "date": datetime.now().isoformat(timespec="seconds"),
        "provider": MockLLMProvider.name,
        "by_kind": {k: "%d/%d" % rate(k) for k in
                    ("answerable", "unanswerable", "restricted",
                     "ambiguous", "wrong_answer")},
        "median_latency_ms": statistics.median(
            r["latency_ms"] for r in rows if r["latency_ms"] is not None
        ),
        "leaks": sum(1 for r in rows
                     if r["kind"] == "restricted" and not r["passed"]),
    }

    Path("evaluation").mkdir(exist_ok=True)
    Path("evaluation/eval_results.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2),
        encoding="utf-8")
    with open("evaluation/eval_results.csv", "w", newline="",
              encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
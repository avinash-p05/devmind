import json
from pathlib import Path


def generate_corpus(output: Path, document_count: int) -> int:
    if document_count < 1:
        raise ValueError("document_count must be positive")
    cases_path = Path(__file__).parents[2] / "data" / "evaluation" / "cases.jsonl"
    cases = [
        json.loads(line)
        for line in cases_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    output.mkdir(parents=True, exist_ok=True)

    written = 0
    source_documents: dict[str, list[str]] = {}
    for case in cases:
        for source, fact in zip(case["expected_sources"], case["key_facts"], strict=False):
            source_documents.setdefault(source, []).append(fact)

    for relative_path, facts in source_documents.items():
        path = output / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# {path.stem}\n\n"
            f"Evidence: {', '.join(sorted(set(facts)))}.\n"
            "This generated fixture represents an engineering knowledge source.\n",
            encoding="utf-8",
        )
        written += 1

    index = 0
    while written < document_count:
        category = ("logs", "runbooks", "source", "incidents")[index % 4]
        path = output / category / f"fixture-{index:04d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Generated engineering fixture {index}\n\n"
            f"fixture_id={index}; category={category}; "
            "This record is included for scale and ingestion testing.\n",
            encoding="utf-8",
        )
        written += 1
        index += 1
    return written

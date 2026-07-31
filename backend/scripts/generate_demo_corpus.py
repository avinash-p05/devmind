import argparse
from pathlib import Path

from app.ingestion.corpus import generate_corpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a reproducible DevMind corpus")
    parser.add_argument("output", type=Path)
    parser.add_argument("--documents", type=int, default=1000)
    args = parser.parse_args()
    print(f"Generated {generate_corpus(args.output, args.documents)} documents in {args.output}")


if __name__ == "__main__":
    main()

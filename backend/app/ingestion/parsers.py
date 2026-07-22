import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from app.domain.contracts import SourceMetadata
from app.ingestion.text import normalize_text


@dataclass(frozen=True)
class ParsedSource:
    content: str
    metadata: SourceMetadata


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    @property
    def text(self) -> str:
        return "\n".join(self._parts)


def parse_text_source(content: str, metadata: SourceMetadata) -> ParsedSource:
    normalized = normalize_text(content)
    if not normalized:
        raise ValueError("source content is empty after normalization")
    return ParsedSource(content=normalized, metadata=metadata)


def parse_file(
    path: str | Path,
    *,
    source_type: str = "document",
    service: str | None = None,
) -> ParsedSource:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"source file does not exist: {file_path}")

    suffix = file_path.suffix.lower()
    metadata = SourceMetadata(
        source_type=source_type,
        source_name=file_path.name,
        uri=file_path.as_uri(),
        path=str(file_path),
        service=service,
        extra={"format": suffix.removeprefix(".") or "text"},
    )
    if suffix == ".pdf":
        content = _extract_pdf_text(file_path)
    elif suffix in {".html", ".htm"}:
        extractor = _HTMLTextExtractor()
        extractor.feed(file_path.read_text(encoding="utf-8"))
        content = extractor.text
    else:
        content = file_path.read_text(encoding="utf-8")
    return parse_text_source(content, metadata)


def parse_repository_snapshot(
    root: str | Path,
    *,
    extensions: Iterable[str] = (
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".sql",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        ".log",
    ),
) -> list[ParsedSource]:
    repository = Path(root)
    if not repository.is_dir():
        raise FileNotFoundError(f"repository directory does not exist: {repository}")

    allowed_extensions = {extension.lower() for extension in extensions}
    commit_sha = _git_commit_sha(repository)
    parsed: list[ParsedSource] = []
    for path in sorted(repository.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in allowed_extensions:
            continue
        if any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        source = parse_file(path, source_type="repository")
        relative_path = str(path.relative_to(repository))
        parsed.append(
            ParsedSource(
                content=source.content,
                metadata=SourceMetadata(
                    source_type=source.metadata.source_type,
                    source_name=source.metadata.source_name,
                    uri=source.metadata.uri,
                    path=relative_path,
                    service=source.metadata.service,
                    commit_sha=commit_sha,
                    extra={
                        **source.metadata.extra,
                        "repository_root": str(repository),
                    },
                ),
            )
        )
    return parsed


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    pages = PdfReader(str(path)).pages
    return "\n".join(page.extract_text() or "" for page in pages)


def _git_commit_sha(repository: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None

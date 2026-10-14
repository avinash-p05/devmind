"""Turn files into plain text plus metadata. One parser per format, chosen by extension."""

import re
import subprocess
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".sql"}
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".ini"}
TEXT_EXTENSIONS = {".md", ".txt", ".log", ".html", ".htm", ".pdf"}
SUPPORTED_EXTENSIONS = CODE_EXTENSIONS | CONFIG_EXTENSIONS | TEXT_EXTENSIONS
SKIPPED_DIRECTORIES = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}

_FIELD = re.compile(r"^(Incident ID|Service|Severity|Date):\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ParsedSource:
    name: str
    path: str  # POSIX-style path relative to the indexed root; this is what gets cited
    source_type: str  # code | config | log | incident | document
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        extractor = _HTMLText()
        extractor.feed(raw)
        return "\n".join(extractor.parts)
    return raw


def classify(path: str) -> str:
    lowered = path.lower()
    suffix = Path(lowered).suffix
    if suffix in CODE_EXTENSIONS:
        return "code"
    if suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix == ".log" or lowered.startswith("logs/"):
        return "log"
    if lowered.startswith(("incidents/", "postmortems/")):
        return "incident"
    return "document"


def extract_metadata(path: str, content: str) -> dict[str, str]:
    """Pull out the fields people filter and ask about: title, service, incident id, severity."""
    metadata = {"format": Path(path).suffix.lstrip(".") or "text"}
    title = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title:
        metadata["title"] = title.group(1).strip()
    for key, value in _FIELD.findall(content):
        metadata[key.lower().replace(" ", "_")] = value.strip()
    return metadata


def parse_text(name: str, content: str, source_type: str | None = None) -> ParsedSource:
    path = name.replace("\\", "/")
    return ParsedSource(
        name=Path(path).name,
        path=path,
        source_type=source_type or classify(path),
        content=content,
        metadata=extract_metadata(path, content),
    )


def parse_directory(root: str | Path) -> list[ParsedSource]:
    """Parse every supported file under `root` (a repository or a folder of docs)."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"directory does not exist: {root}")
    commit_sha = _git_commit_sha(root)
    sources = []
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if SKIPPED_DIRECTORIES & set(file.parts):
            continue
        source = parse_text(file.relative_to(root).as_posix(), read_text(file))
        if commit_sha:
            source.metadata["commit_sha"] = commit_sha
        sources.append(source)
    return sources


def _git_commit_sha(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None

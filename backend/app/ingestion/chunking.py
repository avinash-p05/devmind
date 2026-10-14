import re


def normalize(text: str) -> str:
    """Collapse runs of spaces and blank lines; keep line structure (it matters for code/logs)."""
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Split into ~chunk_size character windows that overlap by `overlap` characters.

    Each window ends at the last paragraph or line break inside it when there is one, so
    chunks don't cut a sentence or a code line in half. The overlap keeps a fact that sits
    on a boundary retrievable from either side.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    text = normalize(text)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            window = text[start:end]
            boundary = max(window.rfind("\n\n"), window.rfind("\n"))
            if boundary > chunk_size // 2:
                end = start + boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        # Start the next chunk `overlap` characters back, snapped forward to a line start.
        next_start = end - overlap
        line_start = text.find("\n", next_start, end)
        if line_start != -1:
            next_start = line_start + 1
        start = max(next_start, start + 1)
    return chunks

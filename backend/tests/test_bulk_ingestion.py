from app.ingestion.bulk import build_repository_payloads


def test_build_repository_payloads_preserves_repository_metadata(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text(
        "def health():\n    return 'ok'\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Service\n", encoding="utf-8")

    payloads = build_repository_payloads(tmp_path)

    assert len(payloads) == 2
    service = next(payload for payload in payloads if payload.name == "service.py")
    assert service.source_type.value == "repository"
    assert service.metadata["path"] == "src\\service.py"
    assert service.metadata["format"] == "py"


def test_build_repository_payloads_ignores_unsupported_files(tmp_path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01")
    (tmp_path / "notes.txt").write_text("incident notes", encoding="utf-8")

    payloads = build_repository_payloads(tmp_path)

    assert [payload.name for payload in payloads] == ["notes.txt"]

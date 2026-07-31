from app.ingestion.corpus import generate_corpus


def test_generate_demo_corpus_creates_requested_scale(tmp_path) -> None:
    count = generate_corpus(tmp_path, 25)

    assert count == 25
    assert len(list(tmp_path.rglob("*"))) >= 25
    assert (tmp_path / "docs" / "oauth.md").exists()

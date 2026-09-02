from app.embeddings import EMBEDDING_DIMENSION, embed_text, embedding_metadata


def test_embedding_is_deterministic_and_normalized() -> None:
    first = embed_text("connection pool exhausted")
    second = embed_text("connection pool exhausted")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSION
    assert max(abs(value) for value in first) <= 1
    assert any(value != 0 for value in first)


def test_embedding_metadata_identifies_the_configured_provider() -> None:
    metadata = embedding_metadata()

    assert metadata["provider"] == "local"
    assert metadata["model"] == "local-hash-v1"
    assert metadata["dimension"] == EMBEDDING_DIMENSION

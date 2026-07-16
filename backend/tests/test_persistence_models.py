from app.persistence.models import Base, ChunkRecord, DocumentRecord


def test_persistence_models_define_expected_tables_and_vector_column() -> None:
    assert set(Base.metadata.tables) == {"documents", "chunks", "incidents"}
    assert DocumentRecord.__tablename__ == "documents"
    assert DocumentRecord.__table__.c.metadata is not None
    assert ChunkRecord.__table__.c.embedding.type.dim == 1536
    assert ChunkRecord.__table__.c.document_id.foreign_keys

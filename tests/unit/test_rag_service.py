from uuid import UUID

from src.models.domain import SearchResult
from src.services.rag_service import RagService


class FakeDocuments:
    def search(self, query, top_k, metadata=None, category=None):
        return [SearchResult(0.9, "pgvector almacena vectores.", {"source": "manual.txt"}, UUID(int=1))]


class FakeLlm:
    def complete(self, messages):
        assert "pgvector almacena vectores" in messages[-1]["content"]
        return "Respuesta [1]", "free/test"


def test_rag_uses_retrieved_context() -> None:
    answer = RagService(FakeDocuments(), FakeLlm()).chat("¿Qué almacena?")
    assert answer.answer == "Respuesta [1]"
    assert answer.sources[0].score == 0.9

"""
공용 임베딩 함수 모듈 — multilingual-e5-large
ChromaDB의 EmbeddingFunction 인터페이스를 구현하여
ingest_laws.py, ingest_pps_qa.py, gemini_engine.py에서 통일 사용.

E5 모델 규칙:
  - 적재 시: "passage: " + 원문
  - 검색 시: "query: " + 질의문
"""
import os
from chromadb import EmbeddingFunction, Documents, Embeddings

MODEL_NAME = "intfloat/multilingual-e5-large"
_model = None  # 싱글턴 지연 로드


def _get_model():
    """SentenceTransformer 모델 싱글턴."""
    global _model
    if _model is not None:
        return _model

    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer(MODEL_NAME)
    print(f"  [Embedding] {MODEL_NAME} loaded")
    return _model


class E5EmbeddingFunction(EmbeddingFunction):
    """
    ChromaDB용 E5 임베딩 함수.
    add() 시에는 "passage: " 접두사, query() 시에는 "query: " 접두사 적용.
    ChromaDB는 add 시 __call__을, query 시 __call__을 호출하므로
    모드를 수동으로 전환해야 함.
    """

    def __init__(self, mode: str = "passage"):
        """mode: 'passage' (적재) 또는 'query' (검색)"""
        self._mode = mode

    def __call__(self, input: Documents) -> Embeddings:
        model = _get_model()
        prefix = "query: " if self._mode == "query" else "passage: "
        texts = [prefix + doc for doc in input]
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


# 편의 함수: 적재/검색용 인스턴스
def get_passage_embedding_fn() -> E5EmbeddingFunction:
    """적재(add) 시 사용: 'passage: ' 접두사 적용."""
    return E5EmbeddingFunction(mode="passage")

def get_query_embedding_fn() -> E5EmbeddingFunction:
    """검색(query) 시 사용: 'query: ' 접두사 적용."""
    return E5EmbeddingFunction(mode="query")

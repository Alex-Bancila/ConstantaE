"""Create multilingual embeddings for law articles (owner: Lucas)."""

from collections.abc import Sequence

from app.ai.rag.articles import LawArticle

MODEL_NAME = "intfloat/multilingual-e5-small"


def build_passages(articles: Sequence[LawArticle]) -> list[str]:
    return [f"passage: {article.text}" for article in articles]


def build_query(question: str) -> str:
    # e5 models are trained with "query: " on questions and "passage: " on documents.
    return f"query: {question}"


class ArticleEmbedder:
    def __init__(self, model_name: str = MODEL_NAME) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "sentence-transformers is required to create law embeddings"
            ) from error

        self._model = SentenceTransformer(model_name)
        dimensions = self._model.get_sentence_embedding_dimension()
        if dimensions is None:
            raise RuntimeError(f"Embedding model {model_name} did not report its dimensions")
        self.dimensions = dimensions

    def embed(self, articles: Sequence[LawArticle]) -> list[list[float]]:
        vectors = self._model.encode(
            build_passages(articles),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, question: str) -> list[float]:
        vector = self._model.encode(
            build_query(question),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()

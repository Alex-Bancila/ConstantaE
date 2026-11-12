from app.ai.rag.articles import LawArticle
from app.ai.rag.embeddings import build_passages


def test_build_passages_uses_e5_passage_prefix():
    articles = [
        LawArticle(
            law_name="OG 21/1992",
            article_number="1",
            text="Protecția consumatorilor.",
            source_url="https://example.test/law",
        )
    ]

    assert build_passages(articles) == ["passage: Protecția consumatorilor."]

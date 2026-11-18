from app.ai.rag.articles import split_articles


def test_split_articles_keeps_paragraphs_and_letters_together():
    articles = split_articles(
        """Preamble
Articolul 1
Titlu
(1) Primul alineat.
a) Prima literă.
b) A doua literă.
Articolul 2
(1) Al doilea articol.
""",
        law_name="Test law",
        source_url="https://example.test/law",
    )

    assert [article.article_number for article in articles] == ["1", "2"]
    assert articles[0].text == "Titlu\n(1) Primul alineat.\na) Prima literă.\nb) A doua literă."
    assert articles[0].law_name == "Test law"
    assert articles[0].source_url == "https://example.test/law"


def test_split_articles_supports_superscript_numbers_and_inline_titles():
    articles = split_articles(
        """Art. 9^1: Drept suplimentar
Conținutul articolului.
Articolul 10
Conținutul următorului articol.
""",
        law_name="Test law",
        source_url="https://example.test/law",
    )

    assert [article.article_number for article in articles] == ["9^1", "10"]
    assert articles[0].text == "Drept suplimentar\nConținutul articolului."


def test_split_articles_can_ignore_quoted_articles_from_an_amendment():
    articles = split_articles(
        """Capitolul VII
Articolul 29
După articolul 17 se introduce:
Articolul 17^1
Textul articolului citat.
""",
        law_name="Test law",
        source_url="https://example.test/law",
        article_numbers={"29"},
    )

    assert [article.article_number for article in articles] == ["29"]
    assert "Articolul 17^1" in articles[0].text

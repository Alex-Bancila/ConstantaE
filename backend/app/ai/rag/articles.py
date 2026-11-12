"""Split consolidated law texts into article records (owner: Lucas)."""

import re
from dataclasses import dataclass

from app.ai.rag.text import normalize_diacritics

_ARTICLE_HEADING = re.compile(
    r"(?m)^[ \t]*(?:Articolul|Art\.)[ \t]+"
    r"(?P<number>\d+(?:\^\d+)?)(?:[ \t]*:[ \t]*(?P<title>[^\r\n]*))?[ \t]*$"
)


@dataclass(frozen=True)
class LawArticle:
    law_name: str
    article_number: str
    text: str
    source_url: str


def split_articles(
    text: str,
    law_name: str,
    source_url: str,
    article_numbers: set[str] | None = None,
) -> list[LawArticle]:
    """Split a consolidated law into article records.

    ``article_numbers`` can be used when the source includes quoted articles
    from other laws inside an amendment article.
    """
    normalized_text = normalize_diacritics(text)
    matches = [
        match
        for match in _ARTICLE_HEADING.finditer(normalized_text)
        if article_numbers is None or match.group("number") in article_numbers
    ]

    articles: list[LawArticle] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized_text)
        body = normalized_text[match.end() : end].strip()
        title = match.group("title")
        if title:
            body = f"{title}\n{body}" if body else title
        if not body:
            raise ValueError(f"Article {match.group('number')} has no text")
        articles.append(
            LawArticle(
                law_name=law_name,
                article_number=match.group("number"),
                text=body,
                source_url=source_url,
            )
        )
    return articles

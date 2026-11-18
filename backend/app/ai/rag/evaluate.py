"""Measures how often the legal report cites the right article (owner: Lucas).

Run from the backend folder, after `python -m app.ai.rag.ingest`:

    python -m app.ai.rag.evaluate                    # retrieval + report (needs LLM_API_KEY)
    python -m app.ai.rag.evaluate --retrieval-only   # free: no LLM calls

The questions and their expected articles are in tests/data/legal_questions.json.
Two numbers are printed:

- retrieval: the expected article is among the articles the LLM is shown;
- report: the report actually cites the expected article.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.ai.rag.report import (
    ARTICLES_PER_QUESTION,
    LLM_FAILED_SUMMARY,
    WriteSummary,
    answer_questions,
)
from app.ai.rag.retrieval import RetrievedArticle
from app.config import get_settings

QUESTIONS_FILE = Path(__file__).resolve().parents[3] / "tests" / "data" / "legal_questions.json"

Search = Callable[[str, int], Sequence[RetrievedArticle]]


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected: frozenset[tuple[str, str]]  # (law, article number), any one counts


@dataclass(frozen=True)
class EvalResult:
    case: EvalCase
    retrieved: list[tuple[str, str]]
    cited: list[tuple[str, str]] | None  # None when the report was not run

    @property
    def retrieval_hit(self) -> bool:
        return any(item in self.case.expected for item in self.retrieved)

    @property
    def report_hit(self) -> bool:
        return self.cited is not None and any(item in self.case.expected for item in self.cited)


def load_cases(path: Path = QUESTIONS_FILE) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        EvalCase(
            question=item["question"],
            expected=frozenset((e["law"], e["article"]) for e in item["expected"]),
        )
        for item in raw
    ]


def evaluate(
    cases: Sequence[EvalCase],
    search: Search,
    write_summary: WriteSummary | None,
) -> list[EvalResult]:
    results = []
    for case in cases:
        retrieved = [
            (r.article.law_name, r.article.article_number)
            for r in search(case.question, ARTICLES_PER_QUESTION)
        ]
        cited = None
        if write_summary is not None:
            legal = answer_questions(
                [case.question],
                problems=[case.question],
                search=search,
                write_summary=write_summary,
            )
            cited = [(c.law, c.article.removeprefix("Art. ")) for c in legal.citations]
            if legal.summary == LLM_FAILED_SUMMARY:
                # The fallback lists every retrieved article; that is not a citation.
                cited = []
        results.append(EvalResult(case=case, retrieved=retrieved, cited=cited))
    return results


def _format(items: Sequence[tuple[str, str]] | None) -> str:
    if items is None:
        return "-"
    return ", ".join(f"{law} art. {article}" for law, article in items) or "nothing"


def print_results(results: Sequence[EvalResult]) -> None:
    for number, result in enumerate(results, start=1):
        expected = _format(sorted(result.case.expected))
        print(f"{number:2}. {result.case.question}")
        print(f"    expected:  {expected}")
        mark = "ok" if result.retrieval_hit else "MISS"
        print(f"    retrieved: {_format(result.retrieved)}  [{mark}]")
        if result.cited is not None:
            mark = "ok" if result.report_hit else "MISS"
            print(f"    cited:     {_format(result.cited)}  [{mark}]")

    total = len(results)
    retrieval = sum(r.retrieval_hit for r in results)
    print()
    print(
        f"Retrieval: {retrieval}/{total} questions have the expected article "
        f"in the top {ARTICLES_PER_QUESTION}"
    )
    if results and results[0].cited is not None:
        report = sum(r.report_hit for r in results)
        print(f"Report:    {report}/{total} reports cite the expected article")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--retrieval-only", action="store_true", help="skip the LLM and only check retrieval"
    )
    args = parser.parse_args()

    from app.ai.rag.retrieval import retrieve

    summarize = None
    if not args.retrieval_only:
        if not get_settings().llm_api_key:
            parser.error("LLM_API_KEY is not set; set it in .env or use --retrieval-only")
        from app.ai.rag.llm import write_summary as summarize

    print_results(evaluate(load_cases(), search=retrieve, write_summary=summarize))


if __name__ == "__main__":
    main()

from app.ai.rag.articles import LawArticle
from app.ai.rag.evaluate import EvalCase, evaluate, load_cases, print_results
from app.ai.rag.ingest import load_articles
from app.ai.rag.retrieval import RetrievedArticle

ART_9 = LawArticle("OUG 34/2014", "9", "Dreptul de retragere.", "https://e.test/oug")
ART_13 = LawArticle("OUG 34/2014", "13", "Rambursarea în 14 zile.", "https://e.test/oug")


def search(question: str, k: int) -> list[RetrievedArticle]:
    return [RetrievedArticle(article=ART_9, score=1.0), RetrievedArticle(article=ART_13, score=0.5)]


def test_test_set_has_ten_questions_whose_expected_articles_exist():
    cases = load_cases()
    stored = {(a.law_name, a.article_number) for a in load_articles()}

    assert len(cases) == 10
    assert len({case.question for case in cases}) == 10
    for case in cases:
        assert case.expected, case.question
        assert case.expected <= stored, case.question


def test_evaluate_counts_retrieval_and_report_hits():
    cases = [
        EvalCase("În cât timp pot returna?", frozenset({("OUG 34/2014", "9")})),
        EvalCase("Când primesc banii?", frozenset({("OUG 34/2014", "13")})),
    ]

    # The report cites only [1] (art. 9), so the second question is a report miss.
    results = evaluate(cases, search=search, write_summary=lambda system, user: "Răspuns [1].")

    assert [r.retrieval_hit for r in results] == [True, True]
    assert [r.report_hit for r in results] == [True, False]


def test_llm_failure_counts_as_a_report_miss():
    def failing(system: str, user: str) -> str:
        raise RuntimeError("API down")

    cases = [EvalCase("În cât timp pot returna?", frozenset({("OUG 34/2014", "9")}))]

    (result,) = evaluate(cases, search=search, write_summary=failing)

    assert result.retrieval_hit
    assert not result.report_hit


def test_retrieval_only_skips_the_report(capsys):
    cases = [EvalCase("În cât timp pot returna?", frozenset({("OUG 34/2014", "9")}))]

    results = evaluate(cases, search=search, write_summary=None)
    print_results(results)

    assert results[0].cited is None
    output = capsys.readouterr().out
    assert "Retrieval: 1/1" in output
    assert "Report:" not in output

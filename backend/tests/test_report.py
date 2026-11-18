from types import SimpleNamespace

import pytest

from app.ai.rag import llm, report
from app.ai.rag.articles import LawArticle
from app.ai.rag.report import (
    LLM_FAILED_SUMMARY,
    NOTHING_FOUND_SUMMARY,
    WITHDRAWAL_QUESTION,
    apply_citations,
    build_prompt,
    build_questions,
    build_report,
    generate_report,
    to_citation,
)
from app.ai.rag.retrieval import RetrievedArticle
from app.config import get_settings
from app.schemas import PageData, TrustCheck

ART_9 = LawArticle("OUG 34/2014", "9", "Dreptul de retragere: 14 zile.", "https://e.test/oug")
ART_6 = LawArticle("OUG 34/2014", "6", "Cerințe de informare.", "https://e.test/oug")
OG_ART_3 = LawArticle("OG 21/1992", "3", "Drepturile consumatorilor.", "https://e.test/og")

NO_CUI = TrustCheck(id="cui_present", passed=False, message="No CUI was found on the page.")
NO_RETURNS = TrustCheck(id="return_policy", passed=False, message="No return policy was found.")


def search_returning(*articles: LawArticle):
    calls: list[tuple[str, int]] = []

    def search(question: str, k: int) -> list[RetrievedArticle]:
        calls.append((question, k))
        return [RetrievedArticle(article=a, score=0.5) for a in articles[:k]]

    search.calls = calls
    return search


def writer_returning(text: str):
    prompts: list[tuple[str, str]] = []

    def write(system: str, user: str) -> str:
        prompts.append((system, user))
        return text

    write.prompts = prompts
    return write


def test_one_question_per_failed_check_plus_withdrawal():
    questions = build_questions([NO_CUI, NO_RETURNS])

    assert len(questions) == 3
    assert questions[-1] == WITHDRAWAL_QUESTION


def test_withdrawal_is_asked_even_when_every_check_passes():
    assert build_questions([]) == [WITHDRAWAL_QUESTION]


def test_checks_asking_the_same_thing_produce_one_question():
    cui_valid = TrustCheck(id="cui_valid", passed=False, message="The CUI is invalid.")

    assert len(build_questions([NO_CUI, cui_valid])) == 2


def test_unknown_check_becomes_a_question_about_its_message():
    new_check = TrustCheck(id="new_check", passed=False, message="Something odd.")

    assert "Something odd." in build_questions([new_check])[0]


def test_prompt_numbers_articles_and_only_includes_check_messages():
    prompt = build_prompt([NO_CUI], [ART_9, OG_ART_3])

    assert "- No CUI was found on the page." in prompt
    assert "[1] OUG 34/2014, art. 9\nDreptul de retragere: 14 zile." in prompt
    assert "[2] OG 21/1992, art. 3" in prompt


def test_markers_become_labels_and_decide_the_citations():
    summary, cited = apply_citations(
        "Ai 14 zile să returnezi bunul [1]. Vânzătorul trebuie să se identifice [2][1].",
        [ART_9, ART_6],
    )

    assert summary == (
        "Ai 14 zile să returnezi bunul (OUG 34/2014, art. 9). Vânzătorul trebuie să se "
        "identifice (OUG 34/2014, art. 6; OUG 34/2014, art. 9)."
    )
    assert cited == [ART_9, ART_6]


def test_markers_outside_the_retrieved_articles_are_dropped():
    summary, cited = apply_citations("Ai 14 zile [1, 7]. Altceva [3].", [ART_9])

    assert summary == "Ai 14 zile (OUG 34/2014, art. 9). Altceva."
    assert cited == [ART_9]


def test_report_cites_only_the_articles_the_summary_uses():
    search = search_returning(ART_9, ART_6, OG_ART_3)
    write = writer_returning("Ai 14 zile [1]. Vânzătorul trebuie să-și afișeze datele [2].")

    legal = build_report([NO_CUI], search=search, write_summary=write)

    assert legal.summary.startswith("Ai 14 zile (OUG 34/2014, art. 9).")
    assert [(c.law, c.article) for c in legal.citations] == [
        ("OUG 34/2014", "Art. 9"),
        ("OUG 34/2014", "Art. 6"),
    ]
    assert [question for question, _ in search.calls][-1] == WITHDRAWAL_QUESTION


def test_each_article_is_sent_to_the_llm_once():
    search = search_returning(ART_9, ART_6)
    write = writer_returning("Ai 14 zile [1].")

    build_report([NO_CUI, NO_RETURNS], search=search, write_summary=write)

    _, user_message = write.prompts[0]
    assert user_message.count("OUG 34/2014, art. 9") == 1
    assert "[3]" not in user_message


def test_nothing_retrieved_says_so_without_calling_the_llm():
    write = writer_returning("should not be used")

    legal = build_report([NO_CUI], search=search_returning(), write_summary=write)

    assert legal.summary == NOTHING_FOUND_SUMMARY
    assert legal.citations == []
    assert write.prompts == []


def test_llm_finding_nothing_relevant_says_so_instead_of_making_something_up():
    legal = build_report(
        [NO_CUI],
        search=search_returning(OG_ART_3),
        write_summary=writer_returning("NIMIC RELEVANT"),
    )

    assert legal.summary == NOTHING_FOUND_SUMMARY
    assert legal.citations == []


def test_llm_failure_still_returns_the_retrieved_articles():
    def failing_writer(system: str, user: str) -> str:
        raise llm.SummaryError("API down")

    legal = build_report([NO_CUI], search=search_returning(ART_9), write_summary=failing_writer)

    assert legal.summary == LLM_FAILED_SUMMARY
    assert [c.article for c in legal.citations] == ["Art. 9"]


def test_long_article_text_is_shortened_in_the_citation():
    long_article = LawArticle("OUG 34/2014", "6", "cuvânt " * 200, "https://e.test/oug")

    citation = to_citation(long_article)

    assert len(citation.text) <= 501
    assert citation.text.endswith("…")
    assert citation.link == "https://e.test/oug"


def test_real_mode_uses_retrieval_and_the_llm(monkeypatch):
    monkeypatch.setenv("AI_MODE", "real")
    get_settings.cache_clear()
    monkeypatch.setattr(report, "retrieve", search_returning(ART_9))
    monkeypatch.setattr(llm, "write_summary", writer_returning("Ai 14 zile [1]."))

    legal = generate_report(PageData(url="https://shop.test"), [NO_CUI])

    assert legal.summary == "Ai 14 zile (OUG 34/2014, art. 9)."
    assert "[MOCK]" not in legal.summary


class FakeMessages:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def fake_client(monkeypatch, response: SimpleNamespace) -> FakeMessages:
    messages = FakeMessages(response)
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    keys: list[str] = []

    def make_client(api_key: str):
        keys.append(api_key)
        return client

    monkeypatch.setattr(llm, "_client", make_client)
    messages.keys = keys
    return messages


def claude_response(stop_reason: str = "end_turn", text: str = "Rezumat [1].") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        _request_id="req_test",
    )


def test_write_summary_requires_the_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(get_settings(), "llm_api_key", None)

    with pytest.raises(llm.SummaryError, match="LLM_API_KEY"):
        llm.write_summary("system", "user")


def test_write_summary_reads_the_key_from_settings_and_returns_the_text(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    get_settings.cache_clear()
    messages = fake_client(monkeypatch, claude_response())

    assert llm.write_summary("system", "user") == "Rezumat [1]."
    assert messages.keys == ["test-key"]
    assert messages.kwargs["model"] == get_settings().llm_model
    assert messages.kwargs["system"] == "system"
    assert messages.kwargs["fallbacks"] == "default"


def test_write_summary_raises_when_the_model_refuses(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    get_settings.cache_clear()
    fake_client(monkeypatch, claude_response(stop_reason="refusal", text=""))

    with pytest.raises(llm.SummaryError, match="declined"):
        llm.write_summary("system", "user")

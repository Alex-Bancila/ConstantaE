from app.ai.rag.text import normalize_diacritics


def test_cedilla_letters_become_comma_letters():
    assert normalize_diacritics("şţŞŢ") == "șțȘȚ"


def test_other_text_is_unchanged():
    assert normalize_diacritics("Art. 9 - dreptul de retragere") == "Art. 9 - dreptul de retragere"

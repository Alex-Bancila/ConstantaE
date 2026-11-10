"""Text clean-up for law texts (owner: Lucas)."""

# Old Romanian texts use ş/ţ with a cedilla; correct Romanian uses ș/ț with a comma.
# They are different characters, so mixing them silently breaks search.
_CEDILLA_TO_COMMA = str.maketrans({"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț"})


def normalize_diacritics(text: str) -> str:
    return text.translate(_CEDILLA_TO_COMMA)

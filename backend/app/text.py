import unicodedata


def unaccent(s: str) -> str:
    """Lower-case Vietnamese text with the diacritics removed, for accent-insensitive search."""
    s = s.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()

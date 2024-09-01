auto_detect_languages = [
    "de",
    "en",
]

locale_by_language = {
    "de": "de-DE",
    "en": "en-US",
    "es": "es-ES",
}


def find_locale(language_query: str) -> str | None:
    return locale_by_language.get(language_query.strip().lower())

auto_detect_languages = [
    "de",
    "en",
]

locale_by_language = {
    "de": "de-DE",
    "🇩🇪": "de-DE",
    "🇦🇹": "de-AT",
    "en": "en-US",
    "🇺🇸": "en-US",
    "🇬🇧": "en-GB",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿": "en-GB",
    "es": "es-ES",
    "🇪🇸": "es-ES",
    "🇲🇽": "es-MX",
}


def find_locale(language_query: str) -> str | None:
    return locale_by_language.get(language_query.strip().lower())

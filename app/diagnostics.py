"""Traduction des messages connus du moteur pour l'interface."""
from i18n import TRANSLATIONS


def localize(message, language):
    source = 'en' if language == 'fr' else 'fr'
    for key, text in TRANSLATIONS[source]['ui'].items():
        if isinstance(text, str) and message == text:
            return TRANSLATIONS[language]['ui'][key]
    replacements = TRANSLATIONS['en']['diagnostic_replacements']
    if language == 'fr':
        replacements = {english: french for french, english in replacements.items()}
    original = TRANSLATIONS[source]['diagnostic_meta']
    translated = TRANSLATIONS[language]['diagnostic_meta']
    if message.startswith(original['journal_prefix']):
        message = message.replace(original['journal_separator'], translated['journal_separator'], 1)
    for old, new in replacements.items():
        message = message.replace(old, new)
    return message

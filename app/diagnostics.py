"""Traduction des messages connus du moteur pour l'interface."""
from i18n import TRANSLATIONS


def localize(message, language):
    if language != 'en':
        return message
    original = TRANSLATIONS['fr']['diagnostic_meta']
    translated = TRANSLATIONS[language]['diagnostic_meta']
    if message.startswith(original['journal_prefix']):
        message = message.replace(original['journal_separator'], translated['journal_separator'], 1)
    for french, english in TRANSLATIONS[language]["diagnostic_replacements"].items():
        message = message.replace(french, english)
    return message

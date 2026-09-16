"""Charge le catalogue unique des textes de l'interface."""
import json
from pathlib import Path


TRANSLATIONS = json.loads(Path(__file__).with_name('translations.json').read_text(encoding='utf-8'))
TEXT = {language: content['ui'] for language, content in TRANSLATIONS.items()}

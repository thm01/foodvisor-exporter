"""Dates saisies dans l'interface graphique."""
import datetime as dt
import re


def parse_date(value):
    if not re.fullmatch(r'\d{2}-\d{2}-\d{4}', value.strip()):
        raise ValueError('Invalid date format')
    return dt.datetime.strptime(value.strip(), '%d-%m-%Y').date()


def format_date(value):
    return value.strftime('%d-%m-%Y')

#!/usr/bin/env python3
"""Un seul lancement pour récupérer et préparer les exports Foodvisor."""
import argparse
import datetime as dt
import getpass
import json
import os
from pathlib import Path

from fusionner_export import merge
from creer_tableur import create
from export_foodvisor import export, ExportCancelled, ExportSession
from i18n import TRANSLATIONS

ROOT = Path(__file__).resolve().parent.parent


def run_export(start=None, end=None, country='BE', locale='fr', source=None,
               output=None, mail=None, password=None, progress=None, cancel=None,
               session=None):
    if locale not in TRANSLATIONS:
        raise ValueError(f'Langue des données non prise en charge : {locale}')
    progress = progress or print
    if source:
        source = Path(source).resolve()
        manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
        start, end = dt.date.fromisoformat(manifest['start']), dt.date.fromisoformat(manifest['end'])
    elif start is None:
        raise ValueError('La date de début est requise.')
    end = end or dt.date.today()
    if start > end:
        raise ValueError('La date de début doit précéder la date de fin.')
    os.umask(0o077)
    out = Path(output or ROOT / 'exports' / dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')).resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    progress(f'Période : {start} → {end}\nDossier : {out}')
    if not source:
        source = out / 'sources'
        progress('1/3 — Connexion et récupération du journal.')
        export(start, end, country, locale, source, mail, password, progress, cancel, session)
    if cancel is not None and cancel.is_set():
        raise ExportCancelled('Export annulé.')
    progress('2/3 — Fusion et suppression des doublons.')
    merged = out / 'historique.json'
    merge(source, merged)
    if cancel is not None and cancel.is_set():
        raise ExportCancelled('Export annulé.')
    progress('3/3 — Création des fichiers Excel et CSV.')
    create(merged, out / 'Foodvisor', locale)
    summary = TRANSLATIONS[locale]['export_summary'].format(
        start=start, end=end, source=source)
    (out / 'EXPORT_TERMINE.txt').write_text(summary, encoding='utf-8')
    progress(f'Tout est prêt. Classeur : {out / "Foodvisor.xlsx"}')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=dt.date.fromisoformat, help='Début inclus (obligatoire sauf avec --source)')
    parser.add_argument('--end', type=dt.date.fromisoformat, default=dt.date.today(), help='Fin incluse (défaut : aujourd’hui)')
    parser.add_argument('--country', default='BE')
    parser.add_argument('--locale', choices=TRANSLATIONS, default='fr')
    parser.add_argument('--source', type=Path, help='Retraiter un dossier de données déjà téléchargé, sans connexion')
    parser.add_argument('--output', type=Path, help='Nouveau dossier de sortie, qui ne doit pas déjà exister')
    parser.add_argument('--interactive', action='store_true',
                        help='Rester dans la console pour lancer plusieurs exports avec la même session')
    args = parser.parse_args()
    if args.interactive and (args.source or args.output):
        parser.error('--interactive ne se combine pas avec --source ou --output.')
    if not args.interactive and not args.source and args.start is None:
        parser.error('--start est obligatoire pour un nouveau téléchargement.')
    mail = input('Adresse e-mail Foodvisor : ').strip() if not args.source else None
    password = getpass.getpass('Mot de passe Foodvisor (masqué) : ') if not args.source and not args.interactive else None
    session = ExportSession(mail, args.country, args.locale) if args.interactive else None
    if not args.interactive:
        run_export(start=args.start, end=args.end, country=args.country, locale=args.locale,
                   source=args.source, output=args.output, mail=mail, password=password)
        return
    start, end = args.start, args.end
    while True:
        if start is None:
            raw = input('Début (AAAA-MM-JJ, Entrée pour quitter) : ').strip()
            if not raw:
                return
            try:
                start = dt.date.fromisoformat(raw)
            except ValueError:
                print('Date invalide. Réessayez.')
                continue
            raw_end = input('Fin (AAAA-MM-JJ, Entrée = aujourd’hui) : ').strip()
            try:
                end = dt.date.fromisoformat(raw_end) if raw_end else dt.date.today()
            except ValueError:
                print('Date invalide. Réessayez.')
                start = None
                continue
        if not session.authenticated and password is None:
            password = getpass.getpass('Mot de passe Foodvisor (masqué) : ')
        try:
            run_export(start=start, end=end, country=args.country, locale=args.locale,
                       mail=mail, password=password, session=session)
        except (OSError, ValueError, KeyError, RuntimeError, ExportCancelled) as exc:
            print(f'Export interrompu : {exc}')
        finally:
            password = None
            start = None


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, ExportCancelled) as exc:
        raise SystemExit(f'Export interrompu : {exc}\nLes données déjà écrites sont conservées. Aucun export complet n’est annoncé.') from None
    except KeyboardInterrupt:
        raise SystemExit('\nExport interrompu par l’utilisateur.') from None

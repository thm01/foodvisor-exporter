#!/usr/bin/env python3
"""Export personnel expérimental via l'API privée Foodvisor ; bibliothèque standard."""
import argparse
import datetime as dt
import getpass
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ExportCancelled(Exception):
    """Arrêt demandé entre deux requêtes."""


class ExportSession:
    """Session limitée à un compte et à une configuration, gardée en mémoire."""

    def __init__(self, mail, country, locale):
        self.mail = mail
        self.country = country
        self.locale = locale
        self.client = None
        self.preferred_country = None
        self.preferred_locale = None

    def matches(self, mail, country, locale):
        return self.mail == mail and self.country == country and self.locale == locale

    @property
    def authenticated(self):
        return self.client is not None and bool(self.client.token)

    def logout(self):
        if self.client is not None:
            self.client.token = None
        self.client = None

    def set_options(self, country, locale):
        if not re.fullmatch(r"[A-Z]{2}", country) or locale not in ('fr', 'en'):
            raise ValueError("Pays ou langue invalide.")
        self.country, self.locale = country, locale
        if self.client is not None:
            self.client.base = f"https://api.foodvisor.io/api/6.0/android/{country}/{locale}/"


class Client:
    def __init__(self, country, locale):
        self.base = f"https://api.foodvisor.io/api/6.0/android/{country}/{locale}/"
        self.token = None
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, route, query=None, body=None):
        url = self.base + route
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code == 401:
                self.token = None
            raise RuntimeError(f"HTTP {code} sur {route}. Export interrompu ; fichiers déjà reçus conservés.") from None
        except urllib.error.URLError:
            raise RuntimeError(f"Connexion impossible à Foodvisor pour {route}.") from None


def save(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)


def food_ids(value):
    result = set()
    if isinstance(value, dict):
        if isinstance(value.get("food_id"), str):
            result.add(value["food_id"])
        for item in value.values():
            result.update(food_ids(item))
    elif isinstance(value, list):
        for item in value:
            result.update(food_ids(item))
    return result


def windows(start, end):
    while start <= end:
        stop = min(start + dt.timedelta(days=30), end)
        yield start, stop
        start = stop + dt.timedelta(days=1)


def authenticate(session, password, progress=None, cancel=None):
    """Authentifie une session sans conserver le mot de passe."""
    if session.authenticated:
        return session
    if not session.mail or not password:
        raise ValueError("Adresse e-mail et mot de passe requis.")
    if not re.fullmatch(r"[A-Z]{2}", session.country) or session.locale not in ('fr', 'en'):
        raise ValueError("Pays ou langue invalide.")
    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise ExportCancelled("Export annulé.")
    check_cancel()
    client = Client(session.country, session.locale)
    if progress is not None:
        progress("Connexion à Foodvisor…")
    nonce = client.call("user/auth/nonce/")["nonce"]
    check_cancel()
    response = client.call("user/auth/", body={
        "auth_method": "mail", "signup": False, "mail": session.mail,
        "password": password, "tags": [], "nonce": nonce,
    })
    tokens = response.get("tokens") if isinstance(response, dict) else None
    token = tokens.get("access") if isinstance(tokens, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("Jeton d'accès vide.")
    client.token = token
    session.client = client
    settings = response.get('settings') if isinstance(response, dict) else None
    if isinstance(settings, dict):
        country = settings.get('food_country')
        if isinstance(country, str) and re.fullmatch(r'[A-Za-z]{2}', country):
            session.preferred_country = country.upper()
        language = settings.get('locale')
        if isinstance(language, str):
            language = language.replace('_', '-').split('-', 1)[0].lower()
            if language in ('fr', 'en'):
                session.preferred_locale = language
    return session


def export(start, end, country, locale, out, mail, password, progress=None, cancel=None,
           session=None):
    if start > end:
        raise ValueError("La date de début doit précéder la date de fin.")
    if not re.fullmatch(r"[A-Z]{2}", country) or locale not in ('fr', 'en'):
        raise ValueError("Pays ou langue invalide.")
    if not mail:
        raise ValueError("Adresse e-mail requise.")
    if session is not None and not session.matches(mail, country, locale):
        raise ValueError("La session ne correspond pas au compte ou aux options Foodvisor.")
    if not password and not (session is not None and session.authenticated):
        raise ValueError("Mot de passe requis pour se connecter.")
    progress = progress or (lambda message: None)
    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise ExportCancelled("Export annulé.")
    def pause():
        if cancel is not None:
            if cancel.wait(1):
                check_cancel()
        else:
            time.sleep(1)

    os.umask(0o077)
    session = session or ExportSession(mail, country, locale)
    check_cancel()
    if session.authenticated:
        progress("Session Foodvisor réutilisée.")
    else:
        authenticate(session, password, progress, cancel)
    client = session.client
    del password
    check_cancel()
    out = Path(out)
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    save(out / "manifest.json", {"start": str(start), "end": str(end), "complete": False})
    ids = set()
    meals = 0
    for window_start, window_end in windows(start, end):
        check_cancel()
        result = client.call("history/journal/", {"start": str(window_start), "end": str(window_end + dt.timedelta(days=1))})
        save(out / f"journal-{window_start}-{window_end}.json", result)
        if not isinstance(result, dict) or not isinstance(result.get("macro_meals"), list):
            raise RuntimeError("Format du journal inattendu ; réponse sauvegardée pour analyse.")
        ids.update(food_ids(result))
        meals += len(result["macro_meals"])
        progress(f"Journal reçu : {window_start} à {window_end} ({len(result['macro_meals'])} entrées)")
        pause()
    ordered = sorted(ids)
    for offset in range(0, len(ordered), 25):
        check_cancel()
        result = client.call("food/", {"food_ids[]": ordered[offset:offset + 25]})
        save(out / f"aliments-{offset // 25:04d}.json", result)
        if not isinstance(result, dict) or not isinstance(result.get("food_info"), list):
            raise RuntimeError("Format des aliments inattendu ; réponse sauvegardée pour analyse.")
        progress(f"Fiches alimentaires reçues : {min(offset + 25, len(ordered))}/{len(ordered)}")
        pause()
    check_cancel()
    save(out / "termine.json", {"complete": True, "meal_entries_with_overlap": meals, "requested_food_ids": len(ids), "note": "JSON bruts ; chevauchements et bornes de dates à normaliser avant conversion CSV."})
    progress(f"Téléchargement terminé : {out.resolve()}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument("--country", default="BE")
    parser.add_argument("--locale", choices=('fr', 'en'), default="fr")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    mail = input("Adresse e-mail Foodvisor : ").strip()
    password = getpass.getpass("Mot de passe Foodvisor (masqué) : ")
    out = args.output or Path(__file__).resolve().parent.parent / "donnees" / "brutes" / ("donnees-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    export(args.start, args.end, args.country, args.locale, out, mail, password, print)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        raise SystemExit(str(exc)) from None

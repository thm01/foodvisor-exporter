#!/usr/bin/env python3
"""Interface web locale pour l'exporteur Foodvisor."""
import datetime as dt
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import locale
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
import webbrowser

from automatiser import run_export
import credential_store
from date_input import format_date, parse_date
from diagnostics import localize
from export_foodvisor import ExportCancelled, ExportSession, authenticate
from i18n import TEXT


CONFIG = Path.home() / '.foodvisor-exporter-gui.json'
ASSETS = Path(__file__).resolve().parent / 'web'
COUNTRIES = ('BE', 'FR', 'CH', 'LU', 'CA', 'US', 'GB', 'DE', 'ES', 'IT')
IDLE_TIMEOUT = 120


def load_config():
    try:
        value = json.loads(CONFIG.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(value):
    try:
        CONFIG.write_text(json.dumps(value), encoding='utf-8')
        if os.name != 'nt':
            CONFIG.chmod(0o600)
    except OSError:
        pass


def default_language(config):
    if config.get('ui_language') in TEXT:
        return config['ui_language']
    system = locale.getlocale()[0] or ''
    return 'fr' if system.lower().startswith('fr') else 'en'


def saved_country(config):
    value = config.get('country')
    return value.strip().upper() if isinstance(value, str) and re.fullmatch(r'[A-Za-z]{2}', value.strip()) else ''


def default_country(config):
    saved = saved_country(config)
    if saved:
        return saved
    system = locale.getlocale()[0] or ''
    region = re.search(r'[_-]([A-Za-z]{2})(?:[.@]|$)', system)
    return region.group(1).upper() if region else ''


def reveal_folder(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(path)])
    else:
        subprocess.Popen(['xdg-open', str(path)])


class WebApplication:
    def __init__(self):
        config = load_config()
        self.lock = threading.RLock()
        self.language = default_language(config)
        self.email = config.get('email', '') if isinstance(config.get('email'), str) else ''
        self.remembered_email = config.get('remembered_email') if isinstance(config.get('remembered_email'), str) else None
        self.keyring_available = credential_store.secure_keyring() is not None
        self.remember = bool(config.get('remember_password')) and self.keyring_available
        self.saved_country = saved_country(config)
        self.country = default_country(config)
        self.data_locale_manual = config.get('data_locale') in ('fr', 'en')
        self.data_locale = config['data_locale'] if self.data_locale_manual else self.language
        self.destination = str(Path.home() / 'Foodvisor-exports')
        self.session = None
        self.busy = False
        self.authenticating = False
        self.cancel_event = None
        self.worker_thread = None
        self.last_output = None
        self.status = 'idle'
        self.error = None
        self.messages = []
        self.csrf = secrets.token_urlsafe(32)
        self.server = None
        self.last_seen = time.monotonic()
        self.stop_event = threading.Event()

    def t(self, key):
        return TEXT[self.language][key]

    def _save(self):
        value = {'ui_language': self.language, 'email': self.email,
                 'remember_password': self.remember}
        if self.data_locale_manual:
            value['data_locale'] = self.data_locale
        if self.saved_country:
            value['country'] = self.saved_country
        if self.remembered_email:
            value['remembered_email'] = self.remembered_email
        save_config(value)

    def _log(self, message):
        self.messages.append(str(message))
        self.messages = self.messages[-1000:]

    def snapshot(self):
        with self.lock:
            return {
                'language': self.language, 'email': self.email,
                'remember': self.remember, 'remembered_email': self.remembered_email,
                'keyring_available': self.keyring_available,
                'country': self.country, 'data_locale': self.data_locale,
                'destination': self.destination,
                'connected': bool(self.session and self.session.authenticated),
                'authenticating': self.authenticating, 'busy': self.busy,
                'status': self.status, 'error': localize(self.error, self.language) if self.error else None,
                'messages': [localize(m, self.language) for m in self.messages],
                'last_output': str(self.last_output) if self.last_output else None,
                'start': format_date(dt.date.today().replace(day=1)),
                'end': format_date(dt.date.today()),
            }

    def _check_options(self, country, data_locale, require_country=True):
        country = str(country).strip().upper()
        if (require_country or country) and not re.fullmatch(r'[A-Z]{2}', country):
            raise ValueError(self.t('bad_country'))
        if data_locale not in ('fr', 'en'):
            raise ValueError(self.t('bad_locale'))
        return country, data_locale

    def settings(self, payload):
        with self.lock:
            if self.busy and any(key in payload for key in ('country', 'data_locale', 'destination')):
                raise ValueError(self.t('working'))
            language = payload.get('language', self.language)
            if language not in TEXT:
                raise ValueError('Unsupported interface language')
            self.language = language
            if not self.data_locale_manual and 'data_locale' not in payload:
                self.data_locale = language
                if self.session and self.session.authenticated and not self.busy:
                    self.session.set_options(self.country, self.data_locale)
            if 'email' in payload and not self.session and not self.authenticating:
                self.email = str(payload['email']).strip()
            if 'destination' in payload:
                self.destination = str(payload['destination']).strip()
            if 'remember' in payload and not self.session and not self.authenticating:
                self.remember = bool(payload['remember']) and self.keyring_available
            if 'country' in payload or 'data_locale' in payload:
                country, data_locale = self._check_options(
                    payload.get('country', self.country), payload.get('data_locale', self.data_locale),
                    require_country=bool(self.session and self.session.authenticated))
                changed = (country, data_locale) != (self.country, self.data_locale)
                self.country, self.data_locale = country, data_locale
                if 'data_locale' in payload:
                    self.data_locale_manual = True
                if changed and self.session and self.session.authenticated and not self.busy:
                    self.session.set_options(country, data_locale)
                    self.saved_country = country
                    self._log(self.t('options_applied').format(country=country, locale=data_locale))
            self._save()

    def login(self, payload):
        with self.lock:
            if self.busy or self.authenticating or (self.session and self.session.authenticated):
                raise ValueError(self.t('connected'))
            mail = str(payload.get('email', '')).strip()
            password = payload.get('password', '')
            remember = bool(payload.get('remember')) and self.keyring_available
            country, data_locale = self._check_options(payload.get('country', self.country),
                                                       payload.get('data_locale', self.data_locale))
            if not mail or (not password and not remember):
                raise ValueError(self.t('credentials'))
            self.email, self.country, self.data_locale, self.remember = mail, country, data_locale, remember
            self.authenticating = True
            self.status, self.error = 'connecting', None
            self._log(self.t('connecting'))
            self._save()
            self.worker_thread = threading.Thread(target=self._login_worker,
                                                   args=(mail, password, country, data_locale, remember), daemon=True)
            self.worker_thread.start()

    def _login_worker(self, mail, password, country, data_locale, remember):
        try:
            if not password and remember:
                password = credential_store.get_password(mail)
                if not password:
                    raise ValueError('Aucun mot de passe enregistré pour ce compte.')
            session = ExportSession(mail, country, data_locale)
            authenticate(session, password, progress=self._progress)
            warning = None
            saved_mail = self.remembered_email
            if remember:
                try:
                    if saved_mail and saved_mail != mail:
                        credential_store.delete_password(saved_mail)
                    credential_store.set_password(mail, password)
                    saved_mail = mail
                except Exception:
                    warning = 'store_failed'
                    remember = False
            with self.lock:
                self.session = session
                self.country = session.preferred_country or country
                self.data_locale = data_locale if self.data_locale_manual else session.preferred_locale or data_locale
                self.session.set_options(self.country, self.data_locale)
                self.saved_country = self.country
                self.remembered_email, self.remember = saved_mail, remember
                self.status = 'connected'
                self._log(self.t('connected'))
                if session.preferred_country or session.preferred_locale:
                    self._log(self.t('options_detected').format(country=self.country, locale=self.data_locale))
                if warning:
                    self._log(self.t(warning))
                self._save()
        except Exception as exc:
            with self.lock:
                self.status, self.error = 'error', str(exc)
                self._log(str(exc))
        finally:
            password = None
            with self.lock:
                self.authenticating = False

    def _progress(self, message):
        with self.lock:
            self._log(message)

    def logout(self):
        with self.lock:
            if self.busy or self.authenticating:
                raise ValueError(self.t('working'))
            if self.session:
                self.session.logout()
            self.session = None
            self.status, self.error = 'disconnected', None
            self._log(self.t('disconnected'))

    def forget_password(self):
        with self.lock:
            mail = self.remembered_email
            self.remember = False
            self.remembered_email = None
            self._save()
        if mail:
            try:
                credential_store.delete_password(mail)
            except Exception:
                with self.lock:
                    self._log(self.t('store_delete_failed'))

    def _destination(self, raw):
        if not str(raw).strip():
            raise ValueError(self.t('no_folder'))
        destination = Path(str(raw)).expanduser()
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        return destination.resolve()

    def export(self, payload, offline=False):
        with self.lock:
            if self.busy or self.authenticating:
                raise ValueError(self.t('working'))
            country, data_locale = self._check_options(payload.get('country', self.country),
                                                       payload.get('data_locale', self.data_locale),
                                                       require_country=not offline)
            if offline:
                source = Path(str(payload.get('source', ''))).expanduser()
                if not all((source / name).is_file() for name in ('manifest.json', 'termine.json')):
                    raise ValueError(self.t('source_missing'))
                options = {'source': source, 'locale': data_locale}
            else:
                if not self.session or not self.session.authenticated:
                    raise ValueError(self.t('login_required'))
                try:
                    start, end = parse_date(str(payload.get('start', ''))), parse_date(str(payload.get('end', '')))
                except ValueError:
                    raise ValueError(self.t('bad_date')) from None
                if start > end:
                    raise ValueError(self.t('date_order'))
                self.session.set_options(country, data_locale)
                options = {'start': start, 'end': end, 'mail': self.session.mail,
                           'password': None, 'country': country, 'locale': data_locale,
                           'session': self.session}
            destination = self._destination(payload.get('destination', self.destination))
            self.country, self.data_locale, self.destination = country, data_locale, str(destination)
            if not offline and self.session and self.session.authenticated:
                self.saved_country = country
            self._save()
            self.busy, self.error = True, None
            self.status = 'converting' if offline else 'working'
            self.messages.clear()
            self.last_output = None
            self._log(self.t('conversion_started' if offline else 'export_started'))
            self.cancel_event = threading.Event()
            self.worker_thread = threading.Thread(target=self._export_worker,
                                                   args=(options, destination, offline, self.cancel_event), daemon=True)
            self.worker_thread.start()

    def _export_worker(self, options, destination, offline, cancel):
        output = destination / dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        try:
            result = run_export(output=output, progress=self._progress, cancel=cancel, **options)
            with self.lock:
                self.last_output = result
                self.status = 'conversion_done' if offline else 'done'
                self._log(self.t(self.status))
        except ExportCancelled:
            with self.lock:
                self.status = 'cancelled'
                self.last_output = output if output.exists() else None
                self._log(self.t('cancelled'))
        except Exception as exc:
            with self.lock:
                self.status, self.error = 'error', str(exc)
                self.last_output = output if output.exists() else None
                self._log(str(exc))
        finally:
            with self.lock:
                self.busy = False
                self.cancel_event = None

    def cancel(self):
        with self.lock:
            if self.cancel_event:
                self.cancel_event.set()

    def open_output(self):
        with self.lock:
            path = self.last_output
        if path:
            reveal_folder(path)

    def directories(self, raw):
        path = Path(raw or Path.home()).expanduser().resolve()
        while not path.is_dir() and path != path.parent:
            path = path.parent
        if not path.is_dir():
            raise ValueError(self.t('no_folder'))
        children = sorted((p.name for p in path.iterdir() if p.is_dir()), key=str.casefold)
        return {'path': str(path), 'parent': str(path.parent), 'children': children[:300]}

    def quit(self):
        with self.lock:
            if self.stop_event.is_set():
                return
            self.stop_event.set()
            self.cancel()
        def stop():
            worker = self.worker_thread
            if worker and worker.is_alive():
                worker.join(timeout=35)
            with self.lock:
                if self.session:
                    self.session.logout()
                self.session = None
            self.server.shutdown()
        threading.Thread(target=stop, daemon=True).start()

    def seen(self):
        with self.lock:
            self.last_seen = time.monotonic()

    def idle_expired(self, now=None):
        with self.lock:
            current = time.monotonic() if now is None else now
            return (current - self.last_seen >= IDLE_TIMEOUT and not self.busy
                    and not self.authenticating and not self.stop_event.is_set())

    def watch_browser(self, interval=5):
        def watch():
            while not self.stop_event.wait(interval):
                if self.idle_expired():
                    self.quit()
                    return
        threading.Thread(target=watch, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _allowed(self):
        host = self.headers.get('Host')
        expected = f'127.0.0.1:{self.server.server_port}'
        if host != expected:
            self.send_error(HTTPStatus.FORBIDDEN)
            return False
        return True

    def _reply(self, status, content, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status, value):
        self._reply(status, json.dumps(value, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def do_GET(self):
        if not self._allowed():
            return
        app = self.server.app
        url = urlsplit(self.path)
        try:
            if url.path == '/api/state':
                if self.headers.get('X-CSRF-Token') != app.csrf:
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                app.seen()
                self._json(200, app.snapshot())
            elif url.path == '/api/i18n':
                self._json(200, {'csrf': app.csrf, 'ui': TEXT, 'countries': COUNTRIES})
            elif url.path == '/api/directories':
                raw = parse_qs(url.query).get('path', [''])[0]
                self._json(200, app.directories(raw))
            elif url.path in ('/', '/app.js', '/style.css'):
                name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[url.path]
                kind = {'index.html': 'text/html', 'app.js': 'text/javascript', 'style.css': 'text/css'}[name]
                self._reply(200, (ASSETS / name).read_bytes(), kind + '; charset=utf-8')
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (OSError, ValueError) as exc:
            self._json(400, {'error': str(exc)})

    def do_POST(self):
        if not self._allowed():
            return
        origin = self.headers.get('Origin')
        if origin and origin != f'http://127.0.0.1:{self.server.server_port}':
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        app = self.server.app
        if self.headers.get('X-CSRF-Token') != app.csrf:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 16384 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Invalid request')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Invalid request')
            route = urlsplit(self.path).path
            if route == '/api/settings':
                app.settings(payload)
            elif route == '/api/login':
                app.login(payload)
            elif route == '/api/logout':
                app.logout()
            elif route == '/api/forget':
                app.forget_password()
            elif route == '/api/export':
                app.export(payload)
            elif route == '/api/convert':
                app.export(payload, offline=True)
            elif route == '/api/cancel':
                app.cancel()
            elif route == '/api/clear':
                with app.lock:
                    app.messages.clear()
            elif route == '/api/open':
                app.open_output()
            elif route == '/api/quit':
                app.quit()
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._json(200, app.snapshot())
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self._json(400, {'error': str(exc)})


def main():
    app = WebApplication()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    server.app = app
    app.server = server
    app.watch_browser()
    url = f'http://127.0.0.1:{server.server_port}/'
    print(url, flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        app.cancel()
    finally:
        server.server_close()
        if app.session:
            app.session.logout()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Interface graphique de l'exporteur Foodvisor non officiel."""
import calendar
import datetime as dt
import json
import locale
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading

from i18n import TEXT

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:
    system = locale.getlocale()[0] or ''
    language = 'fr' if system.lower().startswith('fr') else 'en'
    raise SystemExit(TEXT[language]['missing_tk']) from exc

from automatiser import run_export
from date_input import format_date, parse_date
from diagnostics import localize
from export_foodvisor import ExportCancelled, ExportSession, authenticate
import credential_store


CONFIG = Path.home() / '.foodvisor-exporter-gui.json'


def load_config():
    try:
        value = json.loads(CONFIG.read_text(encoding='utf-8'))
        if isinstance(value, dict):
            return value
    except (OSError, ValueError):
        pass
    return {}


def default_language(config):
    value = config.get('ui_language')
    if value in TEXT:
        return value
    system = locale.getlocale()[0] or ''
    return 'fr' if system.lower().startswith('fr') else 'en'


def reveal_folder(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(path)])
    else:
        subprocess.Popen(['xdg-open', str(path)])


class DatePicker(tk.Toplevel):
    def __init__(self, application, variable, anchor):
        super().__init__(application)
        self.application = application
        self.variable = variable
        try:
            selected = parse_date(variable.get())
        except ValueError:
            selected = dt.date.today()
        self.year, self.month = selected.year, selected.month
        self.title(application.t('calendar_title'))
        self.transient(application)
        self.resizable(False, False)
        self.bind('<Escape>', lambda _: self.destroy())
        self.container = ttk.Frame(self, padding=8)
        self.container.pack()
        self.draw()
        self.update_idletasks()
        x = min(anchor.winfo_rootx(), self.winfo_screenwidth() - self.winfo_reqwidth() - 8)
        y = min(anchor.winfo_rooty() + anchor.winfo_height(), self.winfo_screenheight() - self.winfo_reqheight() - 8)
        self.geometry(f'+{max(0, x)}+{max(0, y)}')

    def draw(self):
        for widget in self.container.winfo_children():
            widget.destroy()
        ttk.Button(self.container, text='‹', width=3,
                   command=lambda: self.shift_month(-1)).grid(row=0, column=0)
        month_name = self.application.t('months')[self.month - 1]
        ttk.Label(self.container, text=f'{month_name} {self.year}', anchor='center').grid(
            row=0, column=1, columnspan=5, sticky='ew')
        ttk.Button(self.container, text='›', width=3,
                   command=lambda: self.shift_month(1)).grid(row=0, column=6)
        for column, name in enumerate(self.application.t('weekdays')):
            ttk.Label(self.container, text=name, anchor='center', width=4).grid(
                row=1, column=column, pady=(6, 2))
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), start=2):
            for column, day in enumerate(week):
                if day:
                    ttk.Button(self.container, text=str(day), width=4,
                               command=lambda value=day: self.choose(value)).grid(row=row, column=column, padx=1, pady=1)
        ttk.Button(self.container, text=self.application.t('today'),
                   command=self.choose_today).grid(row=8, column=0, columnspan=7, pady=(8, 0))

    def shift_month(self, offset):
        current = dt.date(self.year, self.month, 1)
        if offset > 0:
            current = (current + dt.timedelta(days=32)).replace(day=1)
        else:
            current = (current - dt.timedelta(days=1)).replace(day=1)
        self.year, self.month = current.year, current.month
        self.draw()

    def choose(self, day):
        self.variable.set(format_date(dt.date(self.year, self.month, day)))
        self.destroy()

    def choose_today(self):
        self.variable.set(format_date(dt.date.today()))
        self.destroy()


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        config = load_config()
        self.language = tk.StringVar(value=default_language(config))
        self.email = tk.StringVar(value=config.get('email', '') if isinstance(config.get('email'), str) else '')
        self.password = tk.StringVar()
        self.keyring_available = credential_store.secure_keyring() is not None
        self.remember_password = tk.BooleanVar(value=bool(config.get('remember_password')) and self.keyring_available)
        self.remembered_email = config.get('remembered_email') if isinstance(config.get('remembered_email'), str) else None
        self.session = None
        self.start = tk.StringVar(value=format_date(dt.date.today().replace(day=1)))
        self.end = tk.StringVar(value=format_date(dt.date.today()))
        self.country = tk.StringVar(value='BE')
        self.data_locale = tk.StringVar(value='fr')
        self.destination = tk.StringVar(value=str(Path.home() / 'Foodvisor-exports'))
        self.events = queue.Queue()
        self.cancel_event = None
        self.last_output = None
        self.status_key = 'idle'
        self.date_picker = None
        self.running = False
        self.authenticating = False
        self.updating_options = False
        self.current_offline = False
        self.quit_when_done = False
        self.labels = {}
        self.build()
        self.size_to_screen()
        self.language.trace_add('write', self.change_language)
        self.country.trace_add('write', self.connection_options_changed)
        self.data_locale.trace_add('write', self.connection_options_changed)
        self.protocol('WM_DELETE_WINDOW', self.quit_app)
        self.after(100, self.pump)

    def t(self, key):
        return TEXT[self.language.get()][key]

    def save_config(self):
        value = {'ui_language': self.language.get(), 'email': self.email.get().strip(),
                 'remember_password': self.remember_password.get()}
        if self.remembered_email:
            value['remembered_email'] = self.remembered_email
        try:
            CONFIG.write_text(json.dumps(value), encoding='utf-8')
            if os.name != 'nt':
                CONFIG.chmod(0o600)
        except OSError:
            pass

    def label(self, parent, key, **options):
        widget = ttk.Label(parent, text=self.t(key), **options)
        self.labels[key] = widget
        return widget

    def frame(self, key):
        frame = ttk.LabelFrame(self, text=self.t(key), padding=10)
        frame.pack(fill='x', padx=14, pady=5)
        self.labels[key] = frame
        return frame

    def size_to_screen(self):
        self.update_idletasks()
        available_width = max(1, self.winfo_screenwidth() - 80)
        available_height = max(1, self.winfo_screenheight() - 100)
        width = min(max(760, self.winfo_reqwidth() + 24), available_width)
        height = min(max(800, self.winfo_reqheight() + 32), available_height)
        self.geometry(f'{width}x{height}')
        self.minsize(min(640, available_width), min(620, available_height))

    def build(self):
        self.title(self.t('title'))
        self.build_menu()
        toolbar = ttk.Frame(self, padding=(14, 12, 14, 6))
        toolbar.pack(fill='x')
        self.label(toolbar, 'title', font=('TkDefaultFont', 12, 'bold')).pack(side='left')

        account = self.frame('account')
        self.label(account, 'email').grid(row=0, column=0, sticky='w', pady=3)
        self.email_entry = ttk.Entry(account, textvariable=self.email)
        self.email_entry.grid(row=0, column=1, sticky='ew', padx=8)
        self.label(account, 'password').grid(row=1, column=0, sticky='w', pady=3)
        self.password_entry = ttk.Entry(account, textvariable=self.password, show='•')
        self.password_entry.grid(row=1, column=1, sticky='ew', padx=8)
        self.remember_checkbox = ttk.Checkbutton(account, text=self.t('remember_password' if self.keyring_available else 'remember_unavailable'),
                                                  variable=self.remember_password,
                                                  command=self.remember_changed)
        self.remember_checkbox.grid(row=2, column=1, sticky='w', padx=8, pady=3)
        if not self.keyring_available:
            self.remember_checkbox.configure(state='disabled')
        account_actions = ttk.Frame(account)
        account_actions.grid(row=3, column=1, sticky='w', padx=8, pady=3)
        self.login_button = ttk.Button(account_actions, text=self.t('login'), command=self.start_login)
        self.login_button.pack(side='left')
        self.logout_button = ttk.Button(account_actions, text=self.t('logout'),
                                        command=self.logout, state='disabled')
        self.logout_button.pack(side='left', padx=8)
        self.forget_button = ttk.Button(account_actions, text=self.t('forget_password'),
                                        command=self.forget_saved_password, state='disabled')
        self.forget_button.pack(side='left')
        self.account_status = ttk.Label(account, text=self.t('disconnected'))
        self.account_status.grid(row=4, column=1, sticky='w', padx=8, pady=(0, 3))
        account.columnconfigure(1, weight=1)

        period = self.frame('period')
        self.period_controls = []
        self.label(period, 'start').grid(row=0, column=0, sticky='w', pady=3)
        start_entry = ttk.Entry(period, textvariable=self.start, width=18, state='disabled')
        start_entry.grid(row=0, column=1, padx=8)
        start_picker = ttk.Button(period, text='▦', width=3)
        start_picker.configure(command=lambda: self.show_date_picker(self.start, start_picker))
        start_picker.grid(row=0, column=2)
        self.label(period, 'end').grid(row=1, column=0, sticky='w', pady=3)
        end_entry = ttk.Entry(period, textvariable=self.end, width=18, state='disabled')
        end_entry.grid(row=1, column=1, padx=8)
        end_picker = ttk.Button(period, text='▦', width=3)
        end_picker.configure(command=lambda: self.show_date_picker(self.end, end_picker))
        end_picker.grid(row=1, column=2)
        self.period_controls.extend((start_entry, start_picker, end_entry, end_picker))
        start_picker.configure(state='disabled')
        end_picker.configure(state='disabled')

        foodvisor = self.frame('foodvisor')
        self.label(foodvisor, 'country').grid(row=0, column=0, sticky='w')
        self.country_combo = ttk.Combobox(foodvisor, textvariable=self.country,
                                          values=('BE', 'FR', 'CH', 'LU', 'CA', 'US', 'GB', 'DE', 'ES', 'IT'), width=12)
        self.country_combo.grid(row=0, column=1, padx=8)
        self.label(foodvisor, 'data_locale').grid(row=0, column=2, sticky='w')
        locale_choices = ttk.Frame(foodvisor)
        locale_choices.grid(row=0, column=3, padx=8, sticky='w')
        self.locale_controls = []
        for language in ('fr', 'en'):
            button = ttk.Radiobutton(locale_choices, text=language, value=language,
                                     variable=self.data_locale)
            button.pack(side='left', padx=(0, 10))
            self.locale_controls.append(button)

        dest = self.frame('destination')
        ttk.Entry(dest, textvariable=self.destination).pack(side='left', fill='x', expand=True)
        self.browse_button = ttk.Button(dest, text=self.t('browse'), command=self.browse)
        self.browse_button.pack(side='left', padx=(8, 0))

        actions = ttk.Frame(self)
        actions.pack(fill='x', padx=14, pady=8)
        self.run_button = ttk.Button(actions, text=self.t('run'), command=self.start_export,
                                     state='disabled')
        self.run_button.pack(side='left')
        self.offline_button = ttk.Button(actions, text=self.t('offline'), command=self.start_offline)
        self.offline_button.pack(side='left', padx=8)
        self.cancel_button = ttk.Button(actions, text=self.t('cancel'), command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left')

        progress = self.frame('progress')
        progress.pack_configure(fill='both', expand=True)
        self.status = ttk.Label(progress, text=self.t('idle'))
        self.status.pack(anchor='w')
        self.bar = ttk.Progressbar(progress, mode='indeterminate')
        self.bar.pack(fill='x', pady=6)
        self.log = tk.Text(progress, height=7, wrap='word', state='disabled')
        self.log.pack(fill='both', expand=True)
        links = ttk.Frame(progress)
        links.pack(fill='x', pady=(6, 0))
        self.open_button = ttk.Button(links, text=self.t('open'), command=self.open_output, state='disabled')
        self.open_button.pack(side='left')
        self.copy_button = ttk.Button(links, text=self.t('copy'), command=self.copy_log)
        self.copy_button.pack(side='left', padx=8)
        self.clear_button = ttk.Button(links, text=self.t('clear'), command=self.clear_log)
        self.clear_button.pack(side='left')

    def build_menu(self):
        self.menu_bar = tk.Menu(self, tearoff=False)
        self.file_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.file_menu.add_command(command=self.start_export, state='disabled')
        self.file_menu.add_command(command=self.start_offline)
        self.file_menu.add_separator()
        self.file_menu.add_command(command=self.open_output, state='disabled')
        self.file_menu.add_separator()
        self.file_menu.add_command(command=self.quit_app)
        self.window_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.window_menu.add_command(command=self.bring_to_front)
        self.window_menu.add_command(command=self.iconify)
        self.window_menu.add_separator()
        self.language_menu = tk.Menu(self.window_menu, tearoff=False)
        for language in ('fr', 'en'):
            self.language_menu.add_radiobutton(variable=self.language, value=language)
        self.window_menu.add_cascade(menu=self.language_menu)
        self.help_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.help_menu.add_command(command=self.show_about)
        for menu in (self.file_menu, self.window_menu, self.help_menu):
            self.menu_bar.add_cascade(menu=menu)
        self.configure(menu=self.menu_bar)
        self.refresh_menu_labels()

    def refresh_menu_labels(self):
        for index, key in enumerate(('menu_file', 'menu_window', 'menu_help')):
            self.menu_bar.entryconfigure(index, label=self.t(key))
        for index, key in ((0, 'run'), (1, 'offline'), (3, 'open'), (5, 'menu_quit')):
            self.file_menu.entryconfigure(index, label=self.t(key))
        self.window_menu.entryconfigure(0, label=self.t('menu_raise'))
        self.window_menu.entryconfigure(1, label=self.t('menu_minimize'))
        self.window_menu.entryconfigure(3, label=self.t('ui_language'))
        self.language_menu.entryconfigure(0, label=self.t('language_french'))
        self.language_menu.entryconfigure(1, label=self.t('language_english'))
        self.help_menu.entryconfigure(0, label=self.t('menu_about'))

    def bring_to_front(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def show_about(self):
        messagebox.showinfo(self.t('menu_about'), self.t('about_text'), parent=self)

    def quit_app(self):
        if self.running:
            self.quit_when_done = True
            self.cancel()
        else:
            if self.session is not None:
                self.session.logout()
            self.session = None
            self.destroy()

    def change_language(self, *_):
        language = self.language.get()
        if language not in TEXT:
            return
        self.title(self.t('title'))
        self.refresh_menu_labels()
        for key, widget in self.labels.items():
            widget.configure(text=self.t(key))
        for key, widget in (('browse', self.browse_button), ('run', self.run_button),
                            ('offline', self.offline_button), ('cancel', self.cancel_button),
                            ('open', self.open_button), ('copy', self.copy_button),
                            ('clear', self.clear_button), ('login', self.login_button),
                            ('logout', self.logout_button), ('forget_password', self.forget_button),
                            ('remember_password' if self.keyring_available else 'remember_unavailable',
                             self.remember_checkbox)):
            widget.configure(text=self.t(key))
        self.account_status.configure(text=self.t('connecting' if self.authenticating else
                                                   'connected' if self.session and self.session.authenticated
                                                   else 'disconnected'))
        if self.status_key:
            self.status.configure(text=self.t(self.status_key))
        if self.date_picker and self.date_picker.winfo_exists():
            self.date_picker.title(self.t('calendar_title'))
            self.date_picker.draw()
        self.save_config()

    def refresh_auth_controls(self):
        connected = self.session is not None and self.session.authenticated
        busy = self.running or self.authenticating
        self.login_button.configure(state='disabled' if connected or busy else 'normal')
        self.logout_button.configure(state='normal' if connected and not busy else 'disabled')
        self.forget_button.configure(state='normal' if self.remembered_email and not busy else 'disabled')
        self.email_entry.configure(state='disabled' if connected or busy else 'normal')
        self.password_entry.configure(state='disabled' if connected or busy else 'normal')
        self.country_combo.configure(state='disabled' if busy else 'normal')
        for button in self.locale_controls:
            button.configure(state='disabled' if busy else 'normal')
        self.remember_checkbox.configure(state='normal' if self.keyring_available and not connected and not busy else 'disabled')
        for widget in self.period_controls:
            widget.configure(state='normal' if connected and not busy else 'disabled')
        options_valid = bool(re.fullmatch(r'[A-Z]{2}', self.country.get().strip().upper())) and self.data_locale.get() in ('fr', 'en')
        export_state = 'normal' if connected and not busy and options_valid else 'disabled'
        self.run_button.configure(state=export_state)
        self.file_menu.entryconfigure(0, state=export_state)
        offline_state = 'disabled' if busy else 'normal'
        self.offline_button.configure(state=offline_state)
        self.file_menu.entryconfigure(1, state=offline_state)
        self.account_status.configure(text=self.t('connecting' if self.authenticating else
                                                 'connected' if connected else 'disconnected'))

    def remember_changed(self):
        self.save_config()
        if not self.remember_password.get():
            self.forget_saved_password()

    def connection_options_changed(self, *_):
        if self.updating_options:
            return
        if self.session is not None and self.session.authenticated and not self.running and not self.authenticating:
            country = self.country.get().strip().upper()
            language = self.data_locale.get()
            if re.fullmatch(r'[A-Z]{2}', country) and language in ('fr', 'en'):
                if (country, language) != (self.session.country, self.session.locale):
                    self.session.set_options(country, language)
                    self.append_log(self.t('options_applied').format(country=country, locale=language))
            self.refresh_auth_controls()

    def forget_saved_password(self):
        mail = self.remembered_email
        self.remember_password.set(False)
        self.save_config()
        if mail:
            self.forget_button.configure(state='disabled')
            threading.Thread(target=self.forget_password, args=(mail,), daemon=True).start()

    def forget_password(self, mail):
        try:
            if credential_store.get_password(mail) is not None:
                credential_store.delete_password(mail)
            self.events.put(('store_deleted', mail))
        except Exception:
            self.events.put(('store_delete_error', None))

    def start_login(self):
        if self.running or self.authenticating or (self.session and self.session.authenticated):
            return
        mail = self.email.get().strip()
        password = self.password.get()
        country = self.country.get().strip().upper()
        data_locale = self.data_locale.get().strip()
        if not mail or (not password and not self.remember_password.get()):
            messagebox.showerror(self.t('error'), self.t('credentials'), parent=self)
            return
        if not re.fullmatch(r'[A-Z]{2}', country):
            messagebox.showerror(self.t('error'), self.t('bad_country'), parent=self)
            return
        if data_locale not in ('fr', 'en'):
            messagebox.showerror(self.t('error'), self.t('bad_locale'), parent=self)
            return
        self.country.set(country)
        self.authenticating = True
        self.password.set('')
        self.save_config()
        self.refresh_auth_controls()
        self.status_key = 'connecting'
        self.status.configure(text=self.t('connecting'))
        self.bar.start()
        self.append_log(self.t('connecting'))
        threading.Thread(target=self.login_worker,
                         args=(mail, password, country, data_locale,
                               self.remember_password.get(), self.remembered_email),
                         daemon=True).start()

    def login_worker(self, mail, password, country, data_locale, remember, previous_saved_mail):
        try:
            if not password and remember:
                password = credential_store.get_password(mail)
                if not password:
                    raise ValueError('Aucun mot de passe enregistré pour ce compte.')
            session = ExportSession(mail, country, data_locale)
            authenticate(session, password,
                         progress=lambda message: self.events.put(('log', message)))
            warning = None
            saved_mail = previous_saved_mail
            if remember:
                try:
                    if previous_saved_mail and previous_saved_mail != mail:
                        if credential_store.get_password(previous_saved_mail) is not None:
                            credential_store.delete_password(previous_saved_mail)
                        saved_mail = None
                    credential_store.set_password(mail, password)
                    saved_mail = mail
                except Exception:
                    warning = 'store_failed'
            self.events.put(('auth_done', (session, warning, saved_mail)))
        except Exception as exc:
            self.events.put(('auth_error', str(exc)))
        finally:
            password = None

    def logout(self):
        if self.running or self.authenticating:
            return
        if self.session is not None:
            self.session.logout()
        self.session = None
        self.password.set('')
        self.status_key = 'disconnected'
        self.status.configure(text=self.t('disconnected'))
        self.append_log(self.t('disconnected'))
        self.refresh_auth_controls()

    def browse(self):
        selected = filedialog.askdirectory(initialdir=self.destination.get(), title=self.t('destination'))
        if selected:
            self.destination.set(selected)

    def show_date_picker(self, variable, anchor):
        if self.date_picker and self.date_picker.winfo_exists():
            self.date_picker.destroy()
        self.date_picker = DatePicker(self, variable, anchor)

    def validate_destination(self):
        raw = self.destination.get().strip()
        if not raw:
            raise ValueError(self.t('no_folder'))
        destination = Path(raw).expanduser()
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        return destination.resolve()

    def start_export(self):
        if self.running or self.authenticating:
            return
        if self.session is None or not self.session.authenticated:
            messagebox.showerror(self.t('error'), self.t('login_required'), parent=self)
            self.refresh_auth_controls()
            return
        country, data_locale = self.country.get().strip().upper(), self.data_locale.get()
        if not re.fullmatch(r'[A-Z]{2}', country):
            messagebox.showerror(self.t('error'), self.t('bad_country'), parent=self)
            return
        if data_locale not in ('fr', 'en'):
            messagebox.showerror(self.t('error'), self.t('bad_locale'), parent=self)
            return
        self.session.set_options(country, data_locale)
        try:
            start, end = parse_date(self.start.get()), parse_date(self.end.get())
        except ValueError:
            messagebox.showerror(self.t('error'), self.t('bad_date'))
            return
        if start > end:
            messagebox.showerror(self.t('error'), self.t('date_order'))
            return
        try:
            destination = self.validate_destination()
        except (OSError, ValueError) as exc:
            messagebox.showerror(self.t('error'), str(exc))
            return
        self.launch(dict(start=start, end=end, mail=self.session.mail, password=None,
                         country=self.session.country, locale=self.session.locale,
                         destination=destination, session=self.session))

    def start_offline(self):
        if self.running or self.authenticating:
            return
        source = filedialog.askdirectory(title=self.t('source'))
        if not source:
            return
        if not all((Path(source) / item).is_file() for item in ('manifest.json', 'termine.json')):
            messagebox.showerror(self.t('error'), self.t('source_missing'))
            return
        try:
            destination = self.validate_destination()
        except (OSError, ValueError) as exc:
            messagebox.showerror(self.t('error'), str(exc))
            return
        self.launch(dict(source=Path(source), locale=self.data_locale.get(),
                         destination=destination), offline=True)

    def launch(self, options, offline=False):
        self.running = True
        self.current_offline = offline
        self.cancel_event = threading.Event()
        self.last_output = None
        self.open_button.configure(state='disabled')
        self.run_button.configure(state='disabled')
        self.offline_button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.file_menu.entryconfigure(0, state='disabled')
        self.file_menu.entryconfigure(1, state='disabled')
        self.file_menu.entryconfigure(3, state='disabled')
        self.refresh_auth_controls()
        self.status_key = 'converting' if offline else 'working'
        self.status.configure(text=self.t(self.status_key))
        self.bar.start()
        self.clear_log()
        self.append_log(self.t('conversion_started') if offline else self.t('export_started'))
        thread = threading.Thread(target=self.worker, args=(options, self.cancel_event), daemon=True)
        thread.start()

    def worker(self, options, cancel):
        destination = options.pop('destination')
        output = destination / dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        try:
            result = run_export(output=output, progress=lambda message: self.events.put(('log', message)),
                                cancel=cancel, **options)
            self.events.put(('done', result))
        except ExportCancelled:
            self.events.put(('cancelled', output))
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.events.put(('error', (str(exc), output)))
        finally:
            options.pop('password', None)

    def pump(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.append_log(localize(value, self.language.get()))
                elif kind == 'store_deleted':
                    if self.remembered_email == value:
                        self.remembered_email = None
                    self.save_config()
                    self.refresh_auth_controls()
                elif kind == 'store_delete_error':
                    self.append_log(self.t('store_delete_failed'))
                    self.refresh_auth_controls()
                elif kind in ('auth_done', 'auth_error'):
                    self.bar.stop()
                    self.authenticating = False
                    if kind == 'auth_done':
                        self.session, warning, self.remembered_email = value
                        detected_country = self.session.preferred_country or self.country.get().strip().upper()
                        detected_locale = self.session.preferred_locale or self.data_locale.get()
                        self.updating_options = True
                        try:
                            self.country.set(detected_country)
                            self.data_locale.set(detected_locale)
                        finally:
                            self.updating_options = False
                        self.session.set_options(detected_country, detected_locale)
                        self.save_config()
                        self.status_key = 'connected'
                        self.status.configure(text=self.t('connected'))
                        self.append_log(self.t('connected'))
                        if self.session.preferred_country or self.session.preferred_locale:
                            self.append_log(self.t('options_detected').format(country=detected_country,
                                                                             locale=detected_locale))
                        if warning:
                            self.append_log(self.t(warning))
                            self.remember_password.set(False)
                            self.save_config()
                    else:
                        detail = localize(value, self.language.get())
                        self.status_key = None
                        self.status.configure(text=f'{self.t("error")}: {detail}')
                        self.append_log(f'{self.t("error")}: {detail}')
                    self.refresh_auth_controls()
                else:
                    self.bar.stop()
                    self.running = False
                    self.cancel_button.configure(state='disabled')
                    if kind == 'done':
                        self.last_output = value
                        self.status_key = 'conversion_done' if self.current_offline else 'done'
                        self.status.configure(text=self.t(self.status_key))
                        self.append_log(self.t(self.status_key))
                        self.open_button.configure(state='normal')
                    elif kind == 'cancelled':
                        self.last_output = value if value.exists() else None
                        self.status.configure(text=self.t('cancelled'))
                        self.status_key = 'cancelled'
                    else:
                        error, output = value
                        self.last_output = output if output.exists() else None
                        detail = localize(error, self.language.get())
                        self.status.configure(text=f'{self.t("error")}: {detail}')
                        self.status_key = None
                        self.append_log(f'{self.t("error")}: {detail}')
                    if self.last_output:
                        self.open_button.configure(state='normal')
                        self.file_menu.entryconfigure(3, state='normal')
                    self.refresh_auth_controls()
                    if self.quit_when_done:
                        if self.session is not None:
                            self.session.logout()
                        self.session = None
                        self.destroy()
                        return
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def append_log(self, message):
        self.log.configure(state='normal')
        self.log.insert('end', message + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def clear_log(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def cancel(self):
        if self.cancel_event:
            self.cancel_event.set()
            self.cancel_button.configure(state='disabled')

    def open_output(self):
        if self.last_output:
            try:
                reveal_folder(self.last_output)
            except OSError as exc:
                messagebox.showerror(self.t('error'), str(exc))

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log.get('1.0', 'end').strip())


if __name__ == '__main__':
    Application().mainloop()

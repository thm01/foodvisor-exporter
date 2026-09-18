# Foodvisor Exporter

English · [Français](README.md)

Foodvisor Exporter lets you export the diary data from your own Foodvisor account as JSON, CSV, and XLSX. This is an **unofficial, independent project with no affiliation to Foodvisor**. It uses a private API that may change or reject requests. Check [Foodvisor's terms of service](https://www.foodvisor.io/fr/terms-of-service/raw/) before using it.

## Installation and launch

The source code requires [**Python 3.9 or newer**](https://www.python.org/downloads/) and a recent browser. Executable archives, when available, include Python.

| System | File to open |
| --- | --- |
| Windows | `Foodvisor-exporter-windows.cmd` |
| macOS | `Foodvisor-exporter-macos.command` |
| Linux | `Foodvisor-exporter-linux.sh` |

If your file manager does not run the Linux launcher, open a terminal in the project directory and run `bash Foodvisor-exporter-linux.sh`. On macOS, the `.command` file opens in Terminal. You can also start the interface directly with `python3 app/web_interface.py` (or `py -3 app\web_interface.py` on Windows). The program opens a page in your browser automatically; if that fails, copy the local address shown in the terminal.

The source version has no additional required dependencies. To save your password in the system credential store, optionally install `keyring` with `python3 -m pip install keyring` (or `py -3 -m pip install keyring` on Windows).

## Using the graphical interface

1. Choose the interface language from the menu at the top right. The data language follows it by default.
2. Enter the email address and password for your personal Foodvisor account. **Advanced options** lets you change the detected country and data language; it opens automatically if no country was found.
3. Click **Log in**. The date range and export become available after Foodvisor responds. Account preferences may fill in the country and data language unless you selected the latter manually. The system credential store can remember your password when available.
4. Choose the dates in the calendars, then choose the destination directory. You can enter its path or select it in the page's folder browser. Start the export. The page shows progress and errors. **Cancel** stops processing between requests; a request already in progress can take up to 30 seconds.

The “Country” menu offers common countries and “Other country” for a two-letter ISO code. Foodvisor may reject some codes.

Each successful export creates a timestamped directory containing `historique.json`, `Foodvisor.csv`, `Foodvisor.xlsx`, `EXPORT_TERMINE.txt`, and the raw JSON responses in `sources/`. Activities also appear in `Foodvisor-activities.csv` and `.json`; their daily totals appear in `Foodvisor-days.csv` and the workbook. These files may contain sensitive personal data: keep them in a private location. You can convert previously downloaded data without connecting to Foodvisor.

**Log out** clears the in-memory token and locks export again. You can change the country and data language after logging in; changes apply to the next export without logging in again. To switch accounts, log out first. Offline conversion remains available while logged out. **Forget saved password** removes it from the system credential store; clearing the remember option has the same effect.

The interface uses a local server (`127.0.0.1`), which contacts Foodvisor over HTTPS. **Quit** stops it; closing the page stops it after about two minutes of inactivity. The token stays in memory, and the password is saved only if you enable the system credential store.

## Command line

To export without the graphical interface:

```bash
bash Foodvisor-exporter.sh --start 2026-01-01 --end 2026-01-31
```

In the terminal, dates use **YYYY-MM-DD** format. `--start` is required for a download; `--end` defaults to today. Both dates are inclusive. The country (`--country`) and data language (`--locale`) default to `BE` and `fr`, respectively. `--locale en` requests data in English and produces English CSV/XLSX labels. The program prompts for credentials in the terminal, then creates the files under `exports/<timestamp>/`.

To convert previously downloaded responses again, without connecting:

```bash
bash Foodvisor-exporter.sh --source exports/<timestamp>/sources
```

A normal command exits after one export. To run several exports in the same terminal and reuse the session, run `bash Foodvisor-exporter.sh --interactive`. Enter a date range in **YYYY-MM-DD** format for each export, then leave the start date blank to quit. The password is requested again only if the session is no longer valid. It is not stored on disk.
Older `donnees-brutes/` folders still work with `--source` or offline conversion in the interface.

## Limitations

The exporter reads the authenticated account's diary and the food records referenced by that diary. It does not browse the general catalog, change the account, or perform synchronization. Requests run sequentially with a one-second pause between them; this does not guarantee that Foodvisor will accept them.

The API may change, and results may be incomplete if the diary has not synchronized. Meal and food names come from Foodvisor and are not translated locally. The tool does not refresh tokens, download images, or schedule automatic exports. Check the output files before relying on them.
Daily burned kcal are the sum of `calories_burned` from received activities; this may differ from the balance shown by Foodvisor.

The repository contains no APK, decompiled code, secrets extracted from the application, or account data. To request your data through official channels, see [Foodvisor's privacy policy](https://www.foodvisor.io/fr/privacy-policy/raw/).

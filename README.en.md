# Foodvisor Exporter

English · [Français](README.md)

Foodvisor Exporter lets you export the diary data from your own Foodvisor account as JSON, CSV, and XLSX. This is an **unofficial, independent project with no affiliation to Foodvisor**. It uses a private API that may change or reject requests. Check [Foodvisor's terms of service](https://www.foodvisor.io/fr/terms-of-service/raw/) before using it.

## Installation and launch

Download and extract the repository, then install **Python 3.9 or newer**. The launchers check this requirement and show an error if it is missing; they do not install it. A recent web browser is also needed.

| System | File to open |
| --- | --- |
| Windows | `Foodvisor-exporter-windows.cmd` |
| macOS | `Foodvisor-exporter-macos.command` |
| Linux | `Foodvisor-exporter-linux.sh` |

If your file manager does not run the Linux launcher, open a terminal in the project directory and run `bash Foodvisor-exporter-linux.sh`. On macOS, the `.command` file opens in Terminal. You can also start the interface directly with `python3 app/web_interface.py` (or `py -3 app\web_interface.py` on Windows). The program opens a page in your browser automatically; if that fails, copy the local address shown in the terminal.

The application needs no other Python library. To enable the optional system credential store, install `keyring` with `python3 -m pip install keyring` (or `py -3 -m pip install keyring` on Windows). A compatible system credential store must also be available; otherwise, you can still log in manually. The archives built by the GitHub Actions workflow include `keyring` and Python, so users of those archives do not need a separate Python installation.

## Using the graphical interface

1. Choose the interface language at the top of the page. This setting does not change the language of exported data.
2. Enter the email address and password for your personal Foodvisor account. The country uses the last code you used or, on first launch, your computer's region if available. Choose a code if the field is empty. You can change the data language (`fr` or `en`); it determines the responses requested from Foodvisor and the CSV/XLSX labels.
3. Click **Log in**. The window waits for Foodvisor's response and enables the date range and export only after it receives an access token. If the response contains your account preferences, it automatically fills in the country and supported language. Before logging in, you can select **Remember password in the system credential store**; this option is disabled if no compatible credential store is available.
4. Choose the date range in **DD-MM-YYYY** format or with the calendars, then choose the destination directory. You can enter its path or select it in the page's folder browser. Start the export. The page shows progress and errors. **Cancel** stops processing between requests; a request already in progress can take up to 30 seconds.

The “Country” field suggests the two-letter ISO codes `BE`, `FR`, `CH`, `LU`, `CA`, `US`, `GB`, `DE`, `ES`, and `IT`. These are suggestions, not a list of countries officially confirmed by Foodvisor. Your computer's region is only a suggestion: it may differ from the account's food country. The selected code is used in the API URL; the service may still reject a valid ISO code.

Each successful export creates a timestamped directory containing `historique.json`, `Foodvisor.csv`, `Foodvisor.xlsx`, `EXPORT_TERMINE.txt`, and the raw JSON responses in `donnees-brutes/`. These files may contain sensitive personal data: keep them in a private location. You can convert previously downloaded data without connecting to Foodvisor; the window shows its progress and result. Use the dedicated button to clear the diagnostics pane.

**Log out** clears the in-memory token and locks export again. You can change the country and data language after logging in; changes apply to the next export without logging in again. To switch accounts, log out first. Offline conversion remains available while logged out. **Forget saved password** removes it from the system credential store; clearing the remember option has the same effect.

The page communicates only with a local server bound to `127.0.0.1`. The Python program contacts Foodvisor; the browser does not contact it directly. Use **Quit** on the page to stop the local server. The interface language and, after a login attempt, the email address are saved locally. The token is never written to disk. The application saves the password only if you explicitly enable the system credential store; your browser may separately offer to save it. To log in, the application sends your password directly to Foodvisor over HTTPS. It does not send your credentials to the project creator.

## Command line

To export without the graphical interface:

```bash
bash Foodvisor-exporter.sh --start 2026-01-01 --end 2026-01-31
```

In the terminal, dates use **YYYY-MM-DD** format. `--start` is required for a download; `--end` defaults to today. Both dates are inclusive. The country (`--country`) and data language (`--locale`) default to `BE` and `fr`, respectively. `--locale en` requests data in English and produces English CSV/XLSX labels. The program prompts for credentials in the terminal, then creates the files under `exports/<timestamp>/`.

To convert previously downloaded responses again, without connecting:

```bash
bash Foodvisor-exporter.sh --source exports/<timestamp>/donnees-brutes
```

A normal command exits after one export. To run several exports in the same terminal and reuse the session, run `bash Foodvisor-exporter.sh --interactive`. Enter a date range in **YYYY-MM-DD** format for each export, then leave the start date blank to quit. The password is requested again only if the session is no longer valid. It is not stored on disk.

## Limitations

The exporter reads the authenticated account's diary and the food records referenced by that diary. It does not browse the general catalog, change the account, or perform synchronization. Requests run sequentially with a one-second pause between them; this does not guarantee that Foodvisor will accept them.

The API may change, and results may be incomplete if the diary has not synchronized. Meal and food names come from Foodvisor and are not translated locally. The tool does not refresh tokens, download images, or schedule automatic exports. Check the output files before relying on them.

The repository contains no APK, decompiled code, secrets extracted from the application, or account data. To request your data through official channels, see [Foodvisor's privacy policy](https://www.foodvisor.io/fr/privacy-policy/raw/).

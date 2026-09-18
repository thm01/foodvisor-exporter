# Foodvisor Exporter

English · [Français](README.md)

Foodvisor Exporter retrieves the diary from your own Foodvisor account and creates a workbook you can open in Excel or LibreOffice Calc. This is an **unofficial, independent project with no affiliation to Foodvisor**. It uses a private API that may change or reject requests. Check [Foodvisor’s terms of service](https://www.foodvisor.io/fr/terms-of-service/raw/) before using it.

## Install and launch

1. [Download the repository as a ZIP](https://github.com/thm01/foodvisor-exporter/archive/refs/heads/main.zip), then extract it. Keep the files and the `app/` directory together.
2. Install [Python 3.9 or newer](https://www.python.org/downloads/) if needed. The source version has no additional required Python packages; you only need a recent browser for the interface.
3. Open the launcher for your system **inside the extracted directory**:

   | System | Launcher |
   | --- | --- |
   | Windows | `Foodvisor-exporter-windows.cmd` |
   | macOS | `Foodvisor-exporter-macos.command` |
   | Linux | `Foodvisor-exporter-linux.sh` |

The application normally opens a page in your browser. If it does not, copy the `http://127.0.0.1:…` address shown in the terminal. On Linux, if your file manager does not launch the script, run `bash Foodvisor-exporter-linux.sh` in a terminal opened in the extracted directory. You can also start the interface with `python3 app/web_interface.py` (`py -3 app\web_interface.py` on Windows).

To save your password in the system credential store, you may **optionally** install `keyring` using `python3 -m pip install keyring` (`py -3 -m pip install keyring` on Windows). Without this option, the application does not save your password.

## Export your data

1. Choose the interface language in the menu. The data language follows it by default.
2. Enter your Foodvisor account credentials and click **Log in**. You can adjust the country and data language under **Advanced options**. The suggested country comes from your computer or account preferences; Foodvisor may reject some codes.
3. Choose the start and end dates in the calendars, then choose a destination directory. Both dates are included.
4. Click **Export**. Progress and errors appear on the page. When the export finishes, click **Open folder**, then open `Foodvisor.xlsx`.

**Cancel** stops processing between requests; a request already in progress may take up to 30 seconds. **Log out** clears the session from memory. Use **Quit** to stop the local server; closing the page stops it after about two minutes of inactivity.

## Understand the output

Each export creates a timestamped directory with this structure:

```text
<timestamp>/
├── Foodvisor.xlsx       Workbook to open
├── data/                CSV, merged JSON, and completion report
└── sources/             Raw JSON responses from Foodvisor
```

The `Foodvisor.xlsx` workbook contains:

| Sheet | Contents |
| --- | --- |
| **By day** | Daily meal and nutrient totals, recorded water, activity count, and received burned kcal. |
| **By meal** | Nutrient totals for each meal. |
| **Foods** | Food and dish details, quantities, and nutrients. |
| **Water** | Recorded water volumes, when present in the diary. |
| **Activities** | Received activities, duration, burned kcal, entry method, and origin. |
| **Read me** | Calculation methods and explanations of missing values. |

In `data/`, `Foodvisor.csv` contains food details, `Foodvisor-days.csv` contains daily summaries, and `Foodvisor-activities.csv` contains activities. `Foodvisor-activities.json` provides activities and daily totals; `historique.json` preserves the merged diary. The `sources/` directory lets you convert the export again without connecting. Workbook and CSV headers, along with display labels in the activities JSON, follow the selected data language; names supplied by Foodvisor are not translated. An unknown activity origin appears as “Other”, with the raw value kept alongside it.

These files may contain sensitive personal data: keep the directory in a private location.

## Convert previously downloaded data

In the interface, select the `sources/` directory of an existing export, then click **Convert previously downloaded data**. This works without connecting to Foodvisor and creates a self-contained export with a copy of the sources. Older `donnees-brutes/` directories are still accepted.

## Command line

You can also export without the interface:

```bash
bash Foodvisor-exporter.sh --start 2026-01-01 --end 2026-01-31
```

Terminal dates use **YYYY-MM-DD**. `--start` is required; `--end` defaults to today. `--country` defaults to `BE` and `--locale` to `fr`; `--locale en` produces English labels. The program prompts for credentials in the terminal and creates files under `exports/<timestamp>/`.

To convert existing responses, use `bash Foodvisor-exporter.sh --source exports/<timestamp>/sources`. To run several exports with the same session, add `--interactive`; the password is requested again only if the session is no longer valid.

## Limitations

The exporter reads only the logged-in account’s diary and the food records it references. It does not browse the general catalog, change the account, or synchronize phone data. Manually entered activities are exported when present in the received diary; activities from Health Connect or Apple Health may be missing.

Daily burned kcal are the sum of `calories_burned` from received activities; they may differ from the balance shown by Foodvisor. Blank cells mean missing values, not necessarily zero. The API can change, and results may be incomplete. Requests are sequential with a one-second pause, which does not guarantee acceptance by Foodvisor. The tool does not refresh tokens, download images, or schedule exports. Check the data before relying on it.

The repository contains no APK, decompiled code, extracted app secrets, or account data. To request your data through official channels, see [Foodvisor’s privacy policy](https://www.foodvisor.io/fr/privacy-policy/raw/).

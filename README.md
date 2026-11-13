# LeetCode to Google Sheets Sync

This script finds accepted LeetCode submissions newer than the last dated row in a Google Sheet and offers to append any missing problems. It asks for confirmation before writing.

## Requirements

- macOS with Python 3.9 or newer
- A LeetCode account with a current session and CSRF token
- Access to the target Google Sheet
- A Google OAuth client file at `credentials/google_oauth.json`

## One-Time Setup

Run these commands from the repository folder. Replace the example path with the folder where you cloned or saved this repository:

```sh
cd /path/to/lc_excel_sync
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create a `.env` file in the repository folder with your LeetCode credentials:

```text
LEETCODE_SESSION=your_leetcode_session_value
CSRF_TOKEN=your_csrf_token_value
```

The script loads these values from `.env`. Keep this file private; it is ignored by Git.

To obtain both values, sign in to LeetCode in your browser and open the developer tools. In the site's cookies for `leetcode.com`, copy the value of `LEETCODE_SESSION` and the value of `csrftoken`. The `CSRF_TOKEN` entry above should contain the `csrftoken` cookie value. In Chrome, find these under **Developer Tools > Application > Cookies**; in Safari, use **Web Inspector > Storage > Cookies**. Cookie values are sensitive credentials: do not share them or commit them to Git.

Place your Google OAuth client JSON at `credentials/google_oauth.json`. The Google account used for OAuth must have access to the target sheet. The first run may open a browser for Google authorization; complete that step when prompted. Keep the credentials directory private as well; it is ignored by Git.

## Run in VS Code

1. Open this repository folder in VS Code.
2. Select **Terminal > New Terminal**.
3. If the terminal did not open in the repository folder, change to it with `cd /path/to/lc_excel_sync`.
4. Activate the virtual environment and run the script:

```sh
source .venv/bin/activate
python lc_excel_sync.py
```

## Run Outside VS Code

Open Terminal.app (or another terminal), change to the repository folder, then activate the same virtual environment and run the script:

```sh
cd /path/to/lc_excel_sync
source .venv/bin/activate
python lc_excel_sync.py
```

Activate `.venv` again whenever you open a new terminal window.

## What the Script Does

- Prints the run start time and the date in the sheet's last row containing a date.
- Fetches accepted submissions after the end of that date, using the computer's local time zone.
- Skips entries already present in the sheet, comparing both the date and problem URL.
- Shows the number of new rows and a preview. Type `yes` to append them; any other response cancels the write.

The sheet must have a header in its first row, with dates in the first column formatted as `M/D/YYYY`. The script uses the last dated row, so keep the sheet ordered by date with the newest entry at the bottom. If no dated rows are found after the header, the script stops without fetching submissions.

## Troubleshooting

- **Missing `LEETCODE_SESSION` or `CSRF_TOKEN`:** Check that `.env` is in the repository folder and contains both values.
- **LeetCode returns 403:** The session or CSRF token may have expired. Update both values in `.env` from your current LeetCode session.
- **Google authorization or access error:** Confirm `credentials/google_oauth.json` is present, complete any browser authorization prompt, and verify that the authorized Google account can edit the sheet.
- **No dated rows found:** Check that the sheet has a header row and at least one date in column A in `M/D/YYYY` format.
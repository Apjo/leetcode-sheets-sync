"""
Filename: lc_excel_sync.py
Date: 2026-06-24
"""

import os
import time
from datetime import datetime

import gspread
import requests
from dotenv import load_dotenv  # remove this line if using direnv

load_dotenv()  # remove this line if using direnv

SHEET_ID = "1LR57A5rKO0b53TC_iBRIP2lK7RH4TK1FwRGytIfJxLE"
SHEET_TAB = "LC-2026"


GRAPHQL_URL = "https://leetcode.com/graphql"


def fetch_accepted_submissions(cutoff_ts: int) -> list[dict]:
    """
    Fetches accepted submissions newer than cutoff_ts.
    Filters by status and cutoff inline during pagination — stops as soon
    as a submission older than cutoff_ts is encountered (relies on
    LeetCode returning submissions in descending timestamp order).
    """
    leetcode_session = os.environ["LEETCODE_SESSION"]
    csrf_token = os.environ["CSRF_TOKEN"]
    headers = {
        "Cookie": f"LEETCODE_SESSION={leetcode_session}; csrftoken={csrf_token}",
        "x-csrftoken": csrf_token,
        "Referer": "https://leetcode.com",
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
    }

    query = """
    query submissionList($offset: Int!, $limit: Int!) {
      submissionList(offset: $offset, limit: $limit) {
        submissions {
          id
          timestamp
          statusDisplay
          titleSlug
        }
        hasNext
      }
    }
    """

    offset = 0
    limit = 20
    max_retries = 3
    backoff_base = 2
    results = []

    print(f"Fetching accepted submissions after date={datetime.fromtimestamp(cutoff_ts)}.")

    while True:
        payload = {"query": query, "variables": {"offset": offset, "limit": limit}}
        resp=None
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    GRAPHQL_URL, json=payload, headers=headers, timeout=10
                )

                if resp.status_code == 200:
                    break

                print(f"[WARN] HTTP {resp.status_code} (attempt {attempt})")

                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(backoff_base ** (attempt - 1))
                    continue

                if resp.status_code == 403:
                    raise RuntimeError(
                        f"LeetCode auth failed (403), session expired!, response={resp.text[:200]}"
                    )

                raise RuntimeError(
                    f"Error encountered with code={resp.status_code}, error response={resp.text[:200]}"
                )

            except requests.exceptions.RequestException as e:
                print(f"[ERROR] network error attempt={attempt}, error={e}")
                if attempt == max_retries:
                    raise
                time.sleep(backoff_base ** (attempt - 1))
        
        if not resp or resp.status_code != 200:
            raise RuntimeError(
                f"Failed after {max_retries} retries, last status={resp.status_code if resp else 'no response'}"
            )
        
        data = resp.json()

        try:
            block = data["data"]["submissionList"]
            subs = block["submissions"]
            has_next = block["hasNext"]
        except Exception:
            print("[ERROR] unexpected GraphQL response shape")
            print(resp.text[:300])
            raise

        print(f"[INFO] fetched={len(subs)} offset={offset}")

        if not subs:
            break

        for sub in subs:
            ts = int(sub["timestamp"])

            if ts <= cutoff_ts:
                # LeetCode returns newest-first — everything from here is older
                print(f"[INFO] Hit cutoff at offset={offset}, stopping pagination.")
                has_next = False
                break

            if sub.get("statusDisplay") == "Accepted":
                results.append(sub)

        if not has_next:
            break

        offset += limit
        time.sleep(0.3)

    print(f"[DONE] total accepted submissions after cutoff={len(results)}")
    return results


def format_rows(submissions: list[dict]) -> list[list[str]]:
    """
    Converts raw submission dicts to [date_str, url] rows.
    No filtering here — fetch_accepted_submissions already handled that.
    """
    rows = []

    for sub in submissions:
        try:
            dt = datetime.fromtimestamp(int(sub["timestamp"]))
            date_str = f"{dt.month}/{dt.day}/{dt.year}"

            slug = sub.get("titleSlug") or sub.get("title_slug") or sub.get("title")
            if not slug:
                print(f"[WARN] Missing slug for submission id={sub.get('id')}")
                continue

            url = f"https://leetcode.com/problems/{slug}/"
            rows.append([date_str, url])

        except Exception as e:
            print(f"[WARN] Skipping bad record, error={e}")
            continue

    print(f"[DONE] Formatted a total of={len(rows)} rows")
    return rows


def read_sheet():
    gc = gspread.oauth(credentials_filename="credentials/google_oauth.json")
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(SHEET_TAB)
    return ws, ws.get_all_values()


def push_to_sheet(new_rows: list[list[str]], ws, all_vals: list[list[str]]) -> None:
    # Dedup keyed on (date, url) — same problem on different dates = two entries
    existing = set()
    for row in all_vals[1:]:  # skip header
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            existing.add((row[0].strip(), row[1].strip()))

    to_add = [r for r in new_rows if (r[0], r[1]) not in existing]

    if not to_add:
        print("Nothing new to add, all submissions already in sheet.")
        return

    # Sort ascending so oldest new entry lands first
    to_add.sort(key=lambda r: datetime.strptime(r[0], "%m/%d/%Y"))

    print(f"\n[PREVIEW] {len(to_add)} new submissions to write. First record:")
    print(f"  {to_add[0][0]}  {to_add[0][1]}")
    confirm = input("\nLooks good? Type 'yes' to write all rows: ").strip().lower()
    
    if confirm != "yes":
        print("Aborted. Nothing written.")
        return
    
    ws.append_rows(to_add, value_input_option="USER_ENTERED") # type: ignore
    print(f"Appended {len(to_add)}, rows to='{SHEET_TAB}'.")
    for r in to_add:
        print(f"  {r[0]}  {r[1]}")


def main():
    run_started_at = datetime.now().astimezone()
    print(f"[INFO] Script started at {run_started_at.isoformat(timespec='seconds')}")

    ws, all_vals = read_sheet()
    last_date_row = next(
        (row for row in reversed(all_vals[1:]) if row and row[0].strip()),
        None,
    )
    if last_date_row is None:
        raise RuntimeError(f"No dated rows found in '{SHEET_TAB}'.")

    last_date = datetime.strptime(last_date_row[0].strip(), "%m/%d/%Y")
    cutoff_ts = int(last_date.replace(hour=23, minute=59, second=59).timestamp())
    print(f"[INFO] Last date in Excel sheet: {last_date:%m/%d/%Y}")
    print(f"Fetching LeetCode AC submissions after {last_date:%B %d, %Y}.")

    submissions = fetch_accepted_submissions(cutoff_ts=cutoff_ts)

    if not submissions:
        print("Nothing to write.")
        return

    rows = format_rows(submissions)

    if not rows:
        print("Nothing to write after formatting.")
        return

    print("Connecting to Google Sheets...")
    push_to_sheet(rows, ws, all_vals)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"[ERROR] Script failed: {error}")
        raise

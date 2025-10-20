import os, argparse
from googleapiclient.discovery import build
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main():
    ap = argparse.ArgumentParser(description="Share calendar with a user email")
    ap.add_argument("--calendar-id", default=os.getenv("CALENDAR_ID"))
    ap.add_argument("--calendar-name", default=os.getenv("CALENDAR_NAME"))
    ap.add_argument("--share-email", default=os.getenv("SHARE_EMAIL"))
    ap.add_argument("--role", default="writer", choices=["reader","writer","owner"])
    args = ap.parse_args()

    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=SCOPES
    )
    svc = build("calendar", "v3", credentials=creds)

    cid = args.calendar_id
    if not cid:
        page_token = None
        found = None
        while True:
            resp = svc.calendarList().list(pageToken=page_token).execute()
            for cal in resp.get("items", []):
                if cal.get("summary") == args.calendar_name:
                    found = cal["id"]
                    break
            if found or not resp.get("nextPageToken"):
                break
            page_token = resp.get("nextPageToken")
        if not found:
            raise SystemExit(f"Calendar named '{args.calendar_name}' not found")
        cid = found

    rule = {"scope": {"type": "user", "value": args.share_email}, "role": args.role}
    created = svc.acl().insert(calendarId=cid, body=rule).execute()
    print(f"Shared calendar '{cid}' with {args.share_email} as {args.role}: {created.get('id')}")

if __name__ == "__main__":
    main()

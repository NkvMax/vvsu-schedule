from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


CAL_SCOPE = "https://www.googleapis.com/auth/calendar"


def _load_sa_email(sa_json_path: str) -> str:
    try:
        with open(sa_json_path, "r", encoding="utf-8") as f:
            info = json.load(f)
        return info.get("client_email", "<unknown>")
    except Exception:
        return "<unknown>"


def _build_service(sa_json_path: str):
    creds = Credentials.from_service_account_file(sa_json_path, scopes=[CAL_SCOPE])
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _iter_calendar_list(service) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    token: Optional[str] = None
    while True:
        resp = service.calendarList().list(pageToken=token, maxResults=250).execute()
        items.extend(resp.get("items", []))
        token = resp.get("nextPageToken")
        if not token:
            break
    return items


def cmd_list(service, *, json_out: bool, search: Optional[str]) -> int:
    items = _iter_calendar_list(service)
    if search:
        s = search.lower()
        items = [it for it in items if s in (it.get("summary", "") or "").lower() or s in (it.get("id", "") or "").lower()]

    if json_out:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0

    print(f"Calendars total: {len(items)}")
    if not items:
        print(
            "\nСписок пуст.\n"
            "Подсказки:\n"
            "- Сервисный аккаунт видит ТОЛЬКО свои календари и те, которые на него расшарены.\n"
            "- Расшарь календарь на email сервисного аккаунта с правами writer (или выше), затем выполни add.\n"
        )
        return 0

    # pretty table
    rows: List[Tuple[str, str, str, str]] = []
    for it in items:
        rows.append((
            it.get("summary", "<no title>"),
            it.get("id", "<no id>"),
            it.get("timeZone", ""),
            it.get("accessRole", ""),
        ))

    # column widths
    w1 = min(40, max(len(r[0]) for r in rows))
    w2 = min(60, max(len(r[1]) for r in rows))
    w3 = max(2, max(len(r[2]) for r in rows))
    w4 = max(4, max(len(r[3]) for r in rows))

    def cut(s: str, w: int) -> str:
        s = s or ""
        return s if len(s) <= w else (s[: w - 1] + "…")

    header = f"{'SUMMARY'.ljust(w1)}  {'ID'.ljust(w2)}  {'TZ'.ljust(w3)}  {'ROLE'.ljust(w4)}"
    print(header)
    print("-" * len(header))
    for summary, cid, tz, role in rows:
        print(f"{cut(summary,w1).ljust(w1)}  {cut(cid,w2).ljust(w2)}  {cut(tz,w3).ljust(w3)}  {cut(role,w4).ljust(w4)}")
    return 0


def cmd_add(service, calendar_id: str, *, verify: bool) -> int:
    try:
        service.calendarList().insert(body={"id": calendar_id}).execute()
        print(f"Added to service account CalendarList: {calendar_id}")
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        content = e.content.decode("utf-8", errors="ignore") if hasattr(e, "content") else ""
        print(f"Google API error while adding calendar (status={status}).")
        if status in (404, 403):
            print(
                "Проверь:\n"
                "- календарь расшарен на сервисный аккаунт (email из ключа)\n"
                "- выдал права: writer (Make changes to events) или выше\n"
                "- включен Google Calendar API в проекте GCP\n"
            )
        if content:
            print(content[:800])
        return 1

    if verify:
        items = _iter_calendar_list(service)
        hit = next((it for it in items if it.get("id") == calendar_id), None)
        if hit:
            print(f"Visible now: {hit.get('summary')} (tz={hit.get('timeZone')}, role={hit.get('accessRole')})")
        else:
            print("Не видно в списке. Проверь шаринг календаря на SA и права доступа.")
    return 0


def cmd_remove(service, calendar_id: str, *, yes: bool) -> int:
    if not yes:
        print("Это удалит календарь из CalendarList сервисного аккаунта (не удаляет календарь у владельца).")
        print("Если уверен — добавь флаг: --yes")
        return 2

    try:
        service.calendarList().delete(calendarId=calendar_id).execute()
        print(f"Removed from service account CalendarList: {calendar_id}")
        return 0
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        content = e.content.decode("utf-8", errors="ignore") if hasattr(e, "content") else ""
        print(f"Google API error while removing calendar (status={status}).")
        if content:
            print(content[:800])
        return 1


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="add_calendar_to_sa.py",
        description="Manage calendars visible to a Google Service Account (CalendarList).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--sa",
        dest="sa_json",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "./credentials/service_account.json"),
        help="Path to service_account.json",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sp_list = sub.add_parser("list", help="List calendars visible to the Service Account")
    sp_list.add_argument("--json", action="store_true", help="Output raw JSON")
    sp_list.add_argument("--search", default=None, help="Filter by substring in summary/id")

    sp_add = sub.add_parser("add", help="Add a calendar to SA CalendarList")
    sp_add.add_argument("calendar_id", help="Calendar ID (e.g. ...@group.calendar.google.com)")
    sp_add.add_argument("--verify", action="store_true", help="List calendars after add and verify presence")

    sp_rm = sub.add_parser("remove", help="Remove a calendar from SA CalendarList (does NOT delete it globally)")
    sp_rm.add_argument("calendar_id", help="Calendar ID to remove")
    sp_rm.add_argument("--yes", action="store_true", help="Confirm removal")

    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if not os.path.exists(args.sa_json):
        print(f"Service account key not found: {args.sa_json}")
        return 2

    sa_email = _load_sa_email(args.sa_json)
    print(f"Service Account: {sa_email}")
    service = _build_service(args.sa_json)

    if args.cmd == "list":
        return cmd_list(service, json_out=args.json, search=args.search)
    if args.cmd == "add":
        return cmd_add(service, args.calendar_id, verify=args.verify)
    if args.cmd == "remove":
        return cmd_remove(service, args.calendar_id, yes=args.yes)

    print("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

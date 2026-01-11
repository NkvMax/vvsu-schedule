from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _build_service(sa_json_path: str):
    creds = Credentials.from_service_account_file(sa_json_path, scopes=SCOPES)
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


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="check_calendars.py",
        description="List calendars visible to a Google Service Account.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--sa",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "./credentials/service_account.json"),
        help="Path to service_account.json",
    )
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.add_argument("--search", default=None, help="Filter by substring in summary/id")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if not os.path.exists(args.sa):
        print("Файл ключа не найден:", args.sa)
        return 2

    try:
        service = _build_service(args.sa)
        items = _iter_calendar_list(service)

        if args.search:
            s = args.search.lower()
            items = [it for it in items if s in (it.get("summary","") or "").lower() or s in (it.get("id","") or "").lower()]

        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
            return 0

        print(f"Calendars total: {len(items)}")
        for it in items:
            summary = it.get("summary", "<no title>")
            cid = it.get("id")
            tz = it.get("timeZone")
            role = it.get("accessRole")
            print(f"- {summary} (id={cid}) tz={tz} role={role}")

        if not items:
            print(
                "\nСписок пуст.\n"
                "Подсказки:\n"
                "- Сервисный аккаунт видит ТОЛЬКО свои календари и те, которые на него расшарены.\n"
                "- Расшарь нужный календарь на адрес сервисного аккаунта с ролью writer/reader.\n"
            )
        return 0

    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        content = e.content.decode("utf-8", errors="ignore") if hasattr(e, "content") else ""
        if status == 403 and "accessNotConfigured" in content:
            # Try to pull project_id for better message
            try:
                with open(args.sa, "r", encoding="utf-8") as f:
                    project_id = json.load(f).get("project_id")
            except Exception:
                project_id = None
            print(
                "Google Calendar API не включен для проекта этого ключа.\n"
                f"Включи API и повтори. project_id: {project_id}\n"
            )
        else:
            print("HttpError:", e)
            if content:
                print(content[:800])
        return 1
    except Exception as e:
        print("Ошибка:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

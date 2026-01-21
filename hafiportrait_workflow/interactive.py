from __future__ import annotations

from pathlib import Path
from typing import Any

from .api import HafiportraitClient
from .state import load_last_event


def prompt_non_empty(label: str) -> str:
    while True:
        v = input(f"{label}: ").strip()
        if v:
            return v


def interactive_select_event(client: HafiportraitClient, source: str, root: Path) -> str:
    last = load_last_event(root)
    if last:
        ans = input(f"Use last event_id ({last})? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            return last

    events = client.fetch_events(source)
    if not events:
        print("Could not load events list. Please paste EVENT UUID manually.")
        return prompt_non_empty("Event UUID")

    print("\nSelect Event:")
    for i, e in enumerate(events, 1):
        name = (e.get("name") if isinstance(e, dict) else None) or "Event"
        slug = (e.get("slug") if isinstance(e, dict) else None) or ""
        status = (e.get("status") if isinstance(e, dict) else None) or ""
        print(f"  [{i}] {name} ({slug}) {status}")

    while True:
        raw = input("Choose number (or type UUID): ").strip()
        if not raw:
            continue
        if "-" in raw and len(raw) >= 8:
            return raw
        try:
            idx = int(raw)
            if 1 <= idx <= len(events):
                e: Any = events[idx - 1]
                if isinstance(e, dict):
                    event_id = e.get("id")
                    if isinstance(event_id, str) and event_id:
                        return event_id
        except Exception:
            pass
        print("Invalid selection. Try again.")

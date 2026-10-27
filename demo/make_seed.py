"""Writes demo/seed.json: a fictional board used for screenshots, the README GIF and the demo. Nothing personal in it."""
import json
import time
from pathlib import Path

NOW = int(time.time() * 1000)
DRAWERS = [("pkitchen", "kitchen reno"), ("ptrip", "japan trip"), ("pnovel", "novel"), ("pgarden", "garden")]
TABS = ("general", "docs", "ideas")
NOTES = {
    "pkitchen": [("Order the oak worktop", "3 m, oiled, delivery before the 14th.", "todo"),
                 ("Electrician quote", "Second quote received: 1,240 €.", "doing"),
                 ("Tiles chosen", "Zellige, sage green, 10x10.", "done"),
                 ("Measure the window", "", "todo")],
    "ptrip": [("Rail pass", "7 days, start in Kyoto.", "todo"), ("Ryokan in Hakone", "Booked for 2 nights.", "done"),
              ("Learn 50 words", "Greetings, numbers, food.", "doing")],
    "pnovel": [("Chapter 3 rewrite", "The letter arrives too early. Move it after the storm.", "doing"),
               ("Name for the lighthouse keeper", "Ilse? Maren?", "info"), ("Ending", "Open, but not vague.", "todo")],
    "pgarden": [("Plant garlic", "Before the first frost.", "todo"), ("Compost", "Turn it every two weeks.", "info")],
}
AGENT_NOTES = [("RESEARCH-BOT", "Prices of oak worktops", "Found 4 suppliers; cheapest 410 € for 3 m. Sources in docs/oak.md."),
               ("RESEARCH-BOT", "Weather in Kyoto, April", "Average 15 °C, 9 rainy days."),
               ("WATCHER", "Website back online", "The garden blog answered again at 06:12 after 4 minutes down.")]


def main() -> None:
    d = {"projects": {}, "folders": {}, "notes": {}, "imported": {}}
    n = 0
    for i, (pid, name) in enumerate(DRAWERS):
        d["projects"][pid] = {"name": name, "order": i, "createdAt": NOW}
        for j, tab in enumerate(TABS):
            d["folders"][f"f{pid[1:]}{j}"] = {"name": tab, "order": j, "project": pid, "createdAt": NOW}
        for k, (title, body, status) in enumerate(NOTES[pid]):
            n += 1
            d["notes"][f"n{n:03d}"] = {"title": title, "body": body, "status": status, "tag": "", "folder": f"f{pid[1:]}0",
                                       "x": (k % 3) * 270, "y": (k // 3) * 230, "z": n, "n": n, "createdAt": NOW, "updatedAt": NOW, "src": ""}
    d["projects"]["parrivees"] = {"name": "inbox", "order": 100000, "createdAt": NOW}
    for k, (agent, title, body) in enumerate(AGENT_NOTES):
        n += 1
        fid = "f" + agent.lower().replace("-", "")[:12]
        d["folders"].setdefault(fid, {"name": agent, "order": 10 + k, "project": "parrivees", "createdAt": NOW})
        src = f"from-agents/{agent.lower()}/{k}.md"
        d["notes"][f"a{n:03d}"] = {"title": title, "body": body, "status": "info", "tag": agent, "folder": fid,
                                   "x": (k % 3) * 270, "y": 0, "z": n, "n": n, "createdAt": NOW, "updatedAt": NOW, "src": src}
        d["imported"][src] = f"a{n:03d}"
    out = Path(__file__).with_name("seed.json")
    out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out}: {len(d['projects'])} drawers, {len(d['notes'])} notes")


if __name__ == "__main__":
    main()

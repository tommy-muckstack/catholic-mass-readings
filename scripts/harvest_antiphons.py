#!/usr/bin/env python3
"""Harvest daily Mass propers (entrance/communion antiphons) from
catholicculture.org day pages into JSONL, one line per date.

Resumable: skips dates already present in the output file.
"""
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
from html import unescape
from pathlib import Path

BASE = "https://www.catholicculture.org/culture/liturgicalyear/calendar/day.cfm?date={d}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("antiphons.jsonl")
START = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2024, 11, 30)
END = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date(2026, 8, 31)
DELAY = 1.2

TAG_RE = re.compile(r"<[^>]+>")


def clean(s):
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub("", s))).strip()


def parse_propers(html):
    m = re.search(r'<div id="propers"[^>]*>(.*?)</div>', html, re.S)
    if not m:
        return None
    title_m = re.search(r"<title>(.*?)</title>", html, re.S)
    celebrations = []
    current = None
    # Pages mix closed and unclosed <p> tags, so split on <p> boundaries
    # instead of matching pairs.
    for chunk in re.split(r"<p>", m.group(1)):
        # Site HTML is sloppy: <b> headers are sometimes closed by </p>
        # instead of </b>, or the </b> lands in the following chunk.
        if "</b>" in chunk:
            raw_label, raw_body = chunk.split("</b>", 1)
        elif chunk.lstrip().startswith("<b>"):
            raw_label, raw_body = chunk, ""
        else:
            continue
        label = clean(raw_label).rstrip(":").strip()
        body = clean(raw_body)
        head = re.match(r"Mass Propers for (?:the )?(.*)$", label)
        low = label.lower()
        known = low.startswith(("entrance antiphon", "communion antiphon", "or")) or "verse" in low or "alleluia" in low
        # Some pages omit the "Mass Propers for" prefix: a bold heading with
        # no body that isn't a recognized proper starts a new celebration.
        if head or (not body and not known):
            current = {"celebration": head.group(1) if head else label, "propers": []}
            celebrations.append(current)
            continue
        if current is None:
            continue
        if low.startswith("entrance"):
            kind = "entrance"
        elif low.startswith("communion"):
            kind = "communion"
        elif low.startswith("or"):
            kind = "or"  # alternate for the preceding antiphon
        elif "verse" in low or "alleluia" in low:
            kind = "verse"
        else:
            kind = "other"
        ref = re.sub(
            r"(?i)^(entrance[^,:]*|communion[^,:]*|alleluia verse|verse before the gospel|or)[,: ]*",
            "",
            label,
        ).strip()
        if body:
            current["propers"].append({"kind": kind, "reference": ref, "text": body})
    return {
        "pageTitle": clean(title_m.group(1)) if title_m else None,
        "celebrations": celebrations,
    }


def main():
    done = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            try:
                done.add(json.loads(line)["date"])
            except Exception:
                pass
    total = (END - START).days + 1
    fetched = 0
    with OUT.open("a") as f:
        d = START
        while d <= END:
            ds = d.isoformat()
            d += timedelta(days=1)
            if ds in done:
                continue
            req = urllib.request.Request(BASE.format(d=ds), headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    final_url = resp.geturl()
                    html = resp.read().decode("utf-8", "replace")
            except Exception as e:
                print(f"{ds}: FETCH ERROR {e}", flush=True)
                time.sleep(10)
                continue
            if "unavailable" in final_url:
                f.write(json.dumps({"date": ds, "unavailable": True}) + "\n")
                f.flush()
                time.sleep(DELAY)
                continue
            parsed = parse_propers(html)
            row = {"date": ds}
            if parsed is None:
                row["noPropers"] = True
            else:
                row.update(parsed)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            fetched += 1
            if fetched % 25 == 0:
                print(f"progress: {len(done) + fetched}/{total}", flush=True)
            time.sleep(DELAY)
    print(f"done: fetched {fetched} new days -> {OUT}", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Refresh the SVN/PRN/plane table baked into index.html.

Joins two real sources:
  * NAVCEN (US Coast Guard) GPS constellation status -- authoritative SVN, PRN,
    orbital plane/slot and block type.
  * CelesTrak GP element set for GROUP=gps-ops -- gives the NORAD catalogue
    number for each PRN.

The table is keyed by NORAD ID because that never changes for a given
spacecraft, whereas a PRN can be reassigned when a satellite is retired.
NAVCEN sends no CORS headers, so the page cannot fetch it at runtime; this
script bakes the result into index.html between the SVN_TABLE markers.

Usage: python3 tools/update-gps-metadata.py
"""
import json
import pathlib
import re
import urllib.request

NAVCEN = "https://www.navcen.uscg.gov/gps-constellation"
CELESTRAK = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=json"
UA = {"User-Agent": "gps-sky-trails/1.0 (constellation metadata refresh)"}
INDEX = pathlib.Path(__file__).resolve().parent.parent / "index.html"
START = "/* SVN_TABLE_START */"
END = "/* SVN_TABLE_END */"


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read().decode("utf-8", "replace")


def navcen_rows(html):
    """Pull (plane, slot, SVN, PRN, block) out of the constellation status table."""
    rows = []
    for table in re.findall(r"<table.*?</table>", html, re.S):
        for tr in re.findall(r"<tr.*?</tr>", table, re.S):
            cells = [
                re.sub(r"\s+", " ", re.sub("<[^>]+>", "", c)).strip()
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
            ]
            if len(cells) >= 5 and re.fullmatch(r"[A-F]", cells[0]) and cells[2].isdigit() and cells[3].isdigit():
                rows.append({
                    "plane": cells[0] + cells[1],
                    "svn": int(cells[2]),
                    "prn": int(cells[3]),
                    "block": cells[4],
                })
    return rows


def main():
    nav = navcen_rows(get(NAVCEN))
    if not nav:
        raise SystemExit("no constellation rows found at NAVCEN -- page layout may have changed")

    norad_by_prn = {}
    for gp in json.loads(get(CELESTRAK)):
        m = re.search(r"PRN\s*(\d+)", gp["OBJECT_NAME"])
        if m:
            norad_by_prn[int(m.group(1))] = gp["NORAD_CAT_ID"]

    table, missing = {}, []
    for row in nav:
        norad = norad_by_prn.get(row["prn"])
        if norad is None:
            missing.append(row)
            continue
        table[str(norad)] = {"svn": row["svn"], "prn": row["prn"], "plane": row["plane"], "block": row["block"]}

    lines = [
        "  %s:{svn:%d,prn:%d,plane:'%s',block:'%s'}" % (k, v["svn"], v["prn"], v["plane"], v["block"])
        for k, v in sorted(table.items(), key=lambda kv: kv[1]["svn"])
    ]
    block = "%s\n%s\n%s" % (START, ",\n".join(lines), END)

    html = INDEX.read_text(encoding="utf-8")
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, html, count=1, flags=re.S)
    if new == html and START not in html:
        raise SystemExit("markers %s / %s not found in index.html" % (START, END))
    INDEX.write_text(new, encoding="utf-8")

    print("wrote %d satellites to %s" % (len(table), INDEX.name))
    if missing:
        print("no CelesTrak match (not in gps-ops?): " + ", ".join("SVN%d/PRN%d" % (m["svn"], m["prn"]) for m in missing))


if __name__ == "__main__":
    main()

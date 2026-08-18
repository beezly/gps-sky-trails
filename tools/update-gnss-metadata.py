#!/usr/bin/env python3
"""Refresh the constellation metadata baked into index.html.

Two tables, from three real sources:

  * GPS -- NAVCEN (US Coast Guard) constellation status gives SVN, PRN,
    orbital plane/slot and block type; CelesTrak GROUP=gps-ops supplies the
    NORAD catalogue number for each PRN. Keyed by NORAD ID, because that never
    changes for a given spacecraft whereas a PRN can be reassigned when a
    satellite retires.
  * Galileo -- the GSC (European GNSS Service Centre) constellation
    information gives each GSAT serial its SV ID (the E-code broadcast as its
    PRN) and service status. Keyed by GSAT serial, which CelesTrak puts in the
    object name.

Neither source sends CORS headers, so the page cannot fetch them at runtime.
GLONASS and BeiDou need no table -- CelesTrak's own object names carry the
GLONASS number and the BeiDou C-code.

Usage: python3 tools/update-gnss-metadata.py
"""
import json
import pathlib
import re
import urllib.request

NAVCEN = "https://www.navcen.uscg.gov/gps-constellation"
CELESTRAK = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=json"
GSC = "https://www.gsc-europa.eu/system-service-status/constellation-information"
UA = {"User-Agent": "gps-sky-trails/1.0 (constellation metadata refresh)"}
INDEX = pathlib.Path(__file__).resolve().parent.parent / "index.html"
SVN_START, SVN_END = "/* SVN_TABLE_START */", "/* SVN_TABLE_END */"
GAL_START, GAL_END = "/* GALILEO_TABLE_START */", "/* GALILEO_TABLE_END */"


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


def galileo_rows(html):
    """Pull (GSAT serial, SV ID, status) out of the GSC constellation table."""
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", html, re.S):
        cells = [
            re.sub(r"\s+", " ", re.sub("<[^>]+>", "", c)).replace("\xa0", "").strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        ]
        if len(cells) >= 4 and re.fullmatch(r"GSAT\d{4}", cells[0]) and re.fullmatch(r"E\d{2}", cells[1]):
            rows.append({"gsat": cells[0], "svid": cells[1], "status": cells[3]})
    return rows


def splice(html, start, end, lines):
    block = "%s\n%s\n%s" % (start, ",\n".join(lines), end)
    if start not in html:
        raise SystemExit("markers %s / %s not found in index.html" % (start, end))
    return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, html, count=1, flags=re.S)


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

    gal = galileo_rows(get(GSC))
    if not gal:
        raise SystemExit("no Galileo rows found at the GSC -- page layout may have changed")

    html = INDEX.read_text(encoding="utf-8")
    html = splice(html, SVN_START, SVN_END, [
        "  %s:{svn:%d,prn:%d,plane:'%s',block:'%s'}" % (k, v["svn"], v["prn"], v["plane"], v["block"])
        for k, v in sorted(table.items(), key=lambda kv: kv[1]["svn"])
    ])
    html = splice(html, GAL_START, GAL_END, [
        "  %s:{svid:'%s',status:'%s'}" % (r["gsat"], r["svid"], r["status"])
        for r in sorted(gal, key=lambda r: r["gsat"])
    ])
    INDEX.write_text(html, encoding="utf-8")

    print("wrote %d GPS and %d Galileo satellites to %s" % (len(table), len(gal), INDEX.name))
    if missing:
        print("no CelesTrak match (not in gps-ops?): " + ", ".join("SVN%d/PRN%d" % (m["svn"], m["prn"]) for m in missing))


if __name__ == "__main__":
    main()

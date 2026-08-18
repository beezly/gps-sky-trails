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
import socket
import sys
import urllib.error
import urllib.request

NAVCEN = "https://www.navcen.uscg.gov/gps-constellation"
CELESTRAK = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=json"
GSC = "https://www.gsc-europa.eu/system-service-status/constellation-information"
UA = {"User-Agent": "gps-sky-trails/1.0 (constellation metadata refresh)"}
INDEX = pathlib.Path(__file__).resolve().parent.parent / "index.html"
SVN_START, SVN_END = "/* SVN_TABLE_START */", "/* SVN_TABLE_END */"
GAL_START, GAL_END = "/* GALILEO_TABLE_START */", "/* GALILEO_TABLE_END */"


def fail(message):
    """Exit with a one-line reason rather than a traceback -- this runs unattended."""
    sys.stderr.write("update-gnss-metadata: %s\n" % message)
    raise SystemExit(1)


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        fail("%s returned HTTP %s" % (url, e.code))
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        fail("could not reach %s (%s)" % (url, getattr(e, "reason", e)))


def existing(html, start, end):
    """Whatever is currently baked in, so we can report what actually changed."""
    block = re.search(re.escape(start) + r"(.*?)" + re.escape(end), html, re.S)
    if not block:
        return {}
    return dict(re.findall(r"(\w+):\{(.*?)\}", block.group(1)))


def describe(label, before, after):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(after) & set(before) if after[k] != before[k])
    if not (added or removed or changed):
        return "%s: unchanged (%d)" % (label, len(after))
    parts = ["%s: %d" % (label, len(after))]
    if added:
        parts.append("added " + ", ".join(added))
    if removed:
        parts.append("removed " + ", ".join(removed))
    if changed:
        parts.append("updated " + ", ".join(changed))
    return " | ".join(parts)


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
        fail("markers %s / %s not found in index.html" % (start, end))
    return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, html, count=1, flags=re.S)


def main():
    nav = navcen_rows(get(NAVCEN))
    if not nav:
        fail("no constellation rows found at NAVCEN -- page layout may have changed")

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
        fail("no Galileo rows found at the GSC -- page layout may have changed")

    original = INDEX.read_text(encoding="utf-8")
    before_gps = existing(original, SVN_START, SVN_END)
    before_gal = existing(original, GAL_START, GAL_END)

    html = splice(original, SVN_START, SVN_END, [
        "  %s:{svn:%d,prn:%d,plane:'%s',block:'%s'}" % (k, v["svn"], v["prn"], v["plane"], v["block"])
        for k, v in sorted(table.items(), key=lambda kv: kv[1]["svn"])
    ])
    html = splice(html, GAL_START, GAL_END, [
        "  %s:{svid:'%s',status:'%s'}" % (r["gsat"], r["svid"], r["status"])
        for r in sorted(gal, key=lambda r: r["gsat"])
    ])
    print(describe("GPS", before_gps, existing(html, SVN_START, SVN_END)))
    print(describe("Galileo", before_gal, existing(html, GAL_START, GAL_END)))
    if missing:
        print("no CelesTrak match (not in gps-ops?): " + ", ".join("SVN%d/PRN%d" % (m["svn"], m["prn"]) for m in missing))

    if html == original:
        print("index.html already up to date")
        return
    INDEX.write_text(html, encoding="utf-8")
    print("index.html updated")


if __name__ == "__main__":
    main()

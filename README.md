# GPS sky trails

A timelapse of the real GNSS constellations crossing the sky, as seen looking straight up (360-degree fisheye view). Each dot is a satellite; hover one for its identity and current elevation/azimuth.

Toggle **GPS**, **GLONASS**, **Galileo** and **BeiDou** independently, and stretch the timeline from **1 day to 7 days** ahead. Labels are each system's own identifier -- GPS by SVN, GLONASS by GLONASS number, Galileo by SV ID, BeiDou by PRN -- and are hidden automatically when more than 24 satellites are up, since they collide into an unreadable mat; hovering still names any dot. With a single constellation shown, colour is the orbital plane (where that is published); with several, colour is the constellation.

A week of 2-minute samples across every constellation is ~730k points, so tracks are held in typed arrays; a full recompute at the widest setting takes about 240 ms.

Each trail covers the last ~11.5 hours and fades out at its tail — just under one orbital period (11h 58m), so a track is roughly a single pass rather than a full day of overlapping loops.

Press **Use my location** to show the sky from where you are; otherwise it falls back to Nettleton Hill, West Yorkshire (53.65N, 1.83W). The timeline starts at your current local time and runs forward 24 hours in 2-minute steps, so what you see at `now` is the sky above you right now.

## Data sources

- **Orbits** — [CelesTrak](https://celestrak.org/) GP element sets for `GROUP=gnss`, one request covering all four systems, fetched fresh each time the page loads (~145 satellites).
- **GPS identity** — the [NAVCEN](https://www.navcen.uscg.gov/gps-constellation) (US Coast Guard) constellation status gives SVN, PRN, orbital plane/slot and block type.
- **Galileo identity** — the [GSC](https://www.gsc-europa.eu/system-service-status/constellation-information) (European GNSS Service Centre) constellation information gives each GSAT serial its SV ID and service status.
- **GLONASS and BeiDou** need no extra source: CelesTrak's object names already carry the GLONASS number (`COSMOS 2569 (764)`) and the BeiDou PRN and orbit type (`BEIDOU-3 M5 (C23)`).

Neither NAVCEN nor the GSC sends CORS headers, so those two tables cannot be fetched from a static page. They are baked into `index.html` and refreshed with:

```
python3 tools/update-gnss-metadata.py
```

The GPS table is keyed by NORAD catalogue number, which never changes for a given spacecraft, whereas a PRN can be reassigned when a satellite is retired.

### Keeping it current

The orbital elements need no maintenance -- the page fetches them live on every load, so new launches and retirements track reality on their own. Only the two identity tables above go stale, and they are refreshed every Monday by `.github/workflows/refresh-gnss-metadata.yml`, which runs the tool and commits only when something actually changed. Run it by hand from the Actions tab at any time.

One caveat: GitHub disables scheduled workflows in a **public** repository after 60 days with no repository activity. Workflow runs do not count as activity, and this one commits only when a constellation actually changes -- a few times a year, by the Actions bot -- so it will not reliably keep itself alive. It fails visibly rather than silently: GitHub emails the repository admins when it disables a workflow. Re-enable it from the Actions tab, or with

```
gh api -X PUT repos/beezly/gps-sky-trails/actions/workflows/refresh-gnss-metadata.yml/enable
```

Any push to the repository resets the 60-day clock. If you want the schedule to be genuinely self-sustaining, push using a personal access token stored as a secret instead of the default `GITHUB_TOKEN`, so the commits are attributed to you and count as repository activity.

If a table does fall behind, the failure is cosmetic rather than broken: a satellite missing from it still plots and animates correctly, because its position comes from the live elements. It simply loses its label, and in a single-constellation view its plane colour.

**QZSS is deliberately absent.** It is a regional system serving the Asia-Pacific: from the UK its satellites peak at 1.3 degrees elevation, so they never meaningfully rise. Adding it back is one line in `CONSTELLATIONS` (`{key:'qzss', name:'QZSS', color:'#7F77DD', on:false, match:/^QZS-/}`) plus an `identify()` branch -- worth doing if you view the page from Asia or Australasia. Note that BeiDou has the same regional element: its GEO and IGSO satellites sit over Asia, and only the ~33 MEO satellites are a global service.

If the element sets cannot be fetched (offline, or opened as a `file://` URL), the page falls back to an illustrative 24-satellite model and says so.

## Accuracy

Positions come from the element sets' mean elements with the standard SGP4 element recovery and secular J2 rates for RAAN, argument of perigee and mean anomaly. Drag and deep-space periodic terms are ignored, which keeps the page dependency-free. Checked against a full SGP4/SDP4 implementation (the `sgp4` Python library) across all 145 satellites over the full **7-day** span:

| Constellation | Mean error | Worst |
|---|---|---|
| GPS | 0.035° | 0.12° |
| GLONASS | 0.040° | 0.11° |
| Galileo | 0.044° | 0.13° |
| BeiDou | 0.047° | 0.23° |

That is under half a pixel at this plot scale. The element sets themselves age at a few km per day, which is the larger error over a week -- and still only hundredths of a degree in the sky.

Earth rotation uses true Greenwich mean sidereal time; the observer is placed on a spherical Earth, and no refraction correction is applied, so satellites within a degree of the horizon are approximate.

## Running locally

Open `index.html` in a browser -- no build step or dependencies. Geolocation and the CelesTrak fetch both need a real origin, so to see live data serve it instead:

```
python3 -m http.server 8000
```

then visit `http://localhost:8000`.

## Deploying with GitHub Pages

1. Push this repo to GitHub.
2. In the repo, go to **Settings > Pages**.
3. Under **Build and deployment**, set **Source** to `Deploy from a branch`, branch `main`, folder `/ (root)`.
4. Save. GitHub will publish the site at `https://<your-username>.github.io/<repo-name>/`.

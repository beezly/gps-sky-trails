# GPS sky trails

A timelapse of the real GPS constellation crossing the sky, as seen looking straight up (360-degree fisheye view). Each dot is a satellite, labelled with its SVN (space vehicle number) and coloured by its orbital plane; hover one for its PRN, block type, plane/slot and current elevation/azimuth.

Each trail covers the last ~11.5 hours and fades out at its tail — just under one orbital period (11h 58m), so a track is roughly a single pass rather than a full day of overlapping loops.

Press **Use my location** to show the sky from where you are; otherwise it falls back to Nettleton Hill, West Yorkshire (53.65N, 1.83W). The timeline starts at your current local time and runs forward 24 hours in 2-minute steps, so what you see at `now` is the sky above you right now.

## Data sources

- **Orbits** — [CelesTrak](https://celestrak.org/) GP element sets for `GROUP=gps-ops`, fetched fresh each time the page loads. This is the operational constellation, currently 31-32 satellites.
- **Identity** — the [NAVCEN](https://www.navcen.uscg.gov/gps-constellation) (US Coast Guard) GPS constellation status gives SVN, PRN, orbital plane/slot and block type. NAVCEN sends no CORS headers, so it cannot be fetched from a static page; the table is baked into `index.html` and refreshed with:

  ```
  python3 tools/update-gps-metadata.py
  ```

  It is keyed by NORAD catalogue number, which never changes for a given spacecraft, whereas a PRN can be reassigned when a satellite is retired. Re-run it after a launch or decommissioning; without it, new satellites still plot but show no SVN.

If the element sets cannot be fetched (offline, or opened as a `file://` URL), the page falls back to an illustrative 24-satellite model and says so.

## Accuracy

Positions come from the element sets' mean elements with the standard SGP4 element recovery and secular J2 rates for RAAN, argument of perigee and mean anomaly. Drag and deep-space periodic terms are ignored, which keeps the page dependency-free. Checked against a full SGP4/SDP4 implementation (the `sgp4` Python library) over a 24-hour window for the whole constellation, the mean error is **0.03 degrees** and the worst 0.11 degrees -- under a quarter of a pixel at this plot scale.

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

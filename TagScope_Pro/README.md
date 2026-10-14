# TagScope — Disaster Intelligence

TagScope is a disaster-management news monitoring workspace for Windows. Search disaster hazards and incidents, review an incident brief, filter reports, inspect coverage signals, and compare related reports from multiple publishers.

## Disaster-management features

- **Incident reports:** Search news coverage about floods, cyclones and storms, earthquakes, wildfires, landslides, extreme heat, drought, emergency response, and relief/recovery.
- **Incident brief:** Condenses available headlines and descriptions into a quick overview and reported developments.
- **Report filters:** Filter by disaster category, publication window, publisher, and feed; sort by relevance or date.
- **Disaster coverage signals:** Counts retrieved reports and publishers, shows a publication timeline, and surfaces recurring hazard/response terms. These are media-coverage signals, not verified damage or casualty estimates.
- **Compare reports:** Groups similar headlines from different publishers so reports about a potentially shared incident can be reviewed side by side.
- **Multiple news feeds:** Uses Google News and Bing News RSS feeds where available, with duplicate-title cleanup, request spacing, and short-lived in-memory caching.

> **Emergency safety:** TagScope is a news-monitoring aid, not an official warning system. For immediate danger, follow local emergency services and official disaster-management authorities. News coverage may be delayed, incomplete, or incorrect.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Internet connection

No additional Python packages are required.

## Quick start

1. Extract the ZIP to a normal folder.
2. Open the extracted `TagScope_Pro` folder.
3. Double-click `start_windows.bat`.
4. The server starts and your browser should open `http://127.0.0.1:8000`.
5. Try a search such as `India floods`, `cyclone landfall`, `earthquake damage`, `wildfire evacuation`, or `disaster relief`. You can also use the quick-search chips on the homepage.
6. Select the separate workspace tabs for Incident reports, Incident brief, Report filters, Coverage signals, and Compare reports.
7. To stop the app, click the terminal window and press **Ctrl+C**.

## Run from VS Code

1. Open VS Code and choose **File → Open Folder…**.
2. Select the extracted `TagScope_Pro` folder.
3. Choose **Terminal → New Terminal**.
4. Run:

   ```powershell
   py -3 server.py
   ```

   If `py -3` is unavailable, try `python server.py`.
5. Open `http://127.0.0.1:8000` in your browser.
6. Stop the server with **Ctrl+C**.

## Interpreting results

- Category labels are estimated from article headlines and descriptions, with the searched hazard used as a fallback when the report text is too vague.
- Filters and analytics operate only on the reports returned for the current search.
- Keyword frequency is not a measure of disaster severity. The app does not independently verify casualty counts, damage, evacuation orders, or official warnings.
- Headline similarity helps find potentially related reports; it does not establish that reports describe the exact same event.
- Coverage depends on external public news feeds, which can be delayed or unavailable. Search results are cached in memory for five minutes.

## Project files

- `server.py` — local server, RSS retrieval, request spacing, caching, categorization, and incident brief generation
- `static/index.html` — disaster-management workspace and feature views
- `static/style.css` — responsive visual design
- `static/app.js` — report filtering, analytics, and comparison logic
- `start_windows.bat` — Windows launcher

## Troubleshooting

- **Python is not recognized:** install Python 3.10 or newer from <https://www.python.org/downloads/windows/> and enable the PATH option.
- **Port 8000 is already in use:** close another TagScope window or change `PORT = 8000` near the top of `server.py` to `8010`, then open `http://127.0.0.1:8010`.
- **A news feed is unavailable:** wait a moment and try again; public providers may temporarily limit or change their responses.
- **No reports match your filters:** choose **Reset filters** or widen the publication window.
- **No comparison groups appear:** try a broader hazard and location query. Groups require similar headlines from at least two publishers.

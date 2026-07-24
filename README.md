# 🛰️ Sentinel Timelapse Generator

A web application that generates historical change timelapse videos from **Sentinel-2 satellite imagery** via the [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/) STAC API.

Select any location on Earth, configure date range and capture interval, and watch the landscape transform over time — rendered as an MP4 video.

## Features

- **Interactive Map** — Click anywhere or search by name (powered by Leaflet.js + OpenStreetMap Nominatim)
- **Quick-start Locations** — Pre-loaded chips for Palm Jumeirah, Las Vegas, Aral Sea, Shanghai
- **Configurable Parameters** — Date range, capture interval (monthly/quarterly/yearly), cloud cover filter, area radius, playback speed
- **Smart Scene Selection** — Groups satellite scenes by time period and picks the one with lowest cloud cover
- **Progress Tracking** — Real-time progress updates during generation
- **Video Playback & Download** — In-browser looping playback with download option
- **Premium UI** — Dark-mode glassmorphism dashboard with smooth animations

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python, FastAPI, Uvicorn |
| **Satellite Data** | pystac-client, planetary-computer, rasterio (Cloud-Optimized GeoTIFF) |
| **Image/Video** | Pillow, NumPy, imageio + ffmpeg |
| **Frontend** | Vanilla HTML/CSS/JS, Leaflet.js |

## Quick Start

```bash
chmod +x start.sh
./start.sh
```

This will:
1. Create a Python virtual environment
2. Install all dependencies
3. Launch the server at **http://localhost:8000**

## Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd backend && python main.py
```

## CLI Usage

The CLI tool (`cli.py`) gives you the same workflow as the web UI, entirely from the terminal. Activate the venv first:

```bash
source .venv/bin/activate
```

### 1. Find a Location

**By place name** (geocoded via OpenStreetMap):
```bash
python cli.py --place "Palm Jumeirah, Dubai"
```
If multiple results are found, you'll be prompted to pick one.

**By GPS coordinates:**
```bash
python cli.py --lat 25.1124 --lon 55.139
```

**Interactively** (just run with no args):
```bash
python cli.py
```
You'll be prompted to choose between name search and coordinates.

### 2. View the Location

After resolving the location, the CLI shows the coordinates, bounding box, and area size. It then offers to open the location in your browser on OpenStreetMap:

```
  📍 Location
  ────────────────────────────────────
  Name     : Palm Jumeirah, Dubai, UAE
  Latitude : 25.112400
  Longitude: 55.139000
  Radius   : 2.5 km  (5.0 × 5.0 km box)
  Bbox     : [55.1145, 25.0899, 55.1635, 25.1349]

  Open location in browser? [Y/n]:
```

Use `--no-map` to skip this step.

### 3. Configure Parameters

Parameters can be passed as flags or entered interactively when omitted:

| Flag | Description | Default |
|------|-------------|---------|
| `--start` | Start date (YYYY-MM-DD) | 2022-01-01 |
| `--end` | End date (YYYY-MM-DD) | Today |
| `--interval` | `monthly`, `quarterly`, or `yearly` | monthly |
| `--cloud` | Max cloud cover % (0–100) | 20 |
| `--radius` | Area radius in km | 2.5 |
| `--fps` | Video playback speed | 3 |
| `--output` / `-o` | Output directory | ./output |

### 4. Generate

The CLI shows a progress bar as it queries, downloads, and compiles:

```
  [██████████████████░░░░░░░░░░░░]  60.0%  Processing frame 7/12 (2023-07)
```

On completion:
```
  ✓ Timelapse generated successfully!

  📹 Video: /path/to/output/timelapse_a1b2c3d4.mp4
  📦 Size : 2.3 MB
```

Use `--open` to automatically open the video after generation.

### Example Commands

```bash
# Interactive mode — prompted for everything
python cli.py

# Search by name, all defaults, skip confirmations
python cli.py --place "Aral Sea" -y

# GPS coords, yearly interval over 5 years, larger area
python cli.py --lat 45.0 --lon 58.5 --start 2019-01-01 --end 2024-01-01 \
  --interval yearly --radius 5 --cloud 30

# Quarterly timelapse of Las Vegas, auto-open result
python cli.py --place "Las Vegas" --start 2020-01-01 --interval quarterly --open

# Full non-interactive (CI/scripting friendly)
python cli.py --lat 31.23 --lon 121.47 --start 2021-01-01 --end 2023-12-31 \
  --interval monthly --cloud 15 --radius 3 --fps 4 -o ./videos --no-map -y
```

## Project Structure

```
sentinel-timelapse/
├── cli.py               # Command-line interface
├── backend/
│   ├── main.py          # FastAPI server & API endpoints
│   ├── timelapse.py     # Core STAC query, download & video compilation
│   └── __init__.py
├── frontend/
│   ├── index.html       # Dashboard UI
│   ├── style.css        # Dark-mode glassmorphism styles
│   └── app.js           # Map, search, API calls, progress polling
├── requirements.txt
├── start.sh             # One-command setup & launch
└── README.md
```

## How It Works

1. **Location → Bounding Box** — Converts lat/lon + radius to a geographic bounding box
2. **STAC Query** — Searches Planetary Computer for Sentinel-2 L2A scenes within the bbox and date range
3. **Best Scene Selection** — Groups results by period and selects the scene with lowest cloud cover
4. **Windowed Download** — Reads only the relevant pixels from remote Cloud-Optimized GeoTIFFs (no full tile downloads)
5. **Frame Processing** — Resizes, adds date stamp overlay
6. **Video Compilation** — Assembles frames into MP4 using H.264 codec

## License

MIT

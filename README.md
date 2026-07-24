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

## Project Structure

```
sentinel-timelapse/
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

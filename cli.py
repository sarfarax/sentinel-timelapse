#!/usr/bin/env python3
"""
Sentinel Timelapse Generator — Command Line Interface

Mirrors the web UI journey from the terminal:
  1. Find a location by name or GPS coordinates
  2. Preview the location and bounding box on a map
  3. Configure parameters and generate the timelapse video

Usage examples:
  python cli.py --place "Palm Jumeirah, Dubai"
  python cli.py --lat 25.1124 --lon 55.139 --start 2022-01-01 --end 2024-01-01
  python cli.py --place "Aral Sea" --interval yearly --start 2019-01-01 --radius 5
"""

import argparse
import json
import math
import os
import sys
import webbrowser
from datetime import datetime, date

import requests

# Add backend to path so we can import timelapse module
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(SCRIPT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from timelapse import TimelapseGenerator


# ── ANSI colors ──────────────────────────────────────────────────────────────

class C:
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"


def banner():
    print(f"""
{C.CYAN}{C.BOLD}  ╔═══════════════════════════════════════════════╗
  ║  🛰️  Sentinel Timelapse Generator  — CLI      ║
  ║  Visualize Earth's change from the terminal   ║
  ╚═══════════════════════════════════════════════╝{C.RESET}
""")


# ── Geocoding ────────────────────────────────────────────────────────────────

def geocode(place_name: str) -> dict:
    """Search for a place using OpenStreetMap Nominatim and return the top result."""
    print(f"  {C.DIM}Searching for \"{place_name}\"...{C.RESET}")
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place_name, "format": "json", "limit": 5}
    headers = {"User-Agent": "sentinel-timelapse-cli/1.0"}

    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    results = resp.json()

    if not results:
        print(f"  {C.RED}✗ No results found for \"{place_name}\"{C.RESET}")
        sys.exit(1)

    if len(results) == 1:
        pick = results[0]
    else:
        print(f"\n  {C.BOLD}Found {len(results)} results:{C.RESET}")
        for i, r in enumerate(results):
            print(f"    {C.CYAN}[{i + 1}]{C.RESET} {r['display_name']}")
        print()
        while True:
            choice = input(f"  {C.YELLOW}Pick a result [1-{len(results)}]: {C.RESET}").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                pick = results[int(choice) - 1]
                break
            print(f"  {C.RED}Invalid choice, try again.{C.RESET}")

    lat = float(pick["lat"])
    lon = float(pick["lon"])
    name = pick["display_name"]
    return {"lat": lat, "lon": lon, "name": name}


# ── Map preview ──────────────────────────────────────────────────────────────

def compute_bbox(lat: float, lon: float, radius_km: float):
    """Return (min_lon, min_lat, max_lon, max_lat) bounding box."""
    lat_deg = radius_km / 111.32
    lon_deg = radius_km / (111.32 * math.cos(math.radians(lat)))
    return (lon - lon_deg, lat - lat_deg, lon + lon_deg, lat + lat_deg)


def show_map_preview(lat: float, lon: float, radius_km: float, label: str):
    """Print location info and optionally open an interactive map in the browser."""
    bbox = compute_bbox(lat, lon, radius_km)
    box_size_km = radius_km * 2

    print(f"""
  {C.BOLD}📍 Location{C.RESET}
  ────────────────────────────────────
  {C.GREEN}Name     :{C.RESET} {label}
  {C.GREEN}Latitude :{C.RESET} {lat:.6f}
  {C.GREEN}Longitude:{C.RESET} {lon:.6f}
  {C.GREEN}Radius   :{C.RESET} {radius_km} km  ({box_size_km:.1f} × {box_size_km:.1f} km box)
  {C.GREEN}Bbox     :{C.RESET} [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]
""")

    # Build an OpenStreetMap URL centered on the location
    osm_url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=14/{lat}/{lon}"

    answer = input(f"  {C.YELLOW}Open location in browser? [Y/n]: {C.RESET}").strip().lower()
    if answer in ("", "y", "yes"):
        webbrowser.open(osm_url)
        print(f"  {C.DIM}Opened map in browser.{C.RESET}")
    print()


# ── Progress display ─────────────────────────────────────────────────────────

def progress_callback(step: str, pct: float):
    """Pretty-print progress updates."""
    bar_width = 30
    filled = int(bar_width * pct)
    empty = bar_width - filled
    bar = f"{'█' * filled}{'░' * empty}"
    pct_str = f"{pct * 100:5.1f}%"
    # \r to overwrite the line; pad to clear previous text
    print(f"\r  {C.CYAN}[{bar}]{C.RESET} {pct_str}  {C.DIM}{step}{C.RESET}".ljust(100), end="", flush=True)
    if pct >= 1.0:
        print()  # newline when done


# ── Interactive parameter collection ─────────────────────────────────────────

def ask(prompt: str, default: str) -> str:
    """Prompt user with a default value."""
    result = input(f"  {C.YELLOW}{prompt} [{default}]: {C.RESET}").strip()
    return result if result else default


def collect_params_interactive(args) -> dict:
    """Fill in any missing parameters interactively."""
    print(f"  {C.BOLD}⚙️  Configuration{C.RESET}")
    print(f"  ────────────────────────────────────")

    today = date.today().isoformat()
    start = args.start or ask("Start date (YYYY-MM-DD)", "2022-01-01")
    end   = args.end   or ask("End date   (YYYY-MM-DD)", today)

    interval = args.interval or ask("Interval (monthly / quarterly / yearly)", "monthly")

    cloud = args.cloud if args.cloud is not None else int(ask("Max cloud cover %", "20"))
    radius = args.radius if args.radius is not None else float(ask("Radius in km", "2.5"))
    fps = args.fps if args.fps is not None else int(ask("Playback speed (fps)", "3"))
    show_date = not args.no_date if args.no_date is not None else ask("Show date overlay? (y/n)", "y").lower() in ("y", "yes", "true", "1")
    out_dir = args.output or ask("Output directory", os.path.join(SCRIPT_DIR, "output"))

    print()
    return {
        "start_date": start,
        "end_date": end,
        "interval": interval,
        "cloud_cover_max": int(cloud),
        "radius_km": float(radius),
        "fps": int(fps),
        "show_date": show_date,
        "output_dir": out_dir,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sentinel-cli",
        description="Generate satellite timelapse videos from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python cli.py --place "Palm Jumeirah, Dubai"
  python cli.py --lat 25.1124 --lon 55.139
  python cli.py --place "Las Vegas" --start 2020-01-01 --end 2024-01-01 --interval quarterly
  python cli.py --lat 45.0 --lon 58.5 --radius 5 --interval yearly --cloud 30 --fps 2
  python cli.py --place "Shanghai" --start 2019-01-01 --no-map
        """,
    )
    loc = p.add_argument_group("Location (pick one)")
    loc.add_argument("--place", type=str, help="Search for a place by name (geocoded via Nominatim)")
    loc.add_argument("--lat", type=float, help="Center latitude")
    loc.add_argument("--lon", type=float, help="Center longitude")

    cfg = p.add_argument_group("Configuration (all optional — prompted if omitted)")
    cfg.add_argument("--start", type=str, help="Start date, e.g. 2022-01-01")
    cfg.add_argument("--end", type=str, help="End date, e.g. 2024-06-01 (default: today)")
    cfg.add_argument("--interval", choices=["monthly", "quarterly", "yearly"], help="Capture interval")
    cfg.add_argument("--cloud", type=int, help="Max cloud cover %% (0–100, default: 20)")
    cfg.add_argument("--radius", type=float, help="Area radius in km (default: 2.5)")
    cfg.add_argument("--fps", type=int, help="Playback speed in fps (default: 3)")
    cfg.add_argument("--no-date", action="store_true", default=None, help="Hide the date/year overlay stamp on images")

    out = p.add_argument_group("Output")
    out.add_argument("--output", "-o", type=str, help="Output directory (default: ./output)")
    out.add_argument("--open", action="store_true", help="Open the video file after generation")
    out.add_argument("--no-map", action="store_true", help="Skip the map preview prompt")
    out.add_argument("--yes", "-y", action="store_true", help="Skip all confirmations, use defaults")

    return p


def main():
    banner()
    parser = build_parser()
    args = parser.parse_args()

    # ── Step 1: Resolve location ─────────────────────────────────────────
    if args.place:
        loc = geocode(args.place)
        lat, lon, label = loc["lat"], loc["lon"], loc["name"]
    elif args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
        label = f"{lat}, {lon}"
    else:
        # Interactive: ask the user
        print(f"  {C.BOLD}How do you want to specify the location?{C.RESET}")
        print(f"    {C.CYAN}[1]{C.RESET} Search by place name")
        print(f"    {C.CYAN}[2]{C.RESET} Enter GPS coordinates")
        print()
        choice = input(f"  {C.YELLOW}Choose [1/2]: {C.RESET}").strip()

        if choice == "2":
            lat = float(input(f"  {C.YELLOW}Latitude:  {C.RESET}").strip())
            lon = float(input(f"  {C.YELLOW}Longitude: {C.RESET}").strip())
            label = f"{lat}, {lon}"
        else:
            place = input(f"  {C.YELLOW}Place name: {C.RESET}").strip()
            if not place:
                print(f"  {C.RED}✗ No place name provided.{C.RESET}")
                sys.exit(1)
            loc = geocode(place)
            lat, lon, label = loc["lat"], loc["lon"], loc["name"]

    # Normalize coordinates (handle Leaflet-style wrapping, just in case)
    lon = ((lon + 180) % 360) - 180
    lat = max(-90, min(90, lat))

    # ── Step 2: Collect configuration ────────────────────────────────────
    params = collect_params_interactive(args)

    # ── Step 3: Show map preview ─────────────────────────────────────────
    if not args.no_map and not args.yes:
        show_map_preview(lat, lon, params["radius_km"], label)
    else:
        bbox = compute_bbox(lat, lon, params["radius_km"])
        print(f"  {C.GREEN}📍 {label}{C.RESET}  ({lat:.4f}, {lon:.4f})  radius={params['radius_km']}km")
        print()

    # ── Step 4: Confirm and generate ─────────────────────────────────────
    print(f"  {C.BOLD}🔧 Generation Settings{C.RESET}")
    print(f"  ────────────────────────────────────")
    print(f"  {C.GREEN}Period   :{C.RESET} {params['start_date']}  →  {params['end_date']}")
    print(f"  {C.GREEN}Interval :{C.RESET} {params['interval']}")
    print(f"  {C.GREEN}Cloud max:{C.RESET} {params['cloud_cover_max']}%")
    print(f"  {C.GREEN}Radius   :{C.RESET} {params['radius_km']} km")
    print(f"  {C.GREEN}FPS      :{C.RESET} {params['fps']}")
    print(f"  {C.GREEN}Show Date:{C.RESET} {params['show_date']}")
    print(f"  {C.GREEN}Output   :{C.RESET} {params['output_dir']}")
    print()

    if not args.yes:
        confirm = input(f"  {C.YELLOW}Start generation? [Y/n]: {C.RESET}").strip().lower()
        if confirm not in ("", "y", "yes"):
            print(f"  {C.DIM}Aborted.{C.RESET}")
            sys.exit(0)

    print()
    print(f"  {C.BOLD}🛰️  Generating timelapse...{C.RESET}")
    print()

    generator = TimelapseGenerator(output_dir=params["output_dir"])

    try:
        video_path = generator.generate_timelapse(
            lat=lat,
            lon=lon,
            start_date=params["start_date"],
            end_date=params["end_date"],
            interval=params["interval"],
            cloud_cover_max=params["cloud_cover_max"],
            radius_km=params["radius_km"],
            fps=params["fps"],
            show_date=params["show_date"],
            progress_callback=progress_callback,
        )
    except ValueError as e:
        print(f"\n\n  {C.RED}✗ Generation failed: {e}{C.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n  {C.RED}✗ Unexpected error: {e}{C.RESET}")
        sys.exit(1)

    # ── Step 5: Done ─────────────────────────────────────────────────────
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

    print(f"""
  {C.GREEN}{C.BOLD}✓ Timelapse generated successfully!{C.RESET}

  {C.BOLD}📹 Video:{C.RESET} {video_path}
  {C.BOLD}📦 Size :{C.RESET} {file_size_mb:.1f} MB
""")

    if args.open or (not args.yes and input(f"  {C.YELLOW}Open video? [Y/n]: {C.RESET}").strip().lower() in ("", "y", "yes")):
        if sys.platform == "darwin":
            os.system(f'open "{video_path}"')
        elif sys.platform == "linux":
            os.system(f'xdg-open "{video_path}"')
        else:
            os.system(f'start "" "{video_path}"')


if __name__ == "__main__":
    main()

import os
import uuid
import math
import logging
from datetime import datetime
from collections import defaultdict
from typing import Callable, Tuple, Optional, Dict, Any, List

import numpy as np
import rasterio
import rasterio.warp
import rasterio.windows
from pystac_client import Client
import planetary_computer
from PIL import Image, ImageDraw, ImageFont
import imageio

logger = logging.getLogger(__name__)

class TimelapseGenerator:
    """Generates satellite timelapses using Sentinel-2 imagery via Planetary Computer."""
    
    def __init__(self, output_dir: str = 'output'):
        """
        Initialize the TimelapseGenerator.
        
        Args:
            output_dir (str): Directory where generated videos will be saved.
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_timelapse(
        self,
        lat: float,
        lon: float,
        start_date: str,
        end_date: str,
        interval: str = 'monthly',
        cloud_cover_max: int = 20,
        radius_km: float = 2.5,
        frame_size: Tuple[int, int] = (720, 720),
        fps: int = 3,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """
        Generate a timelapse video from Sentinel-2 satellite imagery.
        
        Args:
            lat: Center latitude.
            lon: Center longitude.
            start_date: Start date (ISO format, e.g., '2021-01-01').
            end_date: End date (ISO format).
            interval: Grouping interval ('monthly', 'quarterly', 'yearly').
            cloud_cover_max: Maximum cloud cover percentage (0-100).
            radius_km: Radius in km for the bounding box.
            frame_size: Output frame dimensions (width, height).
            fps: Frames per second for the output video.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            str: Absolute path to the generated MP4 file.
            
        Raises:
            ValueError: If no valid frames are successfully downloaded.
        """
        def report_progress(step: str, pct: float):
            if progress_callback:
                progress_callback(step, pct)
                
        report_progress("Calculating bounding box", 0.01)
        
        # Normalize longitude to [-180, 180] (Leaflet map wrapping can produce values outside this range)
        lon = ((lon + 180) % 360) - 180
        # Clamp latitude to [-90, 90]
        lat = max(-90, min(90, lat))
        
        # 1. Bounding box
        lat_degree_km = 111.32
        lon_degree_km = 111.32 * math.cos(math.radians(lat))
        
        dlat = radius_km / lat_degree_km
        dlon = radius_km / lon_degree_km
        
        min_lon = lon - dlon
        min_lat = lat - dlat
        max_lon = lon + dlon
        max_lat = lat + dlat
        bbox = [
            max(-180, min_lon), max(-90, min_lat),
            min(180, max_lon), min(90, max_lat)
        ]
        
        report_progress("Querying Planetary Computer STAC endpoint", 0.05)
        
        # 2. STAC query
        catalog = Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace
        )
        
        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime=f"{start_date}/{end_date}",
            query={"eo:cloud_cover": {"lt": cloud_cover_max}}
        )
        
        items = list(search.items())
        if not items:
            raise ValueError("No Sentinel-2 items found matching the criteria.")
            
        report_progress(f"Found {len(items)} raw items, filtering best scenes by {interval}", 0.10)
        
        # 3. Group by period
        grouped_items: Dict[str, List[Any]] = defaultdict(list)
        
        for item in items:
            dt = item.datetime
            if not dt:
                continue
                
            if interval == 'monthly':
                group_key = dt.strftime('%Y-%m')
            elif interval == 'yearly':
                group_key = dt.strftime('%Y')
            elif interval == 'quarterly':
                quarter = (dt.month - 1) // 3 + 1
                group_key = f"{dt.year}-Q{quarter}"
            else:
                group_key = dt.strftime('%Y-%m')
                
            grouped_items[group_key].append(item)
            
        # Select best item per period (lowest cloud cover)
        best_items = []
        for period, period_items in sorted(grouped_items.items()):
            best_item = min(period_items, key=lambda i: i.properties.get("eo:cloud_cover", 100))
            best_items.append((period, best_item))
            
        if not best_items:
            raise ValueError("No items selected after filtering.")
            
        # 4. Download frames
        frames = []
        total_items = len(best_items)
        
        for idx, (period, item) in enumerate(best_items):
            try:
                report_progress(f"Processing frame {idx+1}/{total_items} ({period})", 0.10 + 0.80 * (idx / total_items))
                
                signed_item = planetary_computer.sign(item)
                visual_asset = signed_item.assets.get("visual")
                if not visual_asset:
                    logger.warning(f"No 'visual' asset found for item {item.id}, skipping.")
                    continue
                    
                url = visual_asset.href
                
                with rasterio.open(url) as ds:
                    # Transform EPSG:4326 bbox to native CRS
                    left, bottom, right, top = rasterio.warp.transform_bounds(
                        "EPSG:4326", ds.crs, *bbox
                    )
                    
                    window = rasterio.windows.from_bounds(
                        left, bottom, right, top, transform=ds.transform
                    )
                    
                    # Read the window (shape: 3, H, W)
                    data = ds.read(window=window)
                    
                    if data.size == 0 or 0 in data.shape:
                        logger.warning(f"Empty window read for item {item.id}, skipping.")
                        continue
                        
                    # Transpose to (H, W, 3)
                    data_transposed = np.transpose(data, (1, 2, 0))
                    
                    # Convert to PIL Image
                    img = Image.fromarray(data_transposed)
                    
                    # Resize
                    img = img.resize(frame_size, Image.Resampling.LANCZOS)
                    
                    # Draw date stamp overlay
                    draw = ImageDraw.Draw(img)
                    
                    # Try to use a better font, default to basic if not available
                    try:
                        font = ImageFont.truetype("arial.ttf", 28)
                    except IOError:
                        font = ImageFont.load_default()
                        
                    # Parse date to pretty format
                    dt = item.datetime
                    date_str = dt.strftime("%B %Y")
                    
                    # Get text size for background rectangle
                    if hasattr(font, 'getbbox'):
                        f_left, f_top, f_right, f_bottom = font.getbbox(date_str)
                        text_width = f_right - f_left
                        text_height = f_bottom - f_top
                    else:
                        text_width, text_height = draw.textsize(date_str, font=font)
                        
                    margin = 10
                    rect_x0 = margin
                    rect_y0 = frame_size[1] - text_height - 2 * margin
                    rect_x1 = rect_x0 + text_width + 2 * margin
                    rect_y1 = frame_size[1] - margin
                    
                    # Create transparent overlay for rectangle
                    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
                    overlay_draw = ImageDraw.Draw(overlay)
                    overlay_draw.rectangle(
                        [rect_x0, rect_y0, rect_x1, rect_y1],
                        fill=(0, 0, 0, 180)
                    )
                    
                    img = img.convert('RGBA')
                    img = Image.alpha_composite(img, overlay)
                    
                    draw = ImageDraw.Draw(img)
                    draw.text(
                        (rect_x0 + margin, rect_y0 + margin/2),
                        date_str,
                        font=font,
                        fill=(255, 255, 255, 255)
                    )
                    
                    img = img.convert('RGB')
                    frames.append(np.array(img))
                    
            except Exception as e:
                logger.warning(f"Error processing item {item.id}: {str(e)}")
                continue
                
        if not frames:
            raise ValueError("Zero frames successfully downloaded and processed.")
            
        report_progress("Compiling video", 0.95)
        
        # 5. Compile video
        output_filename = f"timelapse_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.abspath(os.path.join(self.output_dir, output_filename))
        
        writer = imageio.get_writer(output_path, fps=fps, codec='libx264', quality=8)
        for frame in frames:
            writer.append_data(frame)
        writer.close()
        
        report_progress("Complete", 1.0)
        
        return output_path

if __name__ == '__main__':
    import sys
    if '--test' in sys.argv:
        gen = TimelapseGenerator()
        def progress(step, pct):
            print(f'  [{pct*100:.0f}%] {step}')
        path = gen.generate_timelapse(
            lat=25.1124, lon=55.1390,  # Palm Jumeirah, Dubai
            start_date='2023-01-01', end_date='2023-06-30',
            interval='monthly', cloud_cover_max=30,
            progress_callback=progress
        )
        print(f'Video saved to: {path}')

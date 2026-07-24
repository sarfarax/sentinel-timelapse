import os
import uuid
import logging
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from timelapse import TimelapseGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title='Sentinel Timelapse Generator')

# Global dict to track jobs
jobs: Dict[str, Dict[str, Any]] = {}

class TimelapseRequest(BaseModel):
    lat: float
    lon: float
    start_date: str
    end_date: str
    interval: str = 'monthly'
    cloud_cover_max: int = 20
    radius_km: float = 2.5
    fps: int = 3
    show_date: bool = True

def process_timelapse_job(job_id: str, req: TimelapseRequest):
    """Background task to generate the timelapse."""
    jobs[job_id]['status'] = 'processing'
    
    def progress_callback(step: str, pct: float):
        jobs[job_id]['step'] = step
        jobs[job_id]['progress'] = pct
        
    try:
        # Create generator with absolute output dir relative to this file
        current_dir = Path(__file__).parent.resolve()
        output_dir = current_dir / 'output'
        
        generator = TimelapseGenerator(output_dir=str(output_dir))
        
        output_path = generator.generate_timelapse(
            lat=req.lat,
            lon=req.lon,
            start_date=req.start_date,
            end_date=req.end_date,
            interval=req.interval,
            cloud_cover_max=req.cloud_cover_max,
            radius_km=req.radius_km,
            fps=req.fps,
            show_date=req.show_date,
            progress_callback=progress_callback
        )
        
        jobs[job_id]['status'] = 'complete'
        jobs[job_id]['result'] = os.path.basename(output_path)
        jobs[job_id]['progress'] = 1.0
        jobs[job_id]['step'] = 'Done'
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)


@app.post("/api/generate", status_code=202)
async def generate_timelapse(req: TimelapseRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        'id': job_id,
        'status': 'pending',
        'progress': 0.0,
        'step': 'Initializing',
        'result': None,
        'error': None
    }
    
    background_tasks.add_task(process_timelapse_job, job_id, req)
    
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/api/video/{filename}")
async def get_video(filename: str):
    current_dir = Path(__file__).parent.resolve()
    video_path = current_dir / 'output' / filename
    
    if not video_path.exists() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="Video file not found")
        
    return FileResponse(str(video_path), media_type='video/mp4')


# Mount frontend static files
current_dir = Path(__file__).parent.resolve()
frontend_dir = current_dir.parent / 'frontend'

if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    logger.warning(f"Frontend directory not found at {frontend_dir}. Static files will not be served.")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)

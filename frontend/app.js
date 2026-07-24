const state = {
  lat: null,
  lon: null,
  marker: null,
  rectangle: null,
  jobId: null,
  pollInterval: null
};

let map;

document.addEventListener('DOMContentLoaded', () => {
  initMap();
  initDateDefaults();
  initEventListeners();
});

function initMap() {
  // Initialize Leaflet map
  map = L.map('map').setView([20, 0], 3);

  // Use CartoDB Dark Matter tiles
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(map);

  // Handle map clicks
  map.on('click', (e) => {
    setLocation(e.latlng.lat, e.latlng.lng, 'Selected Location');
  });
}

function initDateDefaults() {
  const endInput = document.getElementById('end-date');
  const today = new Date();
  endInput.value = today.toISOString().split('T')[0];
}

function initEventListeners() {
  // Search
  const searchBtn = document.getElementById('search-btn');
  const searchInput = document.getElementById('search-input');
  
  searchBtn.addEventListener('click', performSearch);
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch();
  });

  // Suggestion Chips
  const chips = document.querySelectorAll('.chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const lat = parseFloat(chip.dataset.lat);
      const lon = parseFloat(chip.dataset.lon);
      const label = chip.dataset.label;
      setLocation(lat, lon, label);
    });
  });

  // Range Sliders Live Update
  const cloudSlider = document.getElementById('cloud-cover');
  const cloudVal = document.getElementById('cloud-value');
  cloudSlider.addEventListener('input', (e) => {
    cloudVal.textContent = e.target.value;
  });

  const radiusSlider = document.getElementById('radius');
  const radiusVal = document.getElementById('radius-value');
  radiusSlider.addEventListener('input', (e) => {
    radiusVal.textContent = e.target.value;
    updateRectangle();
  });

  const fpsSlider = document.getElementById('fps');
  const fpsVal = document.getElementById('fps-value');
  fpsSlider.addEventListener('input', (e) => {
    fpsVal.textContent = e.target.value;
  });

  // Action Buttons
  document.getElementById('generate-btn').addEventListener('click', generateTimelapse);
  
  document.getElementById('new-btn').addEventListener('click', () => {
    document.getElementById('result-section').classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  document.getElementById('error-dismiss-btn').addEventListener('click', () => {
    document.getElementById('error-section').classList.add('hidden');
  });
}

async function performSearch() {
  const query = document.getElementById('search-input').value.trim();
  if (!query) return;

  const searchBtn = document.getElementById('search-btn');
  const originalText = searchBtn.textContent;
  searchBtn.textContent = '...';
  searchBtn.disabled = true;

  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`);
    const data = await res.json();
    
    if (data && data.length > 0) {
      setLocation(parseFloat(data[0].lat), parseFloat(data[0].lon), data[0].display_name);
    } else {
      alert('Location not found. Please try a different search term.');
    }
  } catch (error) {
    console.error('Search error:', error);
    alert('Error searching for location.');
  } finally {
    searchBtn.textContent = originalText;
    searchBtn.disabled = false;
  }
}

function setLocation(lat, lon, label = null) {
  state.lat = lat;
  state.lon = lon;

  // Clear previous markers
  if (state.marker) map.removeLayer(state.marker);
  if (state.rectangle) map.removeLayer(state.rectangle);

  // Add new marker
  state.marker = L.marker([lat, lon]).addTo(map);

  // Add rectangle
  updateRectangle();

  // View transition
  map.flyTo([lat, lon], 12, { duration: 1.5 });

  // Update UI
  const displayLabel = label ? `${label} <br/>` : '';
  document.getElementById('coord-display').innerHTML = `${displayLabel}Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}`;
  
  document.getElementById('generate-btn').disabled = false;
}

function updateRectangle() {
  if (!state.lat || !state.lon) return;

  if (state.rectangle) {
    map.removeLayer(state.rectangle);
  }

  // Calculate roughly the bounding box based on radius in km
  // 1 deg latitude ≈ 111 km. 1 deg longitude ≈ 111 * cos(lat) km.
  const radiusKm = parseFloat(document.getElementById('radius').value);
  const latOffset = radiusKm / 111.0;
  const lonOffset = radiusKm / (111.0 * Math.cos(state.lat * (Math.PI / 180)));

  const bounds = [
    [state.lat - latOffset, state.lon - lonOffset],
    [state.lat + latOffset, state.lon + lonOffset]
  ];

  state.rectangle = L.rectangle(bounds, {
    color: '#00d4ff',
    weight: 2,
    fillColor: '#00d4ff',
    fillOpacity: 0.1
  }).addTo(map);
}

async function generateTimelapse() {
  if (!state.lat || !state.lon) return;

  // Gather config
  const config = {
    lat: state.lat,
    lon: state.lon,
    start_date: document.getElementById('start-date').value,
    end_date: document.getElementById('end-date').value,
    interval: document.getElementById('interval').value,
    cloud_cover_max: parseInt(document.getElementById('cloud-cover').value),
    radius_km: parseFloat(document.getElementById('radius').value),
    fps: parseInt(document.getElementById('fps').value)
  };

  // UI Updates
  document.getElementById('generate-btn').disabled = true;
  document.getElementById('result-section').classList.add('hidden');
  document.getElementById('error-section').classList.add('hidden');
  
  const progSec = document.getElementById('progress-section');
  progSec.classList.remove('hidden');
  progSec.classList.add('fade-in');
  
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('progress-percent').textContent = '0%';
  document.getElementById('progress-step').textContent = 'Submitting request...';

  // Scroll to progress
  progSec.scrollIntoView({ behavior: 'smooth' });

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    
    if (!res.ok) throw new Error('API Error');
    const data = await res.json();
    
    state.jobId = data.job_id;
    startPolling();

  } catch (error) {
    showError('Failed to start timelapse generation. Is the backend running?');
  }
}

function startPolling() {
  if (state.pollInterval) clearInterval(state.pollInterval);

  state.pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${state.jobId}`);
      if (!res.ok) throw new Error('Poll Error');
      const data = await res.json();

      const pct = Math.round(data.progress * 100);
      document.getElementById('progress-bar').style.width = `${pct}%`;
      document.getElementById('progress-percent').textContent = `${pct}%`;
      if(data.step) document.getElementById('progress-step').textContent = data.step;

      if (data.status === 'complete') {
        clearInterval(state.pollInterval);
        showResult(data.result);
      } else if (data.status === 'error') {
        clearInterval(state.pollInterval);
        showError(data.error || 'An unknown error occurred during generation.');
      }

    } catch (error) {
      console.error('Polling error:', error);
      // Don't stop polling on single network glitch, but could add retry limit
    }
  }, 1500);
}

function showResult(resultId) {
  document.getElementById('progress-section').classList.add('hidden');
  
  const resSec = document.getElementById('result-section');
  resSec.classList.remove('hidden');
  resSec.classList.add('fade-in');
  
  const videoUrl = `/api/video/${resultId}`;
  document.getElementById('result-video').src = videoUrl;
  document.getElementById('download-btn').href = videoUrl;
  
  document.getElementById('generate-btn').disabled = false;
  resSec.scrollIntoView({ behavior: 'smooth' });
}

function showError(msg) {
  document.getElementById('progress-section').classList.add('hidden');
  
  const errSec = document.getElementById('error-section');
  errSec.classList.remove('hidden');
  errSec.classList.add('fade-in');
  
  document.getElementById('error-message').textContent = msg;
  document.getElementById('generate-btn').disabled = false;
}

let currentGifFrames = null;
let currentGifName = null;
let previewInterval = null;
let currentFrameIndex = 0;
let ledPositions = null;

// Load LED positions on page load
async function loadLedPositions() {
  try {
    const response = await fetch('../jsons/led_positions.json');
    const data = await response.json();
    ledPositions = data.map(([idx, pos]) => pos);
    console.log(`Loaded ${ledPositions.length} LED positions`);
    return true;
  } catch (error) {
    console.error('Error loading LED positions:', error);
    alert('Warning: Could not load LED positions for preview. Please run calibration first.');
    return false;
  }
}

// Initialize canvas size based on LED positions
function initializeCanvas() {
  if (!ledPositions || ledPositions.length === 0) {
    const canvas = document.getElementById('preview-canvas');
    canvas.width = 600;
    canvas.height = 800;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'white';
    ctx.font = '20px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('Run calibration to see preview', canvas.width / 2, canvas.height / 2);
    return;
  }

  const canvas = document.getElementById('preview-canvas');
  const ctx = canvas.getContext('2d');

  // Calculate bounding box
  const xs = ledPositions.map(p => p[0]);
  const ys = ledPositions.map(p => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const padding = 40;
  canvas.width = (maxX - minX) + 2 * padding;
  canvas.height = (maxY - minY) + 2 * padding;

  // Store normalization values
  canvas.dataset.minX = minX;
  canvas.dataset.maxX = maxX;
  canvas.dataset.minY = minY;
  canvas.dataset.maxY = maxY;
  canvas.dataset.padding = padding;

  // Clear canvas
  ctx.fillStyle = 'black';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

// Upload GIF file
async function uploadGif() {
  const fileInput = document.getElementById('gif-upload');
  const file = fileInput.files[0];
  
  if (!file) {
    alert('Please select a GIF file');
    return;
  }

  const formData = new FormData();
  formData.append('gif', file);

  try {
    const response = await fetch('/upload_gif_editor', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    
    if (data.status === 'ok') {
      currentGifName = data.filename;
      alert(`✅ GIF uploaded: ${currentGifName}`);
      // Automatically process with default settings
      applyEffects();
    } else {
      alert('❌ Upload failed: ' + (data.error || data.message));
    }
  } catch (error) {
    alert('❌ Upload error: ' + error.message);
  }
}

// Apply effects and get processed frames
async function applyEffects() {
  if (!currentGifName) {
    alert('Please upload a GIF first');
    return;
  }

  const resolution = parseInt(document.getElementById('resolution').value);
  const brightness = parseInt(document.getElementById('brightness').value);
  const saturation = parseInt(document.getElementById('saturation').value);
  const interpolation = document.getElementById('interpolation').checked;
  const temporalSmooth = document.getElementById('temporal-smooth').checked;

  try {
    const response = await fetch('/process_gif_editor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gif_name: currentGifName,
        resolution: resolution,
        brightness: brightness,
        saturation: saturation,
        use_interpolation: interpolation,
        smooth_temporal: temporalSmooth
      })
    });

    const data = await response.json();
    
    if (data.status === 'ok') {
      currentGifFrames = data.frames;
      document.getElementById('total-frames').textContent = currentGifFrames.length;
      currentFrameIndex = 0;
      renderFrame(0);
      alert(`✅ Processed ${currentGifFrames.length} frames`);
    } else {
      alert('❌ Processing failed: ' + (data.error || data.message));
    }
  } catch (error) {
    alert('❌ Processing error: ' + error.message);
  }
}

// Render a single frame on the canvas
function renderFrame(frameIndex) {
  if (!currentGifFrames) return;

  const canvas = document.getElementById('preview-canvas');
  const ctx = canvas.getContext('2d');
  const frame = currentGifFrames[frameIndex];

  // Clear canvas
  ctx.fillStyle = 'black';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (!ledPositions || ledPositions.length === 0) {
    // No LED positions - just show we have frames
    ctx.fillStyle = 'white';
    ctx.font = '16px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(`Frame ${frameIndex + 1} / ${currentGifFrames.length}`, canvas.width / 2, canvas.height / 2 - 20);
    ctx.fillText('Run calibration to see LED preview', canvas.width / 2, canvas.height / 2 + 20);
    document.getElementById('current-frame').textContent = frameIndex + 1;
    return;
  }

  // Get normalization values
  const minX = parseFloat(canvas.dataset.minX);
  const maxX = parseFloat(canvas.dataset.maxX);
  const minY = parseFloat(canvas.dataset.minY);
  const maxY = parseFloat(canvas.dataset.maxY);
  const padding = parseFloat(canvas.dataset.padding);

  // Draw LEDs
  const dotRadius = 6;
  for (let i = 0; i < Math.min(frame.length, ledPositions.length); i++) {
    const [r, g, b] = frame[i];
    const [x, y] = ledPositions[i];

    // Normalize to canvas coordinates
    const canvasX = ((x - minX) / (maxX - minX)) * (canvas.width - 2 * padding) + padding;
    const canvasY = ((y - minY) / (maxY - minY)) * (canvas.height - 2 * padding) + padding;

    // Draw glow effect
    const gradient = ctx.createRadialGradient(canvasX, canvasY, 0, canvasX, canvasY, dotRadius * 2);
    gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 1)`);
    gradient.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, 0.5)`);
    gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
    
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(canvasX, canvasY, dotRadius * 2, 0, 2 * Math.PI);
    ctx.fill();

    // Draw solid center
    ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
    ctx.beginPath();
    ctx.arc(canvasX, canvasY, dotRadius, 0, 2 * Math.PI);
    ctx.fill();
  }

  document.getElementById('current-frame').textContent = frameIndex + 1;
}

// Play preview animation
function playPreview() {
  if (!currentGifFrames) {
    alert('No processed frames to preview. Upload and process a GIF first.');
    return;
  }

  pausePreview(); // Clear any existing interval

  const fps = parseInt(document.getElementById('preview-fps').value);
  const frameDelay = 1000 / fps;

  previewInterval = setInterval(() => {
    renderFrame(currentFrameIndex);
    currentFrameIndex = (currentFrameIndex + 1) % currentGifFrames.length;
  }, frameDelay);
}

// Pause preview animation
function pausePreview() {
  if (previewInterval) {
    clearInterval(previewInterval);
    previewInterval = null;
  }
}

// Send to ESP
async function sendToESP() {
  if (!currentGifName) {
    alert('No GIF to send. Please upload a GIF first.');
    return;
  }

  if (!currentGifFrames) {
    alert('Please process the GIF first by clicking "Apply Effects"');
    return;
  }

  if (!confirm(`Send ${currentGifFrames.length} frames to the tree?`)) {
    return;
  }

  try {
    const response = await fetch('/send_gif', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gif_name: currentGifName })
    });

    const data = await response.json();
    
    if (data.status === 'ok') {
      alert(`✅ Sent to tree: ${data.frames} frames (${data.size_kb} KB)`);
    } else {
      alert('❌ Send failed: ' + (data.error || data.message));
    }
  } catch (error) {
    alert('❌ Send error: ' + error.message);
  }
}

// Go back to home
function goBack() {
  window.location.href = '/';
}

// Update slider value displays
document.addEventListener('DOMContentLoaded', () => {
  loadLedPositions().then(() => {
    initializeCanvas();
  });

  document.getElementById('resolution').addEventListener('input', (e) => {
    document.getElementById('resolution-value').textContent = e.target.value;
  });

  document.getElementById('brightness').addEventListener('input', (e) => {
    document.getElementById('brightness-value').textContent = e.target.value + '%';
  });

  document.getElementById('saturation').addEventListener('input', (e) => {
    document.getElementById('saturation-value').textContent = e.target.value + '%';
  });
});

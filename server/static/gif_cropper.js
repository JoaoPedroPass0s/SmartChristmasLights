let cropper = null;
let currentGifFrames = [];
let currentFrameIndex = 0;
let previewInterval = null;
let ledPositions = null;

// --- Upload GIF ---
document.getElementById('gif-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Display first frame for cropping
    const url = URL.createObjectURL(file);
    const img = document.getElementById('crop-image');
    img.src = url;
    img.style.display = 'block';

    if (cropper) cropper.destroy();
    cropper = new Cropper(img, {
        viewMode: 1,
        autoCropArea: 1,
    });

    // Upload file to server
    const formData = new FormData();
    formData.append('gif', file);
    const resp = await fetch('/upload_gif_editor', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.status === 'ok') window.currentGifName = data.filename;
});

// --- Apply crop ---
document.getElementById('apply-crop-btn').addEventListener('click', async () => {
    if (!cropper) return alert('Select a crop area first.');

    const cropData = cropper.getData(); // x, y, width, height
    const payload = {
        gif_name: window.currentGifName,
        x: Math.round(cropData.x),
        y: Math.round(cropData.y),
        w: Math.round(cropData.width),
        h: Math.round(cropData.height)
    };

    try {
        const resp = await fetch('/crop_gif', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) throw new Error(resp.statusText);
        const data = await resp.json();
        if (data.status !== 'ok' || !data.output) throw new Error('Invalid server response');

        // Load frames directly from the cropped GIF file
        await loadFramesFromFile(data.output);
    } catch (err) {
        console.error(err);
        alert('Failed to crop/load GIF.');
    }
});

async function loadFramesFromFile(filename) {
    try {
        const resp = await fetch(`/get_frames/${filename}`);
        const data = await resp.json();

        if (!data.frames) throw new Error("No frames returned");

        currentGifFrames = data.frames;
        currentFrameIndex = 0;
        renderFrame(0);
        console.log(`Loaded ${currentGifFrames.length} frames from ${filename}`);
    } catch (err) {
        console.error(err);
        alert("Failed to load frames");
    }
}

// --- Render single frame ---
function renderFrame(idx) {
    console.log('Rendering frame:', idx);

    if (!currentGifFrames || !currentGifFrames[idx]) {
        console.error('Invalid frame data');
        return;
    }

    const canvas = document.getElementById('preview-canvas');
    const ctx = canvas.getContext('2d');
    const frame = currentGifFrames[idx];

    // Clear canvas
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!ledPositions || ledPositions.length === 0) {
        // No LED positions - just show we have frames
        ctx.fillStyle = 'white';
        ctx.font = '16px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`Frame ${idx + 1} / ${currentGifFrames.length}`, canvas.width / 2, canvas.height / 2 - 20);
        ctx.fillText('Run calibration to see LED preview', canvas.width / 2, canvas.height / 2 + 20);
        return;
    }

    // Get normalization values
    const minX = parseFloat(canvas.dataset.minX);
    const maxX = parseFloat(canvas.dataset.maxX);
    const minY = parseFloat(canvas.dataset.minY);
    const maxY = parseFloat(canvas.dataset.maxY);
    const padding = parseFloat(canvas.dataset.padding);

    // Validate normalization values
    if (
        isNaN(minX) || isNaN(maxX) || isNaN(minY) || isNaN(maxY) || isNaN(padding) ||
        maxX === minX || maxY === minY
    ) {
        console.error('Invalid normalization values:', { minX, maxX, minY, maxY, padding });
        return;
    }

    // Draw LEDs
    const dotRadius = 6;
    for (let i = 0; i < Math.min(frame.length, ledPositions.length); i++) {
        const [r, g, b] = frame[i];
        const [x, y] = ledPositions[i];

        // Normalize to canvas coordinates
        const canvasX = ((x - minX) / (maxX - minX)) * (canvas.width - 2 * padding) + padding;
        const canvasY = ((y - minY) / (maxY - minY)) * (canvas.height - 2 * padding) + padding;

        // Validate canvas coordinates
        if (!isFinite(canvasX) || !isFinite(canvasY)) {
            console.error('Invalid canvas coordinates:', { x, y, canvasX, canvasY });
            continue;
        }

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

}

function initializeCanvas() {
    const canvas = document.getElementById('preview-canvas');
    const ctx = canvas.getContext('2d');

    if (!ledPositions || ledPositions.length === 0) {
        console.error('LED positions are empty or invalid.');
        canvas.width = 600;
        canvas.height = 800;
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = 'white';
        ctx.font = '20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Run calibration to see preview', canvas.width / 2, canvas.height / 2);
        // Set default dataset values
        canvas.dataset.minX = 0;
        canvas.dataset.maxX = 1;
        canvas.dataset.minY = 0;
        canvas.dataset.maxY = 1;
        canvas.dataset.padding = 40;
        return;
    }

    // Calculate bounding box
    const xs = ledPositions.map(p => p[0]);
    const ys = ledPositions.map(p => p[1]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    if (
        !isFinite(minX) || !isFinite(maxX) ||
        !isFinite(minY) || !isFinite(maxY)
    ) {
        console.error('Invalid LED position values:', { minX, maxX, minY, maxY });
        return;
    }

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

// --- Play/Pause GIF ---
document.getElementById('play-btn').addEventListener('click', () => {
    if (!currentGifFrames.length) return;
    const fps = parseInt(document.getElementById('fps').value);
    previewInterval = setInterval(() => {
        renderFrame(currentFrameIndex);
        currentFrameIndex = (currentFrameIndex + 1) % currentGifFrames.length;
    }, 1000/fps);
});

document.getElementById('pause-btn').addEventListener('click', () => {
    if (previewInterval) clearInterval(previewInterval);
});

// --- Apply effects ---
document.getElementById('apply-effects-btn').addEventListener('click', async () => {
    if (!window.currentGifName) return;
    const payload = {
        gif_name: window.currentGifName,
        resolution: parseInt(document.getElementById('resolution').value),
        brightness: parseInt(document.getElementById('brightness').value),
        saturation: parseInt(document.getElementById('saturation').value),
        use_interpolation: document.getElementById('interpolation').checked,
        smooth_temporal: document.getElementById('temporal-smooth').checked
    };
    const resp = await fetch('/process_gif_editor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (data.status === 'ok') currentGifFrames = data.frames;
    renderFrame(0);
});

document.getElementById('save-gif-btn').addEventListener('click', async () => {
    if (!window.currentGifName) return alert('No GIF to save.');
    try {
        const resp = await fetch('/save_gif/' + encodeURIComponent(`${window.currentGifName.replace(/\.gif$/i, '')}_cropped.gif`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gif_name: document.getElementById('gif-name').value })
        });
        const data = await resp.json();
        if (data.status === 'ok') {
            alert('✅ GIF saved successfully!');
        } else {
            alert('❌ Save failed: ' + (data.error || data.message));
        }
    } catch (error) {
        alert('❌ Upload error: ' + error.message);
    }
});

// --- Load LED positions ---
async function loadLedPositions() {
    const resp = await fetch('/get_led_positions');
    const data = await resp.json();
    ledPositions = data.map(([idx,pos]) => pos);
}

loadLedPositions().then(() => {
    initializeCanvas();
});

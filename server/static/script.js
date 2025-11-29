

document.addEventListener('DOMContentLoaded', () => {
    
    // --- Page Navigation Handlers ---
    const calibrationBtn = document.getElementById('calibration-btn');
    if(calibrationBtn) {
        calibrationBtn.addEventListener('click', () => {
            window.location.href = '/calibration';
        });
    }

    const editorBtn = document.getElementById('gif-editor-btn');
    if(editorBtn) {
        editorBtn.addEventListener('click', () => {
            window.location.href = '/gif_editor';
        });
    }

    // --- Effects Page Logic ---
    // Check if we are on the effects page by looking for the list container
    const gifListContainer = document.getElementById('gif-list');
    if (gifListContainer) {
        loadGifs();
    }
});

// --- GIF Functions ---

async function loadGifs() {
    const list = document.getElementById('gif-list');
    if (!list) return;

    try {
        const resp = await fetch('/list_gifs');
        const data = await resp.json();
        
        if (data.status === 'ok') {
            list.innerHTML = ''; // Clear loading text
            data.gifs.forEach(gifName => {
                const div = document.createElement('div');
                div.className = 'gif-item';
                div.innerText = gifName;
                div.onclick = () => playGif(gifName);
                list.appendChild(div);
            });
        } else {
            list.innerText = "Error loading GIFs.";
        }
    } catch (e) {
        console.error(e);
        list.innerText = "Connection error.";
    }
}

async function playGif(gifName) {
    // Highlight selected
    document.querySelectorAll('.gif-item').forEach(el => el.classList.remove('selected'));
    event.target.classList.add('selected');

    // Show controls
    const controls = document.getElementById('playback-controls');
    if(controls) controls.style.display = 'block';

    try {
        await fetch('/send_gif', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ gif_name: gifName })
        });
    } catch (e) {
        alert("Failed to send GIF to tree");
    }
}

async function controlGif(action) {
    await fetch('/gif_control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ action: action })
    });
}

async function setGifSpeed() {
    const ms = document.getElementById('gif-speed').value;
    await fetch('/gif_control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ action: 'speed', value: parseInt(ms) })
    });
}

async function loadGifs() {
    const list = document.getElementById('gif-list');
    if (!list) return;

    try {
        const resp = await fetch('/list_gifs');
        const data = await resp.json();
        
        if (data.status === 'ok') {
            list.innerHTML = ''; // Clear loading text
            
            if (data.gifs.length === 0) {
                list.innerText = "No GIFs found.";
                return;
            }

            data.gifs.forEach(gifName => {
                // 1. Create the Card Container
                const card = document.createElement('div');
                card.className = 'effect-card';
                card.onclick = () => playGif(gifName);

                // 2. Create the Image
                const img = document.createElement('img');
                img.src = `/get_gif_image/${gifName}`; // URL to the Python route
                img.alt = gifName;
                img.className = 'effect-thumb';
                img.loading = "lazy"; // Performance optimization

                // 3. Create the Label
                const label = document.createElement('div');
                // remove .gif extension for display
                label.innerText = gifName.replace(/\.gif$/i, '');
                label.className = 'effect-name';

                // 4. Assemble
                card.appendChild(img);
                card.appendChild(label);
                list.appendChild(card);
            });
        } else {
            list.innerText = "Error loading GIFs.";
        }
    } catch (e) {
        console.error(e);
        list.innerText = "Connection error.";
    }
}

async function playGif(gifName) {
    // Highlight selected visually
    // Note: We search for '.effect-card' now, not '.gif-item'
    document.querySelectorAll('.effect-card').forEach(el => el.classList.remove('selected'));
    
    // Find the card that was clicked (it might be the image or label that triggered the event)
    const card = event.target.closest('.effect-card');
    if (card) card.classList.add('selected');

    // Show controls
    const controls = document.getElementById('playback-controls');
    if(controls) controls.style.display = 'block';

    try {
        await fetch('/send_gif', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ gif_name: gifName })
        });
    } catch (e) {
        alert("Failed to send GIF to tree");
    }
}


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

async function loadCombinedEffectsAndGifs() {
    const list = document.getElementById('combined-list');
    if (!list) return;

    try {
        // Fetch both effects and GIFs in parallel
        const [effectsResp, gifsResp] = await Promise.all([
            fetch('/list_effects'),
            fetch('/list_gifs')
        ]);
        
        const effectsData = await effectsResp.json();
        const gifsData = await gifsResp.json();
        
        list.innerHTML = ''; // Clear loading text
        
        let hasItems = false;
        
        // Add code effects
        if (effectsData.status === 'ok' && effectsData.effects.length > 0) {
            hasItems = true;
            effectsData.effects.forEach(effectName => {
                const card = document.createElement('div');
                card.className = 'effect-card';
                card.onclick = () => playEffect(effectName);

                // Use video element for effect previews
                const video = document.createElement('video');
                video.src = `/get_effect_preview/${effectName}`;
                video.alt = effectName;
                video.className = 'effect-thumb';
                video.autoplay = true;
                video.loop = true;
                video.muted = true;
                video.playsInline = true;

                const label = document.createElement('div');
                // Convert snake_case to Title Case
                label.innerText = effectName.split('_').map(word => 
                    word.charAt(0).toUpperCase() + word.slice(1)
                ).join(' ');
                label.className = 'effect-name';

                card.appendChild(video);
                card.appendChild(label);
                list.appendChild(card);
            });
        }
        
        // Add GIFs
        if (gifsData.status === 'ok' && gifsData.gifs.length > 0) {
            hasItems = true;
            gifsData.gifs.forEach(gifName => {
                const card = document.createElement('div');
                card.className = 'effect-card';
                card.onclick = () => playGif(gifName);

                const img = document.createElement('img');
                img.src = `/get_gif_image/${gifName}`;
                img.alt = gifName;
                img.className = 'effect-thumb';
                img.loading = "lazy";

                const label = document.createElement('div');
                label.innerText = gifName.replace(/\.gif$/i, '');
                label.className = 'effect-name';

                card.appendChild(img);
                card.appendChild(label);
                list.appendChild(card);
            });
        }
        
        if (!hasItems) {
            list.innerText = "No effects or GIFs found.";
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

async function playEffect(effectName) {
    // Highlight selected visually
    document.querySelectorAll('.effect-card').forEach(el => el.classList.remove('selected'));
    const card = event.target.closest('.effect-card');
    if (card) card.classList.add('selected');

    // Show controls
    const controls = document.getElementById('playback-controls');
    if(controls) controls.style.display = 'block';
    
    try {
        await fetch('/send_effect', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ effect_name: effectName })
        });
    } catch (e) {
        alert("Failed to send effect to tree");
    }
}

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
    const combinedListContainer = document.getElementById('combined-list');
    if (combinedListContainer) {
        loadCombinedEffectsAndGifs();
    }
});
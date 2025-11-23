

// guard calibration button in case this script is loaded on pages without it
const calibBtn = document.getElementById("calibration-btn");
if (calibBtn) {
  calibBtn.onclick = async () => {
    // Redirect to the calibration page (served as a static file)
    // You can change this to a server route like '/calibration' if you prefer.
    window.location.href = '/static/calibration.html';
  };
}

// Effect selection modal
const chooseEffectBtn = document.getElementById("choose-effect-btn");
const effectModal = document.getElementById("effect-modal");
const closeModal = document.querySelector(".close");

if (chooseEffectBtn && effectModal) {
  chooseEffectBtn.onclick = () => {
    effectModal.style.display = "block";
    loadGifList();
  };
}

if (closeModal && effectModal) {
  closeModal.onclick = () => {
    effectModal.style.display = "none";
  };
  
  window.onclick = (event) => {
    if (event.target == effectModal) {
      effectModal.style.display = "none";
    }
  };
}

// Load available GIFs
async function loadGifList() {
  const gifList = document.getElementById("gif-list");
  gifList.innerHTML = "Loading...";
  
  try {
    const response = await fetch('/list_gifs');
    const data = await response.json();
    
    if (data.status === 'ok' && data.gifs.length > 0) {
      gifList.innerHTML = '';
      data.gifs.forEach(gif => {
        const gifButton = document.createElement('button');
        gifButton.className = 'gif-button';
        gifButton.textContent = gif.replace('.gif', '');
        gifButton.onclick = () => sendGif(gif);
        gifList.appendChild(gifButton);
      });
    } else {
      gifList.innerHTML = 'No GIFs found';
    }
  } catch (error) {
    gifList.innerHTML = 'Error loading GIFs: ' + error.message;
  }
}

// Send GIF to ESP
async function sendGif(gifName) {
  const gifList = document.getElementById("gif-list");
  const originalContent = gifList.innerHTML;
  gifList.innerHTML = `Sending ${gifName}...`;
  
  try {
    const response = await fetch('/send_gif', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ gif_name: gifName })
    });
    
    const data = await response.json();
    
    if (data.status === 'ok') {
      alert(`✅ GIF "${gifName}" loaded!\n${data.frames} frames, ${data.size_kb} KB`);
      document.getElementById('playback-controls').style.display = 'block';
    } else {
      alert('❌ Error: ' + data.error);
    }
  } catch (error) {
    alert('❌ Error sending GIF: ' + error.message);
  } finally {
    gifList.innerHTML = originalContent;
    loadGifList(); // Reload the list
  }
}

// Control GIF playback
async function controlGif(action) {
  try {
    const response = await fetch('/gif_control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action: action })
    });
    
    const data = await response.json();
    console.log(`GIF ${action}:`, data);
  } catch (error) {
    console.error('Error controlling GIF:', error);
  }
}

// Set GIF speed
async function setGifSpeed() {
  const speed = document.getElementById('gif-speed').value;
  
  try {
    const response = await fetch('/gif_control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        action: 'speed',
        value: parseInt(speed)
      })
    });
    
    const data = await response.json();
    console.log('Speed set:', data);
  } catch (error) {
    console.error('Error setting speed:', error);
  }
}


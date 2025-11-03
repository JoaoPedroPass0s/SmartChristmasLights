let currentLed = 0;

async function send_led_mapping() {
  await fetch(`/send_led_mapping`);
}

// guard calibration button in case this script is loaded on pages without it
const calibBtn = document.getElementById("calibration-btn");
if (calibBtn) {
  calibBtn.onclick = async () => {
    // Redirect to the calibration page (served as a static file)
    // You can change this to a server route like '/calibration' if you prefer.
    window.location.href = '/static/calibration.html';
  };
}


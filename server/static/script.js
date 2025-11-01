let currentLed = 0;

async function send_led_mapping() {
  await fetch(`/send_led_mapping`);
}

document.getElementById("calibration-btn").onclick = async () => {
  // Redirect to the calibration page (served as a static file)
  // You can change this to a server route like '/calibration' if you prefer.
  window.location.href = '/static/calibration.html';
};

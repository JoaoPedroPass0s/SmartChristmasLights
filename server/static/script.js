let currentLed = 0;

async function lightLED(index) {
  await fetch(`/set_led/${index}`);
  document.getElementById("led-num").innerText = index;
}

document.getElementById("next-btn").onclick = async () => {
  currentLed++;
  await lightLED(currentLed);
};

document.getElementById("send-btn").onclick = async () => {
  const file = document.getElementById("photo-input").files[0];
  if (!file) return alert("Please take a photo first!");
  const formData = new FormData();
  formData.append("photo", file);
  formData.append("led", currentLed);
  const res = await fetch("/upload_photo", { method: "POST", body: formData });
  const data = await res.json();
  console.log(data);
  alert("Photo processed: " + JSON.stringify(data.pos));
};

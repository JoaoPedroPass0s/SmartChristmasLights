if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert("Camera API not supported. Please use a modern browser and HTTPS.");
} else {
    startCamera();
}

let mediaRecorder;
let chunks = [];

async function startCamera() {
    try {
    const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false
    });
    const video = document.getElementById("preview");
    video.srcObject = stream;
    await video.play();

    // Enable the record button after camera starts
        // Enable the record button after camera starts (guard element existence)
        const recordBtnEl = document.getElementById("record-btn");
        if (recordBtnEl) recordBtnEl.disabled = false;

    mediaRecorder = new MediaRecorder(stream, { mimeType: "video/webm" });
    mediaRecorder.ondataavailable = e => chunks.push(e.data);
    mediaRecorder.onstop = async () => {
        const blob = new Blob(chunks, { type: "video/webm" });
        chunks = [];
        const formData = new FormData();
        formData.append("video", blob, "calibration.webm");

        try {
        const res = await fetch("/upload_video", { method: "POST", body: formData });
        if (res.ok) {
            alert("Video uploaded!");
            window.location.href = '/';
        } else {
            const text = await res.text();
            alert("Upload failed: " + res.status + " " + text);
        }
        } catch (err) {
        alert("Upload error: " + err);
        }
    };
    } catch (err) {
    alert("Camera error: " + err.name + " - " + err.message);
    }
}

// Optional "enable camera" button: guard in case the markup doesn't include it
const enableBtnEl = document.getElementById("enable-camera-btn");
if (enableBtnEl) {
    enableBtnEl.onclick = () => {
        startCamera();
        // Disable the enable button after click
        enableBtnEl.disabled = true;
    };
}

// Record button: ensure media is available before starting
const recordBtn = document.getElementById("record-btn");
if (recordBtn) {
    recordBtn.onclick = async () => {
        if (!mediaRecorder) {
            await startCamera();
        }
        try {
            await fetch('/send_led_mapping');
        } catch (err) {
            console.warn('send_led_mapping failed', err);
        }

        chunks = [];
        if (mediaRecorder) mediaRecorder.start();
        recordBtn.disabled = true;
        const stopBtnEl = document.getElementById("stop-btn");
        if (stopBtnEl) stopBtnEl.disabled = false;
    };
}

// Stop button: guard existence and recorder state
const stopBtn = document.getElementById("stop-btn");
if (stopBtn) {
    stopBtn.onclick = () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        if (recordBtn) recordBtn.disabled = false;
        stopBtn.disabled = true;
    };
}
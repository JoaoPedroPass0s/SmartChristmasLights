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
    document.getElementById("record-btn").disabled = false;

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

document.getElementById("enable-camera-btn").onclick = () => {
    startCamera();
    // Disable the enable button after click
    document.getElementById("enable-camera-btn").disabled = true;
};

document.getElementById("record-btn").onclick = async () => {
    try {
    await fetch('/send_led_mapping');
    } catch (err) {
    console.warn('send_led_mapping failed', err);
    }

    chunks = [];
    mediaRecorder.start();
    document.getElementById("record-btn").disabled = true;
    document.getElementById("stop-btn").disabled = false;
};

document.getElementById("stop-btn").onclick = () => {
    mediaRecorder.stop();
    document.getElementById("record-btn").disabled = false;
    document.getElementById("stop-btn").disabled = true;
};
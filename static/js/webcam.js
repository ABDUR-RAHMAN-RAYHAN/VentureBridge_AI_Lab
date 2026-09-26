(function () {
  var stream = null;
  var video, canvas, ctx;
  var captured = { 1: null, 2: null, 3: null };
  var POSES = {
    1: "Live Photo 1 of 3 — Look straight ahead (front-facing)",
    2: "Live Photo 2 of 3 — Turn your head slightly to the LEFT",
    3: "Live Photo 3 of 3 — Turn your head slightly to the RIGHT",
  };

  function updateInstruction() {
    var el = document.getElementById("poseInstruction");
    if (!el) return;
    var nextSlot = [1, 2, 3].find(function (s) { return !captured[s]; });
    if (nextSlot) {
      el.textContent = POSES[nextSlot];
    } else {
      el.textContent = "All 3 live photos captured ✓ — you can retake any of them, or just Save Profile below.";
    }
  }

  async function startCamera() {
    var statusEl = document.getElementById("camStatus");
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      video = document.getElementById("camVideo");
      video.srcObject = stream;
      await video.play();
      document.getElementById("camStartBtn").style.display = "none";
      document.getElementById("camLiveArea").style.display = "block";
      if (statusEl) statusEl.textContent = "Camera live.";
      updateInstruction();
    } catch (err) {
      if (statusEl) statusEl.textContent = "Could not access camera: " + err.message +
        ". Please allow camera permission — live photo capture is required for verification.";
    }
  }

  function capturePhoto(slot) {
    if (!video) return;
    canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    var dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    captured[slot] = dataUrl;

    var img = document.getElementById("preview" + slot);
    img.src = dataUrl;
    img.style.display = "block";
    document.getElementById("placeholder" + slot).style.display = "none";
    document.getElementById("photo_" + slot).value = dataUrl;

    updateInstruction();
  }

  function retake(slot) {
    captured[slot] = null;
    document.getElementById("photo_" + slot).value = "";
    document.getElementById("preview" + slot).style.display = "none";
    document.getElementById("placeholder" + slot).style.display = "flex";
    updateInstruction();
  }

  window.vbWebcam = { startCamera: startCamera, capturePhoto: capturePhoto, retake: retake };
})();

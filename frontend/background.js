chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "ASK_BACKEND") {
    (async () => {
      try {
        const urlObj = new URL(msg.videoUrl);
        const videoId = urlObj.searchParams.get("v");

        const res = await fetch(`http://127.0.0.1:8000/ask?video_id=${encodeURIComponent(videoId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: msg.question
          })
        });
        const data = await res.json();
        sendResponse({ 
          ok: res.ok,
          status: res.status,
          data,
          error: data.error || data.detail });
      } catch (err) {
        sendResponse({ ok: false, status: 0, error: err.message });
      }
    })();
    return true;
  }
});

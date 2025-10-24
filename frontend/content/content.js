const PANEL_ID = "yt-extension-sidepanel";

function isWatchPage(url = location.href) {
  try {
    const u = new URL(url);
    return u.hostname === "www.youtube.com" && u.pathname === "/watch";
  } catch {
    return false;
  }
}

function addPanel() {
  if (document.getElementById(PANEL_ID)) return;

  const sidePanel = document.createElement("div");
  sidePanel.id = PANEL_ID;
  sidePanel.innerHTML = `
    <div id="chat-header">
      <span>YouTube Chatbot</span>
      <button id="close-btn">&#10005;</button>
    </div>
    <div id="chat-messages"></div>
    <div id="chat-input">
      <input id="msg-box" type="text" placeholder="Ask about this video..." />
      <button id="send-btn">Send</button>
    </div>
  `;
  document.body.appendChild(sidePanel);

  // Event listeners
  sidePanel.querySelector("#close-btn").onclick = () => sidePanel.remove();

  sidePanel.querySelector("#send-btn").onclick = async () => {
    const input = sidePanel.querySelector("#msg-box");
    const question = input.value.trim();
    if (!question) return;
    input.value = "";

    addMessage("user", question);

    const videoUrl = location.href;
    const resp = await chrome.runtime.sendMessage({
      type: "ASK_BACKEND",
      question,
      videoUrl
    });

    if (resp?.ok) {
      addMessage("bot", resp.data.answer || "No answer");
    } else if (resp?.status === 429) {
      addMessage("bot", "⚠️ Too many requests. Please wait for an hour before trying again.");
    } else if (resp?.status === 404) {
      addMessage("bot", "This video doesn’t have English subtitles. Please try another video.");
    } else if (resp?.status === 403) {
      addMessage("bot", "Captions are disabled for this video.");
    } else {
      addMessage("bot", "Error: " + (resp?.error ?? "Unknown error"));
    }
  };

  function addMessage(role, text) {
    const chat = sidePanel.querySelector("#chat-messages");
    const msg = document.createElement("div");
    msg.className = `msg ${role}`;
    msg.textContent = text;
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
  }
}

function removePanel() {
  const el = document.getElementById(PANEL_ID);
  if (el) el.remove();
}

function syncPanelToUrl() {
  if (isWatchPage()) addPanel();
  else removePanel();
}

// Initial run
syncPanelToUrl();

// Watch for navigation
let lastUrl = location.href;
const urlObserver = new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    syncPanelToUrl();
  }
});
urlObserver.observe(document, { subtree: true, childList: true });

// Handle fullscreen
document.addEventListener("fullscreenchange", () => {
  const panel = document.getElementById(PANEL_ID);
  if (!panel) return;
  const isFs = !!document.fullscreenElement;
  panel.style.display = isFs ? "none" : "flex";
});
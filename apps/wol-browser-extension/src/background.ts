import { JwApiClient } from "./api";

const api = new JwApiClient();

async function pollHealth(): Promise<void> {
  const ok = await api.healthOrNull();
  if (typeof chrome === "undefined" || !chrome.action) return;
  if (ok) {
    chrome.action.setBadgeText({ text: "" });
    chrome.action.setTitle({ title: "JW Toolkit — connected" });
  } else {
    chrome.action.setBadgeText({ text: "off" });
    chrome.action.setBadgeBackgroundColor({ color: "#9ca3af" });
    chrome.action.setTitle({
      title: "JW Toolkit not running. Run `jw mcp serve`.",
    });
  }
}

chrome.runtime.onInstalled.addListener(() => {
  void pollHealth();
});

// On every tab update to a wol.jw.org page, re-check health (cheap, local).
chrome.tabs?.onUpdated.addListener((_id, info, tab) => {
  if (info.status === "complete" && tab.url?.startsWith("https://wol.jw.org/")) {
    void pollHealth();
  }
});

// Surface a manual health refresh for the popup.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.kind === "health") {
    api.healthOrNull().then((v) => sendResponse({ ok: !!v }));
    return true; // keep channel open for async response
  }
  return false;
});

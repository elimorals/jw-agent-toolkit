const API = "http://127.0.0.1:8765";
let sessionId = null;
let pollHandle = null;

const $image = document.getElementById("media-image");
const $video = document.getElementById("media-video");
const $placeholder = document.getElementById("placeholder");
const $position = document.getElementById("position");
const $title = document.getElementById("title-display");
const $playPause = document.getElementById("play-pause");

function startSession(language, year, week, kind) {
  return fetch(
    `${API}/presenter/sessions?language=${language}&year=${year}&week=${week}&kind=${kind}`,
    { method: "POST" }
  )
    .then((r) => r.json())
    .then((data) => {
      if (data.error) throw new Error(data.error);
      sessionId = data.session_id;
      startPolling();
    });
}

function startPolling() {
  pollHandle = setInterval(refreshState, 800);
  refreshState();
}

async function refreshState() {
  if (!sessionId) return;
  const resp = await fetch(`${API}/presenter/sessions/${sessionId}/state`);
  const state = await resp.json();
  if (state.error) return;
  render(state);
}

function render(state) {
  const item = state.queue[state.cursor];
  if (!item) {
    $placeholder.hidden = false;
    $image.hidden = true;
    $video.hidden = true;
    return;
  }
  $placeholder.hidden = true;
  $position.textContent = `${state.cursor + 1} / ${state.queue.length}`;
  $title.textContent = item.title;
  $playPause.textContent = state.playing ? "⏸" : "⏵";

  const firstMedia = (item.media_refs || [])[0];
  if (!firstMedia) {
    $image.hidden = true;
    $video.hidden = true;
    return;
  }
  if (firstMedia.kind === "image") {
    $image.src = firstMedia.local_path
      ? `file://${firstMedia.local_path}`
      : firstMedia.url;
    $image.hidden = false;
    $video.hidden = true;
  } else if (firstMedia.kind === "video") {
    $video.src = firstMedia.local_path
      ? `file://${firstMedia.local_path}`
      : firstMedia.url;
    $video.hidden = false;
    $image.hidden = true;
    if (state.playing) $video.play().catch(() => {});
    else $video.pause();
  }
}

document.getElementById("prev").onclick = () =>
  fetch(`${API}/presenter/sessions/${sessionId}/prev`, { method: "POST" });
document.getElementById("next").onclick = () =>
  fetch(`${API}/presenter/sessions/${sessionId}/next`, { method: "POST" });
document.getElementById("play-pause").onclick = () => {
  const action = $playPause.textContent === "⏸" ? "pause" : "play";
  fetch(`${API}/presenter/sessions/${sessionId}/${action}`, { method: "POST" });
};
document.getElementById("stop").onclick = () =>
  fetch(`${API}/presenter/sessions/${sessionId}/stop`, { method: "POST" });

document.addEventListener("keydown", (e) => {
  if (!sessionId) return;
  if (e.key === " ") document.getElementById("play-pause").click();
  if (e.key === "ArrowRight") document.getElementById("next").click();
  if (e.key === "ArrowLeft") document.getElementById("prev").click();
  if (e.key === "Escape") document.getElementById("stop").click();
});

const params = new URLSearchParams(location.search);
const lang = params.get("language");
const year = parseInt(params.get("year"));
const week = parseInt(params.get("week"));
const kind = params.get("kind") || "midweek";
if (lang && year && week) {
  startSession(lang, year, week, kind).catch((err) => {
    $placeholder.textContent = `Error: ${err.message}`;
  });
}

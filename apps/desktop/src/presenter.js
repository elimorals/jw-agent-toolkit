const API = "http://127.0.0.1:8765";
let sessionId = null;
let pollHandle = null;

const $image = document.getElementById("media-image");
const $video = document.getElementById("media-video");
const $placeholder = document.getElementById("placeholder");
const $position = document.getElementById("position");
const $title = document.getElementById("title-display");
const $playPause = document.getElementById("play-pause");
const $queueList = document.getElementById("queue-list");
const $dropzone = document.getElementById("dropzone");

// Hash used to skip full DOM rebuild when only the cursor moves.
let lastQueueHash = "";

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
  renderQueue(state);
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
  if (firstMedia.kind === "image" || firstMedia.kind === "external_file") {
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

// ── Queue sidebar rendering + drag-and-drop ────────────────────────────

function renderQueue(state) {
  const items = state.queue || [];
  const hash =
    JSON.stringify(items.map((i) => i.item_id)) + "#" + state.cursor;
  if (hash === lastQueueHash) {
    // Items + cursor identical → nothing to redraw.
    return;
  }
  // If only the cursor moved (same items list), just retoggle .active.
  const prevIdsPart = lastQueueHash.split("#")[0];
  const newIdsPart = JSON.stringify(items.map((i) => i.item_id));
  if (prevIdsPart === newIdsPart) {
    [...$queueList.children].forEach((li, i) => {
      li.classList.toggle("active", i === state.cursor);
    });
    lastQueueHash = hash;
    return;
  }

  lastQueueHash = hash;
  $queueList.innerHTML = "";
  items.forEach((item, i) => {
    const li = document.createElement("li");
    li.textContent = `${i + 1}. ${item.title}`;
    li.draggable = true;
    li.dataset.index = String(i);
    if (i === state.cursor) li.classList.add("active");

    li.addEventListener("click", () => jumpTo(i));
    li.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", String(i));
      e.dataTransfer.effectAllowed = "move";
    });
    li.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      li.classList.add("drag-over");
    });
    li.addEventListener("dragleave", () => li.classList.remove("drag-over"));
    li.addEventListener("drop", async (e) => {
      e.preventDefault();
      li.classList.remove("drag-over");
      const fromIdx = parseInt(e.dataTransfer.getData("text/plain"), 10);
      const toIdx = parseInt(li.dataset.index, 10);
      if (Number.isFinite(fromIdx) && Number.isFinite(toIdx) && fromIdx !== toIdx) {
        await reorderQueue(fromIdx, toIdx);
        await refreshState();
      }
    });
    $queueList.appendChild(li);
  });
}

async function jumpTo(index) {
  if (!sessionId) return;
  await fetch(`${API}/presenter/sessions/${sessionId}/jump?index=${index}`, {
    method: "POST",
  });
  await refreshState();
}

async function reorderQueue(from, to) {
  if (!sessionId) return;
  await fetch(`${API}/presenter/sessions/${sessionId}/reorder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_index: from, to_index: to }),
  });
}

function inferKind(file) {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("audio/")) return "audio";
  return "external_file";
}

async function addLocalFile(file) {
  if (!sessionId) return;
  const kind = inferKind(file);
  // Tauri 2 fills File.path with the absolute FS path on drag-drop.
  // In a plain browser, fall back to file.name (best effort).
  const localPath = file.path || file.name;
  await fetch(`${API}/presenter/sessions/${sessionId}/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: file.name,
      local_path: localPath,
      kind,
    }),
  });
}

// Dropzone — external files (drag-drop from OS file manager).
$dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
  $dropzone.classList.add("drag-over");
});
$dropzone.addEventListener("dragleave", () => {
  $dropzone.classList.remove("drag-over");
});
$dropzone.addEventListener("drop", async (e) => {
  e.preventDefault();
  $dropzone.classList.remove("drag-over");
  const files = Array.from(e.dataTransfer.files || []);
  for (const file of files) {
    await addLocalFile(file);
  }
  if (files.length) await refreshState();
});

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

// ── External monitor selector (F57.15) ────────────────────────────────
// Uses Tauri 2.x custom commands list_monitors + move_presenter_to_monitor
// declared in src-tauri/src/main.rs. When not running inside Tauri (e.g.
// `vite dev` preview), the selector is hidden so the UI degrades cleanly.

const tauriInvoke =
  (typeof window !== "undefined" &&
    window.__TAURI__ &&
    window.__TAURI__.core &&
    window.__TAURI__.core.invoke) ||
  null;

async function refreshMonitorList() {
  if (!tauriInvoke) return;
  const list = document.getElementById("monitor-list");
  list.innerHTML = "";
  try {
    const monitors = await tauriInvoke("list_monitors");
    if (!monitors || monitors.length === 0) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "Sin monitores detectados";
      list.appendChild(li);
      return;
    }
    for (const m of monitors) {
      const li = document.createElement("li");
      li.textContent = `${m.name} ${m.width}×${m.height}`;
      if (m.is_primary) li.classList.add("primary");
      li.addEventListener("click", async () => {
        const fullscreen = document.getElementById("fullscreen-checkbox")
          .checked;
        try {
          await tauriInvoke("move_presenter_to_monitor", {
            monitorName: m.name,
            fullscreen,
          });
          document.getElementById("monitor-menu").hidden = true;
        } catch (err) {
          console.error("move_presenter_to_monitor failed", err);
        }
      });
      list.appendChild(li);
    }
  } catch (err) {
    console.error("list_monitors failed", err);
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "Error al listar monitores";
    list.appendChild(li);
  }
}

const $monitorBtn = document.getElementById("open-monitor-menu");
if ($monitorBtn) {
  $monitorBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const menu = document.getElementById("monitor-menu");
    if (menu.hidden) {
      await refreshMonitorList();
      menu.hidden = false;
    } else {
      menu.hidden = true;
    }
  });
}

document.addEventListener("click", (e) => {
  const menu = document.getElementById("monitor-menu");
  const selector = document.getElementById("monitor-selector");
  if (!menu || !selector) return;
  if (!menu.hidden && !selector.contains(e.target)) menu.hidden = true;
});

// Hide selector entirely if not running in Tauri (e.g. dev preview).
if (!tauriInvoke) {
  const sel = document.getElementById("monitor-selector");
  if (sel) sel.style.display = "none";
}

document.addEventListener("keydown", (e) => {
  if (!sessionId) return;
  // Don't hijack space/arrows when typing in inputs (none today, but futureproof).
  if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) {
    return;
  }
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

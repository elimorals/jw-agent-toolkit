// Frontend stub — Tauri webview falls back to the iframe in index.html.
// When the REST API isn't reachable, hint the user to start it.
window.addEventListener("DOMContentLoaded", async () => {
  try {
    const r = await fetch("http://127.0.0.1:8765/healthz", { mode: "cors" });
    if (!r.ok) throw new Error("non-200");
  } catch {
    // Build the error panel via safe DOM methods (no innerHTML, no XSS surface).
    while (document.body.firstChild) {
      document.body.removeChild(document.body.firstChild);
    }
    const wrap = document.createElement("div");
    wrap.style.padding = "2rem";
    wrap.style.fontFamily = "sans-serif";
    const h = document.createElement("h2");
    h.textContent = "Backend not running";
    const p = document.createElement("p");
    p.textContent = "Start ";
    const code = document.createElement("code");
    code.textContent = "uvicorn jw_mcp.rest_api:app --port 8765";
    p.appendChild(code);
    p.appendChild(document.createTextNode(" and reload."));
    wrap.appendChild(h);
    wrap.appendChild(p);
    document.body.appendChild(wrap);
  }
});

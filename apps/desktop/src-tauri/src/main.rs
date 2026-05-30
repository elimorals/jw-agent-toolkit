// jw-agent-toolkit Tauri shell.
// On startup we attempt to spawn the Python REST API as a sidecar so the
// dashboard at /dashboard becomes reachable. In production builds the
// `python` binary should be packaged alongside (e.g. via PyInstaller).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use tauri_plugin_shell::ShellExt;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let shell = app.shell();
            // Best-effort spawn of the REST API. Failures are non-fatal —
            // the iframe will report "Backend not running" if it can't
            // reach localhost:8765.
            let _ = shell
                .command("uvicorn")
                .args([
                    "jw_mcp.rest_api:app",
                    "--host", "127.0.0.1",
                    "--port", "8765",
                    "--log-level", "warning",
                ])
                .spawn();
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running jw-toolkit");
}

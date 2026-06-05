// jw-agent-toolkit Tauri shell.
// On startup we attempt to spawn the Python REST API as a sidecar so the
// dashboard at /dashboard becomes reachable. In production builds the
// `python` binary should be packaged alongside (e.g. via PyInstaller).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use tauri_plugin_shell::ShellExt;

/// Serializable shape of a connected monitor, exposed to the presenter UI
/// so the operator can pick a target (e.g. an external projector in the
/// Kingdom Hall) and move the presenter window there.
#[derive(serde::Serialize)]
struct MonitorInfo {
    name: String,
    width: u32,
    height: u32,
    x: i32,
    y: i32,
    scale: f64,
    is_primary: bool,
}

/// Enumerate every monitor Tauri reports as connected. Falls back to an
/// empty vector when the host returns no monitor (rare; e.g. headless CI),
/// in which case the UI hides the selector instead of erroring.
#[tauri::command]
fn list_monitors(app: tauri::AppHandle) -> Result<Vec<MonitorInfo>, String> {
    let primary = app.primary_monitor().map_err(|e| e.to_string())?;
    let primary_name = primary
        .as_ref()
        .and_then(|m| m.name().cloned())
        .unwrap_or_default();
    let monitors = app.available_monitors().map_err(|e| e.to_string())?;
    Ok(monitors
        .iter()
        .map(|m| {
            let name = m
                .name()
                .cloned()
                .unwrap_or_else(|| "(unnamed)".to_string());
            let size = m.size();
            let pos = m.position();
            MonitorInfo {
                is_primary: name == primary_name,
                name,
                width: size.width,
                height: size.height,
                x: pos.x,
                y: pos.y,
                scale: m.scale_factor(),
            }
        })
        .collect())
}

/// Move the `presenter` window onto the monitor identified by `monitor_name`
/// and optionally enter fullscreen. We nudge the position by +10/+10 inside
/// the target's frame so the window is guaranteed to land on the right screen
/// even on multi-monitor layouts where the origin pixel is on a neighbour.
#[tauri::command]
fn move_presenter_to_monitor(
    app: tauri::AppHandle,
    monitor_name: String,
    fullscreen: bool,
) -> Result<(), String> {
    let win = app
        .get_webview_window("presenter")
        .ok_or_else(|| "presenter window not found".to_string())?;
    let monitors = app.available_monitors().map_err(|e| e.to_string())?;
    let target = monitors
        .iter()
        .find(|m| {
            m.name()
                .cloned()
                .unwrap_or_default()
                == monitor_name
        })
        .ok_or_else(|| "monitor not found".to_string())?;
    // Exit fullscreen first; resizing/moving while fullscreen is a no-op
    // on most platforms.
    win.set_fullscreen(false).map_err(|e| e.to_string())?;
    let pos = target.position();
    win.set_position(tauri::PhysicalPosition {
        x: pos.x + 10,
        y: pos.y + 10,
    })
    .map_err(|e| e.to_string())?;
    win.show().map_err(|e| e.to_string())?;
    win.set_fullscreen(fullscreen).map_err(|e| e.to_string())?;
    win.set_focus().map_err(|e| e.to_string())?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            list_monitors,
            move_presenter_to_monitor
        ])
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

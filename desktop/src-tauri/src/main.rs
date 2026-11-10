// ThermoGar desktop shell.
//
// This replaces exactly one step of packaging/launcher.pyw: the call to
// os.startfile() that handed the user a browser tab. Everything else stays
// where it was. The launcher still owns the run lock, the run record, the child
// process, the job object and the health probes, and this binary does not
// duplicate any of it.
//
// Two supervisors over one child process would be two sources of truth about
// whether ThermoGar is running. The launcher already proves that carefully, so
// this shell only reads what the launcher publishes and shows it in a window.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use tauri::{RunEvent, WebviewUrl, WebviewWindowBuilder};

/// The launcher publishes its settled UI port in run.json, under
/// %LOCALAPPDATA%\ThermoGar\runtime\. Key names come from RUN_KEYS in
/// packaging/launcher.pyw and must stay in sync with it.
const RECORD_RELATIVE: &str = r"ThermoGar\runtime\run.json";

/// The launcher budgets UI_DISCOVERY_SECONDS = 240 s to find and prove the port.
/// Wait past that so a slow first start is reported by the launcher, not by us.
const PORT_WAIT_SECONDS: f64 = 260.0;

/// The launcher this shell started, if any. Shared rather than reached through
/// tauri::State: a State guard borrows the app handle, and holding one across a
/// thread or an event callback outlives the handle it borrows from.
type ChildSlot = Arc<Mutex<Option<Child>>>;

fn install_root() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| PathBuf::from("."))
}

fn record_path() -> Option<PathBuf> {
    let local = std::env::var_os("LOCALAPPDATA")?;
    Some(PathBuf::from(local).join(RECORD_RELATIVE))
}

/// Minimal read of the ui_port field. run.json is written atomically by the
/// launcher (temp file + MoveFileExW), so a partial read is not a hazard; a
/// missing or malformed file simply means "not published yet".
fn read_ui_port() -> Option<u16> {
    let path = record_path()?;
    let text = std::fs::read_to_string(path).ok()?;
    let key = "\"ui_port\"";
    let start = text.find(key)? + key.len();
    let rest = &text[start..];
    let colon = rest.find(':')?;
    let digits: String = rest[colon + 1..]
        .chars()
        .skip_while(|c| c.is_whitespace())
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse::<u16>().ok()
}

/// Ask the app itself whether the page is ready. A TCP connect is not enough:
/// Streamlit listens long before ThermoGar_app.py has finished its first run,
/// and a window opened at that moment shows a blank page for 20-60 s.
fn script_ready(port: u16) -> bool {
    let mut stream = match TcpStream::connect(("127.0.0.1", port)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(5)));
    let request = format!(
        "GET /_stcore/script-health-check HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        port
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    response.starts_with("HTTP/1.1 200") || response.starts_with("HTTP/1.0 200")
}

fn start_launcher(root: &Path) -> std::io::Result<Child> {
    Command::new(root.join("runtime").join("pythonw.exe"))
        .arg(root.join("launcher.pyw"))
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
}

fn wait_for_ui() -> Option<u16> {
    let deadline = Instant::now() + Duration::from_secs_f64(PORT_WAIT_SECONDS);
    while Instant::now() < deadline {
        if let Some(port) = read_ui_port() {
            if script_ready(port) {
                return Some(port);
            }
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    None
}

fn open_window(handle: &tauri::AppHandle, port: Option<u16>) {
    let builder = match port {
        Some(p) => {
            let url = format!("http://127.0.0.1:{}/", p);
            WebviewWindowBuilder::new(
                handle,
                "main",
                WebviewUrl::External(url.parse().expect("valid local URL")),
            )
            .inner_size(1440.0, 900.0)
            .min_inner_size(1024.0, 700.0)
        }
        None => WebviewWindowBuilder::new(handle, "main", WebviewUrl::App("error.html".into()))
            .inner_size(760.0, 420.0),
    };
    let _ = builder.title("ThermoGar").center().build();
}

fn main() {
    let root = install_root();
    let slot: ChildSlot = Arc::new(Mutex::new(None));

    let slot_for_setup = Arc::clone(&slot);
    let slot_for_exit = Arc::clone(&slot);

    let app = tauri::Builder::default()
        .setup(move |app| {
            let handle = app.handle().clone();
            let root = root.clone();
            let slot = Arc::clone(&slot_for_setup);

            std::thread::spawn(move || {
                // Attach to a run that is already up; otherwise start one.
                let port = match read_ui_port() {
                    Some(p) if script_ready(p) => Some(p),
                    _ => {
                        if let Ok(child) = start_launcher(&root) {
                            if let Ok(mut guard) = slot.lock() {
                                *guard = Some(child);
                            }
                        }
                        wait_for_ui()
                    }
                };
                open_window(&handle, port);
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build ThermoGar window");

    app.run(move |_handle, event| {
        if let RunEvent::ExitRequested { .. } = event {
            // Stop the launcher this shell started, and only that one. A run we
            // attached to belongs to whoever started it, and killing it here
            // would be this shell deciding about someone else's process.
            if let Ok(mut guard) = slot_for_exit.lock() {
                if let Some(mut child) = guard.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        }
    });
}
use tauri::Manager;
use std::sync::{Arc, Mutex};
use std::env;
use std::process::{Command, Stdio};
use std::path::PathBuf;

struct AppState {
    processes: Arc<Mutex<Vec<u32>>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let processes = Arc::new(Mutex::new(Vec::new()));
    let processes_clone = processes.clone();

    tauri::Builder::default()
        .manage(AppState { processes })
        .setup(move |app| {
            // Find the project root directory
            let mut root_dir = env::current_dir().unwrap_or_default();
            
            // If we are in src-tauri, go up one level
            if root_dir.ends_with("src-tauri") {
                root_dir.pop();
            }

            println!("[LAUNCHER] Project Root: {:?}", root_dir);
            spawn_all_services(root_dir, processes_clone);
            Ok(())
        })
        .on_window_event(move |app_handle, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = app_handle.state::<AppState>();
                let mut pids = state.processes.lock().unwrap();
                for pid in pids.iter() {
                    #[cfg(windows)]
                    {
                        let _ = Command::new("taskkill")
                            .args(["/F", "/T", "/PID", &pid.to_string()])
                            .stdout(Stdio::null())
                            .stderr(Stdio::null())
                            .spawn();
                    }
                }
                pids.clear();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn spawn_all_services(root_dir: PathBuf, pids: Arc<Mutex<Vec<u32>>>) {
    let python_path = root_dir.join("venv").join("Scripts").join("python.exe");

    let services = [
        ("Backend", vec!["main.py"]),
        ("Voice Agent", vec!["-m", "voice.agent", "dev"]),
        ("Magic Clipboard", vec!["magic_clipboard.py"]),
    ];

    for (name, args) in services {
        let mut cmd = Command::new(&python_path);
        cmd.args(&args)
            .current_dir(&root_dir)
            .env("PYTHONIOENCODING", "utf-8")
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit());

        match cmd.spawn() {
            Ok(child) => {
                let pid = child.id();
                pids.lock().unwrap().push(pid);
                println!("[LAUNCHER] {} started with PID: {}", name, pid);
            }
            Err(e) => {
                println!("[LAUNCHER] Failed to start {}: {:?} (Path tried: {:?})", name, e, python_path);
            }
        }
    }
}

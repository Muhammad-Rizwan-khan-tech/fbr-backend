#[tauri::command]
fn get_system_platform() -> String {
    format!("{}-{}", std::env::consts::OS, std::env::consts::ARCH)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![get_system_platform])
        .run(tauri::generate_context!())
        .expect("error while running FBR Invoice Cloud Desktop application");
}

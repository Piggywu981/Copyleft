//! 空窗口壳：只为量出 Rust 产物的真实体积，不含任何图像处理。计划 C 整体替换。
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

struct App;

/// eframe 0.33 起 `App::update` 改名为 `App::ui`，CentralPanel 由框架建，
/// 壳里直接往传进来的 `Ui` 上摆内容。
impl eframe::App for App {
    fn ui(&mut self, ui: &mut eframe::egui::Ui, _frame: &mut eframe::Frame) {
        ui.heading("Copyleft 骨架");
    }
}

fn main() -> eframe::Result {
    eframe::run_native(
        "Copyleft",
        eframe::NativeOptions::default(),
        Box::new(|_cc| Ok(Box::new(App))),
    )
}

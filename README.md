# 🚀 Windows Network Speed Overlay (Android-Style)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-11-blue?style=for-the-badge&logo=windows11&logoColor=white)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](https://github.com/MayurVadhadiya360/Windows-Network-Speed-Monitor/blob/main/LICENSE)

A lightweight **always-on-top network speed overlay for Windows 11**, inspired by Android’s real-time status bar speed indicator.

Built with **Python + PyQt**, it displays **live upload/download speed**, supports **click-through overlay**, **system tray controls**, adaptive units, and color-coded speed thresholds.

---

## ✨ Features

- 📡 Real-time **upload & download speed**
- 🪟 **Always-on-top transparent overlay**
- 🖱 **Click-through window** (does not block mouse input)
- 🎨 **Color-coded speed thresholds**
- 📏 **Adaptive units** (B / KB / MB / GB)
- 🔢 **Android-style 3-digit formatting**
- ↕ Separate **Upload / Download indicators**
- 🔔 **System tray toggle** (Show / Hide / Exit)
- ⚡ Very low CPU & memory usage
- 🪟 Optimized for **Windows 11**

---

## 📸 Preview

↓ 12.3 MB/s ↑ 1.2 MB/s

- Green → High speed  
- Orange → Medium speed  
- Red → Low speed  

---

## 🛠 Tech Stack

- **Python 3.9+**
- **PyQt5** – UI & overlay
- **psutil** – Network statistics
- **Windows Win32 API (ctypes)** – Click-through behavior

---

## 📦 Installation

### 1️⃣ Clone the repository
```bash
git clone https://github.com/MayurVadhadiya360/Windows-Network-Speed-Monitor.git
cd Windows-Network-Speed-Monitor
```

### 2️⃣ Install dependencies
```bash
pip install - r requirements.txt
```
Note: Use official python (Using with Anaconda environment may result in `_ctypes ` error)

### 3️⃣ Run the app
```bash
python netspeed_overlay.py
```

## 🎮 Usage

- Overlay starts automatically
- Appears at the top-right corner
- Does not block mouse clicks
- Right-click the system tray icon:
  - Show Overlay
  - Hide Overlay
  - Exit

---

## 🎨 Speed Color Logic
| Speed      | Color     |
| ---------- | --------- |
| < 100 KB/s | 🔴 Red    |
| < 2 MB/s   | 🟠 Orange |
| ≥ 2 MB/s   | 🟢 Green  |
(Thresholds are configurable in code)

## 🔢 Speed Formatting Logic

- Max 3 visible digits (Android-style)
- Automatically switches units:
  - `512 B/s`
  - `1.2 KB/s`
  - `12.3 MB/s`
  - `1.0 GB/s`

## 🧠 How Click-Through Works

The overlay uses Windows extended window styles:
- `WS_EX_LAYERED`
- `WS_EX_TRANSPARENT`

This allows:
- Full visibility
- Zero mouse interference
- Perfect for gaming & fullscreen apps


## 🏁 Auto-Start on Boot (Optional)
### Method 1: Startup Folder
1. Press `Win + R`
2. Type `shell:startup`
3. Place the executable or script shortcut there

### Method 2: Registry
```reg
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
```

## 📦 Build Executable (Optional)
```bash
pyinstaller --onefile --noconsole netspeed_overlay.py
```
The EXE will be created in the `dist/` folder.

## ⚠ Limitations
- Windows-only (uses Win32 API)
- Not a native Windows widget (overlay workaround)
- Requires Python runtime (unless packaged)

## 🧠 Future Improvements
- Multi-monitor positioning
- Acrylic / Mica blur effect
- Per-network-adapter selection
- Save position & preferences
- Rolling average smoothing
- PyQt6 migration

## 📜 License
MIT License — free to use, modify, and distribute.

## 🙌 Acknowledgements
Inspired by Android’s network speed indicator
Built for developers who want clean, functional desktop utilities
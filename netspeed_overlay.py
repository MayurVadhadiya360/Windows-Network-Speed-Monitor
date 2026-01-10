import sys
from typing import Any
import psutil
import ctypes
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTabWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QSystemTrayIcon, QMenu, QAction, QStyle, QPushButton, QSpinBox, QScrollArea,
    QLabel, QColorDialog, QMessageBox, QComboBox, QCheckBox, QFormLayout, QSystemTrayIcon
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QCloseEvent
import json
import copy

import winshell
from win32com.client import Dispatch

import os
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

APP_NAME = "NetworkSpeedOverlay"
CONFIG_PATH = "network_speed_monitor_config.json"

DEFAULT_CONFIG = {
    "appearance": {
        "font_size": 11,
        "layout": "horizontal",
        "download_unit_mode": "Auto",
        "upload_unit_mode": "Auto"
    },
    "thresholds": {
        "link_upload": True,
        "download": {
            "very_low": {
                "limit": 1,
                "unit": "KB/s",
                "color": "#9e9e9e"
            },
            "low": {
                "limit": 100,
                "unit": "KB/s",
                "color": "#ff4d4d"
            },
            "medium": {
                "limit": 2,
                "unit": "MB/s",
                "color": "#ffa500"
            },
            "high": {
                "limit": 10,
                "unit": "MB/s",
                "color": "#00e676"
            },
            "very_high": {
                "limit": 11,
                "unit": "",
                "color": "#00b0ff"
            }
        },
        "upload": {
            "very_low": {
                "limit": 1,
                "unit": "KB/s",
                "color": "#9e9e9e"
            },
            "low": {
                "limit": 100,
                "unit": "KB/s",
                "color": "#ff4d4d"
            },
            "medium": {
                "limit": 2,
                "unit": "MB/s",
                "color": "#ffa500"
            },
            "high": {
                "limit": 10,
                "unit": "MB/s",
                "color": "#00e676"
            },
            "very_high": {
                "limit": 11,
                "unit": "",
                "color": "#00b0ff"
            }
        }
    },
    "behavior": {
        "click_through": True,
        "refresh_interval": 1000,
        "always_on_top": True,
        "pause_when_hidden": False
    },
    "position": {
        "x": 10,
        "y": 20,
    },
    "startup": {
        "enabled": False
    }
}

def startup_shortcut_path():
    startup_dir = winshell.startup()
    return os.path.join(startup_dir, f"{APP_NAME}.lnk")

def enable_startup():
    path = startup_shortcut_path()
    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(path)
    shortcut.Targetpath = sys.executable
    shortcut.Arguments = os.path.abspath(__file__)
    shortcut.WorkingDirectory = os.getcwd()
    shortcut.save()

def disable_startup():
    path = startup_shortcut_path()
    if os.path.exists(path):
        os.remove(path)

def is_startup_enabled():
    return os.path.exists(startup_shortcut_path())


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_PATH, "r") as f:
        cfg: dict[str, Any] = json.load(f)
        cfg.setdefault("startup", {})["enabled"] = is_startup_enabled()
        return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)



# thresholds in bytes per second
VERY_LOW_SPEED = 1024
LOW_SPEED    = 100 * 1024        # < 100 KB/s
MEDIUM_SPEED = 2 * 1024 * 1024   # < 2 MB/s
HIGH_SPEED   = 10 * 1024 * 1024  # >= 10 MB/s


# Windows API constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20


class NetSpeedOverlay(QWidget):
    def __init__(self, config: dict[str, Any]):
        super().__init__()

        self.config = config

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowOpacity(0.8)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        self.down_label = QLabel(self)
        self.up_label = QLabel(self)

        font = QFont("Segoe UI", 11, QFont.Bold)
        self.down_label.setFont(font)
        self.up_label.setFont(font)

        base_style = """
            QLabel {
                background-color: rgba(0, 0, 0, 160);
                padding: 4px 8px;
                border-radius: 6px;
            }
            """

        self.down_label.setStyleSheet(base_style)
        self.up_label.setStyleSheet(base_style)

        layout.addWidget(self.down_label)
        layout.addWidget(self.up_label)

        # self.move(10, 20)
        self.move(
            self.config["position"].get("x", 10),
            self.config["position"].get("y", 20)
        )
        self.prev = psutil.net_io_counters()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_speed)
        self.timer.start(1000)

        self.show()
        self.make_click_through()


    def make_click_through(self):
        hwnd = self.winId().__int__()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        )

    
    def speed_color(self, bytes_per_sec: float, direction: str) -> str:
        """
        direction: 'download' or 'upload'
        """
        thresholds_cfg = self.config["thresholds"]

        def to_bytes(value: float, unit: str) -> float:
            if unit == "KB/s":
                return value * 1024
            if unit == "MB/s":
                return value * 1024 * 1024
            if unit == "GB/s":
                return value * 1024 * 1024 * 1024
            return value  # already bytes

        # Handle upload linking
        if direction == "upload" and thresholds_cfg["link_upload"]:
            rules = thresholds_cfg["download"]
        else:
            rules = thresholds_cfg[direction]

        # Order matters (lowest → highest)
        ordered_keys = ["very_low", "low", "medium", "high"]

        for key in ordered_keys:
            limit = rules[key]["limit"]
            unit = rules[key]["unit"]

            # Convert limit to bytes
            limit_bytes = to_bytes(limit, unit)

            if bytes_per_sec < limit_bytes:
                return rules[key]["color"]

        # Fallback → very_high
        return rules["very_high"]["color"]

    
    def format_speed(self, bytes_per_sec: float, direction: str) -> str:
        """
        direction: 'download' or 'upload'
        """
        unit_mode = self.config["appearance"].get(f"{direction}_unit_mode", "Auto")

        def bytes_to_unit(bytes_per_sec: float, unit: str) -> float:
            if unit == "KB/s":
                return bytes_per_sec / 1024
            if unit == "MB/s":
                return bytes_per_sec / (1024 * 1024)
            if unit == "GB/s":
                return bytes_per_sec / (1024 * 1024 * 1024)
            return bytes_per_sec

        def format_3_digits(value: float) -> str:
            if value < 10:
                text = f"{value:.1f}"
            elif value < 100:
                text = f"{value:.1f}"
            else:
                text = f"{value:.0f}"

            return text.rstrip("0").rstrip(".") if '.' in text else text

        # -------- AUTO MODE --------
        if unit_mode == "Auto":
            value = bytes_per_sec
            unit = "B/s"

            for next_unit in ["KB/s", "MB/s", "GB/s", "TB/s"]:
                if value < 1024:
                    break
                value /= 1024
                unit = next_unit

            return f"{format_3_digits(value):^5} {unit:>4}"

        # -------- FIXED UNIT MODE --------
        value = bytes_to_unit(bytes_per_sec, unit_mode)
        return f"{format_3_digits(value):^5} {unit_mode:>4}"

    def update_speed(self):
        if (
            not self.isVisible()
            and self.config["behavior"].get("pause_when_hidden", False)
        ):
            return


        curr = psutil.net_io_counters()

        down = curr.bytes_recv - self.prev.bytes_recv
        up   = curr.bytes_sent - self.prev.bytes_sent
        self.prev = curr

        down_text = f"↓ {self.format_speed(down, 'download')}"
        up_text   = f"↑ {self.format_speed(up, 'upload')}"

        self.down_label.setText(down_text)
        self.up_label.setText(up_text)

        self.down_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.speed_color(down, "download")};
                background-color: rgba(0, 0, 0, 160);
                padding: 4px 8px;
                border-radius: 6px;
            }}
            """
        )

        self.up_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.speed_color(up, "upload")};
                background-color: rgba(0, 0, 0, 160);
                padding: 4px 8px;
                border-radius: 6px;
            }}
            """
        )

        self.adjustSize()
    
    def apply_settings(self, cfg):
        self.config = cfg
        appearance = cfg["appearance"]
        behavior = cfg["behavior"]

        # ---- Font ----
        font = self.down_label.font()
        font.setPointSize(appearance["font_size"])
        self.down_label.setFont(font)
        self.up_label.setFont(font)

        # ---- Layout ----
        if appearance["layout"] == "vertical":
            self.layout().setDirection(QVBoxLayout.TopToBottom)
        else:
            self.layout().setDirection(QHBoxLayout.LeftToRight)
        
        # ---- Always on top ----
        flags = self.windowFlags()
        if behavior.get("always_on_top", True):
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

        # ---- Click-through ----
        if behavior.get("click_through", True):
            self.make_click_through()

        # ---- Refresh interval ----
        interval = behavior.get("refresh_interval", 1000)
        self.timer.setInterval(interval)

        self.adjustSize()



class SettingsWindow(QWidget):
    def __init__(self, overlay: NetSpeedOverlay, config: dict[str, Any]):
        super().__init__()
        self.overlay = overlay
        self.config = config

        self._original_position = None
        self._position_dirty = False

        self.setWindowTitle("Network Speed Monitor Properties")
        self.setFixedSize(520, 420)

        main_layout = QVBoxLayout(self)

        # ---- Tabs ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self.general_tab(), "General")
        self.tabs.addTab(self.appearance_tab(), "Appearance")
        self.tabs.addTab(self.behavior_tab(), "Behavior")
        self.tabs.addTab(self.position_tab(), "Position")
        self.tabs.addTab(self.advanced_tab(), "Advanced")
        self.tabs.addTab(self.about_tab(), "About")

        main_layout.addWidget(self.tabs)

        # ---- Bottom Buttons (Windows style) ----
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.apply_btn = QPushButton("Apply")
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")

        self.apply_btn.clicked.connect(self.apply)
        self.save_btn.clicked.connect(self.save)
        self.cancel_btn.clicked.connect(self.on_cancel)

        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(btn_layout)
    
    # ----------- Method Override ------------
    def closeEvent(self, event: QCloseEvent | None):
        # Restore overlay position if not applied
        self.restore_original_position()
        
        # Hide instead of closing
        event.ignore()
        self.hide()

    # ----------- Custom Methods -------------
    def general_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # ---------------- STARTUP ----------------
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout()

        self.startup_cb = QCheckBox("Start Network Speed Overlay with Windows")
        self.startup_cb.setChecked(
            self.config.get("startup", {}).get("enabled", False)
        )

        startup_info = QLabel(
            "This will enable NetworkSpeedMonitor to start on Windows Startup. \n\n"
            "⚠️ Note: "
            "Change applied will be immediately saved for this property."
        )
        startup_info.setWordWrap(True)
        startup_info.setStyleSheet("color:#9e9e9e; font-size:11px;")

        startup_layout.addWidget(self.startup_cb)
        startup_layout.addWidget(startup_info)
        startup_group.setLayout(startup_layout)

        # ---------------- DEFAULTS ----------------
        defaults_group = QGroupBox("Reset")
        defaults_layout = QVBoxLayout()

        reset_btn = QPushButton("Restore Default Settings")
        reset_btn.clicked.connect(self.restore_defaults)

        defaults_info = QLabel(
            "This will reset all settings to their default values.\n"
            "Changes are applied immediately but are not saved until you click Save."
        )
        defaults_info.setWordWrap(True)
        defaults_info.setStyleSheet("color:#9e9e9e; font-size:11px;")

        defaults_layout.addWidget(reset_btn)
        defaults_layout.addWidget(defaults_info)
        defaults_group.setLayout(defaults_layout)

        layout.addWidget(startup_group)
        layout.addWidget(defaults_group)
        layout.addStretch()

        return w


    def appearance_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        scroll.setWidget(content)

        main = QVBoxLayout(content)
        main.setSpacing(12)
        main.setContentsMargins(10, 10, 10, 10)

        # ---------------- BASIC APPEARANCE ----------------
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setHorizontalSpacing(12)

        label_width = 120

        def fixed_label(text):
            lbl = QLabel(text)
            lbl.setFixedWidth(label_width)
            return lbl

        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setFixedWidth(80)
        self.font_size_spin.setValue(self.config["appearance"]["font_size"])
        form.addRow(fixed_label("Font size:"), self.font_size_spin)

        # Layout
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["horizontal", "vertical"])
        self.layout_combo.setFixedWidth(140)
        self.layout_combo.setCurrentText(self.config["appearance"]["layout"])
        form.addRow(fixed_label("Layout:"), self.layout_combo)

        # Speed units
        self.dl_unit_combo = QComboBox()
        self.dl_unit_combo.addItems(["Auto", "B/s", "KB/s", "MB/s"])
        self.dl_unit_combo.setFixedWidth(140)
        self.dl_unit_combo.setCurrentText(self.config["appearance"].get("download_unit_mode", "Auto"))
        form.addRow(fixed_label("Download Speed Unit:"), self.dl_unit_combo)

        self.ul_unit_combo = QComboBox()
        self.ul_unit_combo.addItems(["Auto", "B/s", "KB/s", "MB/s"])
        self.ul_unit_combo.setFixedWidth(140)
        self.ul_unit_combo.setCurrentText(self.config["appearance"].get("upload_unit_mode", "Auto"))
        form.addRow(fixed_label("Upload Speed Unit:"), self.ul_unit_combo)

        main.addLayout(form)

        # ---------------- DOWNLOAD THRESHOLDS ----------------
        # main.addWidget(QLabel("Speed thresholds (Download):"))
        self.speed_th_download_group_box = QGroupBox("Speed Thresholds (Download)")
        vbox_layout_download = QVBoxLayout()

        self.dl_thresholds: dict[str, QSpinBox] = {}
        self.dl_color_btns: dict[str, QPushButton] = {}

        for key, text, unit in [
            ("very_low", "Very low", "KB/s"),
            ("low", "Low", "KB/s"),
            ("medium", "Medium", "MB/s"),
            ("high", "High", "MB/s"),
            ("very_high", "Very high", "MB/s"),
        ]:
            row = QHBoxLayout()

            label = QLabel(text)
            label.setFixedWidth(90)

            spin = QSpinBox()
            spin.setRange(0, 10000)
            spin.setFixedWidth(80)
            spin.setValue(self.config["thresholds"]["download"][key]["limit"])
            if key == "very_high":
                spin.setValue(self.config["thresholds"]["download"]["high"]["limit"])
                spin.setEnabled(False)
                spin.setPrefix("≥ ")
            else:
                spin.setPrefix("< ")

            unit_lbl = QLabel(unit)
            unit_lbl.setFixedWidth(50)

            color_btn = QPushButton()
            color_btn.setFixedSize(60, 24)
            color_btn.setStyleSheet(
                f"background-color: {self.config['thresholds']['download'][key]['color']};"
            )
            color_btn.clicked.connect(lambda _, k=key: self.pick_color("download", k))

            row.addWidget(label)
            row.addWidget(spin)
            row.addWidget(unit_lbl)
            row.addStretch()
            row.addWidget(color_btn)

            self.dl_thresholds[key] = spin
            self.dl_color_btns[key] = color_btn

            # main.addLayout(row)
            vbox_layout_download.addLayout(row)
        self.speed_th_download_group_box.setLayout(vbox_layout_download)
        main.addWidget(self.speed_th_download_group_box)

        # ---------------- UPLOAD LINK OPTION ----------------
        self.speed_th_upload_group_box = QGroupBox("Speed Thresholds (Upload)")
        vbox_layout_upload = QVBoxLayout()

        self.link_upload_cb = QCheckBox("Use Download settings for Upload")
        self.link_upload_cb.setChecked(self.config["thresholds"]["link_upload"])
        self.link_upload_cb.stateChanged.connect(self.toggle_upload_settings)
        # main.addWidget(self.link_upload_cb)
        vbox_layout_upload.addWidget(self.link_upload_cb)

        # ---------------- UPLOAD THRESHOLDS ----------------
        # main.addWidget(QLabel("Speed thresholds (Upload):"))

        self.ul_thresholds: dict[str, QSpinBox] = {}
        self.ul_color_btns: dict[str, QPushButton] = {}

        for key, text, unit in [
            ("very_low", "Very low", "KB/s"),
            ("low", "Low", "KB/s"),
            ("medium", "Medium", "MB/s"),
            ("high", "High", "MB/s"),
            ("very_high", "Very high", "MB/s"),
        ]:
            row = QHBoxLayout()

            label = QLabel(text)
            label.setFixedWidth(90)

            spin = QSpinBox()
            spin.setRange(0, 10000)
            spin.setFixedWidth(80)
            spin.setValue(self.config["thresholds"]["upload"][key]["limit"])
            if key == "very_high":
                spin.setValue(self.config["thresholds"]["upload"]["high"]["limit"])
                spin.setEnabled(False)
                spin.setPrefix("≥ ")
            else:
                spin.setPrefix("< ")
            # ------Link Upload Thresold value with download thresold value----
            self.dl_thresholds[key].valueChanged.connect(lambda _, k=key: self.link_upload_cb.isChecked() and self.ul_thresholds[k].setValue(self.dl_thresholds[k].value()))

            unit_lbl = QLabel(unit)
            unit_lbl.setFixedWidth(50)

            color_btn = QPushButton()
            color_btn.setFixedSize(60, 24)
            color_btn.setStyleSheet(
                f"background-color: {self.config['thresholds']['upload'][key]['color']};"
            )
            color_btn.clicked.connect(lambda _, k=key: self.pick_color("upload", k))
            
            row.addWidget(label)
            row.addWidget(spin)
            row.addWidget(unit_lbl)
            row.addStretch()
            row.addWidget(color_btn)

            self.ul_thresholds[key] = spin
            self.ul_color_btns[key] = color_btn

            # main.addLayout(row)
            vbox_layout_upload.addLayout(row)
        self.speed_th_upload_group_box.setLayout(vbox_layout_upload)
        main.addWidget(self.speed_th_upload_group_box)

        self.toggle_upload_settings()

        main.addStretch()
        return scroll


    def behavior_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # ---------------- INTERACTION ----------------
        interaction_group = QGroupBox("Interaction")
        interaction_layout = QVBoxLayout()

        self.click_through_cb = QCheckBox("Enable click-through overlay (mouse passes through)")
        self.click_through_cb.setChecked(
            self.config["behavior"].get("click_through", True)
        )

        self.always_on_top_cb = QCheckBox("Always keep overlay on top")
        self.always_on_top_cb.setChecked(
            self.config["behavior"].get("always_on_top", True)
        )

        interaction_layout.addWidget(self.click_through_cb)
        interaction_layout.addWidget(self.always_on_top_cb)
        interaction_group.setLayout(interaction_layout)

        # ---------------- UPDATE BEHAVIOR ----------------
        update_group = QGroupBox("Update Behavior")
        update_layout = QFormLayout()
        update_layout.setHorizontalSpacing(12)

        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(250, 5000)
        self.refresh_spin.setSingleStep(250)
        self.refresh_spin.setSuffix(" ms")
        self.refresh_spin.setFixedWidth(120)
        self.refresh_spin.setValue(
            self.config["behavior"].get("refresh_interval", 1000)
        )

        update_layout.addRow("Refresh interval(250s to 5000s):", self.refresh_spin)
        update_group.setLayout(update_layout)

        # ---------------- VISIBILITY ----------------
        visibility_group = QGroupBox("Visibility")
        visibility_layout = QVBoxLayout()

        self.pause_when_hidden_cb = QCheckBox("Pause updates when overlay is hidden")
        self.pause_when_hidden_cb.setChecked(
            self.config["behavior"].get("pause_when_hidden", False)
        )

        visibility_layout.addWidget(self.pause_when_hidden_cb)
        visibility_group.setLayout(visibility_layout)

        layout.addWidget(interaction_group)
        layout.addWidget(update_group)
        layout.addWidget(visibility_group)

        # ---------------- WARNING NOTE ----------------
        warning = QLabel(
            "⚠️ Note: "
            "Click-through and pause updates options may not function reliably in some "
            "Windows environments, fullscreen applications, or due to system limitations."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("""
            QLabel {
                color: #9e9e9e;
                font-size: 11px;
                margin-top: 8px;
            }
        """)

        layout.addWidget(warning)
        layout.addStretch()

        return w


    def position_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # ---------------- PRESETS ----------------
        preset_group = QGroupBox("Quick Position Presets")
        preset_layout = QHBoxLayout()

        self.position_preset_combo = QComboBox()
        self.position_preset_combo.addItems([
            "Top Left",
            "Top Right",
            "Bottom Left",
            "Bottom Right",
            "Center"
        ])

        apply_preset_btn = QPushButton("Apply Preset")
        apply_preset_btn.clicked.connect(self.apply_position_preset)

        preset_layout.addWidget(self.position_preset_combo)
        preset_layout.addWidget(apply_preset_btn)
        preset_group.setLayout(preset_layout)

        # ---------------- MANUAL POSITION ----------------
        manual_group = QGroupBox("Manual Position")
        manual_layout = QFormLayout()

        self.pos_x_spin = QSpinBox()
        self.pos_x_spin.setRange(-5000, 5000)
        self.pos_x_spin.setFixedWidth(120)
        self.pos_x_spin.setValue(self.config["position"]["x"])

        self.pos_y_spin = QSpinBox()
        self.pos_y_spin.setRange(-5000, 5000)
        self.pos_y_spin.setFixedWidth(120)
        self.pos_y_spin.setValue(self.config["position"]["y"])

        manual_layout.addRow("X position:", self.pos_x_spin)
        manual_layout.addRow("Y position:", self.pos_y_spin)
        manual_group.setLayout(manual_layout)

        # Live update overlay when spinboxes change
        self.pos_x_spin.valueChanged.connect(self.update_overlay_position)
        self.pos_y_spin.valueChanged.connect(self.update_overlay_position)

        # ---------------- INFO ----------------
        # info = QLabel(
        #     "Tip: You can also drag the overlay directly on the desktop "
        #     "when position is not locked."
        # )
        # info.setWordWrap(True)
        # info.setStyleSheet("color:#9e9e9e; font-size:11px;")

        layout.addWidget(preset_group)
        layout.addWidget(manual_group)
        # layout.addWidget(info)
        layout.addStretch()

        return w


    def advanced_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("• Network adapter"))
        layout.addWidget(QLabel("• Low CPU mode"))
        layout.addWidget(QLabel("• Import / Export config"))
        layout.addStretch()
        return w
    
    def about_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Network Speed Monitor"))
        layout.addWidget(QLabel("Version: 1.2.0"))
        layout.addWidget(QLabel("Built with Python & PyQt"))
        layout.addWidget(QLabel("GitHub: github.com/MayurVadhadiya360"))
        layout.addStretch()
        return w


    def pick_color(self, direction: str, key: str):
        current = QColor(self.config["thresholds"][direction][key]["color"])
        color = QColorDialog.getColor(current, self)
        if color.isValid():
            # self.config["thresholds"][direction][key]["color"] = color.name()
            btn = (
                self.dl_color_btns[key]
                if direction == "download"
                else self.ul_color_btns[key]
            )
            btn.setStyleSheet(f"background-color: {color.name()};")
            if direction == "download" and self.link_upload_cb.isChecked():
                self.ul_color_btns[key].setStyleSheet(f"background-color: {color.name()};")
    
    def toggle_upload_settings(self):
        linked = self.link_upload_cb.isChecked()
        for key in self.ul_thresholds:
            if key != "very_high": self.ul_thresholds[key].setEnabled(not linked)
            self.ul_color_btns[key].setEnabled(not linked)
            
            if linked:
                self.ul_thresholds[key].setValue(self.dl_thresholds[key].value())
                self.ul_color_btns[key].setStyleSheet(
                    f"background-color: {self.dl_color_btns[key].palette().color(QPalette.ColorRole.Button).name()};"
                )
    
    def apply_position_preset(self):
        screen = QApplication.primaryScreen().availableGeometry()
        overlay = self.overlay
        ow = overlay.width()
        oh = overlay.height()

        preset = self.position_preset_combo.currentText()

        if preset == "Top Left":
            x, y = 10, 10
        elif preset == "Top Right":
            x = screen.width() - ow - 10
            y = 10
        elif preset == "Bottom Left":
            x = 10
            y = screen.height() - oh - 10
        elif preset == "Bottom Right":
            x = screen.width() - ow - 10
            y = screen.height() - oh - 10
        else:  # Center
            x = (screen.width() - ow) // 2
            y = (screen.height() - oh) // 2

        self.overlay.move(x, y)
        self.pos_x_spin.setValue(x)
        self.pos_y_spin.setValue(y)
        self._position_dirty = True
    
    def snapshot_original_position(self):
        self._original_position = (
            self.overlay.x(),
            self.overlay.y()
        )
        self._position_dirty = False

    def update_overlay_position(self):
        x = self.pos_x_spin.value()
        y = self.pos_y_spin.value()
        self.overlay.move(x, y)
        self._position_dirty = True

    def restore_original_position(self):
        if self._position_dirty and self._original_position:
            x, y = self._original_position
            self.overlay.move(x, y)

    def load_config_into_ui(self, config: dict[str, Any]):
        """
        Reload config into Settings UI.
        Called every time Settings window is opened.
        """
        self.config = config

        # ---------------- Appearance ----------------
        self.font_size_spin.setValue(
            config["appearance"].get("font_size", 11)
        )

        self.layout_combo.setCurrentText(
            config["appearance"].get("layout", "horizontal")
        )

        self.dl_unit_combo.setCurrentText(
            config["appearance"].get("download_unit_mode", "Auto")
        )

        self.ul_unit_combo.setCurrentText(
            config["appearance"].get("upload_unit_mode", "Auto")
        )

        # ---------------- Thresholds ----------------
        self.link_upload_cb.setChecked(
            config["thresholds"].get("link_upload", True)
        )

        # ---- Download thresholds ----
        for key in self.dl_thresholds:
            self.dl_thresholds[key].setValue(
                config["thresholds"]["download"][key]["limit"]
            )

            self.dl_color_btns[key].setStyleSheet(
                f"background-color: {config['thresholds']['download'][key]['color']};"
            )

        # ---- Upload thresholds ----
        for key in self.ul_thresholds:
            self.ul_thresholds[key].setValue(
                config["thresholds"]["upload"][key]["limit"]
            )

            self.ul_color_btns[key].setStyleSheet(
                f"background-color: {config['thresholds']['upload'][key]['color']};"
            )

        # Apply link-upload UI state
        self.toggle_upload_settings()

    def restore_defaults(self):
        reply = QMessageBox.question(
            self,
            "Restore Defaults",
            "Are you sure you want to restore all settings to default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Reset config in memory
        self.config = copy.deepcopy(DEFAULT_CONFIG)

        # Reload UI from defaults
        self.load_config_into_ui(self.config)

        # Reset overlay immediately
        self.overlay.apply_settings(self.config)

        # Reset position
        self.overlay.move(
            self.config["position"]["x"],
            self.config["position"]["y"]
        )

        # Mark position as clean
        self._original_position = (
            self.overlay.x(),
            self.overlay.y()
        )
        self._position_dirty = False


    def apply(self):
        # ---------------- Appearance ----------------
        self.config["appearance"]["font_size"] = self.font_size_spin.value()
        self.config["appearance"]["layout"] = self.layout_combo.currentText()
        self.config["appearance"]["download_unit_mode"] = self.dl_unit_combo.currentText()
        self.config["appearance"]["upload_unit_mode"] = self.ul_unit_combo.currentText()

        self.config["thresholds"]["link_upload"] = self.link_upload_cb.isChecked()

        for key in self.dl_thresholds:
            self.config["thresholds"]["download"][key]["limit"] = self.dl_thresholds[key].value()

            if self.link_upload_cb.isChecked():
                self.config["thresholds"]["upload"][key]["limit"] = self.config["thresholds"]["download"][key]["limit"]
            else:
                self.config["thresholds"]["upload"][key]["limit"] = self.ul_thresholds[key].value()
        
        for key in self.dl_color_btns:
            self.config["thresholds"]["download"][key]["color"] = self.dl_color_btns[key].palette().color(QPalette.ColorRole.Button).name()
            if self.link_upload_cb.isChecked():
                self.config["thresholds"]["upload"][key]["color"] = self.config["thresholds"]["download"][key]["color"]
            else:
                self.config["thresholds"]["upload"][key]["color"] = self.ul_color_btns[key].palette().color(QPalette.ColorRole.Button).name()

        # ---------------- Behavior ----------------
        self.config["behavior"]["click_through"] = self.click_through_cb.isChecked()
        self.config["behavior"]["always_on_top"] = self.always_on_top_cb.isChecked()
        self.config["behavior"]["refresh_interval"] = self.refresh_spin.value()
        self.config["behavior"]["pause_when_hidden"] = self.pause_when_hidden_cb.isChecked()

        # ---------------- Position ----------------
        self.config["position"]["x"] = self.pos_x_spin.value()
        self.config["position"]["y"] = self.pos_y_spin.value()

        # Position successfully applied → update snapshot
        self._original_position = (
            self.overlay.x(),
            self.overlay.y()
        )
        self._position_dirty = False

        # ---------------- Startup ----------------
        startup_enabled = self.startup_cb.isChecked()
        self.config.setdefault("startup", {})["enabled"] = startup_enabled

        if startup_enabled:
            enable_startup()
        else:
            disable_startup()

        self.overlay.apply_settings(self.config)

    def save(self):
        self.apply()
        save_config(self.config)
        # self.hide()
    
    def on_cancel(self):
        self.restore_original_position()
        self.hide()


class TrayController:
    def __init__(self, app: QApplication, overlay: NetSpeedOverlay):
        self.app = app
        self.overlay = overlay

        icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, app)
        self.tray.setToolTip("Network Speed Monitor")

        self.tray.activated.connect(self.on_tray_activated)

        self.menu = QMenu()

        self.toggle_action = QAction("Hide Overlay", self.menu)
        self.toggle_action.triggered.connect(self.toggle_overlay)

        self.settings_action = QAction("Settings", self.menu)
        self.settings_action.triggered.connect(self.open_settings)

        self.exit_action = QAction("Exit", self.menu)
        self.exit_action.triggered.connect(self.exit_app)

        self.menu.addAction(self.toggle_action)
        self.menu.addAction(self.settings_action)
        self.menu.addSeparator()
        self.menu.addAction(self.exit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.show()
    
    def on_tray_activated(self, reason):
        # Where ActivationReason can be:
        # Trigger → single click
        # DoubleClick → double click
        # Context → right click
        # MiddleClick → Middle (mouse-wheel) click
        if reason == QSystemTrayIcon.Trigger:
            self.open_settings()

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.toggle_action.setText("Show Overlay")
        else:
            self.overlay.show()
            self.overlay.make_click_through()
            self.toggle_action.setText("Hide Overlay")
    
    def open_settings(self):
        config = load_config()
        if not hasattr(self, "settings"):
            self.settings = SettingsWindow(self.overlay, config)
        else:
            self.settings.load_config_into_ui(config)

        self.settings.snapshot_original_position()
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def exit_app(self):
        self.tray.hide()
        self.overlay.close()
        self.app.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    config = load_config()

    overlay = NetSpeedOverlay(config)
    overlay.apply_settings(config)
    tray = TrayController(app, overlay)

    sys.exit(app.exec_())

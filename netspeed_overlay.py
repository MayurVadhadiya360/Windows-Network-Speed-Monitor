import sys
import psutil
import ctypes
from PyQt5.QtWidgets import (
    QApplication, QLabel, QWidget, QHBoxLayout, 
    QSystemTrayIcon, QMenu, QAction, QStyle
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon

import os
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


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
    def __init__(self):
        super().__init__()

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
        layout

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

        self.move(10, 20)
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
    
    def speed_color(self, bytes_per_sec: float) -> str:
        if bytes_per_sec < VERY_LOW_SPEED:
            return "#9e9e9e"
        if bytes_per_sec < LOW_SPEED:
            return "#ff4d4d"   # red
        elif bytes_per_sec < MEDIUM_SPEED:
            return "#ffa500"   # orange
        elif bytes_per_sec < HIGH_SPEED:
            return "#00e676"   # green
        else: # Very High
            return "#00b0ff"   # blue

    
    def format_speed(self, bytes_per_sec: float) -> str:
        units = ["B/s", "KB/s", "MB/s", "GB/s", "TB/s"]
        value = float(bytes_per_sec)
        unit_index = 0

        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1

        if value < 10:
            text = f"{value:.1f}"
        elif value < 100:
            text = f"{value:.1f}"
        else:
            text = f"{value:.0f}"

        # text = text.rstrip("0").rstrip(".")
        return f"{text} {units[unit_index]}"


    def update_speed(self):
        curr = psutil.net_io_counters()

        down = curr.bytes_recv - self.prev.bytes_recv
        up   = curr.bytes_sent - self.prev.bytes_sent
        self.prev = curr

        down_text = f"↓ {self.format_speed(down)}"
        up_text   = f"↑ {self.format_speed(up)}"

        self.down_label.setText(down_text)
        self.up_label.setText(up_text)

        self.down_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.speed_color(down)};
                background-color: rgba(0, 0, 0, 160);
                padding: 4px 8px;
                border-radius: 6px;
            }}
            """
        )

        self.up_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.speed_color(up)};
                background-color: rgba(0, 0, 0, 160);
                padding: 4px 8px;
                border-radius: 6px;
            }}
            """
        )

        self.adjustSize()


class TrayController:
    def __init__(self, app: QApplication, overlay: NetSpeedOverlay):
        self.app = app
        self.overlay = overlay

        icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, app)
        self.tray.setToolTip("Network Speed Monitor")

        self.menu = QMenu()

        self.toggle_action = QAction("Hide Overlay", self.menu)
        self.toggle_action.triggered.connect(self.toggle_overlay)

        self.exit_action = QAction("Exit", self.menu)
        self.exit_action.triggered.connect(self.exit_app)

        self.menu.addAction(self.toggle_action)
        self.menu.addSeparator()
        self.menu.addAction(self.exit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.toggle_action.setText("Show Overlay")
        else:
            self.overlay.show()
            self.overlay.make_click_through()
            self.toggle_action.setText("Hide Overlay")

    def exit_app(self):
        self.tray.hide()
        self.overlay.close()
        self.app.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    overlay = NetSpeedOverlay()
    tray = TrayController(app, overlay)

    sys.exit(app.exec_())

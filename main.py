"""
Yaesu FT-8XX Suite by K3LH - Main Entry Point
Yaesu FT-8XX Suite by K3LH
"""

import sys
import os

# Ensure we can find our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont
from ui.main_window import MainWindow


def main():
    # High DPI support
    app = QApplication(sys.argv)
    app.setApplicationName("Yaesu FT-8XX Suite by K3LH")
    app.setApplicationVersion("2.1.0")
    app.setOrganizationName("K3LH")

    # Set default application font
    app.setFont(QFont("Consolas", 10))

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

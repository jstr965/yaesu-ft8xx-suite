"""
Waterfall / Spectrum Display Widget
Real-time FFT spectrum and scrolling waterfall from audio input
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QImage, QPen, QFont


# Colour maps for waterfall
def _make_colormap():
    """Build a 256-entry heat colormap (black → blue → cyan → green → yellow → red)."""
    cmap = []
    for i in range(256):
        t = i / 255.0
        if t < 0.2:
            r, g, b = 0, 0, int(t / 0.2 * 200)
        elif t < 0.4:
            r, g, b = 0, int((t - 0.2) / 0.2 * 255), 200
        elif t < 0.6:
            r, g, b = 0, 255, int(200 - (t - 0.4) / 0.2 * 200)
        elif t < 0.8:
            r, g, b = int((t - 0.6) / 0.2 * 255), 255, 0
        else:
            r, g, b = 255, int(255 - (t - 0.8) / 0.2 * 255), 0
        cmap.append((r, g, b))
    return cmap


COLORMAP = _make_colormap()


class WaterfallWidget(QWidget):
    """
    Dual-pane widget:
      Top 40%  — live spectrum (line graph)
      Bottom 60% — scrolling waterfall
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(200)
        self.setMinimumHeight(200)

        self._fft_data   = np.zeros(1024)
        self._floor_db   = -120.0
        self._ceil_db    = -40.0

        # Waterfall image buffer (will be resized on first paint)
        self._wf_image: QImage | None = None
        self._wf_height = 0
        self._wf_width  = 0

        # Smoothing
        self._smooth     = np.zeros(1024)
        self._alpha      = 0.3   # smoothing factor

    def update_fft(self, fft_data: np.ndarray):
        """Receive new FFT data from audio engine."""
        if fft_data is None or len(fft_data) == 0:
            return

        # Resize internal buffer to match FFT length
        n = len(fft_data)
        if len(self._smooth) != n:
            self._smooth   = np.zeros(n)
            self._fft_data = np.zeros(n)

        # Exponential moving average for smooth spectrum
        self._smooth    = self._alpha * fft_data + (1 - self._alpha) * self._smooth
        self._fft_data  = self._smooth

        # Scroll waterfall and add new line
        self._append_waterfall_line(fft_data)

        self.update()   # trigger paintEvent

    def _append_waterfall_line(self, fft_data: np.ndarray):
        """Add one new row to the waterfall image."""
        w = self.width()
        h = self.height()
        if w < 4 or h < 4:
            return

        wf_h = max(10, int(h * 0.60))

        # (Re)create image buffer if size changed
        if (self._wf_image is None
                or self._wf_width != w
                or self._wf_height != wf_h):
            self._wf_image  = QImage(w, wf_h, QImage.Format.Format_RGB888)
            self._wf_image.fill(QColor(0, 0, 20))
            self._wf_width  = w
            self._wf_height = wf_h

        # Scroll image down by 1 pixel
        region = self._wf_image.copy(0, 0, w, wf_h - 1)
        painter = QPainter(self._wf_image)
        painter.drawImage(0, 1, region)

        # Resample FFT to image width
        n = len(fft_data)
        if n != w:
            indices = np.linspace(0, n - 1, w).astype(int)
            row_data = fft_data[indices]
        else:
            row_data = fft_data

        # Map dB range to 0–255
        norm = np.clip(
            (row_data - self._floor_db) / (self._ceil_db - self._floor_db),
            0.0, 1.0
        )
        pixels = (norm * 255).astype(np.uint8)

        # Draw top row pixel-by-pixel
        for x, val in enumerate(pixels):
            r, g, b = COLORMAP[val]
            painter.setPen(QPen(QColor(r, g, b)))
            painter.drawPoint(x, 0)

        painter.end()

    def paintEvent(self, event):
        if self.width() < 4 or self.height() < 4:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        sp_h = int(h * 0.40)   # spectrum height
        wf_y = sp_h + 1        # waterfall start y

        # ── Background ───────────────────────────────────────────────────────
        painter.fillRect(0, 0, w, sp_h, QColor(10, 12, 18))
        painter.fillRect(0, sp_h, w, h - sp_h, QColor(0, 0, 20))

        # ── Spectrum line ─────────────────────────────────────────────────────
        n = len(self._fft_data)
        if n > 1:
            # Resample to widget width
            if n != w:
                xs = np.linspace(0, n - 1, w).astype(int)
                data = self._fft_data[xs]
            else:
                data = self._fft_data

            norm = np.clip(
                (data - self._floor_db) / (self._ceil_db - self._floor_db),
                0.0, 1.0
            )
            ys = ((1.0 - norm) * (sp_h - 4) + 2).astype(int)

            pen = QPen(QColor(0, 200, 80), 1)
            painter.setPen(pen)
            for x in range(1, w):
                painter.drawLine(x - 1, ys[x - 1], x, ys[x])

            # Fill under line
            fill_color = QColor(0, 200, 80, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill_color)
            from PyQt6.QtGui import QPolygon
            from PyQt6.QtCore import QPoint
            pts = [QPoint(0, sp_h)]
            for x in range(w):
                pts.append(QPoint(x, ys[x]))
            pts.append(QPoint(w - 1, sp_h))
            painter.drawPolygon(QPolygon(pts))

        # ── Grid lines ────────────────────────────────────────────────────────
        painter.setPen(QPen(QColor(40, 40, 60), 1, Qt.PenStyle.DotLine))
        for frac in [0.25, 0.5, 0.75]:
            y = int(sp_h * frac)
            painter.drawLine(0, y, w, y)
            db_val = self._floor_db + (1.0 - frac) * (self._ceil_db - self._floor_db)
            painter.setPen(QPen(QColor(80, 80, 100)))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(2, y - 2, f"{db_val:.0f}dB")
            painter.setPen(QPen(QColor(40, 40, 60), 1, Qt.PenStyle.DotLine))

        # ── Divider ───────────────────────────────────────────────────────────
        painter.setPen(QPen(QColor(40, 60, 80), 1))
        painter.drawLine(0, sp_h, w, sp_h)

        # ── Waterfall image ───────────────────────────────────────────────────
        if self._wf_image and self._wf_width == w:
            painter.drawImage(0, wf_y, self._wf_image)

        # ── Axis labels ───────────────────────────────────────────────────────
        painter.setPen(QPen(QColor(100, 120, 140)))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(2, h - 4, "0 Hz")
        painter.drawText(w // 2 - 20, h - 4, "12 kHz")
        painter.drawText(w - 40, h - 4, "24 kHz")

        # ── Labels ────────────────────────────────────────────────────────────
        painter.setPen(QPen(QColor(60, 80, 100)))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(2, 10, "SPECTRUM")
        painter.drawText(2, wf_y + 12, "WATERFALL")

        painter.end()

    def set_range(self, floor_db: float, ceil_db: float):
        self._floor_db = floor_db
        self._ceil_db  = ceil_db

    def set_smoothing(self, alpha: float):
        self._alpha = max(0.01, min(1.0, alpha))

"""Small custom-painted widgets used by the Catalog visual prototype."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget


class GradientLabel(QWidget):
    """A crisp, static gradient text label without browser-style CSS tricks."""

    def __init__(
        self,
        text: str,
        font_family: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        font = QFont(self.font())
        if font_family:
            font.setFamily(font_family)
        font.setPointSize(29)
        font.setWeight(QFont.Weight.ExtraBold)
        self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _apply_brand_font(self) -> None:
        font = QFont(self.font())
        font.setFamily("Onest")
        font.setPixelSize(29)
        font.setWeight(QFont.Weight.ExtraBold)
        self.setFont(font)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_brand_font()
        super().showEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.StyleChange:
            self._apply_brand_font()
        super().changeEvent(event)

    def sizeHint(self) -> QSize:
        metrics = QFontMetricsF(self.font())
        return QSize(
            round(metrics.horizontalAdvance(self._text) + 2),
            round(metrics.height() + 4),
        )

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        metrics = QFontMetricsF(self.font())
        baseline = (self.height() - metrics.height()) / 2 + metrics.ascent()
        path = QPainterPath()
        path.addText(1, baseline, self.font(), self._text)
        gradient = QLinearGradient(0, 0, max(1, self.width()), 0)
        gradient.setColorAt(0.0, QColor("#fffaff"))
        gradient.setColorAt(0.48, QColor("#e6d8ff"))
        gradient.setColorAt(1.0, QColor("#ab69ff"))
        painter.fillPath(path, gradient)


class AmbientHeader(QWidget):
    """Catalog header surface with a pair of static, low-opacity light blooms."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_bloom(painter, self.width() * 0.16, self.height() * 0.48, self.width() * 0.22, 34)
        self._paint_bloom(painter, self.width() * 0.82, self.height() * 0.48, self.width() * 0.16, 15)

    @staticmethod
    def _paint_bloom(painter: QPainter, x: float, y: float, radius: float, alpha: int) -> None:
        gradient = QRadialGradient(x, y, max(1.0, radius))
        gradient.setColorAt(0.0, QColor(164, 92, 255, alpha))
        gradient.setColorAt(0.48, QColor(132, 73, 210, max(1, alpha // 2)))
        gradient.setColorAt(1.0, QColor(105, 57, 170, 0))
        painter.fillRect(painter.viewport(), gradient)

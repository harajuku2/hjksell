"""Small custom-painted widgets used by the Catalog visual prototype."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


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
        self._font_family = font_family or self.font().family()
        font = QFont(self.font())
        font.setFamily(self._font_family)
        font.setPointSize(29)
        font.setWeight(QFont.Weight.ExtraBold)
        self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _apply_brand_font(self) -> None:
        font = QFont(self.font())
        font.setFamily(self._font_family)
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
        self._paint_bloom(painter, self.width() * 0.16, self.height() * 0.48, self.width() * 0.22, 18)
        self._paint_bloom(painter, self.width() * 0.82, self.height() * 0.48, self.width() * 0.16, 9)

    @staticmethod
    def _paint_bloom(painter: QPainter, x: float, y: float, radius: float, alpha: int) -> None:
        gradient = QRadialGradient(x, y, max(1.0, radius))
        gradient.setColorAt(0.0, QColor(164, 92, 255, alpha))
        gradient.setColorAt(0.48, QColor(132, 73, 210, max(1, alpha // 2)))
        gradient.setColorAt(1.0, QColor(105, 57, 170, 0))
        painter.fillRect(painter.viewport(), gradient)


class CatalogBackdrop(QWidget):
    """Continuous graphite backplate with restrained atmospheric light."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#070811"))
        self._paint_zone(painter, self.width() * 0.10, self.height() * 0.10, self.width() * 0.62, QColor(91, 55, 157, 68))
        self._paint_zone(painter, self.width() * 0.84, self.height() * 0.34, self.width() * 0.48, QColor(45, 58, 150, 46))
        self._paint_zone(painter, self.width() * 0.78, self.height() * 0.86, self.width() * 0.56, QColor(62, 36, 137, 48))
        self._paint_zone(painter, self.width() * 0.38, self.height() * 0.98, self.width() * 0.42, QColor(117, 43, 156, 38))
        self._paint_zone(painter, self.width() * 0.46, self.height() * 0.48, self.width() * 0.32, QColor(84, 42, 137, 24))

    @staticmethod
    def _paint_zone(painter: QPainter, x: float, y: float, radius: float, color: QColor) -> None:
        gradient = QRadialGradient(x, y, max(1.0, radius))
        center = QColor(color)
        edge = QColor(color)
        edge.setAlpha(0)
        gradient.setColorAt(0.0, center)
        gradient.setColorAt(0.55, QColor(center.red(), center.green(), center.blue(), center.alpha() // 2))
        gradient.setColorAt(1.0, edge)
        painter.fillRect(painter.viewport(), gradient)


class PhotoSurface(QLabel):
    """Rounded image well that blends unused aspect-ratio space into the island."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        well = self.rect().adjusted(1, 1, -1, -1)
        well_path = QPainterPath()
        well_path.addRoundedRect(well, 14, 14)
        painter.fillPath(well_path, QColor(9, 10, 18, 205))
        painter.setClipPath(well_path)
        pixmap = self.pixmap()
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                well.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                well.center().x() - scaled.width() // 2,
                well.center().y() - scaled.height() // 2,
                scaled,
            )
        elif self.text():
            painter.setPen(QColor("#91899c"))
            painter.drawText(well, Qt.AlignmentFlag.AlignCenter, self.text())
        painter.setClipping(False)
        painter.setPen(QColor(169, 131, 220, 90))
        painter.drawPath(well_path)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

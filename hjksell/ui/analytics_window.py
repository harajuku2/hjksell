"""The standalone detailed analytics screen."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from ..database.models import Portfolio
from ..repositories.item_repository import ItemRepository
from ..repositories.portfolio_repository import PortfolioRepository
from ..services.analytics import AnalyticsService, PeriodPreset
from .neon_widgets import GradientLabel
from .typography import Typography, TypographyRole


class MiniLineChart(QWidget):
    """A dependency-free, dark line chart suitable for a compact dashboard."""

    def __init__(
        self,
        title: str,
        typography: Typography,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.typography = typography
        self.labels: list[str] = []
        self.values: list[float] = []
        self.setMinimumHeight(170)

    def set_data(self, labels: list[str], values: list[Decimal]) -> None:
        self.labels = labels
        self.values = [float(value) if value.is_finite() else 0.0 for value in values]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101014"))
        painter.setFont(self.typography.font(TypographyRole.SECTION_HEADING))
        painter.setPen(QColor("#cfc2df"))
        painter.drawText(14, 22, self.title)
        left, top, right, bottom = 14, 36, self.width() - 12, self.height() - 28
        if right <= left or bottom <= top:
            return
        painter.setPen(QPen(QColor("#2d2638"), 1))
        painter.drawLine(left, bottom, right, bottom)
        if not self.values:
            painter.setFont(self.typography.font(TypographyRole.SUPPORTING_TEXT))
            painter.setPen(QColor("#91899c"))
            painter.drawText(left, (top + bottom) // 2, "Нет данных за период")
            return
        low, high = min(0.0, min(self.values)), max(0.0, max(self.values))
        if math.isclose(low, high):
            high = low + 1.0
        width = max(1, right - left)
        height = max(1, bottom - top)

        def point(index: int) -> tuple[int, int]:
            x = left + int(width * index / max(1, len(self.values) - 1))
            y = top + int((high - self.values[index]) / (high - low) * height)
            return x, y

        zero_y = top + int((high / (high - low)) * height)
        painter.setPen(QPen(QColor("#493b58"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(left, zero_y, right, zero_y)
        path = QPainterPath()
        first = point(0)
        path.moveTo(*first)
        for index in range(1, len(self.values)):
            path.lineTo(*point(index))
        painter.setPen(QPen(QColor("#a66be0"), 2))
        painter.drawPath(path)
        painter.setBrush(QColor("#c9a6ee"))
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(len(self.values)):
            x, y = point(index)
            painter.drawEllipse(x - 3, y - 3, 6, 6)
        painter.setPen(QColor("#91899c"))
        for index, label in enumerate(self.labels):
            if index in (0, len(self.labels) - 1) or len(self.labels) <= 6:
                x, _y = point(index)
                painter.drawText(x - 26, bottom + 18, label)


def _decimal(value: Decimal | None, suffix: str = " BYN") -> str:
    return "—" if value is None else f"{value:.2f}{suffix}"


def _tone(value: Decimal | None) -> str:
    if value is None or value == 0:
        return "neutral"
    return "positive" if value > 0 else "negative"


class AnalyticsWindow(QMainWindow):
    """Premium-dark analytics window with a portfolio and period scope."""

    def __init__(
        self,
        session_factory: Callable,
        selected_portfolio_id: int | None = None,
        parent: QWidget | None = None,
        typography: Typography | None = None,
    ) -> None:
        super().__init__(parent)
        self.session_factory = session_factory
        self.portfolios: list[Portfolio] = []
        self.current_portfolio_id = selected_portfolio_id
        self.typography = typography or Typography.fallback()
        self.setWindowTitle("HJKsell — АНАЛИТИКА")
        self.resize(1080, 760)
        self.setMinimumSize(820, 600)
        self._build_ui()
        self._load_portfolios()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("analyticsRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        header_surface = QWidget()
        header_surface.setObjectName("analyticsHeader")
        header = QHBoxLayout(header_surface)
        header.setContentsMargins(2, 0, 2, 2)
        header.setSpacing(10)
        title = GradientLabel("АНАЛИТИКА", self.typography.family(TypographyRole.DISPLAY))
        title.setObjectName("analyticsTitle")
        header.addWidget(title)
        header.addSpacing(12)
        self.portfolio_tabs = QTabBar()
        self.portfolio_tabs.setObjectName("analyticsPortfolioTabs")
        self.portfolio_tabs.currentChanged.connect(self._portfolio_changed)
        header.addWidget(self.portfolio_tabs)
        header.addStretch()
        period_label = QLabel("ПЕРИОД")
        period_label.setObjectName("analyticsControlLabel")
        header.addWidget(period_label)
        self.period_combo = QComboBox()
        self.period_combo.setObjectName("analyticsPeriodCombo")
        for preset, text in (
            (PeriodPreset.CURRENT_MONTH, "Текущий месяц"),
            (PeriodPreset.PREVIOUS_MONTH, "Предыдущий месяц"),
            (PeriodPreset.THREE_MONTHS, "3 месяца"),
            (PeriodPreset.SIX_MONTHS, "6 месяцев"),
            (PeriodPreset.CURRENT_YEAR, "Текущий год"),
            (PeriodPreset.ALL_TIME, "Всё время"),
        ):
            self.period_combo.addItem(text, preset)
        self.period_combo.currentIndexChanged.connect(self.refresh)
        header.addWidget(self.period_combo)
        back = QPushButton("← КАТАЛОГ")
        back.setObjectName("analyticsBack")
        back.clicked.connect(self.close)
        header.addWidget(back)
        layout.addWidget(header_surface)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("analyticsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 2, 6, 10)
        content_layout.setSpacing(10)
        self.period_label = QLabel()
        self.period_label.setObjectName("analyticsSubtitle")
        content_layout.addWidget(self.period_label)
        self.metric_labels: dict[str, QLabel] = {}
        sections = (
            (
                "РЕЗУЛЬТАТ",
                "analyticsPrimarySection",
                (
                    ("revenue", "ПРОДАЖИ"),
                    ("realized_profit", "РЕАЛИЗОВАННАЯ ПРИБЫЛЬ"),
                    ("net_profit", "ЧИСТАЯ ПРИБЫЛЬ"),
                    ("expenses", "РАСХОДЫ"),
                    ("sold_count", "ПРОДАНО"),
                ),
                "analyticsPrimaryValue",
            ),
            (
                "ЭФФЕКТИВНОСТЬ",
                "analyticsSection",
                (
                    ("roi", "ROI"),
                    ("roi_after_expenses", "ROI ПОСЛЕ РАСХОДОВ"),
                    ("average_x", "СРЕДНИЙ X"),
                    ("best_x", "ЛУЧШИЙ X"),
                    ("worst_x", "ХУДШИЙ X"),
                ),
                "analyticsValue",
            ),
            (
                "ЗАКУПКИ И СКЛАД",
                "analyticsSection",
                (
                    ("invested", "ВЛОЖЕНО"),
                    ("purchased_count", "КУПЛЕНО"),
                    ("in_stock_count", "В НАЛИЧИИ"),
                    ("warehouse_value", "СТОИМОСТЬ НА СКЛАДЕ"),
                ),
                "analyticsValue",
            ),
            (
                "СРЕДНИЕ ПОКАЗАТЕЛИ",
                "analyticsSection",
                (
                    ("average_cost", "СРЕДНЯЯ СЕБЕСТОИМОСТЬ"),
                    ("average_sale", "СРЕДНЯЯ ПРОДАЖА"),
                    ("average_profit", "СРЕДНЯЯ ПРИБЫЛЬ"),
                    ("average_sale_days", "СРЕДНЕЕ ВРЕМЯ ПРОДАЖИ"),
                ),
                "analyticsValue",
            ),
        )
        for title, section_object_name, fields, value_object_name in sections:
            section = QGroupBox(title)
            section.setObjectName(section_object_name)
            section_layout = QGridLayout(section)
            section_layout.setContentsMargins(14, 22, 14, 12)
            section_layout.setHorizontalSpacing(10)
            section_layout.setVerticalSpacing(8)
            for index, (key, label) in enumerate(fields):
                card = QWidget()
                card.setObjectName("analyticsMetricCell")
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(10, 8, 10, 8)
                card_layout.setSpacing(3)
                value = QLabel("—")
                value.setObjectName("analyticsHeroValue" if key == "net_profit" else value_object_name)
                caption = QLabel(label)
                caption.setObjectName("analyticsMetricLabel")
                card_layout.addWidget(value)
                card_layout.addWidget(caption)
                self.metric_labels[key] = value
                columns = 5 if title in {"РЕЗУЛЬТАТ", "ЭФФЕКТИВНОСТЬ"} else 4
                section_layout.addWidget(card, index // columns, index % columns)
            content_layout.addWidget(section)
        charts = QHBoxLayout()
        charts.setSpacing(10)
        self.revenue_chart = MiniLineChart("ПРОДАЖИ ПО МЕСЯЦАМ", self.typography)
        self.revenue_chart.setObjectName("analyticsChart")
        self.profit_chart = MiniLineChart("ЧИСТАЯ ПРИБЫЛЬ ПО МЕСЯЦАМ", self.typography)
        self.profit_chart.setObjectName("analyticsChart")
        self.invested_chart = MiniLineChart("ВЛОЖЕНО ПО МЕСЯЦАМ", self.typography)
        self.invested_chart.setObjectName("analyticsChart")
        charts.addWidget(self.revenue_chart)
        charts.addWidget(self.profit_chart)
        charts.addWidget(self.invested_chart)
        content_layout.addLayout(charts)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.setCentralWidget(root)

    def _repolish_metric_labels(self) -> None:
        for label in self.metric_labels.values():
            style = label.style()
            style.unpolish(label)
            style.polish(label)
            label.update()

    def _load_portfolios(self) -> None:
        with self.session_factory() as session:
            all_portfolios = PortfolioRepository(session).list_all()
            self.portfolios = [portfolio for portfolio in all_portfolios if portfolio.id in {1, 2}]
        self.portfolio_tabs.blockSignals(True)
        while self.portfolio_tabs.count() > 0:
            self.portfolio_tabs.removeTab(0)
        for portfolio in self.portfolios:
            self.portfolio_tabs.addTab(portfolio.name)
        self.portfolio_tabs.blockSignals(False)
        if self.current_portfolio_id is None and self.portfolios:
            self.current_portfolio_id = self.portfolios[0].id
        selected = next(
            (index for index, portfolio in enumerate(self.portfolios) if portfolio.id == self.current_portfolio_id),
            0,
        )
        self.portfolio_tabs.setCurrentIndex(selected)
        self.refresh()

    def reload_portfolios(self) -> None:
        self._load_portfolios()

    def _portfolio_changed(self, index: int) -> None:
        if 0 <= index < len(self.portfolios):
            self.current_portfolio_id = self.portfolios[index].id
            self.refresh()

    def refresh(self) -> None:
        if self.current_portfolio_id is None:
            return
        preset = self.period_combo.currentData()
        with self.session_factory() as session:
            service = AnalyticsService(ItemRepository(session))
            period = service.resolve_period(preset)
            metrics = service.detailed_metrics(self.current_portfolio_id, period)
            monthly = service.monthly_breakdown(self.current_portfolio_id, period)
        self.period_label.setText(f"{period.start_date.isoformat()} — {period.end_date.isoformat()}")
        money_fields = {"revenue", "realized_profit", "net_profit", "expenses", "average_cost", "average_sale", "average_profit", "warehouse_value"}
        percent_fields = {"roi", "roi_after_expenses"}
        x_fields = {"average_x", "best_x", "worst_x"}
        day_fields = {"average_sale_days"}
        for key, label in self.metric_labels.items():
            value = getattr(metrics, key)
            if key in money_fields:
                text = _decimal(value)
            elif key in percent_fields:
                text = _decimal(value, "%")
            elif key in x_fields:
                text = _decimal(value, "x")
            elif key in day_fields:
                text = _decimal(value, " дн.")
            else:
                text = str(value)
            label.setText(text)
            if key == "expenses":
                label.setProperty("tone", "amber")
            elif key in {"realized_profit", "net_profit", "roi", "roi_after_expenses", "average_profit"}:
                label.setProperty("tone", _tone(value))
            else:
                label.setProperty("tone", "neutral")
            label.style().unpolish(label)
            label.style().polish(label)
        self._repolish_metric_labels()
        labels = [entry.label for entry in monthly]
        self.revenue_chart.set_data(labels, [entry.revenue for entry in monthly])
        self.profit_chart.set_data(labels, [entry.net_profit for entry in monthly])
        self.invested_chart.set_data(labels, [entry.invested for entry in monthly])

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self._repolish_metric_labels()

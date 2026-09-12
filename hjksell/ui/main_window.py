"""The dense, spreadsheet-like catalogue window for HJKsell."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ..config import AppPaths, ensure_app_directories, get_app_paths
from ..database.connection import initialize_database
from ..database.models import Item, ItemStatus, Portfolio
from ..repositories.item_repository import ItemRepository
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.settings_repository import SettingsRepository
from ..services.analytics import AnalyticsService, MonthlyMetrics
from ..services.finance import calculate_cost, item_metrics, parse_decimal
from ..services.items import ItemService
from ..services.photos import PhotoService


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class PhotoViewer(QDialog):
    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Фото")
        self.setModal(True)
        self.resize(720, 720)
        layout = QVBoxLayout(self)
        close = QToolButton()
        close.setText("✕")
        close.clicked.connect(self.accept)
        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(close)
        layout.addLayout(top)
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            image.setPixmap(pixmap.scaled(680, 650, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            image.setText("Фото недоступно")
        layout.addWidget(image, 1)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)


class AddItemDialog(QDialog):
    """Small manual-entry form; the caller owns persistence and photo copying."""

    def __init__(
        self,
        portfolios: list[Portfolio],
        selected_portfolio: int,
        current_rate: Decimal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добавить вещь")
        self.setMinimumWidth(430)
        layout = QFormLayout(self)
        self.photo_edit = QLineEdit()
        browse = QPushButton("Выбрать…")
        browse.clicked.connect(self._browse)
        photo_row = QHBoxLayout()
        photo_row.addWidget(self.photo_edit, 1)
        photo_row.addWidget(browse)
        photo_widget = QWidget()
        photo_widget.setLayout(photo_row)
        self.portfolio = QComboBox()
        for portfolio in portfolios:
            self.portfolio.addItem(portfolio.name, portfolio.id)
        index = self.portfolio.findData(selected_portfolio)
        if index >= 0:
            self.portfolio.setCurrentIndex(index)
        self.price = QLineEdit()
        self.price.setPlaceholderText("например, 150 или 150,50")
        self.current_rate = current_rate
        self.cost_preview = QLabel("—")
        self.price.textChanged.connect(self._update_cost)
        self.purchase_date = QLineEdit(date.today().isoformat())
        self.purchase_date.setPlaceholderText("ГГГГ-ММ-ДД")
        layout.addRow("Фото *", photo_widget)
        layout.addRow("Портфель", self.portfolio)
        layout.addRow("Цена PLN *", self.price)
        layout.addRow(f"Себестоимость BYN (курс {current_rate:.4f})", self.cost_preview)
        layout.addRow("Дата *", self.purchase_date)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите фото", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif)")
        if path:
            self.photo_edit.setText(path)

    def _update_cost(self, text: str) -> None:
        try:
            self.cost_preview.setText(f"{calculate_cost(parse_decimal(text, positive=True), self.current_rate):.2f} BYN")
        except (ValueError, ArithmeticError):
            self.cost_preview.setText("—")

    def values(self) -> tuple[str, int, str, date]:
        source = self.photo_edit.text().strip()
        if not source:
            raise ValueError("Выберите фотографию.")
        try:
            purchase_date = date.fromisoformat(self.purchase_date.text().strip())
        except ValueError as exc:
            raise ValueError("Дата должна быть в формате ГГГГ-ММ-ДД.") from exc
        return source, int(self.portfolio.currentData()), self.price.text(), purchase_date


class MainWindow(QMainWindow):
    """Main catalogue UI. Database operations stay in repositories/services."""

    def __init__(
        self,
        session_factory: Callable | None = None,
        paths: AppPaths | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("HJKsell")
        self.resize(1120, 820)
        self.setMinimumSize(800, 600)
        self.paths = ensure_app_directories(paths or get_app_paths())
        if session_factory is None:
            _engine, session_factory = initialize_database(self.paths)
        self.session_factory = session_factory
        self.photo_service = PhotoService(self.paths)
        self.current_filter = "all"
        self.current_portfolio_id: int | None = None
        self._build_ui()
        self._load_portfolios()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 14, 18, 12)
        root_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        self.portfolio_tabs = QTabBar()
        self.portfolio_tabs.setExpanding(False)
        self.portfolio_tabs.currentChanged.connect(self._portfolio_changed)
        toolbar.addWidget(self.portfolio_tabs)
        toolbar.addSpacing(16)
        rate_label = QLabel("PLN → BYN")
        self.rate_edit = QLineEdit()
        self.rate_edit.setObjectName("exchangeRate")
        self.rate_edit.setFixedWidth(90)
        self.rate_edit.setToolTip("Текущий курс для новых покупок")
        self.rate_edit.returnPressed.connect(self._save_rate)
        self.rate_edit.editingFinished.connect(self._save_rate)
        toolbar.addWidget(rate_label)
        toolbar.addWidget(self.rate_edit)
        toolbar.addStretch()
        self.add_button = QPushButton("+ Добавить")
        self.add_button.clicked.connect(self._add_item)
        toolbar.addWidget(self.add_button)
        root_layout.addLayout(toolbar)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Показать:"))
        self.filter_buttons: dict[str, QRadioButton] = {}
        for key, text in (("all", "Все"), ("stock", "В наличии"), ("sold", "Продано")):
            button = QRadioButton(text)
            button.setProperty("filter", key)
            button.clicked.connect(lambda checked, value=key: self._set_filter(value))
            self.filter_buttons[key] = button
            filters.addWidget(button)
        self.filter_buttons["all"].setChecked(True)
        filters.addStretch()
        root_layout.addLayout(filters)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.catalogue = QWidget()
        self.catalogue_layout = QVBoxLayout(self.catalogue)
        self.catalogue_layout.setContentsMargins(0, 0, 8, 0)
        self.catalogue_layout.setSpacing(10)
        self.scroll.setWidget(self.catalogue)
        root_layout.addWidget(self.scroll, 1)
        self.setCentralWidget(root)

    def _load_portfolios(self) -> None:
        with self.session_factory() as session:
            portfolios = PortfolioRepository(session).list_all()
            self.portfolios = portfolios
            for portfolio in portfolios:
                self.portfolio_tabs.addTab(portfolio.name)
            if portfolios:
                self.current_portfolio_id = portfolios[0].id
            settings = SettingsRepository(session)
            self.rate_edit.setText(f"{settings.current_exchange_rate():.4f}")
            session.commit()
        self.refresh()

    def _portfolio_changed(self, index: int) -> None:
        if 0 <= index < len(self.portfolios):
            self.current_portfolio_id = self.portfolios[index].id
            self.refresh()

    def _set_filter(self, value: str) -> None:
        self.current_filter = value
        self.refresh()

    def _save_rate(self) -> None:
        try:
            value = parse_decimal(self.rate_edit.text(), field_name="курс", positive=True)
            with self.session_factory() as session:
                SettingsRepository(session).set_exchange_rate(value)
                session.commit()
            self.rate_edit.setText(f"{value.quantize(Decimal('0.0001')):.4f}")
        except (ValueError, ArithmeticError) as exc:
            QMessageBox.warning(self, "Курс", str(exc))
            with self.session_factory() as session:
                self.rate_edit.setText(f"{SettingsRepository(session).current_exchange_rate():.4f}")

    @staticmethod
    def _months(items: list[Item]) -> list[tuple[int, int]]:
        periods = {(item.purchase_date.year, item.purchase_date.month) for item in items}
        today = date.today()
        periods.add((today.year, today.month))
        return sorted(periods, reverse=True)

    def refresh(self) -> None:
        if self.current_portfolio_id is None:
            return
        while self.catalogue_layout.count():
            child = self.catalogue_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        with self.session_factory() as session:
            repository = ItemRepository(session)
            all_items = repository.active_items(self.current_portfolio_id)
            status = {"stock": ItemStatus.IN_STOCK.value, "sold": ItemStatus.SOLD.value}.get(self.current_filter)
            visible = [item for item in all_items if status is None or item.status == status]
            analytics = AnalyticsService(repository)
            if not visible:
                if not all_items:
                    empty_widget = QWidget()
                    empty_layout = QVBoxLayout(empty_widget)
                    empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    empty = QLabel("В этом портфеле пока нет вещей")
                    empty.setObjectName("emptyState")
                    empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    add_first = QPushButton("+ Добавить первую вещь")
                    add_first.clicked.connect(self._add_item)
                    empty_layout.addWidget(empty)
                    empty_layout.addWidget(add_first, alignment=Qt.AlignmentFlag.AlignCenter)
                    self.catalogue_layout.addWidget(empty_widget)
                else:
                    empty = QLabel("Нет вещей по выбранному фильтру")
                    empty.setObjectName("emptyState")
                    empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    empty.setMinimumHeight(180)
                    self.catalogue_layout.addWidget(empty)
            for year, month in self._months(all_items):
                month_items = [item for item in visible if item.purchase_date.year == year and item.purchase_date.month == month]
                metrics = analytics.monthly_metrics(self.current_portfolio_id, year, month)
                self.catalogue_layout.addWidget(self._month_group(session, year, month, month_items, metrics))
        self.catalogue_layout.addStretch()

    def _month_group(self, session, year: int, month: int, items: list[Item], metrics: MonthlyMetrics) -> QWidget:
        names = ("ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ")
        group = QGroupBox()
        group.setCheckable(True)
        group.setChecked((year, month) == (date.today().year, date.today().month))
        group.setTitle(f"{names[month - 1]} {year}")
        outer = QVBoxLayout(group)
        stats = QLabel(self._stats_text(metrics))
        stats.setObjectName("monthlyStats")
        outer.addWidget(stats)
        expense = QLineEdit(f"{metrics.expenses:.2f}")
        expense.setObjectName("monthlyExpense")
        expense.setPlaceholderText("Расходы BYN")
        expense.setMaximumWidth(140)
        expense.setToolTip("Расходы месяца в BYN")
        expense.editingFinished.connect(lambda e=expense, y=year, m=month: self._save_expense(e, y, m))
        expense_row = QHBoxLayout()
        expense_row.addWidget(QLabel("Расходы BYN:"))
        expense_row.addWidget(expense)
        expense_row.addStretch()
        outer.addLayout(expense_row)
        items_container = QWidget()
        items_layout = QVBoxLayout(items_container)
        items_layout.setContentsMargins(0, 4, 0, 0)
        for item in items:
            items_layout.addWidget(self._item_row(item))
        outer.addWidget(items_container)
        group.toggled.connect(items_container.setVisible)
        items_container.setVisible(group.isChecked())
        return group

    @staticmethod
    def _stats_text(metrics: MonthlyMetrics) -> str:
        average_x = "—" if metrics.average_x is None else f"{metrics.average_x:.2f}x"
        roi = "—" if metrics.roi is None else f"{metrics.roi:.2f}%"
        return (
            f"Вложено: {metrics.invested:.2f} BYN   Куплено: {metrics.purchased_count}   "
            f"Продано: {metrics.sold_count}   Продажи: {metrics.revenue:.2f} BYN   "
            f"X: {average_x}   ROI: {roi}   Чистая прибыль: {metrics.net_profit:.2f} BYN"
        )

    def _item_row(self, item: Item) -> QWidget:
        row = QFrameCard()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        photo = ClickableLabel()
        photo.setFixedSize(180, 180)
        photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        photo.setStyleSheet("background:#30343a;")
        if item.photo_path and Path(item.photo_path).is_file():
            photo.setPixmap(QPixmap(item.photo_path).scaled(175, 175, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            photo.clicked.connect(lambda path=item.photo_path: PhotoViewer(path, self).exec())
        else:
            photo.setText("Нет фото")
        layout.addWidget(photo)
        details = QVBoxLayout()
        details.addWidget(QLabel(f"Куплено {item.purchase_price_pln:.2f} PLN"))
        details.addWidget(QLabel(f"Себестоимость {item.cost_byn:.2f} BYN"))
        details.addWidget(QLabel(f"Курс {item.exchange_rate:.4f}"))
        details.addWidget(QLabel(f"Дата {item.purchase_date:%d.%m.%Y}"))
        metrics = item_metrics(item.sale_price_byn, item.cost_byn)
        if item.status == ItemStatus.SOLD.value and item.sale_price_byn is not None:
            details.addWidget(QLabel(f"ПРОДАНО {item.sale_price_byn:.2f} BYN"))
            details.addWidget(QLabel(f"Прибыль {metrics.profit:+.2f} BYN   X {metrics.x:.2f}x   ROI {metrics.roi:+.2f}%"))
            if item.sale_date:
                details.addWidget(QLabel(f"Продано {item.sale_date:%d.%m.%Y} ({(item.sale_date - item.purchase_date).days} дней)"))
        else:
            sale = QLineEdit()
            sale.setPlaceholderText("Продажа BYN — Enter")
            sale.setObjectName("saleInput")
            sale.returnPressed.connect(lambda edit=sale, current=item: self._sell(current, edit))
            details.addWidget(sale)
            details.addWidget(QLabel("Продажа —   Прибыль —   X —   ROI —"))
        layout.addLayout(details, 1)
        menu_button = QToolButton()
        menu_button.setText("⋯")
        menu = QMenu(menu_button)
        replace = QAction("Заменить фото", menu)
        replace.triggered.connect(lambda current=item: self._replace_photo(current))
        delete = QAction("Удалить", menu)
        delete.triggered.connect(lambda current=item: self._delete_item(current))
        menu.addAction(replace)
        menu.addAction(delete)
        menu_button.setMenu(menu)
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        layout.addWidget(menu_button, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _sell(self, item: Item, edit: QLineEdit) -> None:
        try:
            with self.session_factory() as session:
                current = ItemRepository(session).get(item.id, self.current_portfolio_id)
                if current is None:
                    raise ValueError("Вещь больше недоступна.")
                ItemService(ItemRepository(session), SettingsRepository(session)).sell(current, edit.text())
                session.commit()
            self.refresh()
        except ValueError as exc:
            edit.setStyleSheet("border:1px solid #df6262;")
            edit.setToolTip(str(exc))

    def _save_expense(self, edit: QLineEdit, year: int, month: int) -> None:
        try:
            value = parse_decimal(edit.text(), field_name="расходы")
            if value < 0:
                raise ValueError("Расходы не могут быть отрицательными.")
            with self.session_factory() as session:
                ItemRepository(session).set_monthly_expense(self.current_portfolio_id, year, month, value.quantize(Decimal("0.01")))
                session.commit()
            self.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Расходы", str(exc))

    def _add_item(self) -> None:
        try:
            current_rate = parse_decimal(self.rate_edit.text(), field_name="курс", positive=True)
        except ValueError:
            current_rate = Decimal("0.8500")
        dialog = AddItemDialog(self.portfolios, self.current_portfolio_id, current_rate, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            source, portfolio_id, price, purchase_date = dialog.values()
            stored_photo = self.photo_service.copy_photo(source)
            with self.session_factory() as session:
                ItemService(ItemRepository(session), SettingsRepository(session)).create_from_text(
                    portfolio_id, price, purchase_date, stored_photo
                )
                session.commit()
            self.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Добавить вещь", str(exc))

    def _replace_photo(self, item: Item) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Выберите новое фото", "", "Images (*.jpg *.jpeg *.png *.webp *.bmp *.gif)")
        if not source:
            return
        try:
            stored = self.photo_service.copy_photo(source)
            with self.session_factory() as session:
                current = ItemRepository(session).get(item.id, self.current_portfolio_id)
                if current:
                    ItemRepository(session).replace_photo(current, stored)
                    session.commit()
            self.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Фото", str(exc))

    def _delete_item(self, item: Item) -> None:
        answer = QMessageBox.question(
            self,
            "Удалить вещь?",
            "Она будет исключена из всей статистики.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        with self.session_factory() as session:
            current = ItemRepository(session).get(item.id, self.current_portfolio_id)
            if current:
                ItemRepository(session).soft_delete(current)
                session.commit()
        self.refresh()


class QFrameCard(QWidget):
    """A light card container, kept as a class for reliable object discovery in UI tests."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("itemCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

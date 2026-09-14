"""Centralized runtime font registration and semantic font roles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QFont, QFontDatabase

logger = logging.getLogger(__name__)


class TypographyRole(StrEnum):
    DISPLAY = "display"
    UI_LABEL = "ui_label"
    UI_CONTROL = "ui_control"
    METRIC = "metric"
    INPUT = "input"
    HERO_FINANCIAL_VALUE = "hero_financial_value"
    PRIMARY_MONEY_VALUE = "primary_money_value"
    METRIC_VALUE = "metric_value"
    METRIC_LABEL = "metric_label"
    SUPPORTING_TEXT = "supporting_text"
    INPUT_VALUE = "input_value"
    SECTION_HEADING = "section_heading"


@dataclass(frozen=True)
class Typography:
    """Registered families used by the application's typography roles."""

    kulag_sha: str
    kulag_sha_outline: str
    oswald: str
    onest: str
    kulag_sha_style: str
    kulag_sha_outline_style: str
    oswald_style: str

    @classmethod
    def fallback(cls) -> "Typography":
        return cls(
            kulag_sha="KULAG SHA",
            kulag_sha_outline="KULAG",
            oswald="Oswald",
            onest="Onest",
            kulag_sha_style="Regular",
            kulag_sha_outline_style="Outline",
            oswald_style="Regular",
        )

    def family(self, role: TypographyRole) -> str:
        del role
        return self.oswald

    @staticmethod
    def pixel_size(role: TypographyRole) -> int:
        return {
            TypographyRole.HERO_FINANCIAL_VALUE: 31,
            TypographyRole.PRIMARY_MONEY_VALUE: 26,
            TypographyRole.METRIC_VALUE: 21,
            TypographyRole.METRIC_LABEL: 15,
            TypographyRole.SUPPORTING_TEXT: 13,
            TypographyRole.INPUT_VALUE: 26,
            TypographyRole.SECTION_HEADING: 19,
        }.get(role, 13)

    def font(
        self,
        role: TypographyRole,
        *,
        pixel_size: int | None = None,
        point_size: int | None = None,
        weight: QFont.Weight | None = None,
    ) -> QFont:
        font = QFont(self.family(role))
        if pixel_size is not None:
            font.setPixelSize(pixel_size)
        if point_size is not None:
            font.setPointSize(point_size)
        if weight is not None:
            font.setWeight(weight)
        return font


def _register_font(
    path: Path,
    *,
    fallback_family: str,
) -> tuple[str, str]:
    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id < 0:
        logger.warning("Font could not be loaded: %s", path)
        return fallback_family, ""
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        logger.warning("Font has no registered family: %s", path)
        return fallback_family, ""
    family = families[0]
    styles = QFontDatabase.styles(family)
    return family, styles[0] if styles else ""


def load_typography(resource_path: Callable[[str], Path]) -> Typography:
    """Register bundled fonts and return discovered family/style metadata."""

    kulag_sha, kulag_sha_style = _register_font(
        resource_path("assets/fonts/kulag-sha/KULAG SHA.otf"),
        fallback_family="Segoe UI",
    )
    kulag_outline, kulag_outline_style = _register_font(
        resource_path("assets/fonts/kulag-sha/KULAG SHA Outline.otf"),
        fallback_family=kulag_sha,
    )
    oswald, oswald_style = _register_font(
        resource_path("assets/fonts/oswald/Oswald[wght].ttf"),
        fallback_family="Segoe UI",
    )
    onest, _onest_style = _register_font(
        resource_path("assets/fonts/onest/Onest[wght].ttf"),
        fallback_family="Segoe UI",
    )
    return Typography(
        kulag_sha=kulag_sha,
        kulag_sha_outline=kulag_outline,
        oswald=oswald,
        onest=onest,
        kulag_sha_style=kulag_sha_style,
        kulag_sha_outline_style=kulag_outline_style,
        oswald_style=oswald_style,
    )

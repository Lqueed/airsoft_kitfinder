"""Перечисления домена. Хранятся в БД как VARCHAR + CHECK (native_enum=False)."""

from enum import StrEnum


class Role(StrEnum):
    """Роль игрока, под которую собран кит."""

    ASSAULT = "assault"  # штурмовик
    SNIPER = "sniper"  # снайпер
    SUPPORT = "support"  # пулемётчик
    DMR = "dmr"  # марксман
    SCOUT = "scout"  # разведчик


class DriveType(StrEnum):
    """Тип привода."""

    AEG = "aeg"  # электро
    GBB = "gbb"  # газобаллонный
    SPRING = "spring"  # пружинный
    HPA = "hpa"  # пневматика на сжатом воздухе


class ExperienceLevel(StrEnum):
    """Уровень опыта игрока (для визарда)."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class KitStatus(StrEnum):
    """Статус публикации кита."""

    DRAFT = "draft"
    PUBLISHED = "published"


class KitItemType(StrEnum):
    """Тип позиции кита."""

    FIXED = "fixed"  # конкретный товар
    FLEXIBLE = "flexible"  # категория + критерии

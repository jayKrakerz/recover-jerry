"""Scanner auto-registration."""

from typing import Optional
from .base import BaseScanner

_registry: dict[str, BaseScanner] = {}


def register_scanner(scanner: BaseScanner) -> None:
    _registry[scanner.source_id] = scanner


def get_scanner(source_id: str) -> Optional[BaseScanner]:
    return _registry.get(source_id)


def get_all_scanners() -> dict[str, BaseScanner]:
    return dict(_registry)


def scanner_registry() -> dict[str, BaseScanner]:
    return dict(_registry)

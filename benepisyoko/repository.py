"""Loads and caches the benefits corpus from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .models import Benefit

DATA_FILE = Path(__file__).parent / "data" / "benefits.yaml"


@lru_cache(maxsize=1)
def load_benefits() -> list[Benefit]:
    raw = yaml.safe_load(DATA_FILE.read_text(encoding="utf-8")) or []
    benefits = [Benefit.model_validate(item) for item in raw]

    ids = [b.id for b in benefits]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"Duplicate benefit ids in corpus: {sorted(duplicates)}")

    return benefits


def get_benefit(benefit_id: str) -> Benefit | None:
    return next((b for b in load_benefits() if b.id == benefit_id), None)


def categories() -> list[str]:
    return sorted({b.category for b in load_benefits()})

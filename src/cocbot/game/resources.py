"""
Resource dataclasses and thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Resources:
    gold: int = 0
    elixir: int = 0
    dark_elixir: int = 0

    def meets_threshold(self, min_gold: int, min_elixir: int, min_dark: int) -> bool:
        """Return True if all thresholds are met."""
        return (
            self.gold >= min_gold
            and self.elixir >= min_elixir
            and self.dark_elixir >= min_dark
        )

    def total_value(self, gold_weight: float = 1.0, elixir_weight: float = 1.0, dark_weight: float = 5.0) -> float:
        """Weighted 'value' score for ranking bases."""
        return (
            self.gold * gold_weight
            + self.elixir * elixir_weight
            + self.dark_elixir * dark_weight
        )

    def __str__(self) -> str:
        return f"Gold={self.gold:,} | Elixir={self.elixir:,} | DE={self.dark_elixir:,}"

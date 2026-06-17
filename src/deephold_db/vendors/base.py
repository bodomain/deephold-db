"""Abstract vendor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import polars as pl


class Vendor(ABC):
    """Base class for all vendor adapters.

    Vendors return raw polars DataFrames. Mapping to instruments and
    DQ/upsert happens in the pipelines layer.
    """

    code: str
    base_url: str

    @abstractmethod
    def fetch(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Fetch raw data for `symbol` in [`start`, `end`] inclusive."""
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> bool:
        """Return True if the vendor is reachable."""
        raise NotImplementedError


__all__ = ["Vendor"]

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class ChronologicalSplit:
    development: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def chronological_split(frame: pd.DataFrame, *, development: float = 0.60, validation: float = 0.20, test: float = 0.20) -> ChronologicalSplit:
    if len(frame) < 3:
        raise ValueError("at least 3 rows are required")
    if any(x <= 0 for x in (development, validation, test)):
        raise ValueError("split proportions must be positive")
    if abs(development + validation + test - 1.0) > 1e-9:
        raise ValueError("split proportions must sum to 1")
    ordered = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
    n = len(ordered)
    dev_end = int(n * development)
    val_end = dev_end + int(n * validation)
    if dev_end == 0 or val_end <= dev_end or val_end >= n:
        raise ValueError("dataset is too small for requested proportions")
    return ChronologicalSplit(
        development=ordered.iloc[:dev_end].copy(),
        validation=ordered.iloc[dev_end:val_end].copy(),
        test=ordered.iloc[val_end:].copy(),
    )

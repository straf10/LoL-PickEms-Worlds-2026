"""Markdown and number-format helpers shared by the report writers."""
import math

import numpy as np
import pandas as pd


def md_table(df: pd.DataFrame, floatfmt: str | None = None) -> str:
    """Markdown table for df. NaN and None cells are blank; floats use floatfmt when one is given."""
    if len(df) == 0:
        return "_(no rows)_"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(_cell(v, floatfmt) for v in row) + " |")
    return "\n".join(lines)


def md_rows(headers: list, rows) -> str:
    """Markdown table from header names and an iterable of row sequences."""
    return md_table(pd.DataFrame(list(rows), columns=headers))


def _cell(v, floatfmt: str | None) -> str:
    if v is None or (pd.api.types.is_scalar(v) and pd.isna(v)):
        return ""
    if floatfmt and isinstance(v, (float, np.floating)):
        return floatfmt.format(v)
    return str(v)


def fmt_num(x, nd: int = 1, missing: str = "-") -> str:
    """Fixed-point number for display; missing (None or NaN) becomes the placeholder."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return missing
    return f"{x:.{nd}f}"


def round_finite(x, nd: int = 4) -> float:
    """float(x) rounded to nd places. Raises on NaN or infinity so JSON output never gets a bad value."""
    x = float(x)
    assert math.isfinite(x), f"non-finite value {x}"
    return round(x, nd)

"""
Calibration interpolation for g9auto.

Provides linear interpolation of laser wavelengths and Rb frequency standard
to any date within the calibration range stored in config.yaml.
"""

import datetime
from typing import Union

import numpy as np


def interpolate(config: dict, date: Union[datetime.date, str]) -> dict:
    """
    Linearly interpolate laser and Rb calibration values for the given date.

    Parameters
    ----------
    config : dict
        Loaded YAML config (must contain a ``calibration`` section with
        ``laser`` and ``rubidium`` sub-sections).
    date : datetime.date or ISO-format string
        Target date for interpolation.

    Returns
    -------
    dict with keys:
        red           – red laser wavelength, fm
        red_ste       – interpolated std. error, fm
        blue          – blue laser wavelength, fm
        blue_ste      – interpolated std. error, fm
        frequency     – Rb frequency standard, MHz
        frequency_ste – interpolated std. error, MHz
        frequency_hz  – Rb frequency converted to Hz (for G-9 app)

    Raises
    ------
    ValueError
        If ``date`` is outside the calibration range for either instrument.
    KeyError
        If the ``calibration`` section is missing from ``config``.
    """
    if isinstance(date, str):
        date = datetime.date.fromisoformat(date)

    cal = config["calibration"]
    result = {}

    # --- Laser ---------------------------------------------------------------
    laser_records = sorted(cal["laser"], key=lambda r: r["date"])
    _check_range(date, [r["date"] for r in laser_records], instrument="laser")

    laser_x = np.array([r["date"].toordinal() for r in laser_records], dtype=float)
    target = float(date.toordinal())

    for field in ("red", "red_ste", "blue", "blue_ste"):
        y = np.array([r[field] for r in laser_records], dtype=float)
        result[field] = float(np.interp(target, laser_x, y))

    # --- Rubidium ------------------------------------------------------------
    rb_records = sorted(cal["rubidium"], key=lambda r: r["date"])
    _check_range(date, [r["date"] for r in rb_records], instrument="rubidium")

    rb_x = np.array([r["date"].toordinal() for r in rb_records], dtype=float)

    for field in ("frequency", "frequency_ste"):
        y = np.array([r[field] for r in rb_records], dtype=float)
        result[field] = float(np.interp(target, rb_x, y))

    # Convenience value in Hz for direct use with G-9 app
    result["frequency_hz"] = result["frequency"] * 1e6

    return result


def _check_range(
    date: datetime.date,
    cal_dates: list,
    instrument: str,
) -> None:
    """Raise ValueError if date is outside the calibration range."""
    lo, hi = min(cal_dates), max(cal_dates)
    if not (lo <= date <= hi):
        raise ValueError(
            f"Date {date} is outside the {instrument} calibration range "
            f"[{lo}, {hi}]. Extrapolation is not supported."
        )

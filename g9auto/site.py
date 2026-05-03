"""
Site parameter preparation for g9auto.

Accepts two input formats:
  1. A flat pandas DataFrame row.
  2. A nested dict loaded from a site YAML file.

Both are normalised to the same flat dict and then processed into a dict
that ``run_app`` / ``info_tab`` / ``system_tab`` expect.

Gradient resolution (mutually exclusive, first match wins):
  • Column ``vgg`` present and not NaN  → used as-is.
  • Columns ``a``, ``b`` (and optionally ``ua``, ``ub``, ``covab``) present
    → computed via :func:`g9auto.gradient.vgg_from_quadratic`.

Calibration (red / blue / frequency):
  • Columns ``red``, ``blue``, ``frequency`` present → used as-is.
  • Column ``date`` present → interpolated from ``config['calibration']``
    via :func:`g9auto.calibration.interpolate`.
"""

import datetime
from functools import lru_cache
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from g9auto.gradient import vgg_from_quadratic, vgg_ste_from_quadratic


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prepare_dataframe(df: pd.DataFrame, config: dict, source_base_dir: Union[str, Path, None] = None) -> pd.DataFrame:
    """
    Prepare a complete DataFrame of sites for ``run_app``.

    Each row is processed through :func:`prepare_site`.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame loaded from a site CSV.
    config : dict
        Loaded config.yaml.

    Returns
    -------
    pd.DataFrame
        Normalised DataFrame with all columns expected by ``run_app``.
    """
    rows = [prepare_site(row, config, source_base_dir=source_base_dir) for _, row in df.iterrows()]
    return pd.DataFrame(rows)


def prepare_site(
    row: Union[dict, pd.Series],
    config: dict,
    source_base_dir: Union[str, Path, None] = None,
) -> dict:
    """
    Resolve all parameters for a single project row.

    Accepts a flat dict/Series (from CSV) **or** a nested dict that matches
    the site YAML structure (see ``data/site_template.yaml``).

    Parameters
    ----------
    row : dict, pd.Series, or nested YAML dict
        Raw site data.  If the dict has a top-level ``site`` key the YAML
        layout is assumed; otherwise the flat CSV layout is assumed.
    config : dict
        Loaded config.yaml.

    Returns
    -------
    dict
        Flat dict with all keys needed by ``run_app``.
    """
    # --- normalise input ------------------------------------------------
    if isinstance(row, dict) and "site" in row:
        flat = _flatten_yaml_site(row)
    else:
        flat = dict(row) if hasattr(row, "to_dict") else dict(row)
        # CSV: prefer station_name over station as the g9 "Name" field
        if "station_name" in flat and _notna(flat.get("station_name")):
            flat["station"] = flat["station_name"]

    # --- project path (absolute) ----------------------------------------
    flat["fg5_file"] = _resolve_fg5_path(flat.get("fg5_file", ""), source_base_dir)

    # --- date normalisation ---------------------------------------------
    if _notna(flat.get("date")):
        flat["date"] = _normalize_date(flat.get("date"))

    # --- transfer height (cm) ------------------------------------------
    # Must be provided explicitly in site YAML/CSV.
    # Do not derive from h_eff/config because h_eff absence triggers two-pass mode.
    if _notna(flat.get("transfer_height")):
        flat["transfer_height"] = round(float(flat["transfer_height"]), 4)
    else:
        flat["transfer_height"] = np.nan

    # --- setup height (cm) ---------------------------------------------
    if _notna(flat.get("setup_height")):
        flat["setup_height"] = round(float(flat["setup_height"]), 4)
    else:
        flat["setup_height"] = np.nan

    # --- height linking -------------------------------------------------
    if _notna(flat.get("h_eff")) and _notna(flat.get("setup_height")) and not _notna(flat.get("h_eff_plate")):
        flat["h_eff_plate"] = round(float(flat["h_eff"]) + float(flat["setup_height"]) / 100.0, 6)
    if _notna(flat.get("h_eff_plate")) and _notna(flat.get("setup_height")) and not _notna(flat.get("h_eff")):
        flat["h_eff"] = round(float(flat["h_eff_plate"]) - float(flat["setup_height"]) / 100.0, 6)

    # --- gradient -------------------------------------------------------
    # Compute working (local) gradient on the reduction segment:
    #   h1 = transfer_height (or h_eff when transfer_height is missing)
    #   h2 = h_eff_plate
    # setup_height is not a profile height and must not be used as h1.
    if not _notna(flat.get("vgg")):
        h2 = _resolve_gradient_h2_m(flat)
        if h2 is not None:
            a = float(flat["a"])
            b = float(flat["b"])
            if _notna(flat.get("transfer_height")):
                h1 = float(flat["transfer_height"]) / 100.0
            elif _notna(flat.get("h_eff")):
                h1 = float(flat["h_eff"])
            else:
                h1 = float(flat.get("grad_h1", 0.0))
            vgg_m = vgg_from_quadratic(a, b, h1, h2)
            flat["vgg"] = round(vgg_m / 100.0, 6)  # uGal/m → uGal/cm

    if not _notna(flat.get("vgg_ste")):
        h2 = _resolve_gradient_h2_m(flat)
        if h2 is not None:
            ua = float(flat.get("ua", 0.0))
            ub = float(flat.get("ub", 0.0))
            covab = float(flat.get("covab", 0.0))
            if _notna(flat.get("transfer_height")):
                h1 = float(flat["transfer_height"]) / 100.0
            elif _notna(flat.get("h_eff")):
                h1 = float(flat["h_eff"])
            else:
                h1 = float(flat.get("grad_h1", 0.0))
            ste_m = vgg_ste_from_quadratic(ua, ub, covab, h1, h2)
            flat["vgg_ste"] = round(ste_m / 100.0, 6)  # uGal/m → uGal/cm

    # --- calibration: laser + Rb ----------------------------------------
    date = flat.get("date")
    if _notna(date):
        date = _normalize_date(date)
        flat["date"] = date
        try:
            from g9auto.calibration import interpolate
            cal = interpolate(config, date)
            flat.setdefault("red", cal["red"])
            flat.setdefault("blue", cal["blue"])
            flat.setdefault("frequency", cal["frequency_hz"])
        except (ValueError, KeyError):
            pass  # calibration section absent or date out of range

    # --- polar motion from IERS by date ---------------------------------
    if (not _notna(flat.get("polar_x")) or not _notna(flat.get("polar_y"))) and _notna(flat.get("date")):
        polar = _polar_motion_for_date(flat["date"])
        if polar is not None:
            flat["polar_x"], flat["polar_y"] = polar

    # --- defaults for optional fields -----------------------------------
    flat.setdefault("polar_x", 0.0)
    flat.setdefault("polar_y", 0.0)
    flat.setdefault("comments", "")
    flat.setdefault("order", "")

    return flat


# ---------------------------------------------------------------------------
# Site YAML → flat dict
# ---------------------------------------------------------------------------

def _flatten_yaml_site(data: dict) -> dict:
    """
    Flatten a nested site YAML dict into the same flat layout as a CSV row.

    ::

        fg5_file: path/to/project.fg5
        date: 2024-09-15
        site:
          name: ...
          code: ...
          gradient: -3.086          # Option A: direct value
          gradient_ste: 0.03
          gradient_params:          # Option B: quadratic params
            a: -300.0
            ...

    The two gradient options are mutually exclusive; Option A wins if both
    are specified.
    """
    flat: dict = {}
    flat["fg5_file"] = data.get("fg5_file", "")
    flat["date"] = data.get("date")

    site = data.get("site", {})
    flat["station"] = site.get("name", "")
    flat["point"] = site.get("code", "")
    flat["latitude"] = float(site.get("latitude", 0.0))
    flat["longitude"] = float(site.get("longitude", 0.0))
    flat["elevation"] = float(site.get("elevation", 0.0))
    if _notna(site.get("h_eff")):
        flat["h_eff"] = float(site.get("h_eff"))
    if _notna(site.get("h_eff_plate")):
        flat["h_eff_plate"] = float(site.get("h_eff_plate"))
    if _notna(site.get("setup_height")):
        flat["setup_height"] = float(site.get("setup_height"))
    if _notna(site.get("transfer_height")):
        flat["transfer_height"] = float(site.get("transfer_height"))
    if _notna(site.get("polar_x")):
        flat["polar_x"] = float(site.get("polar_x"))
    if _notna(site.get("polar_y")):
        flat["polar_y"] = float(site.get("polar_y"))

    # Gradient: Option A — direct value
    if _notna(site.get("gradient")):
        flat["vgg"] = float(site["gradient"])
        flat["vgg_ste"] = float(site.get("gradient_ste", 0.0))

    # Gradient: Option B — quadratic profile parameters
    elif "gradient_params" in site:
        p = site["gradient_params"]
        flat["a"] = float(p["a"])
        flat["b"] = float(p["b"])
        flat["ua"] = float(p.get("ua", 0.0))
        flat["ub"] = float(p.get("ub", 0.0))
        flat["covab"] = float(p.get("covab", 0.0))
        flat["grad_h1"] = float(p.get("h1", 0.0))
        if _notna(p.get("h2")):
            flat["grad_h2"] = float(p.get("h2"))

    # Optional explicit calibration overrides (prefer top-level keys).
    for key in ("red", "blue", "frequency"):
        if _notna(data.get(key)):
            flat[key] = float(data[key])
        elif _notna(site.get(key)):
            flat[key] = float(site[key])

    return flat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_date(value) -> datetime.date:
    """Convert date-like values to ``datetime.date``."""
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    if hasattr(value, "date"):
        return value.date()
    raise ValueError(f"Unsupported date value: {value!r}")


def _effective_height_cm_from_config(config: dict) -> Union[float, None]:
    """Resolve default effective height in cm from config gravimeter section."""
    grav = config.get("gravimeter", {})
    meter_type = str(grav.get("type", "")).strip().upper()
    defaults = grav.get("effective_height_cm", {})
    if meter_type and meter_type in defaults:
        return float(defaults[meter_type])
    return None


def _effective_height_m(flat: dict, config: dict) -> Union[float, None]:
    """Resolve effective height in metres for gradient computations."""
    if _notna(flat.get("h_eff_plate")):
        return float(flat["h_eff_plate"])
    if _notna(flat.get("h_eff")):
        return float(flat["h_eff"])
    fallback_cm = _effective_height_cm_from_config(config)
    if fallback_cm is not None:
        return float(fallback_cm) / 100.0
    return None


def _resolve_gradient_h2_m(flat: dict) -> Union[float, None]:
    """Resolve h2 for quadratic gradient computation.

    Returns None when h_eff_plate/h_eff are not explicitly provided.
    Config fallback is intentionally excluded: gradient must be computed
    from real data, not an instrument default.
    """
    if _notna(flat.get("grad_h2")):
        return float(flat["grad_h2"])
    if _notna(flat.get("h_eff_plate")):
        return float(flat["h_eff_plate"])
    if _notna(flat.get("h_eff")):
        return float(flat["h_eff"])
    return None


@lru_cache(maxsize=1)
def _get_iers_table():
    from astropy.utils import iers
    return iers.IERS_Auto.open()


def _polar_motion_for_date(date: datetime.date) -> Union[tuple[float, float], None]:
    """Return (polar_x, polar_y) from IERS table for a measurement date."""
    try:
        from astropy.time import Time

        ts = pd.Timestamp(date)
        iers_table = _get_iers_table()
        x, y = iers_table.pm_xy(Time(ts.to_datetime64()))
        return float(x.value), float(y.value)
    except (ImportError, AttributeError, TypeError, ValueError):
        return None

def _notna(value) -> bool:
    """Return True if value is present and not NaN/None."""
    if value is None:
        return False
    try:
        return not (isinstance(value, float) and np.isnan(value))
    except (TypeError, ValueError):
        return True


def _resolve_fg5_path(path_value, source_base_dir: Union[str, Path, None]) -> str:
    """Return absolute path for FG5 project file."""
    if not path_value:
        return ""
    p = Path(str(path_value).strip())
    if p.is_absolute():
        return str(p)

    # Try as-is first (relative to current working directory), because inputs
    # may already include a folder prefix like "example/...".
    as_is = p.resolve()
    if as_is.exists():
        return str(as_is)

    # Then try relative to source file directory (site yaml / batch csv location).
    if source_base_dir:
        from_source = (Path(source_base_dir) / p).resolve()
        if from_source.exists():
            return str(from_source)
        return str(from_source)

    return str(as_is)

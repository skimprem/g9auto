"""
params.py  —  g9auto/params.py
==============================
Resolves transfer_height, vgg, and vgg_ste for a single station
before launching g9 via proc().

Integration in run_app() — replace lines 631-709 with:

    params = resolve_g9_params(
        app=app,
        main=main,
        row=row,
        config=config,
        max_wait_time=max_wait_time,
        base_name=base_name,
        project_path=project_path,
        result=result,
    )
    if params is None:
        close_project(main)
        continue

    vgg             = params['vgg']
    vgg_ste         = params['vgg_ste']
    transfer_height = params['transfer_height']
"""

from __future__ import annotations

import os
from typing import Optional

# These are already imported in core.py.
# Uncomment when using this file standalone (e.g. for unit tests):
from g9auto.logger import get_logger
from g9auto.gradient import vgg_from_quadratic, vgg_ste_from_quadratic
from g9auto.loader import read_project
log = get_logger()

def _as_float(value):
    try:
        result = float(value)
        if result != result:  # NaN check
            return None
        return result
    except (TypeError, ValueError):
        return None



def resolve_g9_params(
    app,
    main,
    row,
    config: dict,
    max_wait_time: int,
    base_name: str,
    project_path: str,
    result: list,
    run_single_pass,
    report_txt_path,
) -> Optional[dict]:
    """
    Resolve transfer_height, vgg, and vgg_ste for a single station.

    Algorithm (three blocks):

    Block A — h_eff_plate:
        1. row.h_eff_plate provided explicitly          -> use as-is
        2. row.h_eff provided                           -> h_eff_plate = h_eff - setup_height
        3. Neither given, but a and b are available     -> two-pass mode via g9:
               pass-0  : vgg=0,       transfer=0 -> g0
               pass-vgg: vgg=vgg_ref, transfer=0 -> g_vgg
               h_eff_plate = setup_height + (g0 - g_vgg) / vgg_ref
        4. Nothing available                            -> default from config (68.3 cm)

    Block B — transfer_height:
        1. row.transfer_height provided explicitly      -> use as-is
        2. Otherwise: transfer_height = h_eff_plate + setup_height

    Block C — vgg / vgg_ste:
        1. row.vgg / row.vgg_ste provided explicitly    -> use as-is
        2. Otherwise: compute from a, b via
           vgg_from_quadratic / vgg_ste_from_quadratic
           with h1=h_eff_plate, h2=transfer_height

    Parameters
    ----------
    app, main       : pywinauto Application and main window (needed for two-pass mode)
    row             : DataFrame row with station fields
    config          : configuration dict (paths, gravimeter, processing, ...)
    max_wait_time   : processing wait timeout in seconds
    base_name       : project filename without extension
    project_path    : full path to the .fg5 project file
    result          : results list (two-pass runs are appended here)

    Returns
    -------
    dict with keys 'transfer_height', 'vgg', 'vgg_ste', 'h_eff_plate',
    or None if a required parameter is missing (station should be skipped).
    """

    # ── Read all row parameters ───────────────────────────────────────────────

    transfer_height_in = _as_float(getattr(row, 'transfer_height', None))
    setup_height       = _as_float(getattr(row, 'setup_height',    None))
    h_eff_plate_in     = _as_float(getattr(row, 'h_eff_plate',     None))
    h_eff_in           = _as_float(getattr(row, 'h_eff',           None))
    vgg_in             = _as_float(getattr(row, 'vgg',             None))
    vgg_ste_in         = _as_float(getattr(row, 'vgg_ste',         None))
    a                  = _as_float(getattr(row, 'a',               None))
    b                  = _as_float(getattr(row, 'b',               None))
    ua                 = _as_float(getattr(row, 'ua',              None))
    ub                 = _as_float(getattr(row, 'ub',              None))
    covab              = _as_float(getattr(row, 'covab',           None))

    instrument = config.get('gravimeter', {}).get('type', 'A10')
    default_plate_cm = _as_float(
        config.get('gravimeter', {}).get('effective_height_cm', {}).get(instrument, 68.3)
    ) or 68.3

    # setup_height is always required
    if setup_height is None:
        log.fail("setup_height is required but missing — skipping station")
        return None

    # ── Block A: resolve h_eff_plate ─────────────────────────────────────────

    h_eff_plate: float

    if h_eff_plate_in is not None:
        # Priority 1: provided explicitly
        h_eff_plate = h_eff_plate_in
        log.info(f"h_eff_plate: provided explicitly = {h_eff_plate:.3f} cm")

    elif h_eff_in is not None:
        # Priority 2: derive from h_eff - setup_height
        h_eff_plate = h_eff_in - setup_height
        log.info(
            f"h_eff_plate: derived from h_eff ({h_eff_in:.3f}) - setup_height ({setup_height:.3f})"
            f" = {h_eff_plate:.3f} cm"
        )

    elif a is not None and b is not None:
        # Priority 3: two-pass mode via g9
        h_eff = _two_pass_h_eff_plate(
            app=app,
            main=main,
            row=row,
            config=config,
            max_wait_time=max_wait_time,
            base_name=base_name,
            project_path=project_path,
            result=result,
            run_single_pass=run_single_pass,
            report_txt_path=report_txt_path
        )
        h_eff_plate = h_eff - setup_height
        if h_eff_plate is None:
            return None
        log.info(f"h_eff: resolved via two-pass mode = {h_eff:.3f} cm")
        log.info(f"h_eff_plate: resolved via two-pass mode = {h_eff_plate:.3f} cm")

    else:
        # Priority 4: default from config
        h_eff_plate = default_plate_cm
        log.info(
            f"h_eff_plate: not provided and a/b missing"
            f" — using default {h_eff_plate:.3f} cm"
        )

    # ── Block B: resolve transfer_height ─────────────────────────────────────

    if transfer_height_in is not None:
        transfer_height = transfer_height_in
        log.info(f"transfer_height: provided explicitly = {transfer_height:.3f} cm")
    else:
        transfer_height = h_eff_plate + setup_height
        log.info(
            f"transfer_height: computed as h_eff_plate + setup_height"
            f" = {h_eff_plate:.3f} + {setup_height:.3f} = {transfer_height:.3f} cm"
        )

    # ── Block C: resolve vgg and vgg_ste ─────────────────────────────────────

    if vgg_in is not None:
        vgg = vgg_in
        log.info(f"vgg: provided explicitly = {vgg:.4f} µGal/cm")
    elif a is not None and b is not None:
        # h1 = h_eff_plate  (a, b are defined relative to the pillar plane)
        # h2 = transfer_height
        vgg = vgg_from_quadratic(a, b, h1=h_eff_plate/100.0, h2=transfer_height/100.0)/100.0
        log.info(
            f"vgg: computed via vgg_from_quadratic("
            f"a={a}, b={b}, h1={h_eff_plate:.3f}, h2={transfer_height:.3f})"
            f" = {vgg:.4f} µGal/cm"
        )
    else:
        log.fail("vgg is missing and cannot be computed (no a/b) — skipping station")
        return None

    if vgg_ste_in is not None:
        vgg_ste = vgg_ste_in
        log.info(f"vgg_ste: provided explicitly = {vgg_ste:.4f} µGal/cm")
    elif ua is not None and ub is not None and covab is not None:
        vgg_ste = vgg_ste_from_quadratic(ua, ub, covab, h1=h_eff_plate/100.0, h2=transfer_height/100.0)/100.0
        log.info(
            f"vgg_ste: computed via vgg_ste_from_quadratic("
            f"ua={ua}, ub={ub}, covab={covab},"
            f" h1={h_eff_plate:.3f}, h2={transfer_height:.3f})"
            f" = {vgg_ste:.4f} µGal/cm"
        )
    else:
        vgg_ste = 0.03  # fallback — move to config['gravimeter']['vgg_ste_default'] if needed
        log.info(f"vgg_ste: not provided — using fallback {vgg_ste:.3f} µGal/cm")

    log.info(
        f"Resolved: transfer_height={transfer_height:.3f} cm |"
        f" vgg={vgg:.4f} µGal/cm | vgg_ste={vgg_ste:.4f} µGal/cm |"
        f" h_eff_plate={h_eff_plate:.3f} cm"
    )

    return {
        'transfer_height': transfer_height,
        'vgg':             vgg,
        'vgg_ste':         vgg_ste,
        'h_eff_plate':     h_eff_plate,
    }


# ── Helper: two-pass h_eff_plate determination ───────────────────────────────

def _two_pass_h_eff_plate(
    app,
    main,
    row,
    config: dict,
    max_wait_time: int,
    base_name: str,
    project_path: str,
    result: list,
    run_single_pass,
    report_txt_path,
) -> Optional[float]:
    """
    Determine h_eff_plate from two g9 runs with transfer_height=0:
        pass-0  : vgg=0       -> g0
        pass-vgg: vgg=vgg_ref -> g_vgg

    Formula: h_eff_plate = setup_height + (g0 - g_vgg) / vgg_ref

    Runs are skipped if the report files already exist on disk,
    allowing safe restarts without re-processing.
    """
    VGG_REF     = -3.086  # µGal/cm — reference gradient for the second pass
    VGG_STE_REF =  0.03   # µGal/cm — placeholder uncertainty for two-pass runs

    report_0   = f"{base_name}_0"
    report_vgg = f"{base_name}_vgg"

    path_0   = report_txt_path(project_path, report_0)
    path_vgg = report_txt_path(project_path, report_vgg)

    # Skip runs if reports already exist (safe restart behaviour)
    if not os.path.exists(path_0) or not os.path.exists(path_vgg):
        log.info("Two-pass mode: running pass-0 (vgg=0, transfer_height=0)")
        run_single_pass(
            app, main, row, config, max_wait_time,
            vgg_value=0.0,
            vgg_ste_value=VGG_STE_REF,
            transfer_height_cm=0.0,
            report_file=report_0,
        )

        log.info(f"Two-pass mode: running pass-vgg (vgg={VGG_REF}, transfer_height=0)")
        run_single_pass(
            app, main, row, config, max_wait_time,
            vgg_value=VGG_REF,
            vgg_ste_value=VGG_STE_REF,
            transfer_height_cm=0.0,
            report_file=report_vgg,
        )

    # Read results from both reports
    try:
        project_0, _ = read_project(path_0)
        result.append(project_0)
        g0 = project_0[('Processing Results', 'Gravity', 'µGal')]

        project_vgg, _ = read_project(path_vgg)
        g_vgg = project_vgg[('Processing Results', 'Gravity', 'µGal')]
    except Exception as e:
        log.fail(f"Two-pass mode: failed to read report — {e}")
        return None

    h_eff = (g0 - g_vgg) / VGG_REF
    log.info(
        f"Two-pass mode: g0={g0:.2f}, g_vgg={g_vgg:.2f}, vgg_ref={VGG_REF}"
        f" -> h_eff = {h_eff:.3f} cm"
    )
    return h_eff
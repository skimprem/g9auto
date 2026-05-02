"""
Command-line interface for g9auto.

Commands
--------
run     Run the automation workflow (CSV list or single-site YAML).
init    Copy the default config.yaml template to the current directory.
site-init
        Copy the single-site site_template.yaml to the current directory.
"""

import argparse
import sys
from importlib import resources
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _setup_logging(config: dict) -> None:
    from g9auto.logger import setup_logging
    log_cfg = config.get("logging", {})
    setup_logging(
        log_dir=log_cfg.get("log_dir", "logs"),
        verbose=log_cfg.get("verbose", True),
        log_to_file=log_cfg.get("log_to_file", True),
    )


# ---------------------------------------------------------------------------
# run subcommand
# ---------------------------------------------------------------------------

def cmd_run(args):
    try:
        import pandas as pd
    except ImportError:
        print("pandas is required: pip install pandas", file=sys.stderr)
        sys.exit(1)

    config = _load_config(Path(args.config))
    _setup_logging(config)

    print(config)

    from g9auto.core import run_app
    from g9auto.site import prepare_dataframe, prepare_site

    # ── Mode A: single-site YAML ─────────────────────────────────────────
    if args.site:
        site_path = Path(args.site)
        if not site_path.exists():
            print(f"Site file not found: {site_path}", file=sys.stderr)
            sys.exit(1)
        with open(site_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        row = prepare_site(raw, config, source_base_dir=site_path.parent)
        df = pd.DataFrame([row])
        run_app(df, config)
        return

    # ── Mode B: CSV list of sites ─────────────────────────────────────────
    if not args.data:
        print("Provide either --data <csv> or --site <yaml>.", file=sys.stderr)
        sys.exit(1)

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    # auto-detect separator
    sep = _detect_sep(data_path)
    df = pd.read_csv(data_path, sep=sep)

    # optional single-station filter
    if args.station:
        code = args.station
        mask = (
            df.get("station", pd.Series(dtype=str)).astype(str).eq(code)
            | df.get("point", pd.Series(dtype=str)).astype(str).eq(code)
            | df.get("station_name", pd.Series(dtype=str)).astype(str).eq(code)
        )
        df = df[mask]
        if df.empty:
            print(
                f"No rows found for --station '{code}'. "
                f"Available: {_available_stations(data_path, sep)}",
                file=sys.stderr,
            )
            sys.exit(1)

    df = prepare_dataframe(df, config, source_base_dir=data_path.parent)
    run_app(df, config)


def _detect_sep(path: Path) -> str:
    """Return ';' if the first line contains it, else ','."""
    first_line = path.read_text(encoding="utf-8").split("\n", 1)[0]
    return ";" if ";" in first_line else ","


def _available_stations(path: Path, sep: str) -> str:
    import pandas as pd
    df = pd.read_csv(path, sep=sep, nrows=0)
    cols = [c for c in ("station", "point", "station_name") if c in df.columns]
    if not cols:
        return "(unknown)"
    df = pd.read_csv(path, sep=sep, usecols=cols)
    values: set = set()
    for col in cols:
        values.update(df[col].dropna().astype(str).tolist())
    return ", ".join(sorted(values))


# ---------------------------------------------------------------------------
# config-init subcommand
# ---------------------------------------------------------------------------

def cmd_config_init(args):
    dest = Path.cwd() / "config.yaml"
    if dest.exists() and not args.force:
        print("config.yaml already exists in current directory. Use --force to overwrite.")
        sys.exit(1)
    with resources.files("g9auto.data").joinpath("config.yaml").open("rb") as src:
        dest.write_bytes(src.read())
    print(f"Created {dest}")


# ---------------------------------------------------------------------------
# site-init subcommand
# ---------------------------------------------------------------------------

def cmd_site_init(args):
    dest = Path.cwd() / (args.output or "site.yaml")
    if dest.exists() and not args.force:
        print(f"{dest.name} already exists. Use --force to overwrite.")
        sys.exit(1)
    with resources.files("g9auto.data").joinpath("site_template.yaml").open("rb") as src:
        dest.write_bytes(src.read())
    print(f"Created {dest}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="g9auto",
        description="Automation tool for Micro-g LaCoste G-9 gravimeter software.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── run ──────────────────────────────────────────────────────────────
    run_parser = subparsers.add_parser(
        "run",
        help="Run the automation workflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Run G-9 automation for one or more projects.\n\n"
            "Single site:   g9auto run --site site.yaml [--config config.yaml]\n"
            "List of sites: g9auto run --data sites.csv [--station CODE] [--config config.yaml]"
        ),
    )
    run_parser.add_argument(
        "--config",
        default="config.yaml",
        metavar="FILE",
        help="Path to YAML instrument config (default: config.yaml).",
    )
    run_parser.add_argument(
        "--data",
        metavar="FILE",
        help="CSV file with one project per row.",
    )
    run_parser.add_argument(
        "--station",
        metavar="CODE",
        help=(
            "Run only the row matching this station/point code "
            "(matched against 'station', 'point', or 'station_name' columns)."
        ),
    )
    run_parser.add_argument(
        "--site",
        metavar="FILE",
        help="Single-site YAML file (alternative to --data).",
    )
    run_parser.set_defaults(func=cmd_run)

    # ── config-init ───────────────────────────────────────────────────────
    config_init_parser = subparsers.add_parser(
        "config-init",
        help="Copy the default config.yaml template to the current directory.",
    )
    config_init_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing config.yaml."
    )
    config_init_parser.set_defaults(func=cmd_config_init)

    # ── site-init ─────────────────────────────────────────────────────────
    site_init_parser = subparsers.add_parser(
        "site-init",
        help="Copy the single-site template (site_template.yaml) to the current directory.",
    )
    site_init_parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        default="site.yaml",
        help="Output filename (default: site.yaml).",
    )
    site_init_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing file."
    )
    site_init_parser.set_defaults(func=cmd_site_init)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

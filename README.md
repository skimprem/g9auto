# g9auto

Automation tool for **Micro-g LaCoste g9** software.  
Drives the g9 GUI to process absolute gravity data from FG5/A10 gravimeters in single-site or batch mode.

## Requirements

- Windows (g9 runs on Windows only)
- Python ≥ 3.10
- g9 software installed

## Installation

```powershell
pip install .
```

## Quick start

Copy default templates to the current directory:

```powershell
g9auto init          # config.yaml
g9auto site-init     # site_template.yaml
```

Edit `config.yaml` for your setup, then run:

```powershell
# Single site
g9auto run --site site.yaml --config config.yaml

# Batch (CSV list of sites)
g9auto run --data sites.csv --config config.yaml

# Batch with station filter
g9auto run --data sites.csv --station 63 --config config.yaml
```

## Input formats

| Mode | File | Key fields |
|------|------|------------|
| Single | `site.yaml` | `fg5_file`, `transfer_height`, `h_eff`, … |
| Batch | `sites.csv` | same fields as columns |

See [`example/`](example/) for ready-to-edit templates.

## Dependencies

`pywinauto` · `pandas` · `PyYAML` · `astropy`


# Example Inputs (AKTO)

This folder contains ready-to-edit templates for both package modes.

## 1) Single project mode (`--site`)

Input file: `example/site_akto.yaml`

Command:

```powershell
g9auto run --site example/site_akto.yaml --config config.yaml
```

Use this mode when you process one project directly.

## 2) Batch mode (`--data`)

Input file: `example/sites_akto_batch.csv`

Command:

```powershell
g9auto run --data example/sites_akto_batch.csv --config config.yaml
```

Optional filter (single row from list):

```powershell
g9auto run --data example/sites_akto_batch.csv --station 1303 --config config.yaml
```

Use this mode to process a list of points. The CSV intentionally contains
only fields required by `g9auto.site.prepare_site` and `run_app`:

- `fg5_file`
- `site` (mapped to station)
- `code`
- `latitude`, `longitude`, `elevation`
- `a`, `b`, `ua`, `ub`, `covab` (gradient parameters)
- `setup_height` (required, cm)
- `date` (for laser/Rb and polar x/y interpolation)

Notes:

- `polar_x` and `polar_y` are computed automatically from `date` (IERS).
- `transfer_height` must be provided in input (YAML/CSV).
- If `h_eff` is omitted, `run_app` performs two runs (`vgg = 0` and
	`vgg = -3.086`), computes effective height by:
	`h_eff = (gravity(-3.086) - gravity(0)) / -3.086`, then runs final
	processing with computed gradient between `h_eff` and `transfer_height`.

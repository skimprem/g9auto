#!/usr/bin/env python
"""Compare interpolation methods numerically for 2023-07-28."""

import datetime
import numpy as np
import sys
import yaml

# Load g9auto calibration
from g9auto.calibration import interpolate

with open("config.yaml") as f:
    config = yaml.safe_load(f)

target_date = datetime.date(2023, 7, 28)

# Method 1: g9auto np.interp()
print("=" * 60)
print("METHOD 1: g9auto/calibration.py (np.interp)")
print("=" * 60)

result_g9auto = interpolate(config, target_date)
print(f"Date: {target_date}")
print(f"Red:  {result_g9auto['red']:.11f} nm")
print(f"Blue: {result_g9auto['blue']:.11f} nm")
print(f"Red_ste:  {result_g9auto['red_ste']:.11f} nm")
print(f"Blue_ste: {result_g9auto['blue_ste']:.11f} nm")

# Method 2: qazgrf24_proc calibration data
print("\n" + "=" * 60)
print("METHOD 2: qazgrf24_proc calibration (manual linear interp)")
print("=" * 60)

sys.path.insert(0, r"c:\Users\roman\gitrepo\qazgrf24_proc")
from resources import LASER

# Reconstruct as ordinal dates
cal_dates = LASER["date"]
red_vals_fm = LASER["red"]  # in fm
blue_vals_fm = LASER["blue"]  # in fm

# Convert to nm for consistency with g9auto config.yaml
red_vals = [x / 1e6 for x in red_vals_fm]
blue_vals = [x / 1e6 for x in blue_vals_fm]

cal_x = np.array([d.toordinal() for d in cal_dates], dtype=float)
target_x = float(target_date.toordinal())

red_interp = float(np.interp(target_x, cal_x, red_vals))
blue_interp = float(np.interp(target_x, cal_x, blue_vals))

print(f"Date: {target_date}")
print(f"Red:  {red_interp:.11f} nm")
print(f"Blue: {blue_interp:.11f} nm")

# Show calibration points
print(f"\nCalibration points (qazgrf24_proc, converted to nm):")
for date, red_fm, blue_fm in zip(cal_dates, red_vals_fm, blue_vals_fm):
    print(f"  {date}: red={red_fm/1e6:.11f} nm, blue={blue_fm/1e6:.11f} nm")

# Comparison
print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
red_diff = result_g9auto['red'] - red_interp
blue_diff = result_g9auto['blue'] - blue_interp
print(f"Red difference:  {red_diff:.11f} nm")
print(f"Blue difference: {blue_diff:.11f} nm")

# Display in nm
print(f"\nRed (g9auto):  {result_g9auto['red']:.11f} nm")
print(f"Red (qazgrf):  {red_interp:.11f} nm")
print(f"Blue (g9auto): {result_g9auto['blue']:.11f} nm")
print(f"Blue (qazgrf): {blue_interp:.11f} nm")

# Reference values
print("\n" + "=" * 60)
print("REFERENCE (from 1303_akto.project.txt)")
print("=" * 60)
print(f"Red:  632.99027404 nm = 632990274.04 fm")
print(f"Blue: 632.99125578 nm = 632991255.78 fm")
red_ref = 632.99027404
blue_ref = 632.99125578
print(f"\nInterpolated red vs reference:  {result_g9auto['red'] - red_ref:.11f} nm")
print(f"Interpolated blue vs reference: {result_g9auto['blue'] - blue_ref:.11f} nm")

print("\n" + "=" * 60)
print("CONCLUSION")
print("=" * 60)
if abs(red_diff) < 0.1 and abs(blue_diff) < 0.1:
    print("✓ Methods are numerically identical (difference < 0.1 fm)")
    print("✓ Discrepancy with reference is due to missing 2023 calibration points")
else:
    print("✗ Methods differ significantly!")

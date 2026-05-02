"""
g9auto — automation library for Micro-g LaCoste G-9 gravimeter software.
"""

from g9auto.core import run_app
from g9auto.logger import get_logger, setup_logging
from g9auto.calibration import interpolate as interpolate_calibration
from g9auto.gradient import vgg_from_quadratic, vgg_ste_from_quadratic
from g9auto.site import prepare_site, prepare_dataframe

__version__ = "0.1.0"
__all__ = [
	"run_app",
	"get_logger",
	"setup_logging",
	"interpolate_calibration",
	"vgg_from_quadratic",
	"vgg_ste_from_quadratic",
	"prepare_site",
	"prepare_dataframe",
]

"""
Vertical gravity gradient computation from a quadratic gravity profile.

Quadratic profile model:
    g(h) = g0 + a*(h - h0) + (b/2)*(h - h0)^2

Mean gradient from h1 to h2 (both measured from the floor, h0 = 0):
    VGG = (g(h2) - g(h1)) / (h2 - h1) = a + (b/2)*(h1 + h2)

Units convention used in this module:
    a     [uGal/m],  b    [uGal/m²],  h [m]  →  VGG [uGal/m]
    ua    [uGal/m],  ub   [uGal/m²],  covab [uGal²/m³]

The g9 application expects the gradient in uGal/cm → divide result by 100.
"""

import math


def vgg_from_quadratic(a: float, b: float, h1: float, h2: float) -> float:
    """
    Compute the mean VGG between heights h1 and h2.

    Parameters
    ----------
    a : float
        Linear coefficient of the quadratic gravity profile, uGal/m.
    b : float
        Quadratic coefficient of the gravity profile, uGal/m².
    h1 : float
        Lower height, m (typically 0 = floor level).
    h2 : float
        Upper height, m (= effective measurement height h_eff).

    Returns
    -------
    float
        Mean VGG between h1 and h2, uGal/m.
        Divide by 100 to convert to uGal/cm for g9 input.
    """
    return a + 0.5 * b * (h1 + h2)


def vgg_ste_from_quadratic(
    ua: float,
    ub: float,
    covab: float,
    h1: float,
    h2: float,
) -> float:
    """
    Propagate uncertainty from quadratic profile parameters to VGG.

    Jacobian of VGG = a + (b/2)*(h1+h2):
        ∂VGG/∂a = 1
        ∂VGG/∂b = (h1 + h2) / 2

    Variance:
        Var(VGG) = ua² + h_mean² × ub² + 2 × h_mean × covab
        where h_mean = (h1 + h2) / 2

    Parameters
    ----------
    ua : float
        Standard error of a, uGal/m.
    ub : float
        Standard error of b, uGal/m².
    covab : float
        Covariance of a and b, uGal²/m³.
    h1 : float
        Lower height, m.
    h2 : float
        Upper height, m.

    Returns
    -------
    float
        Standard error of VGG, uGal/m.
        Divide by 100 to convert to uGal/cm.
    """
    h_mean = 0.5 * (h1 + h2)
    variance = ua ** 2 + h_mean ** 2 * ub ** 2 + 2.0 * h_mean * covab
    return math.sqrt(max(variance, 0.0))

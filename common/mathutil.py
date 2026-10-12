"""Logit and sigmoid shared by the rating models, the calibration layer and the Crystal Ball sims."""
import numpy as np


def logit(p):
    p = np.asarray(p, dtype=float)
    return np.log(p / (1.0 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))

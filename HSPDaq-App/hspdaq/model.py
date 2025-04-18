# hspdaq/model.py
"""
Train‑once / predict‑many Random‑Forest ETA model.
Keeps the fitted model in a module‑level singleton so importing is cheap.
"""
from __future__ import annotations

import pathlib
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_PATH    = PROJECT_ROOT / "data" / "trainingData.csv"

FEATURE_COLUMNS = [
    "supply_pressure",
    "supply_temperature",
    "run_pressure",
    "run_temperature",
    "current_mass",
]
TARGET_COLUMN = "full_fill_time"


# --------------------------------------------------------------------------- #
# Model training / loading
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _train_model() -> RandomForestRegressor:
    """Load data, train Random‑Forest, return the fitted estimator."""
    data = pd.read_csv(DATA_PATH)                          # :contentReference[oaicite:1]{index=1}
    X_train, X_test, y_train, y_test = train_test_split(   # :contentReference[oaicite:2]{index=2}
        data[FEATURE_COLUMNS],
        data[TARGET_COLUMN],
        test_size=0.2,
        random_state=42,
    )
    model = RandomForestRegressor(n_estimators=100, random_state=42)  # :contentReference[oaicite:3]{index=3}
    model.fit(X_train, y_train)
    return model


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #
def predict_remaining_time(feature_dict: dict[str, float]) -> float:
    """
    Given a dict with keys exactly equal to FEATURE_COLUMNS, return ETA (seconds).
    """
    model = _train_model()
    features_df = pd.DataFrame([feature_dict], columns=FEATURE_COLUMNS)
    return float(model.predict(features_df)[0])

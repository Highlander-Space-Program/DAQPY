#!/usr/bin/env python3
"""sensor_plot.py — CSV grapher + LC impulse + per‑tag maxima w/ units (v3.3)

2025-05-18 – **adds units to maxima output**
-------------------------------------------
* `Maximum value per tag` now prints both the value **and its unit symbol**.
* Auto‑detects the unit column (`units` or `unit`) just like other columns.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

###############################################################################
# CLI timestamp helper
###############################################################################
_CLI_TS_RE = re.compile(r"^(?P<iso>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})([.,])(?P<ms>\d{1,3})$")
_EPOCH_RE = re.compile(r"^(\d{13})$")

def _cli_to_timestamp(raw: str) -> pd.Timestamp:
    raw = raw.strip()
    if _EPOCH_RE.fullmatch(raw):
        return pd.to_datetime(int(raw), unit="ms", utc=True)
    m = _CLI_TS_RE.fullmatch(raw)
    if m:
        iso, ms = m.group("iso"), m.group("ms").zfill(3)
        return pd.to_datetime(f"{iso}.{ms}000", format="%Y-%m-%d %H:%M:%S.%f", utc=True)
    raise argparse.ArgumentTypeError(
        "Timestamp must be epoch-ms or 'YYYY-MM-DD HH:MM:SS,mmm' / '.mmm'"
    )

###############################################################################
# CSV streaming helpers
###############################################################################

def _chunk_iter(path: Path, size: int = 250_000):
    return pd.read_csv(
        path,
        dtype=str,
        header=0,
        chunksize=size,
        iterator=True,
        engine="python",
        skipinitialspace=True,
        on_bad_lines="skip",
        encoding="utf-8-sig",
    )

_REQUIRED1 = {"date_time", "ms", "tag", "value", "units"}
_REQUIRED2 = {"timestamp", "timestamp_ms", "name", "value", "unit"}

def _map_columns(cols: pd.Index):
    lc = {c.lower(): c for c in cols}
    if _REQUIRED1 <= lc.keys():
        return {
            "date": lc["date_time"],
            "ms": lc["ms"],
            "tag": lc["tag"],
            "value": lc["value"],
            "unit": lc["units"],
        }
    if _REQUIRED2 <= lc.keys():
        return {
            "date": lc["timestamp"],
            "ms": lc["timestamp_ms"],
            "tag": lc["name"],
            "value": lc["value"],
            "unit": lc["unit"],
        }
    raise ValueError("CSV missing required columns for recognised schema (need date, ms, tag/name, value, unit/units).")

###############################################################################
# Stream rows in window
###############################################################################

def stream_window(path: Path, start_ts: pd.Timestamp, end_ts: pd.Timestamp, *, verbose=False, debug=False):
    kept = 0
    mapper = None
    for idx, chunk in enumerate(_chunk_iter(path), 1):
        if mapper is None:
            mapper = _map_columns(chunk.columns)
        ts_str = chunk[mapper["date"]].str.strip() + "." + chunk[mapper["ms"]].str.zfill(3)
        ts = pd.to_datetime(ts_str, format="%Y-%m-%d %H:%M:%S.%f", errors="coerce", utc=True)
        chunk["timestamp"] = ts
        chunk.dropna(subset=["timestamp"], inplace=True)
        chunk["value"] = pd.to_numeric(chunk[mapper["value"]], errors="coerce")
        chunk.dropna(subset=["value"], inplace=True)
        filt = chunk[(chunk["timestamp"] >= start_ts) & (chunk["timestamp"] <= end_ts)]
        if not filt.empty:
            kept += len(filt)
            yield filt[["timestamp", mapper["tag"], "value", mapper["unit"]]].rename(
                columns={mapper["tag"]: "tag", mapper["unit"]: "unit"}
            )
        if debug and idx == 1:
            print("[DEBUG] Timestamp sample:", ts.head(3).tolist())
            print("[DEBUG] Rows in window (chunk 1):", len(filt))
        if verbose and idx % 25 == 0:
            print(f"chunk {idx}: cumulative kept rows = {kept}")
    if verbose or debug:
        print(f"Total rows kept: {kept}")

###############################################################################
# Aggregate per tag (store unit once)
###############################################################################

def collect_series(path: Path, start_ts: pd.Timestamp, end_ts: pd.Timestamp, *, verbose=False, debug=False):
    series: Dict[str, Tuple[List[pd.Timestamp], List[float]]] = {}
    units: Dict[str, str] = {}
    for chunk in stream_window(path, start_ts, end_ts, verbose=verbose, debug=debug):
        for tag, grp in chunk.groupby("tag", sort=False):
            ts_list, val_list = series.setdefault(tag, ([], []))
            ts_list.extend(grp["timestamp"].tolist())
            val_list.extend(grp["value"].tolist())
            if tag not in units and not grp["unit"].empty:
                units[tag] = grp["unit"].iloc[0]
    return series, units

###############################################################################
# Impulse (LC-only)
###############################################################################

def compute_impulses(series):
    impulses = {}
    for tag, (ts_list, val_list) in series.items():
        if not tag.upper().startswith("LC") or len(ts_list) < 2:
            continue
        t = np.array([t.timestamp() for t in ts_list])
        v = np.array(val_list, dtype=float)
        dt = np.diff(t)
        impulses[tag] = float(np.sum(0.5 * (v[:-1] + v[1:]) * dt))
    return impulses

###############################################################################
# Max per tag
###############################################################################

def compute_maxes(series):
    return {tag: float(np.nanmax(vals)) for tag, (_, vals) in series.items() if vals}

###############################################################################
# Plotting (unchanged)
###############################################################################

def plot_series(series, *, out_dir: Path, interactive: bool):
    if not series:
        print("No numeric sensor data found in the specified window.")
        return
    if not interactive:
        out_dir.mkdir(parents=True, exist_ok=True)
    for tag, (ts_list, val_list) in series.items():
        if not ts_list:
            continue
        plt.figure()
        plt.plot(ts_list, val_list, linewidth=1)
        plt.title(tag)
        plt.xlabel("Timestamp (UTC)")
        plt.ylabel("Value")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        if interactive:
            plt.show(block=False)
        else:
            fname = out_dir / f"{tag.replace('/', '_')}.png"
            plt.savefig(fname, dpi=150)
            plt.close()
            print(f"Saved {fname}")
    if interactive:
        print("Close all plot windows to return to the shell…")
        plt.show()

###############################################################################
# CLI glue
###############################################################################

def _cli():
    p = argparse.ArgumentParser(description="Plot sensor readings, load-cell impulse, and per-tag maxima with units.")
    p.add_argument("filepath", type=Path)
    p.add_argument("start_time", type=_cli_to_timestamp)
    p.add_argument("end_time", type=_cli_to_timestamp)
    p.add_argument("--output_dir", default="plots", type=Path)
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main():
    args = _cli()
    if not args.filepath.is_file():
        sys.exit(f"File not found: {args.filepath}")
    if args.end_time < args.start_time:
        sys.exit("End time must not precede start time.")

    window_s = (args.end_time - args.start_time).total_seconds()
    print(f"Total window duration: {window_s:.3f} s")

    series, units = collect_series(args.filepath, args.start_time, args.end_time, verbose=args.verbose, debug=args.debug)

    impulses = compute_impulses(series)
    if impulses:
        print("\nLoad-cell impulse (value × s):")
        for tag, J in impulses.items():
            unit = units.get(tag, "")
            print(f"  {tag:20s} {J:.4g} {unit}")
    else:
        print("No load-cell impulse calculable.")

    maxes = compute_maxes(series)
    if maxes:
        print("\nMaximum value per tag:")
        for tag, mx in maxes.items():
            unit = units.get(tag, "")
            print(f"  {tag:20s} {mx:.4g} {unit}")
    else:
        print("No numeric data to compute maxima.")

    plot_series(series, out_dir=args.output_dir, interactive=args.interactive)

if __name__ == "__main__":
    main()

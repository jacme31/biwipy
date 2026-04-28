# -*- coding: utf-8 -*-
"""
Utilities for comparing Grib objects without side effects.
"""

from typing import Any
import numpy as np


def _arrays_match(arr1: np.ndarray, arr2: np.ndarray) -> bool:
    return np.array_equal(arr1, arr2)


def compare_grib_objects(grib1: Any,
                         grib2: Any,
                         name1: str = "grib1",
                         name2: str = "grib2",
                         verbose: bool = True) -> bool:
    """
    Compare two Grib-like objects and return True if identical.

    Expected attributes:
    - lst_gribtimes: list of datetime
    - lst_u10: list of numpy arrays
    - lst_v10: list of numpy arrays
    - lst_gust: list of numpy arrays
    """
    all_match = True

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    log("\n" + "=" * 60)
    log(f"COMPARISON: {name1} vs {name2}")
    log("=" * 60)

    # 1. Compare timestamps
    log("\n1. Timestamps comparison:")
    log(f"   {name1}: {len(grib1.lst_gribtimes)} timestamps")
    log(f"   {name2}: {len(grib2.lst_gribtimes)} timestamps")

    if len(grib1.lst_gribtimes) != len(grib2.lst_gribtimes):
        log("   ! LENGTH MISMATCH")
        all_match = False
    else:
        times_match = all(t1 == t2 for t1, t2 in zip(grib1.lst_gribtimes, grib2.lst_gribtimes))
        if times_match:
            log("   OK All timestamps match")
            log(f"   Time range: {grib1.lst_gribtimes[0]} to {grib1.lst_gribtimes[-1]}")
        else:
            log("   ! TIMESTAMPS DIFFER")
            all_match = False
            for i, (t1, t2) in enumerate(zip(grib1.lst_gribtimes, grib2.lst_gribtimes)):
                if t1 != t2:
                    log(f"      Index {i}: {t1} != {t2}")
                    if i > 5:
                        log("      ... (showing first 5 differences)")
                        break

    # 2. Compare u10 data
    log("\n2. U10 wind component comparison:")
    log(f"   {name1}: {len(grib1.lst_u10)} arrays")
    log(f"   {name2}: {len(grib2.lst_u10)} arrays")

    if len(grib1.lst_u10) != len(grib2.lst_u10):
        log("   ! LENGTH MISMATCH")
        all_match = False
    else:
        u10_diffs = []
        for i, (u1, u2) in enumerate(zip(grib1.lst_u10, grib2.lst_u10)):
            if not _arrays_match(u1, u2):
                max_diff = np.max(np.abs(u1 - u2))
                u10_diffs.append((i, max_diff))

        if not u10_diffs:
            log("   OK All u10 arrays match exactly")
        else:
            log(f"   ! {len(u10_diffs)} arrays differ")
            all_match = False
            for i, diff in u10_diffs[:5]:
                log(f"      Index {i} (time {grib1.lst_gribtimes[i]}): max diff = {diff:.6f}")
            if len(u10_diffs) > 5:
                log(f"      ... (showing first 5 of {len(u10_diffs)} differences)")

    # 3. Compare v10 data
    log("\n3. V10 wind component comparison:")
    log(f"   {name1}: {len(grib1.lst_v10)} arrays")
    log(f"   {name2}: {len(grib2.lst_v10)} arrays")

    if len(grib1.lst_v10) != len(grib2.lst_v10):
        log("   ! LENGTH MISMATCH")
        all_match = False
    else:
        v10_diffs = []
        for i, (v1, v2) in enumerate(zip(grib1.lst_v10, grib2.lst_v10)):
            if not _arrays_match(v1, v2):
                max_diff = np.max(np.abs(v1 - v2))
                v10_diffs.append((i, max_diff))

        if not v10_diffs:
            log("   OK All v10 arrays match exactly")
        else:
            log(f"   ! {len(v10_diffs)} arrays differ")
            all_match = False
            for i, diff in v10_diffs[:5]:
                log(f"      Index {i} (time {grib1.lst_gribtimes[i]}): max diff = {diff:.6f}")
            if len(v10_diffs) > 5:
                log(f"      ... (showing first 5 of {len(v10_diffs)} differences)")

    # 4. Compare gust data
    log("\n4. Gust wind comparison:")
    log(f"   {name1}: {len(grib1.lst_gust)} arrays")
    log(f"   {name2}: {len(grib2.lst_gust)} arrays")

    if len(grib1.lst_gust) != len(grib2.lst_gust):
        log("   ! LENGTH MISMATCH")
        all_match = False
    else:
        gust_diffs = []
        for i, (g1, g2) in enumerate(zip(grib1.lst_gust, grib2.lst_gust)):
            if not _arrays_match(g1, g2):
                max_diff = np.max(np.abs(g1 - g2))
                gust_diffs.append((i, max_diff))

        if not gust_diffs:
            log("   OK All gust arrays match exactly")
        else:
            log(f"   ! {len(gust_diffs)} arrays differ")
            all_match = False
            for i, diff in gust_diffs[:5]:
                log(f"      Index {i} (time {grib1.lst_gribtimes[i]}): max diff = {diff:.6f}")
            if len(gust_diffs) > 5:
                log(f"      ... (showing first 5 of {len(gust_diffs)} differences)")

    log("\n" + "=" * 60)
    if all_match:
        log(f"OK RESULT: {name1} and {name2} are IDENTICAL")
    else:
        log(f"! RESULT: {name1} and {name2} are DIFFERENT")
    log("=" * 60 + "\n")

    return all_match

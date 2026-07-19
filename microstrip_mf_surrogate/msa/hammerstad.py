"""
Hammerstad(-Jensen) の近似式によるマイクロストリップ線路パラメータ。

資料 p.33 「線路インピーダンスはHammerstadの近似式で求める」
資料 p.31 「W4 50Ωライン幅 Hammerstad-Jensen式 誘電率と基板厚さの関数」

- eeff : 実効比誘電率 (フリンジングにより er と 1 の間の値になる)
- Z0   : 特性インピーダンス [ohm]
- 逆問題: 目標 Z0 (=50ohm) を与える線路幅 W を数値的に求める

いずれも幅 W と基板厚 h の比 u=W/h と 基板比誘電率 er の関数。
"""
from __future__ import annotations

import numpy as np


def eeff_microstrip(w: float, h: float, er: float) -> float:
    """実効比誘電率 eeff (Hammerstad)。"""
    u = w / h
    a = 1.0 + (1.0 / 49.0) * np.log(
        (u ** 4 + (u / 52.0) ** 2) / (u ** 4 + 0.432)
    ) + (1.0 / 18.7) * np.log(1.0 + (u / 18.1) ** 3)
    b = 0.564 * ((er - 0.9) / (er + 3.0)) ** 0.053
    eeff = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 * (1.0 + 10.0 / u) ** (-a * b)
    return float(eeff)


def z0_microstrip(w: float, h: float, er: float) -> float:
    """特性インピーダンス Z0 [ohm] (Hammerstad)。"""
    u = w / h
    eeff = eeff_microstrip(w, h, er)
    # Hammerstad-Jensen 単位インピーダンス (空気中)
    f = 6.0 + (2.0 * np.pi - 6.0) * np.exp(-((30.666 / u) ** 0.7528))
    z01 = 60.0 * np.log(f / u + np.sqrt(1.0 + (2.0 / u) ** 2))
    return float(z01 / np.sqrt(eeff))


def width_for_z0(z0_target: float, h: float, er: float) -> float:
    """目標 Z0 を与える線路幅 W [m] を二分法で求める(合成問題)。"""
    lo, hi = 1e-5 * h + 1e-6, 100.0 * h
    # z0 は W に対して単調減少
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if z0_microstrip(mid, h, er) > z0_target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def line_params(w: float, h: float, er: float, length: float, c0: float):
    """線路寸法 -> (遅延時間 td [s], 特性インピーダンス Z0 [ohm])。

    資料 p.33「線路中の伝搬速度は有効誘電率√εeffで真空の光速を割って求める」
    伝搬速度 v = c0 / sqrt(eeff), td = length / v。
    """
    eeff = eeff_microstrip(w, h, er)
    z0 = z0_microstrip(w, h, er)
    v = c0 / np.sqrt(eeff)
    td = length / v
    return td, z0, eeff

"""
S11(f) から評価指標 f0, |S11min|, QL を計算し、エラーデータを除外する。

資料 p.35 「後処理」:
 (1) データをスプライン補間 (FEMのみ 20MHz -> 2MHz)
 (2) 2GHz-3GHz の最小 |S11| を s11min、その時の周波数を f0
 (3) |S11| <= sqrt((1+s11min^2)/2) の周波数幅 Δf から QL = f0/Δf
 (4) 共振が見えない等のデータはエラーとして除外
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.interpolate import CubicSpline


@dataclass
class Metrics:
    f0: float          # 共振周波数 [Hz]
    s11min: float      # |S11| の最小値 (線形, <=0.316 で RL>=10dB)
    QL: float          # Loaded Q
    valid: bool        # エラー判定 (True=有効)
    reason: str = ""   # 無効理由


def extract_metrics(freqs: np.ndarray, s11: np.ndarray,
                    refine: bool = False,
                    f_lo: float = 2.0e9, f_hi: float = 3.0e9) -> Metrics:
    """周波数と S11(複素) から指標を抽出。

    refine=True で 2MHz 相当にスプライン補間(FEM後処理を模擬)。
    """
    mag = np.abs(s11)
    if refine:
        # 20MHz -> 2MHz 相当に細分化
        cs = CubicSpline(freqs, mag)
        fine = np.linspace(freqs[0], freqs[-1], (len(freqs) - 1) * 10 + 1)
        freqs, mag = fine, cs(fine)

    # 帯域内 (2-3GHz) に限定
    band = (freqs >= f_lo) & (freqs <= f_hi)
    if not np.any(band):
        return Metrics(np.nan, np.nan, np.nan, False, "no band data")
    fb, mb = freqs[band], mag[band]

    i = int(np.argmin(mb))
    s11min = float(mb[i])
    f0 = float(fb[i])

    # 共振が浅すぎる / 端で最小 = エラー
    if s11min > 0.98:
        return Metrics(f0, s11min, np.nan, False, "no resonance")
    if i == 0 or i == len(mb) - 1:
        return Metrics(f0, s11min, np.nan, False, "min at edge")

    # 半電力相当のしきい値 (資料の定義)
    thr = np.sqrt((1.0 + s11min ** 2) / 2.0)

    # f0 の左右で mag=thr を横切る点を線形補間で求める
    def cross(dir_):
        j = i
        while 0 <= j + dir_ < len(mb) and mb[j + dir_] < thr:
            j += dir_
        jn = j + dir_
        if jn < 0 or jn >= len(mb):
            return None
        # mb[j] < thr <= mb[jn] の間を線形補間
        x0, x1 = fb[j], fb[jn]
        y0, y1 = mb[j], mb[jn]
        if y1 == y0:
            return x1
        return x0 + (thr - y0) * (x1 - x0) / (y1 - y0)

    fL = cross(-1)
    fR = cross(+1)
    if fL is None or fR is None:
        return Metrics(f0, s11min, np.nan, False, "band edge not found")
    df = fR - fL
    if df <= 0:
        return Metrics(f0, s11min, np.nan, False, "bad bandwidth")
    QL = f0 / df
    return Metrics(f0, s11min, float(QL), True, "")


# 仕様 (資料 p.28)
SPEC = {
    "f0_lo": 2.44e9,
    "f0_hi": 2.46e9,
    "s11min_max": 0.316,   # RL >= 10 dB
    "QL_max": 30.0,
}


def check_spec(m: Metrics) -> dict:
    """仕様適合判定。"""
    return {
        "f0": SPEC["f0_lo"] <= m.f0 <= SPEC["f0_hi"],
        "s11min": m.s11min <= SPEC["s11min_max"],
        "QL": m.QL <= SPEC["QL_max"],
    }

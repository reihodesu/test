"""
無次元設計変数 X1..X6 -> 物理寸法への変換。

資料 p.32 の実験計画(パラメータ表)に対応:

    X1 : 幅/波長           W1 = X1 * lambda        [0.15, 1]
    X2 : 下部パッチ幅比     W2 = X2*(W1-W4-1mm)/2   [0.5, 1]   ※資料の比
    X3 : パッチ長さ係数     Len3 = 2*X3*lambda      [0.15, 0.35] (片側λ/4共振で~0.25)
    X4 : 給電オフセット     0=中央給電, 1=端給電    [-0.1, 1]
    X5 : 基板厚さ H [m]                             [0.0015, 0.005]
    X6 : 基板比誘電率 er                            [1.5, 5]

    W4 : 50Ωライン幅 = Hammerstad-Jensen で er,H から決まる従属量
    Len4: 給電線長 = lambda (資料「1波長分を確保」)

資料 p.31「共振周波数はパッチ部分の長さで調整/インピーダンスは給電位置で調整」。

lambda は非次元化の基準波長。ここでは設計周波数の自由空間波長 lambda0 を用い、
各線路の実際の電気長は Hammerstad の eeff から個別に計算する(tline側)。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import numpy as np

from . import hammerstad

# 設計変数の範囲 (資料 p.32)
BOUNDS = {
    "X1": (0.15, 1.00),
    "X2": (0.50, 1.00),
    "X3": (0.15, 0.35),
    "X4": (-0.10, 1.00),
    "X5": (0.0015, 0.005),
    "X6": (1.5, 5.0),
}
XKEYS = ["X1", "X2", "X3", "X4", "X5", "X6"]

# 長さ較正定数: 本トイモデル(自由空間波長で無次元化)の共振点を、資料の動作点
# (X3~0.22 付近で f0~2.45GHz) に合わせるための係数。物理を変えず縮尺のみ調整。
LEN_CAL = 0.69


@dataclass
class Geometry:
    """物理寸法 [m] とサブストレート。tline / 各モデルが参照する。"""
    W1: float      # 上部パッチ幅
    W2: float      # 下部(ノッチ)アーム幅 (片側)
    W3: float      # 下部アーム幅 (対称、= W2)
    W4: float      # 50Ω 給電線幅
    Len1: float    # 給電点 -> 近接放射端 (T1) 長さ
    Len2: float    # 給電点 -> 遠方放射端アーム (T2) 長さ
    Len3: float    # 給電点 -> 遠方放射端アーム (T3) 長さ
    Len4: float    # 50Ω 給電線長
    H: float       # 基板厚
    er: float      # 基板比誘電率
    lam0: float    # 基準自由空間波長

    def as_dict(self):
        return asdict(self)


def build_geometry(X, f_design: float, c0: float) -> Geometry:
    """設計変数ベクトル X=[X1..X6] -> Geometry。"""
    X1, X2, X3, X4, X5, X6 = [float(v) for v in X]
    H = X5
    er = X6
    lam0 = c0 / f_design

    # 50Ω 給電線幅 (誘電率と基板厚の関数)
    W4 = hammerstad.width_for_z0(50.0, H, er)

    # 幅
    W1 = X1 * lam0
    W2 = X2 * max(W1 - W4 - 1e-3, 1e-3) / 2.0   # 資料の式
    W3 = W2

    # パッチ長(半波共振 ~ 2*(λg/4))。基準は自由空間波長で無次元化。
    patch = 2.0 * X3 * lam0 * LEN_CAL   # Len3 = 2*X3*lambda 相当の全長(較正済み)
    half = patch / 2.0
    # 給電オフセット: X4=0 中央, X4=1 端 -> 近/遠の非対称化
    off = X4 * half * 0.9
    Len1 = max(half - off, 0.05 * lam0)   # 近接端まで
    Len2 = half + off                     # 遠方端まで (アーム)
    Len3 = half + off
    Len4 = lam0                           # 給電線長 = 1波長 (資料)

    return Geometry(W1, W2, W3, W4, Len1, Len2, Len3, Len4, H, er, lam0)

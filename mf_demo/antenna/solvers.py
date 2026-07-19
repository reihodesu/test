"""antenna/solvers.py  —  成果物A / A-4: 疑似ソルバ（LF・HF・delta）

■ 設計意図（HANDOVER A-4）
  HF(x) を「真値」とし、LF(x) = HF(x) - delta(x) と定義する。
  すなわち LF/HF を別々にでっち上げず、両者の差 delta を明示的に設計する。

  ここでは実装上、次の等価な分解で構成する:
      base(x)   … 低忠実度（回路モデル相当）が捉える滑らかな主構造  → LF
      delta(x)  … 高忠実度だけが捉える微細構造（表面波・高次モード結合等の
                   等価効果）。滑らか・低周波・小振幅・X4 に非単調。
      HF(x) = base(x) + delta(x)          （= 物理的にもっともらしい真値）
      LF(x) = HF(x) - delta(x) = base(x)  （= HF の劣化版）

  この分解により:
    - delta は「滑らかで学習しやすい差分」になり、MF が効く前提を満たす。
    - log10(QL) の X4 依存に dip（くぼみ）を delta 内へ入れることで、
      「LF 単独では見えず、MF なら再現できる構造」のベンチマークになる
      （LF=base は X4 に対し単調、HF=base+delta は dip を持つ）。

■ 物理の骨格（demo grade。較正定数で目標帯に中心化している）
  - f0    : 半波長パッチの共振式（Hammerstad の実効誘電率＋フリンジ長補正）
  - s11min: インセット給電の入力抵抗 R_in(X4) と 50Ω の反射係数 |Γ|
  - log10QL: 放射Qの経験則（薄い基板・低誘電率ほど広帯域＝低Q）

  参考: Balanis, "Antenna Theory"（パッチ共振・フリンジ・インセット給電）。
  数値は原理提示用の合成モデルであり実測較正ではない。

■ 数値的な暴れ（HANDOVER A-4 末尾）
  一部の設計で共振が帯域外に出る／薄基板×高誘電率の隅で解が破綻する状況を
  意図的に作り、後段（A-5）の「エラーデータ除外」工程が意味を持つようにする。
  無効サンプルは valid=False（応答は NaN）で返す。
"""
from __future__ import annotations

import numpy as np

from .config import (
    C_LIGHT, F_DESIGN_HZ, LAM0, NOMINAL, VAR_NAMES, RESP_NAMES,
)

Z0 = 50.0  # 給電線特性インピーダンス [Ω]

# 有効帯域: この外に共振が出たら「ソルバ発散」= 無効サンプル扱い
# 設計箱は f0 を広く散らす（~1.6-4.7GHz）ため、帯域外は一定割合発生する。
# エラー除外(A-5)が意味を持つ水準に調整（~1/4 前後）。
_F_BAND = (1.8, 3.3)  # [GHz]


# ---------------------------------------------------------------------------
# 物理ヘルパ
# ---------------------------------------------------------------------------
def _unpack(X: np.ndarray):
    """(n,6) を各設計変数の列に展開。"""
    X = np.atleast_2d(np.asarray(X, dtype=float))
    return (X[:, 0], X[:, 1], X[:, 2], X[:, 3], X[:, 4], X[:, 5]), X.shape[0]


def _eps_eff(eps_r, W, h):
    """Hammerstad-Jensen の実効比誘電率（マイクロストリップ）。"""
    return (eps_r + 1.0) / 2.0 + (eps_r - 1.0) / 2.0 / np.sqrt(1.0 + 12.0 * h / W)


def _delta_L(eps_eff, W, h):
    """開放端フリンジングによる等価長さ増分 ΔL（Hammerstad）。"""
    return (0.412 * h * (eps_eff + 0.3) * (W / h + 0.264)
            / ((eps_eff - 0.258) * (W / h + 0.8)))


def _f0_raw_hz(X1, X2, X3, X4, X5, X6):
    """較正前の共振周波数 [Hz]。半波長パッチ f0 = c / (2 (L+2ΔL) √εeff)。"""
    W = X1 * LAM0                       # パッチ幅 [m]
    h = X5                              # 基板厚さ [m]
    eps_r = X6
    eps_eff = _eps_eff(eps_r, W, h)
    dL = _delta_L(eps_eff, W, h)
    # 実効長: X3(=L/λ) を基準に、下部パッチ幅比 X2 と給電オフセット X4 で微修正
    L = X3 * LAM0 * (1.0 + 0.02 * (X2 - 0.75)) * (1.0 - 0.01 * X4)
    return C_LIGHT / (2.0 * (L + 2.0 * dL) * np.sqrt(eps_eff)), eps_eff


# 公称点で 2.45GHz になるよう較正（import 時に一度だけ確定 → 再現性あり）
def _calibration_kf() -> float:
    (x1, x2, x3, x4, x5, x6), _ = _unpack(NOMINAL)
    f_raw, _ = _f0_raw_hz(x1, x2, x3, x4, x5, x6)
    return float(F_DESIGN_HZ / f_raw[0])


_K_F = _calibration_kf()


# ---------------------------------------------------------------------------
# base(x)  … LF（滑らかな主構造）
# ---------------------------------------------------------------------------
def _base(X: np.ndarray) -> dict:
    (x1, x2, x3, x4, x5, x6), n = _unpack(X)

    # --- f0 [GHz] : 較正済み半波長パッチ ---
    f_raw, eps_eff = _f0_raw_hz(x1, x2, x3, x4, x5, x6)
    f0 = _K_F * f_raw / 1e9  # GHz

    # --- s11min : インセット給電 R_in(X4) と 50Ω の反射 ---
    # R_in = R_edge * cos^2(pi*(0.5 - X4))
    #   X4=0(中央) → R_in≈0（電圧ノード）, 端に寄るほど高抵抗。
    #   50Ω 整合は中間の X4 で達成 → そこで |Γ| が最小（深いノッチ）。
    R_edge = 200.0 + 30.0 * (x6 - 3.25) - 250.0 * (x1 - 0.25)
    R_edge = np.clip(R_edge, 80.0, 400.0)
    R_in = R_edge * np.cos(np.pi * (0.5 - x4)) ** 2
    gamma = (R_in - Z0) / (R_in + Z0)
    s11min = np.sqrt(gamma ** 2 + 0.02 ** 2)  # 有限の整合下限を持たせる

    # --- log10(QL) : 放射Qの経験則（X4 には緩い単調項のみ = dip を持たない） ---
    log10QL = (
        1.445
        + 0.60 * (x6 - 3.25) / 3.5      # 高誘電率 → 高Q（狭帯域）
        - 0.50 * (x5 - 0.00325) / 0.0035  # 厚い基板 → 低Q（広帯域）
        + 0.15 * (x3 - 0.25) / 0.20
        + 0.10 * x4                       # X4 に対しては緩やかな単調（dip なし）
    )
    return {"f0": f0, "s11min": s11min, "log10QL": log10QL,
            "_eps_eff": eps_eff}


# ---------------------------------------------------------------------------
# delta(x)  … HF だけが持つ微細構造（滑らか・小振幅・X4 に非単調）
# ---------------------------------------------------------------------------
def delta(X: np.ndarray) -> dict:
    """LF→HF の差分補正 delta を返す（応答ごと）。

    性質（HANDOVER A-4）:
      - 滑らかで低周波（設計変数に対しゆっくり変化）
      - HF より小振幅
      - X4（給電位置）に対して非単調な構造を持つ
      - log10(QL) には X4=0.10 近傍に dip（表面波結合の等価効果）を入れる
    """
    (x1, x2, x3, x4, x5, x6), n = _unpack(X)

    # f0: ごく小さな滑らかうねり（振幅 < ~0.02GHz、f0 の 1% 未満）
    d_f0 = 0.012 * np.sin(np.pi * (x1 - 0.25) / 0.20) \
        + 0.008 * np.cos(np.pi * (x4 - 0.075) / 0.35)

    # s11min: 小さな滑らか補正（X4 に非単調）
    d_s11 = 0.03 * np.sin(np.pi * (x4 - 0.05) / 0.30) \
        + 0.01 * np.cos(np.pi * (x6 - 3.25) / 3.5)

    # log10QL: 主役の dip（X4=0.10, 幅0.06 のガウス窪み）＋微小な滑らか項
    #   他変数で軽く変調し、純粋な 1 次元構造にならないようにする。
    dip_center, dip_width, dip_depth = 0.10, 0.06, 0.28
    modulation = 1.0 + 0.30 * (x6 - 3.25) / 3.5
    dip = -dip_depth * modulation * np.exp(-((x4 - dip_center) / dip_width) ** 2)
    d_QL = dip + 0.05 * np.sin(np.pi * (x6 - 3.25) / 3.5)

    return {"f0": d_f0, "s11min": d_s11, "log10QL": d_QL}


# ---------------------------------------------------------------------------
# 有効性（数値的な暴れの模擬）
# ---------------------------------------------------------------------------
def _validity(base: dict, X: np.ndarray, fidelity: str) -> np.ndarray:
    (x1, x2, x3, x4, x5, x6), n = _unpack(X)
    f0 = base["f0"]
    eps_eff = base["_eps_eff"]
    valid = np.ones(n, dtype=bool)
    # 共振が帯域外に飛んだ設計は「発散」＝無効
    valid &= (f0 >= _F_BAND[0]) & (f0 <= _F_BAND[1])
    # 実効誘電率の退化（フリンジ式が不安定）を無効化
    valid &= (eps_eff > 0.30)
    # HF（電磁界解析相当）は薄基板×高誘電率の隅でメッシュ/表面波が破綻しやすい
    if fidelity == "HF":
        valid &= ~((x5 < 0.0018) & (x6 > 4.5))
    return valid


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------
def solve(X: np.ndarray, fidelity: str = "HF") -> dict:
    """設計点 X（(n,6) または (6,)）を評価。

    Returns dict:
      f0, s11min, log10QL : 各 shape (n,) の応答（無効サンプルは NaN）
      valid               : shape (n,) の bool
    """
    if fidelity not in ("HF", "LF"):
        raise ValueError("fidelity must be 'HF' or 'LF'")
    base = _base(X)
    out = {r: np.array(base[r], dtype=float) for r in RESP_NAMES}
    if fidelity == "HF":
        d = delta(X)
        for r in RESP_NAMES:
            out[r] = out[r] + d[r]
    valid = _validity(base, X, fidelity)
    for r in RESP_NAMES:
        out[r] = np.where(valid, out[r], np.nan)
    out["valid"] = valid
    return out


def hf_response(X: np.ndarray) -> dict:
    """高忠実度（真値）。"""
    return solve(X, "HF")


def lf_response(X: np.ndarray) -> dict:
    """低忠実度（回路モデル相当）。"""
    return solve(X, "LF")


if __name__ == "__main__":
    # 動作確認: 公称点の HF/LF と較正定数
    print(f"[calibration] K_F = {_K_F:.4f}")
    hf = hf_response(NOMINAL)
    lf = lf_response(NOMINAL)
    d = delta(NOMINAL)
    for r in RESP_NAMES:
        print(f"  {r:8s} HF={hf[r][0]:+.4f}  LF={lf[r][0]:+.4f}  "
              f"delta={d[r][0]:+.4f}")

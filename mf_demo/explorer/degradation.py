"""explorer/degradation.py — 保存劣化モデル（DC_v5 実式のラッパ）

■ 中核は DC_v5 の実式そのまま
  vendor_dcv5/dc_model.py（= calculators/DC_index/aging/dc_model.py）の
  calc_dc_outputs() を無改変で呼ぶ。保存劣化の閉形式:
      R(t) = R0 + resistance_increase_rate · t        （抵抗: 線形）
      a(t) = a0 + capacity_fade_rate · √t              （容量傾き: √t）
      定 W 放電の閉形式で y_end, Q_t, Ymax 等を算出。

■ HANDOVER B-3 / B-4③（時間依存＋Arrhenius）
  DC_v5 の劣化速度係数（capacity_fade_rate, resistance_increase_rate）を、
  使用温度 T_use の Arrhenius 関数として与える（＝材料/劣化速度は温度依存）:
      k(T) = k_ref · exp(−Ea/R · (1/T − 1/T_ref))
  これにより「初期は √t 項が支配、長期は温度加速した項が支配へ移る」遷移が
  時間推移感度（B-4③）に現れる。飽和項＝√t 由来、Arrhenius 項＝温度加速。

■ 応答（容量維持率 @ 指定時点）
  retention(t) = tmax(storage_year=t) / tmax(storage_year=0)  ∈ (0, 1]
  tmax = 定 W 放電でカットオフ電圧まで放電できる最大時間 [sec]
       = 3600·(b'²−z·R)/(z·a)（∝ 取り出せる容量）。
  劣化で R(t)↑・a(t)↑ すると tmax↓ → 維持率が低下。時間・温度で単調に劣化。
  （注: Q_t=消費容量は劣化で電圧が下がると電流増で逆に増えるため維持率には不適）

■ B-4④ 物理妥当域マスキング
  DomainError（判別式負＝放電不能）/ retention∉(0,1] / T 外挿 は無効サンプル。
"""
from __future__ import annotations

import os
import sys
import math
import numpy as np

# vendor（DC_v5 実式）を import パスに追加
_VENDOR = os.path.join(os.path.dirname(__file__), "vendor_dcv5")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
from dc_model import calc_dc_outputs, DCInputs  # noqa: E402  (DC_v5 実式)
from core.exceptions import DomainError          # noqa: E402

from .cell_design import cell_design
from .config import T_CALIB_C

# --- Arrhenius / 固定放電条件 ------------------------------------------------
R_GAS = 8.3145          # 気体定数 [J/(mol·K)]
T_ABS = 273.15
T_REF_C = 25.0          # Arrhenius 基準温度 [°C]
EA_CAP = 45000.0        # 容量劣化の活性化エネルギー [J/mol]（SEI 成長相当）
EA_RES = 35000.0        # 抵抗上昇の活性化エネルギー [J/mol]

# 固定放電条件（DC_v5 row82 実値: _DVT_DEFAULTS / AgingConstants）
DSCG_POWER = 300.0      # [W]
DSCG_TIME = 90.0        # [sec]
INIT_DSCG_V = 4.0       # b' = b_ocv/2 [V]（row82）
ELY_DIFF = 4.0e-10      # 電解液拡散係数 [m²/s]（AgingConstants.dc_electrolyte_diffusion）
DC_A = 0.7491           # τ² 係数 A
POS_TORT = 0.8733       # ブラッジマン乗数 b


def _arrhenius(k_ref: float, Ea: float, T_c: float) -> float:
    """k(T) = k_ref · exp(−Ea/R·(1/T − 1/T_ref))."""
    Tk = T_c + T_ABS
    Trefk = T_REF_C + T_ABS
    return k_ref * math.exp(-Ea / R_GAS * (1.0 / Tk - 1.0 / Trefk))


def _build_inputs(cell, storage_year: float, T_use: float,
                  k_fade_ref: float, r_inc_ref_mOhm: float) -> DCInputs:
    cap_fade = _arrhenius(k_fade_ref, EA_CAP, T_use)          # [V/Ah/√yr]
    r_inc = _arrhenius(r_inc_ref_mOhm * 1e-3, EA_RES, T_use)  # [Ohm/yr]
    return DCInputs(
        dscg_power=DSCG_POWER, dscg_time=DSCG_TIME,
        initial_dscg_voltage=INIT_DSCG_V, storage_year=storage_year,
        R0=cell.R0, resistance_increase_rate=r_inc,
        a0=cell.a0, capacity_fade_rate=cap_fade,
        K=cell.K, omegaAM=cell.omegaAM, cap_2cyc=cell.cap_2cyc,
        electrolyte_diffusion=ELY_DIFF, eps=cell.eps,
        A=DC_A, pos_tortuosity=POS_TORT, L=cell.L,
        cell_typ_ah=cell.Typ,
    )


def retention_at(x: dict, storage_year: float) -> tuple[float, bool]:
    """独立上流変数 x（dict）と保存時点 t → (容量維持率, 有効フラグ)。

    x keys: coat_load, mix_density, am_frac, am_cap, T_use, k_fade_ref, r_inc_ref
    """
    T_use = x["T_use"]
    # B-4④: 温度較正域外は外挿 → 無効
    if not (T_CALIB_C[0] <= T_use <= T_CALIB_C[1]):
        return math.nan, False
    cell = cell_design(x["coat_load"], x["mix_density"], x["am_frac"], x["am_cap"])
    if cell.eps <= 0.0 or cell.eps >= 1.0:
        return math.nan, False
    try:
        tmax_t = calc_dc_outputs(_build_inputs(cell, storage_year, T_use,
                                               x["k_fade_ref"], x["r_inc_ref"])).tmax
        tmax_0 = calc_dc_outputs(_build_inputs(cell, 0.0, T_use,
                                               x["k_fade_ref"], x["r_inc_ref"])).tmax
    except (DomainError, ValueError):
        return math.nan, False           # 判別式負＝放電不能（寿命超過）
    if not (math.isfinite(tmax_t) and math.isfinite(tmax_0)) or tmax_0 <= 0:
        return math.nan, False
    ret = tmax_t / tmax_0
    if not (0.0 < ret <= 1.0000001):     # 非物理（負/1超）は無効
        return math.nan, False
    return min(ret, 1.0), True


def evaluate(X: np.ndarray, keys: list[str], storage_year: float):
    """設計点行列 X（n×d, 列順=keys）→ (retention[n], valid[n])。

    HANDOVER の evaluate() 差し替え点。中身を DC_v5 実式に置換したもの。
    """
    n = len(X)
    ret = np.full(n, np.nan)
    ok = np.zeros(n, bool)
    for i, row in enumerate(X):
        x = {k: float(v) for k, v in zip(keys, row)}
        r, v = retention_at(x, storage_year)
        ret[i] = r
        ok[i] = v
    return ret, ok


if __name__ == "__main__":
    from .config import VARSPEC, XKEYS
    x0 = {k: VARSPEC[k]["mean"] if "mean" in VARSPEC[k]
          else sum(VARSPEC[k]["design"]) / 2 for k in XKEYS}
    print("[公称点 x0]", {k: round(v, 4) for k, v in x0.items()})
    for t in [0.0, 1.0, 3.0, 5.0, 8.0]:
        r, v = retention_at(x0, t)
        print(f"  t={t:4.1f}yr  retention={r:.4f}  valid={v}")

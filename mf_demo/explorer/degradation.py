"""explorer/degradation.py — 保存劣化モデル（DC_v5 実式のラッパ, 報告書準拠 v2）

■ 中核は DC_v5 の実式そのまま（vendor_dcv5/dc_model.py = 無改変）
  定 W 放電の閉形式で放電後電圧 y_end と限界Li塩濃度 Cli_plus_min を算出:
      R(t) = R0 + r(T)·t                     （抵抗: 線形 / 報告書 §4 で実証）
      a(t) = a0 + k(T)·√t                     （容量傾き: √t / 報告書 §3・復帰率√t）
      y_end = b' + √(b'² − z·R − z·a·t/3600)   （放電後電圧）
      Cli_plus_min = C_rate·Qareal/(Jlim·1000), Jlim=2zF·Dely·ε^γ / L  （限界Li塩濃度）

■ 報告書との対応（レビュー反映）
  - b' = b_ocv/2 = 2.0V（AgingConstants.b_ocv=4.0）→ y_end は物理域 2.5-4V。
  - 主応答は「放電後電圧 y_end」「限界Li塩濃度 Cli」＝設計成立条件（§2, NCR2170JB Step2）。
  - 劣化速度係数 k, r は使用温度 T の Arrhenius（10℃2倍則 Ea≈60kJ/mol で較正, §6）。
  - 劣化率は現行から半減想定（NCR2170JB Step2 の前提）。
  - 2劣化モード: 無次元指標 Cli/C_Li_design で 抵抗劣化 / 拡散劣化 を判定（§2 図）。

■ B-4④ 物理妥当域マスキング
  DomainError（判別式負＝300W維持不可＝寿命超過）/ 温度外挿 / 非物理値 は無効。
"""
from __future__ import annotations

import os
import sys
import math
import numpy as np

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor_dcv5")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
from dc_model import calc_dc_outputs, DCInputs  # noqa: E402  (DC_v5 実式)
from core.exceptions import DomainError          # noqa: E402

from .cell_design import cell_design
from .config import T_CALIB_C, C_LI_DESIGN

# --- Arrhenius（10℃2倍則で較正）／固定放電条件 ------------------------------
R_GAS = 8.3145
T_ABS = 273.15
T_REF_C = 45.0          # 劣化速度の基準温度（保存中央域）[°C]
# Ea ≈ 60 kJ/mol → 45℃近傍で 10℃あたり速度比 ~2（10℃2倍則, 報告書 §1/§6）
EA_CAP = 60000.0        # 容量劣化の活性化エネルギー [J/mol]
EA_RES = 60000.0        # 抵抗上昇の活性化エネルギー [J/mol]

# 固定放電条件（DC 向け目標: 300W/90s, 報告書 NCR2170JB Step2）
DSCG_POWER = 300.0
DSCG_TIME = 90.0
INIT_DSCG_V = 2.0       # b' = b_ocv/2 [V]（物理域）
B_OCV = 2.0 * INIT_DSCG_V
DC_A = 0.7491
# 劣化速度基準（現行から半減想定, @25℃）。T の Arrhenius で加速。
K_FADE_REF = 0.0085     # 容量劣化速度 [V/Ah/√yr]（row82 実測）
R_INC_REF = 0.5e-3      # 抵抗上昇率 [Ohm/yr]（現行~1mΩ/yr の半減想定）


def _arrhenius(k_ref: float, Ea: float, T_c: float) -> float:
    Tk, Trefk = T_c + T_ABS, T_REF_C + T_ABS
    return k_ref * math.exp(-Ea / R_GAS * (1.0 / Tk - 1.0 / Trefk))


def _build_inputs(cell, R0_ohm, Dely, gamma, storage_year, T_use) -> DCInputs:
    return DCInputs(
        dscg_power=DSCG_POWER, dscg_time=DSCG_TIME,
        initial_dscg_voltage=INIT_DSCG_V, storage_year=storage_year,
        R0=R0_ohm,
        resistance_increase_rate=_arrhenius(R_INC_REF, EA_RES, T_use),
        a0=cell.a0,
        capacity_fade_rate=_arrhenius(K_FADE_REF, EA_CAP, T_use),
        K=cell.K, omegaAM=cell.omegaAM, cap_2cyc=cell.cap_2cyc,
        electrolyte_diffusion=Dely, eps=cell.eps,
        A=DC_A, pos_tortuosity=gamma, L=cell.L,
        tau_pos=gamma,            # 曲路率 γ を直接採用（D_eff=Dely·ε^γ）
        cell_typ_ah=cell.Typ,
    )


def responses_at(x: dict, storage_year: float) -> dict:
    """独立上流変数 x（dict）と保存時点 t → 応答一式。

    x keys: R0_init[mΩ], coat_load, am_cap, mix_density, Dely, gamma, T_use
    returns: {y_end, Cli, ndc, mode, valid}
      y_end : 放電後電圧 [V]
      Cli   : 限界Li塩濃度 [mol/L]
      ndc   : 無次元指標 = Cli / C_Li_design（>1 で拡散劣化モード）
      mode  : 'resistance' / 'diffusion'
    """
    T_use = x["T_use"]
    if not (T_CALIB_C[0] <= T_use <= T_CALIB_C[1]):
        return {"y_end": math.nan, "Cli": math.nan, "ndc": math.nan,
                "mode": None, "valid": False}
    cell = cell_design(x["coat_load"], x["mix_density"], x["am_cap"])
    if not (0.0 < cell.eps < 1.0):
        return {"y_end": math.nan, "Cli": math.nan, "ndc": math.nan,
                "mode": None, "valid": False}
    try:
        o = calc_dc_outputs(_build_inputs(cell, x["R0_init"] * 1e-3, x["Dely"],
                                          x["gamma"], storage_year, T_use))
    except (DomainError, ValueError):
        return {"y_end": math.nan, "Cli": math.nan, "ndc": math.nan,
                "mode": None, "valid": False}
    y_end, cli = o.y_end, o.Cli_plus_min
    if not (math.isfinite(y_end) and math.isfinite(cli)) or cli <= 0 \
            or not (0.0 < y_end <= B_OCV):
        return {"y_end": math.nan, "Cli": math.nan, "ndc": math.nan,
                "mode": None, "valid": False}
    ndc = cli / C_LI_DESIGN
    return {"y_end": y_end, "Cli": cli, "ndc": ndc,
            "mode": "diffusion" if ndc > 1.0 else "resistance", "valid": True}


def evaluate(X: np.ndarray, keys: list[str], storage_year: float) -> dict:
    """設計点行列 X（n×d, 列順=keys）→ 応答配列一式。"""
    n = len(X)
    out = {"y_end": np.full(n, np.nan), "Cli": np.full(n, np.nan),
           "ndc": np.full(n, np.nan), "valid": np.zeros(n, bool)}
    for i, row in enumerate(X):
        x = {k: float(v) for k, v in zip(keys, row)}
        r = responses_at(x, storage_year)
        out["y_end"][i] = r["y_end"]; out["Cli"][i] = r["Cli"]
        out["ndc"][i] = r["ndc"]; out["valid"][i] = r["valid"]
    return out


if __name__ == "__main__":
    from .config import VARSPEC, XKEYS
    x0 = {k: VARSPEC[k]["mean"] for k in XKEYS}
    print("[公称点]", {k: (f"{v:.2e}" if v < 1e-3 else round(v, 3))
                     for k, v in x0.items()})
    for t in [0.0, 1.0, 3.0, 5.0, 8.0]:
        r = responses_at(x0, t)
        print(f"  t={t:4.1f}yr  y_end={r['y_end']:.3f}V  Cli={r['Cli']:.3f}M  "
              f"ndc={r['ndc']:.2f}  mode={r['mode']}  valid={r['valid']}")

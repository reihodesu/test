"""explorer/cell_design.py — セル設計計算（独立上流変数 → 派生量）

■ 役割（HANDOVER B-4②「DOE は独立な上流変数にのみ張る」）
  Sobol 分解は入力が独立であることが前提。電極厚・空隙率・容量のように設計式で
  結ばれた派生量を直接サンプリングすると分解の解釈が破綻する。DOE を張るのは
  真に独立な上流変数のみとし、派生量（K/eps/L/Qareal/Typ/a0）は評価関数の
  内部（本モジュール）で計算する。

■ 報告書準拠 v2
  独立変数: 正極塗布量・活物質密度・正極利用率（＋固定 活物質比）。
  セル抵抗 R0 は本モジュールでは派生させず、独立変数として degradation 側で扱う
  （報告書 NCR2170JB Step2 は「セル抵抗」を探索変数に取る＝機構/ケミカルで独立に
   決まる量のため）。

  参考: 標準的な電極設計（面積容量=塗布量×活物質比×比容量、
        空隙率=1−合剤密度/真密度、合剤厚み=塗布量/合剤密度）。
"""
from __future__ import annotations

from dataclasses import dataclass

RHO_TRUE = 4.75          # 正極合剤の理論（真）密度 [g/cm³]（NCA系相当）
AREA_M2 = 0.2256         # 正負極対向面積 [m²]（DC_v5 row82: 2×1880×60×1e-6）
AM_FRAC_FIX = 0.985      # 正極活物質比率 omegaAM [-]（固定; 報告書6因子外）
# Typ↔a0 線形（DC_v5 dc_model.interpolate_typ_capacity と同一係数）
_TYP_C1 = -9.022706511547215
_TYP_C0 = 5.671518551713159


@dataclass(frozen=True)
class DerivedCell:
    K: float          # 正極塗布量 [g/m²]
    eps: float        # 正極合剤空隙率 [-]
    L: float          # 片面正極合剤厚み [m]
    omegaAM: float    # 正極活物質比率 [-]
    cap_2cyc: float   # 正極活物質比容量（利用率）[Ah/g]
    Qareal: float     # 正極面積容量 [Ah/m²]
    Typ: float        # セル Typ 容量 [Ah]
    a0: float         # 初期容量傾き [V/Ah]（Typ と整合）


def cell_design(coat_load: float, mix_density: float, am_cap: float,
                am_frac: float = AM_FRAC_FIX) -> DerivedCell:
    """独立上流変数（設計因子・材料物性）→ 派生量。

    coat_load : 正極塗布量 [mg/cm²]
    mix_density : 正極合剤密度 [g/cm³]
    am_cap : 正極利用率（比容量）[Ah/g]
    """
    K = coat_load * 10.0                      # mg/cm² → g/m²
    eps = 1.0 - mix_density / RHO_TRUE        # 空隙率
    L = coat_load * 1e-3 / mix_density * 1e-2  # 片面合剤厚み [m]
    Qareal = K * am_frac * am_cap             # 面積容量 [Ah/m²]
    Typ = Qareal * AREA_M2                     # セル容量 [Ah]
    a0 = (_TYP_C0 - Typ) / (-_TYP_C1)          # 初期容量傾き（Typ↔a0 整合）
    return DerivedCell(K=K, eps=eps, L=L, omegaAM=am_frac, cap_2cyc=am_cap,
                       Qareal=Qareal, Typ=Typ, a0=a0)

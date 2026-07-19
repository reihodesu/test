"""explorer/cell_design.py — セル設計計算（独立上流変数 → 派生量）

■ 役割（HANDOVER B-4②「DOE は独立な上流変数にのみ張る」）
  Sobol 分解は入力が独立であることが前提。電極厚・空隙率・容量のように
  設計式で結ばれた派生量を直接サンプリングすると、物理的にありえない組合せを
  踏み、分解の解釈が破綻する。
  そこで DOE を張るのは **真に独立な上流変数のみ** とし、派生量（K/eps/L/
  Qareal/Typ）は本モジュール（＝評価関数の内部）で計算する。

  ※ 派生量そのものの寄与を見たい場合は Shapley effects 等が必要になるが、
    本デモのスコープ外（HANDOVER B-4② の注記どおり）。

■ 位置づけ
  ここで実装するのは、DC_v5 CellDesign（calculators/CellDesign/.../Calc.py）の
  「上流→派生」写像を、感度解析デモ用に **物理的に無矛盾な最小スラブモデル** で
  再構成したもの。数値は DC_v5 row82 近傍のオーダーに合わせてある。
  本番では本モジュールを DC_v5 の run_calc() 呼び出しに差し替えられる（seam）。

  参考: 標準的な電極設計（面積容量 = 塗布量×活物質比×比容量、
        空隙率 = 1 − 合剤密度/真密度、合剤厚み = 塗布量/合剤密度）。
"""
from __future__ import annotations

from dataclasses import dataclass

# --- 固定パラメータ（幾何・材料定数） ---------------------------------------
RHO_TRUE = 4.75          # 正極合剤の理論（真）密度 [g/cm³]（NCA系相当）
AREA_M2 = 0.2256         # 正負極対向面積 [m²]（DC_v5 row82: 2×1880×60×1e-6）
# Typ↔a0 線形（DC_v5 dc_model.interpolate_typ_capacity と同一係数）
_TYP_C1 = -9.022706511547215
_TYP_C0 = 5.671518551713159

# R0（初期抵抗）基準（DC_v5 row82: 0.0045 Ω @ 基準厚み/空隙率）
R0_REF = 0.0045
L_REF = 6.3e-5           # 基準合剤厚み [m]
EPS_REF = 0.2864         # 基準空隙率 [-]


@dataclass(frozen=True)
class DerivedCell:
    """セル設計計算の派生量（劣化式への入力になる中間量）。"""
    K: float          # 正極塗布量 [g/m²]
    eps: float        # 正極合剤空隙率 [-]
    L: float          # 片面正極合剤厚み [m]
    omegaAM: float    # 正極活物質比率 [-]
    cap_2cyc: float   # 正極活物質比容量 [Ah/g]
    Qareal: float     # 正極面積容量 [Ah/m²]
    Typ: float        # セル Typ 容量 [Ah]
    a0: float         # 初期容量傾き [V/Ah]（Typ と整合）
    R0: float         # 初期抵抗 [Ohm]


def cell_design(coat_load: float, mix_density: float,
                am_frac: float, am_cap: float) -> DerivedCell:
    """独立上流変数（設計因子・材料物性）→ 派生量。

    Parameters
    ----------
    coat_load : 正極塗布量 [mg/cm²]（設計因子・独立）
    mix_density : 正極合剤密度 [g/cm³]（設計因子・独立）
    am_frac : 正極活物質比率 [-]（材料/設計・独立）
    am_cap : 正極活物質比容量 [Ah/g]（材料物性・独立）
    """
    # 塗布量: mg/cm² → g/m²  (1 mg/cm² = 10 g/m²)
    K = coat_load * 10.0
    # 空隙率: eps = 1 − 合剤密度/真密度
    eps = 1.0 - mix_density / RHO_TRUE
    # 片面合剤厚み: L[m] = (塗布量[g/cm²]) / 合剤密度[g/cm³] を m に換算
    #   coat_load[mg/cm²]*1e-3 = [g/cm²];  /density[g/cm³] = [cm];  *1e-2 = [m]
    L = coat_load * 1e-3 / mix_density * 1e-2
    # 面積容量 [Ah/m²] = 塗布量 × 活物質比 × 比容量（DC_v5 Qareal = K·omegaAM·cap_2cyc）
    Qareal = K * am_frac * am_cap
    # セル Typ 容量 [Ah] = 面積容量 × 対向面積
    Typ = Qareal * AREA_M2
    # 初期容量傾き a0（DC_v5 の Typ↔a0 線形の逆算で整合を取る）
    a0 = (_TYP_C0 - Typ) / (-_TYP_C1)
    # 初期抵抗 R0: 合剤厚み大・空隙率小ほどイオン経路抵抗増（簡易スケーリング）
    R0 = R0_REF * (L / L_REF) * (EPS_REF / eps) ** 1.5
    return DerivedCell(K=K, eps=eps, L=L, omegaAM=am_frac, cap_2cyc=am_cap,
                       Qareal=Qareal, Typ=Typ, a0=a0, R0=R0)

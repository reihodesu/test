"""
DC Design Constraint Model (27 outputs)
========================================

DC 設計制約 + 劣化モデル 統合計算。
定 W 放電条件下でのセル寿命・電圧・発熱を閉形式で算出する。

出力 #1-23: DC 設計制約
出力 #24:   自己整合 (SC) 初期温度 T0
出力 #25:   臨界 Li+ 濃度 (= Cli_plus_min × 1000, 検算用)
出力 #26:   有効端子電圧 Veff
出力 #27:   有効放電電流 Ieff

Author: V3.7 Veff/Ieff 追加
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict
from core.exceptions import DomainError
from core.config import ThermalDefaults

# ── 物理定数 ──────────────────────────────────────────────────
F_FARADAY: float = 96_485.0   # ファラデー定数 [C/mol = A·s/mol]
Z_CATION_VALENCE: int = 1     # Li+ 価数 [-]  (Heubner 2020 DLC 式 (1) の z)

# ===== γ 派生計算パラメータ (2026-05-11 統一: row79/80/81/82 全ケース) =====
# γ = √(A · ε^(-Q))
#   xlsx 数式: =SQRT(P*(O^-Q))
#   出典: ★蓄電保存_劣化推定_最新版.xlsx row79-82 で P, Q 統一
_GAMMA_A_COEF:  float = 0.7491   # P 列: γ 派生計算用係数 A
_GAMMA_BRUGG_Q: float = 0.8733   # Q 列: ブラッジマン乗数

# ── Arrhenius 電解液拡散係数 (廃止予定 2026-05-11) ────────────
# 旧 D_eff = D₀·exp(-Ea/RT)·ε^0.9572 (Arrhenius + 固定 Brugg) を、
# 新 D_eff = Dely_user × ε^γ (ユーザー指定 + 派生 γ) に統一。
# 以下の定数は他経路 (DCIR 等) から参照されている可能性のため保持。
_D0_DELY: float   = 2.21729e-7   # pre-exponential factor [m²/s]
_EA_DELY: float   = 17500.0      # 活性化エネルギー [J/mol]
_R_GAS: float     = 8.314        # 気体定数 [J/(mol·K)]
_T_DELY_K: float  = 333.15       # 計算温度 [K] = 60°C
_BRUG_B_DC: float = 0.9572       # Bruggeman b (廃止: D_eff = D(T)·ε^b 直接式)

# ── 熱物性定数 (core.config.ThermalDefaults から一元取得) ─────
_TH_C_TH: float       = ThermalDefaults.C_th
_TH_H_T: float        = ThermalDefaults.h_t
_TH_A_SURFACE: float  = ThermalDefaults.A_surf
_TH_T_AMB: float      = ThermalDefaults.T_amb
_TH_ALPHA_K: float    = ThermalDefaults.alpha_K
_TH_T_BASE: float     = ThermalDefaults.T_base

# ── τ² / D_eff 統一計算関数群 (v3.1) ─────────────────────────────
# τ² = A × ε^(-b)  →  D_eff = D_ely × ε^τ  (τ = √τ²)
# 2026-06-02: 21JB_MP_design (A=0.7491/b=0.8733) が唯一の基準 (旧系列は完全削除済)。
_TAU2_PARAMS: dict = {
    "MC":              {"A": 0.7491, "b": 0.8733},  # MC 実測フィッティング (row82 BASE と同値)
    "SC":              {"A": 1.3965, "b": 0.3048},  # SC 実測フィッティング
    "21JB_MP_DESIGN":  {"A": 0.7491, "b": 0.8733},  # row82 BASE — γ=1.494110 派生 (calc_tau_sq は upper() で参照)
}

# Ref = row82 21JB_MP (A=0.7491, b=0.8733)
_TAU2_A_REF: float = 0.7491   # τ² = A × ε^(-b) の A 係数 (Ref = 21JB_MP_design row82)
_TAU2_B_REF: float = 0.8733   # τ² = A × ε^(-b) の b 指数 (Ref)

# 21JB_MP_design (row82) 基準 電極対向面積 [m²] = 2 × p_len × p_width × 1e-6
# Ref = row82 (1880×60=0.2256 m²)
_A_M2_REF: float = 2.0 * 1880.0 * 60.0 * 1e-6   # 0.22560 m² (row82 BASE)


def calc_tau_sq(eps: float, material: str = "21JB_MP_design") -> float:
    """τ² = A × ε^(-b) を材料種別で返す。"""
    key = material.upper()
    if key not in _TAU2_PARAMS:
        raise ValueError(f"Unknown material: {material!r}. Use {list(_TAU2_PARAMS.keys())}")
    p = _TAU2_PARAMS[key]
    return p["A"] * (eps ** (-p["b"]))


def calc_tau(eps: float, material: str = "21JB_MP_design") -> float:
    """τ = √τ² を返す。"""
    return math.sqrt(calc_tau_sq(eps, material))


def calc_D_eff(Dely: float, eps: float, material: str = "21JB_MP_design") -> float:
    """D_eff = Dely × ε^τ  (τ = √(A × ε^(-b)))."""
    tau = calc_tau(eps, material)
    return Dely * (eps ** tau)


def _calc_deff(D_ely: float, eps: float,
               tau2_A: float = _TAU2_A_REF,
               tau2_b: float = _TAU2_B_REF) -> float:
    """
    D_eff 統一計算関数 — Ref パターン固定。

    τ² = tau2_A × ε^(-tau2_b)
    τ  = √τ²
    D_eff = D_ely × ε^τ

    検証値 (ε=0.286422): τ=1.699, D_eff=4.03e-11 m²/s
    """
    if eps <= 0.0 or eps >= 1.0:
        raise ValueError(f"eps={eps!r} は (0, 1) の範囲外")
    tau = math.sqrt(tau2_A * (eps ** (-tau2_b)))
    return D_ely * (eps ** tau)


def _solve_sc_temperature(
    R0: float,
    P_w: float,
    OCV: float,
    t_end: float,
    dt: float = 1.0,
    max_inner: int = 20,
    tol_T: float = 1e-3,
    relax: float = 0.3,
) -> float:
    """
    自己整合 (Self-Consistent) 電気+熱連成ソルバー。

    R0 (既知の初期抵抗) と P_w (放電電力) から、放電終了時の
    温度 T_end を求める。

    温度補正:
        R(T) = R0 / (1 + alpha_kappa * (T - T_base))
    定電力:
        V = (OCV + sqrt(OCV^2 - 4*P*R)) / 2,  I = P/V
    熱 ODE (暗黙 Euler):
        T_new = T_prev + dt/C_th * (I^2*R - hA*(T_guess - T_amb))

    Parameters
    ----------
    R0 : float  初期抵抗 [Ohm]
    P_w : float  放電電力 [W]
    OCV : float  開回路電圧 [V]
    t_end : float  放電時間 [sec]

    Returns
    -------
    float  放電終了時温度 T_end [degC]
    """
    hA = _TH_H_T * _TH_A_SURFACE
    T_cur = _TH_T_AMB
    n_steps = max(1, int(round(t_end / dt)))

    for _ in range(n_steps):
        T_guess = T_cur
        for _ in range(max_inner):
            # 温度補正 R(T) = R0 * f_T(T)
            denom = 1.0 + _TH_ALPHA_K * (T_guess - _TH_T_BASE)
            f_T = 1.0 / denom if denom > 0.0 else 1.0
            R_t = R0 * f_T

            # 定電力: V^2 - OCV*V + P*R = 0
            disc = OCV ** 2 - 4.0 * P_w * R_t
            if disc < 0.0:
                V = OCV * 0.5
                I = P_w / V if V > 0.0 else 0.0
            else:
                V = (OCV + math.sqrt(disc)) / 2.0
                I = P_w / V if V > 0.0 else 0.0
            I = min(max(I, 0.0), 2000.0)  # 暴走防止

            # ジュール発熱 + 暗黙 Euler
            Q_dot = I * I * R_t
            T_new = T_cur + dt / _TH_C_TH * (Q_dot - hA * (T_guess - _TH_T_AMB))

            if abs(T_new - T_guess) < tol_T:
                T_guess = T_new
                break
            T_guess = (1.0 - relax) * T_guess + relax * T_new

        T_cur = T_guess

    return T_cur


# ── Typ 容量: a0 → Typ 線形近似 ──────────────────────────────
# 300W放電試算用.csv から a0 (初期容量傾き) と Typ (想定Typ容量) の
# 一次線形回帰で算出。  Typ = C1 * a0 + C0
#   回帰結果 (25 点, R² ≈ 1.0): 傾き = -9.022706511547, 切片 = 5.671518551713
_TYP_C1: float = -9.022706511547215   # 傾き [Ah / (V/Ah)]
_TYP_C0: float =  5.671518551713159   # 切片 [Ah]


def interpolate_typ_capacity(a0: float) -> float:
    """
    想定 Typ 容量 [Ah] を初期容量傾き a0 から線形式で算出する。

    Typ = -9.022706511547215 * a0 + 5.671518551713159

    Parameters
    ----------
    a0 : float
        初期容量傾き [V/Ah]

    Returns
    -------
    float
        想定 Typ 容量 [Ah]
    """
    return _TYP_C1 * a0 + _TYP_C0


# ── 臨界 Li+ 濃度 5 項式 (critical_li.py より移植) ────────────

@dataclass
class CriticalLiParameters:
    """
    臨界 Li+ 濃度計算パラメータ (5 項式)

    calc_critical_li_concentration() の入力。
    dc_model の簡易式 Cli_plus_min = C_rate×Qareal/(Jlim×1000) と
    同じ値を異なるパラメータ表現で算出し、検算に用いる。
    """
    omega_AM: float      # 活物質重量比率 [-]
    F: float             # ファラデー定数 [A·s/mol]
    V0: float            # セル群体積 [m³]
    Dely: float          # 電解液拡散係数 [m²/s]
    eps_CrLi: float      # 空隙率 [-]
    gamma_CrLi: float    # ブルッゲマン指数 [-]
    L_p: float           # 正極有効厚み [m]
    u: float             # N/P 比 [-]
    rho: float           # 電極密度比 [-]
    q: float             # 電極利用率 [-]
    z_W: float           # 放電出力 [W]
    t_s: float           # パルス持続時間 [s]
    b: float             # 容量劣化切片 [V]  (= b_ocv)
    a: float             # 容量劣化傾き [V/Ah]


def calc_voltage_discriminant(
    b: float, z_W: float, a: float, t_s: float, R: float
) -> float:
    """
    電圧方程式の判別式: Δ = b² − 4·z_W·(a·t_s/3600 + R)

    Raises DomainError if Δ ≤ 0.
    """
    disc = b ** 2 - 4.0 * z_W * (a * t_s / 3600.0 + R)
    if disc <= 0:
        raise DomainError(
            f"voltage discriminant = {disc:.6e} <= 0  "
            f"(b={b}, z_W={z_W}, a={a}, t_s={t_s}, R={R})"
        )
    return disc


def calc_critical_li_concentration(
    params: CriticalLiParameters, R: float
) -> float:
    """
    臨界 Li+ 塩濃度を 5 項の乗算構造で算出する。

    式:
        C_crit = (ω_AM / (2·F·V0))
                 × ((1−ε) / (Dely·ε^γ))
                 × (1 + u·ρ·q)
                 × (2·z_W) / (b + √Δ)
                 × L_p²

    Parameters
    ----------
    params : CriticalLiParameters
    R : float  初期抵抗 [Ω]

    Returns
    -------
    float  臨界 Li+ 濃度 [mol/m³]
    """
    disc = calc_voltage_discriminant(
        params.b, params.z_W, params.a, params.t_s, R,
    )
    sqrt_disc = math.sqrt(disc)

    term1 = params.omega_AM / (2.0 * params.F * params.V0)
    term2 = (1.0 - params.eps_CrLi) / (
        params.Dely * (params.eps_CrLi ** params.gamma_CrLi)
    )
    term3 = 1.0 + params.u * params.rho * params.q
    term4 = (2.0 * params.z_W) / (params.b + sqrt_disc)
    term5 = params.L_p ** 2

    return term1 * term2 * term3 * term4 * term5


# ── 入出力データクラス ────────────────────────────────────────

@dataclass(frozen=True)
class DCInputs:
    """
    DC 設計制約モデルの入力パラメータ (16 + 1 項目)

    定 W 放電条件:
        dscg_power              : 放電電力 [W]
        dscg_time               : 放電時間 [sec]
        initial_dscg_voltage    : b' = b_ocv/2 放電開始電圧 [V]
        storage_year            : 保管年数 [Year]

    劣化パラメータ:
        R0                      : 初期抵抗値 [Ohm]
        resistance_increase_rate: 抵抗上昇率 [Ohm/Year]
        a0                      : 初期容量傾き [V/Ah]
        capacity_fade_rate      : 容量劣化速度 [V/Ah/√Year]

    電極設計パラメータ:
        K                       : 正極塗布量 [g/m²]
        omegaAM                 : 正極活物質比率 [-]
        cap_2cyc                : 正極放電容量(2cyc 目) [Ah/g]
        electrolyte_diffusion   : 電解液拡散係数 [m²/s]
        eps                     : 正極合剤空隙率 [-]
        A                       : 係数 A [-]
        pos_tortuosity          : ブラッジュマン乗数 [-]
        L                       : 片面正極合剤厚み [m]

    温度パラメータ:
        DeltaT  : 断熱前提の上限温度上昇量 [K]
                  (sc_solver.py の自己整合モデルとは異なる)

    Note:
        Typ (想定 Typ 容量) は入力ではなく、保管後容量傾き a から
        typ_capacity_table による線形補間で算出される出力項目 (#8)。
    """
    # --- 定 W 放電条件 ---
    dscg_power: float              # [W]  放電電力
    dscg_time: float               # [sec]  放電秒数
    initial_dscg_voltage: float    # [V]  b' = b_ocv/2 放電開始電圧
    storage_year: float            # [Year]  保管年数
    # --- 劣化パラメータ ---
    R0: float                      # [Ohm]
    resistance_increase_rate: float  # [Ohm/Year]  抵抗上昇率
    a0: float                      # [V/Ah]
    capacity_fade_rate: float      # [V/Ah/√Year]  容量劣化速度
    # --- 電極設計 ---
    K: float                       # [g/m²]
    omegaAM: float                 # [-]
    cap_2cyc: float                # [Ah/g]
    electrolyte_diffusion: float   # [m²/s]  電解液拡散係数
    eps: float                     # [-]
    A: float                       # [-]
    pos_tortuosity: float          # [-]  τ² fitting exponent b (Ref=0.848)
    L: float                       # [m]
    # --- 材料種別 (v3.1) ---
    material: str = "21JB_MP_design"   # 'MC', 'SC', '21JB_MP_design' (row82 BASE, 既定)
    tau2_A: float = 1.0           # [-]  τ² fitting coefficient A (Ref=1.0)
    # --- 電極面積 (p_len/p_width 連動) ---
    electrode_area_m2: float = _A_M2_REF  # [m²] 正負極対向面積
    # --- セル Typ 容量直接指定 (2026-05-19 v5.0 改訂) ---
    # CellDesign シートが算出した「Pana 電池容量 (25℃ 空冷 0.2C)」を Typ として直接渡す。
    # 設定された場合: dc_model 内の a0→Typ 回帰 + 面積補正を bypass し、本値をそのまま使う。
    # None の場合: 従来の interpolate_typ_capacity(a0) × area/area_ref を使用 (後方互換)。
    # 推奨ソース: design_result["CellCap_ocv"] × CELLCAP_TO_TYP_RATIO / 1000  [Ah]
    cell_typ_ah: float | None = None
    # --- 温度パラメータ ---
    DeltaT: float = 0.0            # [K]  断熱前提の上限温度上昇量 (placeholder; calc_dc_outputs が上書き)
    # --- D_eff 計算モード (2026-05-04 担当者規約統一) ---
    # tau_pos: 曲路率 τ [-]。
    #   None の場合は従来の τ² = A·ε^(-b) ベース計算 (後方互換)。
    #   値が設定されている場合は D_eff = D_ely × ε^tau_pos を採用 (Excel V2 整合)。
    #   採用 τ 起点 (MP 案専用) = 1.8 (truth CSV の AE 列と整合)。
    #   実運用は MC fit (A=0.7491, b=0.8733) から τ² = A·ε^(-b) で計算 (core/bruggeman_fit.py)。
    tau_pos: float | None = None


@dataclass(frozen=True)
class DCOutputs:
    """
    DC 設計制約モデルの出力 (25 項目: #1-23 DC制約 + #24 SC温度 + #25 検算)
    """
    # --- 定 W 放電 ---
    R: float                # [Ohm]      #1 保管後抵抗値
    a: float                # [V/Ah]     #2 保管後容量傾き
    y_end: float            # [V]        #3 放電末電圧
    Q_t: float              # [Ah]       #4 消費容量
    tmax: float             # [sec]      #5 最大放電時間
    Ymax: float             # [Year]     #6 最大保管年数 (= root_pos²)
    H_t: float              # [J]        #7 トータル発熱量
    # --- 外部設計 ---
    Typ: float              # [Ah]       #8 想定 Typ 容量 (a から線形補間で算出)
    DeltaT: float           # [K]        #9 断熱前提の上限温度上昇量
    # --- DLC / 拡散限界 ---
    Cli_plus_min: float     # [mol/L]    #10 下限 Li 塩濃度
    Qareal: float           # [Ah/m²]    #11 正極面積容量
    gamma_tortuosity: float # [-]        #12 正極合剤曲路率
    I: float                # [A]        #13 放電電流
    C_rate: float           # [-]        #14 セル C レート
    Jlim_other_than_C: float# [-]        #15 C 以外の Jlim
    # --- 中間変数 ---
    bprime_out: float       # [V]        #16 b' = b_ocv/2
    S0: float               # [-]        #17 s₀ = √(b'²−z·R)
    St: float               # [-]        #18 s_t = √(s₀²−z·a·t/3600)  y_end の第2項
    # --- 寿命 ---
    alpha_2nd: float        # [-]        #19 2 次係数 α
    beta_1st: float         # [-]        #20 1 次係数 β
    gamma_0th: float        # [-]        #21 0 次係数 γ
    root_pos: float         # [√Year]    #22 正の解
    root_neg: float         # [√Year]    #23 負の解
    # --- SC 初期温度 ---
    T0_sc: float                # [degC]    #24 自己整合初期温度 (SC solver)
    # --- 検算 ---
    Cli_plus_min_mol_m3: float  # [mol/m3]  #25 臨界Li塩濃度 (= Cli_plus_min*1000)
    # --- 定電力有効電圧・電流 ---
    Veff: float                 # [V]       #26 有効端子電圧 Veff = (OCV + √(OCV²−4PR))/2
    Ieff: float                 # [A]       #27 有効放電電流 Ieff = P / Veff


# ── ドメインチェック ──────────────────────────────────────────


def _check_positive(value: float, name: str, context: str = "") -> None:
    """値が正であることを確認"""
    if value < 0:
        raise DomainError(f"{name} = {value:.6e} < 0  ({context})")


# ── 出力フィールド表示順 ──────────────────────────────────────

DC_OUTPUT_FIELD_ORDER = [
    "R", "a", "y_end", "Q_t", "tmax", "Ymax", "H_t",
    "Typ", "DeltaT", "Cli_plus_min",
    "Qareal", "gamma_tortuosity", "I", "C_rate", "Jlim_other_than_C",
    "bprime_out", "S0", "St", "alpha_2nd", "beta_1st", "gamma_0th", "root_pos", "root_neg",
    "T0_sc",
    "Cli_plus_min_mol_m3",
    "Veff", "Ieff",
]


# ── コア計算関数 ──────────────────────────────────────────────

def calc_dc_outputs(inp: DCInputs, y_cutoff: float = 2.5) -> DCOutputs:
    """
    全 25 出力項目を計算する。

    Parameters
    ----------
    inp : DCInputs
        入力パラメータ (16 + 1 項目)
    y_cutoff : float
        寿命算出のカットオフ電圧 [V] (デフォルト: 2.5 V)

    Returns
    -------
    DCOutputs
        25 出力項目

    Raises
    ------
    DomainError
        平方根の中身が負 / 対数の引数が非正 の場合
    """
    # ==============================================================
    # STEP 1: 劣化 (保管)
    # ==============================================================
    R = inp.R0 + inp.resistance_increase_rate * inp.storage_year        # 1 保管後抵抗値 [Ohm]
    a = inp.a0 + inp.capacity_fade_rate * math.sqrt(inp.storage_year)   # 2 保管後容量傾き [V/Ah]

    # ==============================================================
    # STEP 2: Typ 容量 (a0 線形近似)
    # ==============================================================
    b_ocv = 2.0 * inp.initial_dscg_voltage
    # ── Typ 決定 (2026-05-19 v5.0): cell_typ_ah が指定されていれば直接採用 ──
    # 優先順位:
    #   1. inp.cell_typ_ah (CellDesign 由来; p_len 変化で容量が動的更新される)
    #   2. interpolate_typ_capacity(a0) × area/area_ref (後方互換)
    if inp.cell_typ_ah is not None and inp.cell_typ_ah > 0:
        Typ = float(inp.cell_typ_ah)                    # 8 想定 Typ 容量 [Ah] (CellDesign 直接)
    else:
        Typ = interpolate_typ_capacity(inp.a0)          # 8 想定 Typ 容量 [Ah] (回帰)
        # 電極面積補正: p_len/p_width が基準と異なる場合に Typ をスケーリング
        _area = getattr(inp, "electrode_area_m2", _A_M2_REF)
        if _area != _A_M2_REF:
            Typ *= _area / _A_M2_REF

    # ==============================================================
    # STEP 3: 定 W 放電 閉形式
    # ==============================================================
    bp = inp.initial_dscg_voltage

    disc0 = bp ** 2 - inp.dscg_power * R
    _check_positive(disc0, "disc0 = b'^2 - z*R",
                    f"b'={bp}, z={inp.dscg_power}, R={R}")

    disct = bp ** 2 - inp.dscg_power * R - inp.dscg_power * a * inp.dscg_time / 3600.0
    _check_positive(disct, "disc_t = b'^2 - z*R - z*a*t/3600",
                    f"a={a}, t={inp.dscg_time}")

    s0 = math.sqrt(disc0)                              # 16 s0 [-]
    st = math.sqrt(disct)

    y_end = bp + st                                    # 3 放電後電圧 [V]
    tmax = 3600.0 * disc0 / (inp.dscg_power * a)      # 5 放電可能秒数 [sec]

    Q_t = (2.0 / a) * (                               # 4 放電時消費容量 [Ah]
        (s0 - st) - bp * math.log((bp + s0) / (bp + st))
    )

    H_t = (7200.0 * inp.dscg_power * R / a) * (       # 7 トータル発熱量 [J]
        math.log((bp + s0) / (bp + st))
        + bp * (1.0 / (bp + s0) - 1.0 / (bp + st))
    )

    # ==============================================================
    # STEP 4: 電極・派生
    # ==============================================================
    Qareal = inp.K * inp.omegaAM * inp.cap_2cyc       # 11 正極面積容量 [Ah/m²]
    # 曲路率 γ 統一派生計算 (2026-05-11 Phase D):
    #   γ = √(A · ε^(-Q))  with A=0.7491, Q=0.8733 (row79/80/81/82 統一)
    #   xlsx 数式: =SQRT(P*(O^-Q))
    # 2026-05-21: inp.tau_pos が指定されていれば、docstring 通り tau_pos を優先採用
    #   (Excel V2 / teacher row79-81 検証で γ=1.45 / 1.80 等の固定値を渡せるようにする)
    if inp.tau_pos is not None and inp.tau_pos > 0:
        gamma_tortuosity = float(inp.tau_pos)             # 明示指定の τ を γ として採用
    else:
        gamma_tortuosity = math.sqrt(_GAMMA_A_COEF * (inp.eps ** (-_GAMMA_BRUGG_Q)))  # 12 正極合剤曲路率 γ [-]
    I_discharge = inp.dscg_power / y_end               # 13 放電電流 [A]

    # ==============================================================
    # STEP 5: DLC / 拡散限界 + 臨界 Li+ 検算
    # ==============================================================
    # --- D_eff 計算 (2026-05-11 Phase D 改訂: Excel ★蓄電保存_劣化推定_最新版.xlsx と統一) ---
    # 出典: Heubner et al. 2020, "Diffusion-Limited C-Rate", Adv. Energy Mater.
    # 式 (1): j_lim = 2·z·F·D_eff·c°_Li+/L
    # 式 (2): D_eff = D · ε^γ
    # 統一方針 (JYO 2026-05-11):
    #   - Dely はユーザー指定値をそのまま使う (Arrhenius 補正は織り込み済とみなす)
    #   - γ は ε と統一パラメータ (A=0.7491, Q=0.8733) から派生計算
    D_eff = inp.electrolyte_diffusion * (inp.eps ** gamma_tortuosity)
    Jlim_other_than_C = 2.0 * Z_CATION_VALENCE * F_FARADAY * D_eff / inp.L  # 15 C以外のJlim [-]
    C_rate = I_discharge / Typ                              # 14 セルCレート (I/Typ) [-]
    Cli_plus_min = C_rate * Qareal / (Jlim_other_than_C * 1000.0)  # 10 下限Li塩濃度 [mol/L]

    # ── 検算: 臨界 Li+ 濃度 [mol/m³] ──
    # ■ 数式の同一性:
    #   calc_critical_li_concentration (5 項式):
    #     C_critical = (ω_AM/(2F·V0))·((1−ε)/(Dely·ε^γ))·(1+u·ρ·q)·(2z/(b+√Δ))·L²
    #   dc_model (簡易式):
    #     Cli_plus_min [mol/L] = C_rate × Qareal / (Jlim_other_than_C × 1000)
    #   → Cli_plus_min × 1000 ≡ C_critical [mol/m³]
    #
    # ■ Stage3 検算 — 保存後電圧:
    #   post_storage_voltage.py:  V = 2 + √(4 − W·(R + cap_slope·sec/3600))
    #   dc_model.py:              y_end = b' + √(b'² − z·R − z·a·t/3600)
    #   b'=2 のとき: y_end = 2 + √(4 − z·(R + a·t/3600)) ≡ V_post
    Cli_plus_min_mol_m3 = Cli_plus_min * 1000.0        # 25 臨界Li塩濃度 [mol/m3]

    # ==============================================================
    # STEP 5b: 定電力有効電圧・電流 (Veff, Ieff)
    # ==============================================================
    # 定電力条件 P = V·I, V = OCV − I·R を連立:
    #   V² − OCV·V + P·R = 0
    #   Veff = (OCV + √(OCV² − 4PR)) / 2 = b' + s0
    Veff = bp + s0                                      # 26 有効端子電圧 [V]
    Ieff = inp.dscg_power / Veff                        # 27 有効放電電流 [A]  (P = Veff × Ieff)

    # ==============================================================
    # STEP 6: SC 初期温度 (self-consistent solver)
    # ==============================================================
    # R0 (既知) + z (放電電力) + t (放電時間) から放電終了時温度を算出
    T0_sc = _solve_sc_temperature(
        R0=inp.R0, P_w=inp.dscg_power,
        OCV=b_ocv, t_end=inp.dscg_time,
    )                                                   # 24 SC初期温度 [degC]

    # ==============================================================
    # STEP 7: 寿命 (二次式)
    # ==============================================================
    alpha_2nd = inp.resistance_increase_rate            # 17 2次係数α [-]
    beta_1st = inp.capacity_fade_rate * inp.dscg_time / 3600.0  # 18 1次係数β [-]
    gamma_0th = (                                      # 19 0次係数γ [-]
        inp.R0
        + inp.a0 * inp.dscg_time / 3600.0
        + ((y_cutoff - bp) ** 2 - bp ** 2) / inp.dscg_power
    )

    disc_q = beta_1st ** 2 - 4.0 * alpha_2nd * gamma_0th
    _check_positive(disc_q, "disc_q = β²−4αγ₀", "寿命二次式の判別式が負")

    sqrt_disc_q = math.sqrt(disc_q)
    root_pos = (-beta_1st + sqrt_disc_q) / (2.0 * alpha_2nd)   # 20 正の解 [√Year]
    root_neg = (-beta_1st - sqrt_disc_q) / (2.0 * alpha_2nd)   # 21 負の解 [√Year]
    Ymax = root_pos ** 2                                        # 6 保管可能年数 [Year]

    # ==============================================================
    # STEP 5c: 断熱温度上昇量 ΔT = H_t / C_th
    # ==============================================================
    DeltaT = H_t / _TH_C_TH                                    # 9 断熱温度上昇量 [K]

    return DCOutputs(
        R=R, a=a, y_end=y_end, Q_t=Q_t, tmax=tmax, Ymax=Ymax, H_t=H_t,
        Typ=Typ, DeltaT=DeltaT,
        Cli_plus_min=Cli_plus_min, Qareal=Qareal,
        gamma_tortuosity=gamma_tortuosity,
        I=I_discharge, C_rate=C_rate,
        Jlim_other_than_C=Jlim_other_than_C, bprime_out=bp, S0=s0, St=st,
        alpha_2nd=alpha_2nd, beta_1st=beta_1st, gamma_0th=gamma_0th,
        root_pos=root_pos, root_neg=root_neg,
        T0_sc=T0_sc,
        Cli_plus_min_mol_m3=Cli_plus_min_mol_m3,
        Veff=Veff, Ieff=Ieff,
    )


# ── CSV → CriticalLiParameters 構築 (Calc.py 由来) ────────────

def calculate_critical_li_unified(
    R: float,
    z_W: float,
    t_s: float,
    T_eval: float | None = None,
    return_intermediate: bool = False,
) -> float | tuple:
    """
    P() 経由で CSV / AgingConstants から CriticalLiParameters を構築し、
    臨界 Li+ 濃度 [mol/m³] を算出する。

    Parameters
    ----------
    R : float  初期抵抗 [Ω]
    z_W : float  放電出力 [W]
    t_s : float  パルス持続時間 [s]
    T_eval : float | None  Dely 算出用温度 [°C] (未使用: AgingConstants.T_Dely 固定)
    return_intermediate : bool  True → (C_critical, 中間値 dict) を返す

    Returns
    -------
    float | tuple
    """
    # 遅延 import — 循環回避
    from core.param_loader_design import get_params, P
    from core.config import AgingConstants

    params = get_params()

    def _val(name: str, default: float = 0.0) -> float:
        return params.get(name, default)

    # ==========================================================
    # Calc.py 由来パラメータ — P() 経由でオーバーライド対応
    # ==========================================================

    # omega_AM = 100 / (100 + CM_r + BA_r)
    CM_r = float(P('pos_ca1_r_total_solid')) if P('pos_ca1_r_total_solid') is not None else 2.3
    BA_r = float(P('pos_binder1_r')) if P('pos_binder1_r') is not None else 1.5
    omega_AM_calc = 100.0 / (100.0 + CM_r + BA_r)

    # V0 = 極板幅(cm) × 0.01 × π × (CanDin)²
    p_width = float(P('p_width')) if P('p_width') is not None else 60.0  # mm (row82 BASE)
    CanDin = AgingConstants.CanDin  # m (缶内半径 = 10.25 mm 固定)
    V0_calc = (p_width / 10.0) * 0.01 * math.pi * (CanDin ** 2)  # mm → cm → m

    # Dely (Arrhenius)
    Dely_csv = _val("Dely", 0.0)
    if Dely_csv > 0:
        Dely_calc = Dely_csv
    else:
        T_kelvin = AgingConstants.T_Dely + AgingConstants.T_abs
        Dely_calc = AgingConstants.A0 * math.exp(
            AgingConstants.Ea / (AgingConstants.R_gas * T_kelvin)
        )

    # rho = p_density / n_density
    p_density = float(P('p_density')) if P('p_density') is not None else 3.32
    n_density = float(P('n_density')) if P('n_density') is not None else 1.552
    if n_density == 0:
        n_density = 1.552
    rho_calc = p_density / n_density

    # L_p = (電極厚み − 集電箔厚み) / 2 [m]
    p_thk_mm = float(P('p_thk')) if P('p_thk') is not None else 0.0835
    p_foil_thk_mm = float(P('p_foil_thk')) if P('p_foil_thk') is not None else 0.015
    L_p_calc = (p_thk_mm - p_foil_thk_mm) / 2.0 * 1e-3  # mm → m

    # q = pos_discharge_utilization_r / neg_specific_charge_capa
    n_chg_capa = float(P('pos_discharge_utilization_r')) if P('pos_discharge_utilization_r') is not None else 197.6
    n_th_capa = float(P('neg_specific_charge_capa')) if P('neg_specific_charge_capa') is not None else 383.3
    q_calc = n_chg_capa / n_th_capa if n_th_capa > 0 else 0.515

    # ==========================================================
    # AgingConstants の固定パラメータ (CSV 外)
    # ==========================================================
    crit_params = CriticalLiParameters(
        omega_AM=omega_AM_calc,
        F=AgingConstants.F,
        V0=V0_calc,
        Dely=Dely_calc,
        eps_CrLi=AgingConstants.Cr_Li_eps,
        gamma_CrLi=AgingConstants.Cr_Li_bruggeman,
        u=AgingConstants.Cr_Li_u,
        rho=rho_calc,
        q=q_calc,
        L_p=L_p_calc,
        b=AgingConstants.b_ocv,
        a=AgingConstants.cap_slope,
        z_W=z_W,
        t_s=t_s,
    )

    C_critical = calc_critical_li_concentration(crit_params, R)

    if return_intermediate:
        D_eff = crit_params.Dely * (crit_params.eps_CrLi ** crit_params.gamma_CrLi)
        intermediate = {
            "omega_AM": crit_params.omega_AM,
            "V0": crit_params.V0,
            "Dely": crit_params.Dely,
            "D_eff": D_eff,
            "L_p": crit_params.L_p,
        }
        return C_critical, intermediate

    return C_critical


# ── CSV → DCInputs ブリッジ ───────────────────────────────────

# CSV Name → DCInputs フィールド名のマッピング (全 17 項目)
# variable_parameter.csv / fixed_parameter.csv の Name 列で参照する。
# CSV に定義があれば CSV 値を優先、未定義なら _DVT_DEFAULTS をフォールバック。
_CSV_TO_DC: Dict[str, str] = {
    "dscg_power":              "dscg_power",
    "dscg_time":               "dscg_time",
    "storage_year":            "storage_year",
    "initial_dscg_voltage":    "initial_dscg_voltage",
    "dc_R0":                   "R0",
    "resistance_increase_rate": "resistance_increase_rate",
    "dc_a0":                   "a0",
    "capacity_fade_rate":      "capacity_fade_rate",
    "dc_K":                    "K",
    "dc_omegaAM":              "omegaAM",
    "dc_cap_2cyc":             "cap_2cyc",
    "dc_eps":                  "eps",
    "dc_L":                    "L",
    "electrolyte_diffusion":   "electrolyte_diffusion",
    "dc_A":                    "A",
    "pos_tortuosity":          "pos_tortuosity",
    "dc_DeltaT":               "DeltaT",
    # 2026-05-21: 設計探索インプットシート v0.10 で variable_parameter.csv に
    # 追加された dc_gamma_tortuosity を DCInputs.tau_pos へ配線。
    # tau_pos が有限値なら calc_dc_outputs が γ = tau_pos を honor する
    # (dc_model.py:514-517)。csv 未登録時は None → 物理式 √(A·ε^-Q) で算出。
    "dc_gamma_tortuosity":     "tau_pos",
}

# DVT Step2 デフォルト値 (CSV 未登録時のフォールバック = ③ OTHER)
# resistance_increase_rate / capacity_fade_rate / electrolyte_diffusion /
# pos_tortuosity / A は config.AgingConstants を Single Source of Truth とする。
# R0 は CSV (dc_R0) 優先、未登録時は _DVT_DEFAULTS フォールバック。
from core.config import AgingConstants as _AC_defaults
_DVT_DEFAULTS: Dict[str, float] = {
    "dscg_power": 300, "dscg_time": 90, "initial_dscg_voltage": 4.0, "storage_year": 5,
    "R0": 0.0045,  # 21JB_MP_design row82 値。CSV (dc_R0) 未登録時に使用。
    "resistance_increase_rate": _AC_defaults.dc_resistance_increase_rate,
    "a0": 0.215,
    "capacity_fade_rate": _AC_defaults.dc_capacity_fade_rate,
    "K": 81, "omegaAM": 0.99108, "cap_2cyc": 0.21,
    "electrolyte_diffusion": _AC_defaults.dc_electrolyte_diffusion,
    "eps": 0.2864,
    "A": _AC_defaults.dc_A_coefficient,
    "pos_tortuosity": _AC_defaults.dc_pos_tortuosity,
    "L": 2.4043e-05,
    "DeltaT": 0.0,
    # tau_pos: csv (dc_gamma_tortuosity) 未登録時は None → 物理式で γ 算出
    "tau_pos": None,
}

# Calc.py 設計計算で導出する 5+2 項目 (build_dc_inputs_from_design で使用)
# R0 は低精度 Bruggeman 理論値のため設計導出から除外。
# CSV (dc_R0) または _DVT_DEFAULTS でのみ供給する。
_DESIGN_DERIVED = ["K", "omegaAM", "cap_2cyc", "eps", "L", "a0", "initial_dscg_voltage"]




def build_dc_inputs_from_loader(P) -> DCInputs:
    """
    param_loader_design.P() 経由で CSV → デフォルトのフォールバックで
    DCInputs を構築する。

    全 17 項目について CSV (dc_*) を検索し、定義があれば CSV 値を優先。
    未定義なら _DVT_DEFAULTS (= param_loader_aging ③) をフォールバック。

    Note:
        initial_dscg_voltage は CSV/デフォルトともに b_ocv [V] で格納されて
        おり、内部で b' = b_ocv / 2 に変換して DCInputs に渡す。

    Parameters
    ----------
    P : callable(name, default) -> float
        param_loader_design.P 関数、または同じシグネチャの callable。

    Returns
    -------
    DCInputs
    """
    resolved: Dict[str, float] = {}
    used_defaults: list = []

    for csv_name, dc_field in _CSV_TO_DC.items():
        default = _DVT_DEFAULTS[dc_field]
        val = P(csv_name, None)
        if val is not None:
            try:
                resolved[dc_field] = float(val)
            except (ValueError, TypeError):
                resolved[dc_field] = default
                used_defaults.append(dc_field)
        else:
            resolved[dc_field] = default
            used_defaults.append(dc_field)

    # initial_dscg_voltage: CSV / デフォルトは b_ocv [V]。
    # DCInputs では b' = b_ocv / 2 として使用するため変換。
    resolved["initial_dscg_voltage"] = resolved["initial_dscg_voltage"] / 2.0

    if used_defaults:
        print(f"  [DC] CSV 未登録 → デフォルト使用: {', '.join(used_defaults)}")

    return DCInputs(**resolved)


# ── Calc.py 設計計算結果からの DCInputs 構築 ─────────────────

# pos_am_ratio 算出に使う CSV 組成キー
_POS_COMP_KEYS = [
    "cam_r", "pos_ca1_r_total_solid", "pos_ca2_r",
    "pos_binder1_r", "pos_binder2_r", "pos_thickener_r",
]


def build_dc_inputs_from_design(
    result: dict,
    P,
    pos_util_method: str = "poly",
    cli_dependency_mode: str = "np_strict",
    enable_a0_capacity_coupling: bool = True,
    charge_end_voltage: float = 4.2,
    enable_precise_a0_from_ocv: bool = False,
    a0_mode: str = "cellcap_ocv",
    packing_density_target: float = 1.011,
    model_dir=None,
    material: str = "21JB_MP_design",   # 2026-06-02: 21JB_MP_design のみ (旧基準フォールバック禁止)
) -> DCInputs:
    """
    Calc.py の設計計算結果 + param_loader.P() から DCInputs を構築する。

    全 17 項目について CSV (dc_*) を検索し、定義があれば CSV 値を優先。
    未定義の場合:
      ② DESIGN (K, omegaAM, cap_2cyc, eps, L) → 設計計算 result / P() から導出
      ③ OTHER (その他 12 項目)                 → _DVT_DEFAULTS フォールバック

    導出ルール (② DESIGN)
    ----------
    K [g/m²]        result['Pos_Coating_Amount']
    omegaAM [-]      cam_r / Σ(cam_r..pos_thickener_r)
    cap_2cyc [Ah/g]  np_strict: NP比→OCV連鎖 / legacy: result['pos_utilize_rate'] / 1000
    eps [-]          result['Cathode_porosity_pct'] / 100
    L [m]            (P('p_thk') - P('p_foil_thk')) / 2 × 1e-3

    Parameters
    ----------
    result : dict
        calculators.design.Calc.calc_all() の戻り値
    P : callable(name, default) -> float
        param_loader.P 関数
    pos_util_method : str
        "poly" (従来) | "ocv_np_coupled" (NP比連鎖)
    cli_dependency_mode : str
        "legacy" (従来) | "np_strict" (NP比→cap_2cyc 厳密連鎖)
    enable_a0_capacity_coupling : bool
        True で a0 = a0_ref × (Qareal_ref / Qareal) の容量結合を適用 (v3.1 既定)
    charge_end_voltage : float
        充電終止電圧 [V] (4.2=従来, 4.0=4V設計)
    enable_precise_a0_from_ocv : bool
        True で resolve_a0_for_dc_inputs() による厳密 a0 モードを有効化
    a0_mode : str
        "cellcap_ocv" | "actual_cellcapa"
    packing_density_target : float
        緊迫率目標値（比率形式、例: 1.011 = 101.1%）
    model_dir : Path or None
        OCP Map ディレクトリ（enable_precise_a0_from_ocv=True 時に必要）
    material : str
        材料種別 'MC', 'SC', or '21JB_MP_design' (τ² 分岐)

    Returns
    -------
    DCInputs
    """
    resolved: Dict[str, float] = {}
    used_defaults: list[str] = []
    csv_overrides: list[str] = []

    # CSV 由来のみの辞書を参照（CATALOG フォールバックとの誤判定を防止）
    from core.param_loader_design import _PARAMS as _csv_params

    # ── 全 17 項目: CSV 優先 → デフォルト ──
    for csv_name, dc_field in _CSV_TO_DC.items():
        default = _DVT_DEFAULTS[dc_field]
        val = P(csv_name, None)
        if val is not None:
            try:
                resolved[dc_field] = float(val)
                # CATALOG フォールバックを CSV override と誤判定しないよう
                # _PARAMS (CSV由来のみ) を直接チェック
                if dc_field in _DESIGN_DERIVED:
                    if csv_name in _csv_params and _csv_params[csv_name] is not None:
                        csv_overrides.append(dc_field)
            except (ValueError, TypeError):
                resolved[dc_field] = default
                used_defaults.append(dc_field)
        else:
            resolved[dc_field] = default
            used_defaults.append(dc_field)

    # ── ② DESIGN: CSV に未定義なら設計計算から導出 ──

    # initial_dscg_voltage: CSV / デフォルトは b_ocv [V]。
    # DCInputs では b' = b_ocv / 2 として使用するため変換。
    resolved["initial_dscg_voltage"] = resolved["initial_dscg_voltage"] / 2.0


    if "K" not in csv_overrides:
        resolved["K"] = float(result.get("Pos_Coating_Amount", _DVT_DEFAULTS["K"]))

    if "omegaAM" not in csv_overrides:
        comp_vals = [float(P(k) or 0) for k in _POS_COMP_KEYS]
        comp_sum = sum(comp_vals)
        resolved["omegaAM"] = (
            comp_vals[0] / comp_sum if comp_sum > 0
            else _DVT_DEFAULTS["omegaAM"]
        )

    if "cap_2cyc" not in csv_overrides:
        if cli_dependency_mode == "np_strict":
            # NP比→pos_util→cap_2cyc の厳密連鎖
            try:
                from calculators.CellDesign.calculators.design.Calc import (
                    compute_electrode_capacity, compute_np_ratio
                )
            except ModuleNotFoundError:
                from calculators.design.Calc import (
                    compute_electrode_capacity, compute_np_ratio
                )
            compute_np_ratio()  # NP比を確定させる
            _manual, _fitting, pos_util_ocv, *_ = compute_electrode_capacity(
                return_all_methods=True,
            )
            pos_util_np = pos_util_ocv
            resolved["cap_2cyc"] = float(pos_util_np) / 1000.0
        else:
            pos_util = result.get("pos_utilize_rate")
            resolved["cap_2cyc"] = (
                float(pos_util) / 1000.0 if pos_util is not None
                else _DVT_DEFAULTS["cap_2cyc"]
            )

    if "eps" not in csv_overrides:
        cath_por = result.get("Cathode_porosity_pct")
        resolved["eps"] = (
            float(cath_por) / 100.0 if cath_por is not None
            else _DVT_DEFAULTS["eps"]
        )

    if "L" not in csv_overrides:
        p_thk = float(P("p_thk") or 0)
        p_foil_thk = float(P("p_foil_thk") or 0)
        resolved["L"] = (
            (p_thk - p_foil_thk) / 2.0 * 1.0e-3
            if p_thk > p_foil_thk
            else _DVT_DEFAULTS["L"]
        )

    # ── ⑥ a0: モード選択 ──
    if "a0" not in csv_overrides:
        if enable_precise_a0_from_ocv and model_dir is not None:
            from .ocv_pipeline_peak import resolve_a0_for_dc_inputs
            a0_info = resolve_a0_for_dc_inputs(
                design_result=result,
                model_dir=model_dir,
                mode=a0_mode,
                packing_density_target=packing_density_target,
                verbose=True,
            )
            resolved["a0"] = a0_info["a0"]
            print(f"  [DC] a0 resolve: mode={a0_info['a0_mode']}, "
                  f"a0_adopted={a0_info['a0']:.6f}")
        else:
            # 従来互換: result["a0_ocv"] をそのまま使う
            a0_ocv = result.get("a0_ocv")
            if a0_ocv is not None:
                resolved["a0"] = float(a0_ocv)

    # ── ⑧ initial_dscg_voltage: OCV pipeline → デフォルト ──
    if "initial_dscg_voltage" not in csv_overrides:
        bprime_ocv = result.get("bprime_ocv")
        if bprime_ocv is not None:
            # bprime_ocv は既に b'（b_ocv/2）として保存済み → そのまま代入
            resolved["initial_dscg_voltage"] = float(bprime_ocv)

    # ── 電極対向面積 (p_len/p_width → Typ スケーリング) ──
    # fallback = row82 (1880/60)
    _p_len_mm   = float(P("p_len",   1880.0))
    _p_width_mm = float(P("p_width",   60.0))
    resolved["electrode_area_m2"] = 2.0 * _p_len_mm * _p_width_mm * 1.0e-6
    resolved["material"] = material

    # ── cell_typ_ah: CellDesign Pana 0.2C 容量を直接 dc_model に渡す (v5.0) ──
    # 優先順位:
    #   1. result["cell_typ_ah"] (main_v5.py BLOCK 1a-Typ で算出済み)
    #   2. result["cell_typ_mAh"] / 1000  (互換性)
    #   3. None (= 従来の a0→Typ 回帰 + 面積補正にフォールバック)
    _cell_typ_ah = result.get("cell_typ_ah")
    if _cell_typ_ah is None:
        _cell_typ_mah = result.get("cell_typ_mAh")
        if _cell_typ_mah is not None:
            _cell_typ_ah = float(_cell_typ_mah) / 1000.0
    if _cell_typ_ah is not None and float(_cell_typ_ah) > 0:
        resolved["cell_typ_ah"] = float(_cell_typ_ah)

    # ── 診断ログ ──
    provenance = {
        "K":         resolved.get("K"),
        "omegaAM":   resolved.get("omegaAM"),
        "cap_2cyc":  resolved.get("cap_2cyc"),
        "Qareal":    (resolved.get("K", 0) * resolved.get("omegaAM", 0)
                      * resolved.get("cap_2cyc", 0)),
        "a0":        resolved.get("a0"),
        "pos_util_source": (
            "ocv_np_coupled" if cli_dependency_mode == "np_strict" else "poly_or_csv"
        ),
        "a0_source": (
            f"precise_{a0_mode}" if enable_precise_a0_from_ocv else "legacy"
        ),
    }
    design_info = ", ".join(
        f"{k}={resolved[k]:.6g}" for k in _DESIGN_DERIVED if k in resolved
    )
    print(f"  [DC] 設計計算から導出: {design_info}")
    if csv_overrides:
        print(f"  [DC] CSV 優先で上書き: {', '.join(csv_overrides)}")
    if used_defaults:
        print(f"  [DC] CSV 未登録 → デフォルト使用: {', '.join(used_defaults)}")
    print(f"  [DC] provenance: pos_util={provenance['pos_util_source']}, "
          f"a0={provenance['a0_source']}, "
          f"Qareal={provenance['Qareal']:.6g}")

    inp = DCInputs(**resolved)

    # ── a0 容量結合適用 (v3.1 既定: enable_a0_capacity_coupling=True) ──
    if enable_a0_capacity_coupling:
        inp = apply_a0_capacity_coupling(inp)

    return inp


def apply_a0_capacity_coupling(inp: DCInputs) -> DCInputs:
    """
    DCInputs の a0 を容量結合モデル (a0 ∝ 1/Qareal) で再計算する。

    緊迫率一定の下では OCV(SOC) カーブ形状が固定されるため、
    Qareal (= K×ωAM×cap) 変化に対して a0 は逆比例する:
        a0_new = a0_ref × (Qareal_ref / Qareal_new)
    """
    from .a0_capacity_coupling import apply_a0_coupling
    return apply_a0_coupling(inp)


__all__ = [
    "F_FARADAY",
    "CriticalLiParameters",
    "calc_critical_li_concentration",
    "calc_voltage_discriminant",
    "calculate_critical_li_unified",
    "DCInputs",
    "DCOutputs",
    "DomainError",
    "calc_dc_outputs",
    "interpolate_typ_capacity",
    "DC_OUTPUT_FIELD_ORDER",
    "build_dc_inputs_from_loader",
    "build_dc_inputs_from_design",
    "apply_a0_capacity_coupling",
    "_DVT_DEFAULTS",
    "_CSV_TO_DC",
    "calc_tau_sq",
    "calc_tau",
    "calc_D_eff",
    "_TAU2_PARAMS",
]

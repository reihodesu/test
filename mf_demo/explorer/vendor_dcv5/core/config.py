"""
Configuration module for battery cell design calculation system.

Provides:
- Path management (input/output directories)
- Exception hierarchy
- Environment variable setup
"""
from __future__ import annotations
from pathlib import Path
import os
from typing import Optional

# ============================================================
# Path Configuration
# ============================================================

class Paths:
    """Centralized path management."""
    
    def __init__(self, script_dir: Optional[Path] = None):
        if script_dir is None:
            # 相対パスで自動検出: config.py → module/ → dict/
            script_dir = Path(__file__).parent.parent
        
        self.script_dir = script_dir
        self.module_dir = script_dir / "module"
        self.input_dir = script_dir / "input"
        self.output_dir = script_dir / "output"
        
        # Subdirectories (2026-05-31: MAP/曲線を input/maps/ 配下へ集約。
        #   cellsim 系 → maps/cellsim/、np_OCV/Si テーブル → maps/ 直下)
        self.ocv_dir = self.input_dir / "maps" / "cellsim"
        self.ocv_celldesign_dir = self.input_dir / "maps"
        self.swell_celldesign_dir = self.input_dir / "maps"

        # CSV file paths
        self.variable_csv = self.input_dir / "variable_parameter.csv"
        self.fixed_csv = self.input_dir / "fixed_parameter.csv"
        self.np_ocv_csv = self.ocv_celldesign_dir / "np_OCV.csv"
        self.si_table_csv = self.swell_celldesign_dir / "Si1pct_linear_table.csv"
    
    def setup_env_vars(self):
        """Set environment variables for legacy modules."""
        os.environ['NP_OCV_CSV_PATH'] = str(self.np_ocv_csv)
        os.environ['SI_LINEAR_TABLE_PATH'] = str(self.si_table_csv)
    
    def validate(self) -> list[str]:
        """Validate that required files exist. Returns list of missing files."""
        missing = []
        # 必須ファイル: variable/fixed CSVとOCV/Siテーブル
        for name, path in [
            ("variable_csv", self.variable_csv),
            ("fixed_csv", self.fixed_csv),
            ("np_ocv_csv", self.np_ocv_csv),
            ("si_table_csv", self.si_table_csv),
        ]:
            if not path.exists():
                missing.append(f"{name}: {path}")
        return missing


# ============================================================
# Exception Hierarchy (defined in exceptions.py, re-exported here)
# ============================================================

from .exceptions import CalcError, ConfigError, DataError, DomainError


# ============================================================
# Global Configuration Instance
# ============================================================

# Default paths instance (can be overridden)
paths = Paths()


# ============================================================
# Physical Constants & Aging Calculation Parameters
# ============================================================

class AgingConstants:
    """
    Fixed constants for C_critical and aging calculations.
    
    These parameters are not in fixed_parameter.csv because they are
    physical constants or empirical values that should not be modified
    via optiSLang optimization.
    
    Usage:
        from module.config import AgingConstants
        F = AgingConstants.F
    """
    
    # Physical constants
    F = 96485.0              # Faraday constant [C/mol]
    R_gas = 8.3145           # Gas constant [J/(mol·K)]
    T_abs = 273.15           # Absolute zero offset [K]
    
    # Arrhenius parameters for Dely (electrolyte diffusion coefficient)
    A0 = 2.06e-7             # Pre-exponential factor [m²/s]
    Ea = -17500.0            # Activation energy [J/mol]
    T_Dely = 55.0            # Temperature for Dely calculation [°C] (fixed)
    
    # Cell geometry for V0 calculation
    CanDin = 0.01025         # Case inner radius [m] (10.25 mm)
    
    # C_critical calculation parameters
    Cr_Li_eps = 0.25         # Porosity for C_critical [-]
    Cr_Li_bruggeman = 1.8    # Bruggeman exponent (diffusion) [-]
    Cr_Li_u = 1.045          # N/P ratio for C_critical [-]
    b_ocv = 4.0              # OCV voltage [V]
    cap_slope = 0.227        # Capacity slope [V/Ah]
    
    # Tortuosity parameters (γ = A_tortuosity · ε^(1 - gamma_b))
    A_tortuosity = 1.0       # Tortuosity coefficient [-]
    gamma_b = 1.425          # Tortuosity Bruggeman exponent [-]
    
    # ── DC constraint model fixed inputs ──
    # resistance_increase_rate / capacity_fade_rate は 21JB_MP_design (row82) 実測値。
    # electrolyte_diffusion / pos_tortuosity / dc_A は物理定数。
    # variable_parameter.csv にも設計シート計算にも由来しないため config 登録。
    dc_resistance_increase_rate = 0.00024              # 抵抗上昇率 [Ohm/Year]  (row82)
    dc_capacity_fade_rate       = 0.0085               # 容量劣化速度 [V/Ah/√Year]  (row82)
    dc_electrolyte_diffusion    = 4.0e-10              # 電解液拡散係数 [m²/s]  (row82)
    dc_pos_tortuosity           = 0.8733               # τ² fitting exponent b (row82 BASE) [-]
    dc_A_coefficient            = 0.7491               # 係数 A (row82 BASE) [-]
    
    # ── Aging model parameters (旧 fixed CSV Index 2001-2016 より移設) ──
    # 曲路率 (Tortuosity factor)
    p_tau    = 3.182724621       # 正極曲路率 [-]
    n_tau    = 2.621868273       # 負極曲路率 [-]
    sepa_tau = 1.851017363       # セパレータ曲路率 [-]
    # タブ本数
    p_tab_N  = 2.0              # 正極タブ本数 [-]
    n_tab_N  = 0.0              # 負極タブ本数 [-]
    # 電解液イオン伝導率
    K0_ely   = 1.074            # 電解液イオン伝導率 [S/m]
    # 2026-06-02: R0_correction_factor (Bruggeman理論×経験補正フダ, 旧0.41282) を完全削除。
    #   非物理の実測フィットだったため撤廃。R0 は DCIR の V7 R01〜R06 予測 (verify_v7_R0x) を真値採用。

    @classmethod
    def to_dict(cls) -> dict:
        """Return all constants as a dictionary."""
        return {
            "F": cls.F,
            "R_gas": cls.R_gas,
            "T_abs": cls.T_abs,
            "A0": cls.A0,
            "Ea": cls.Ea,
            "T_Dely": cls.T_Dely,
            "CanDin": cls.CanDin,
            "Cr_Li_eps": cls.Cr_Li_eps,
            "Cr_Li_bruggeman": cls.Cr_Li_bruggeman,
            "Cr_Li_u": cls.Cr_Li_u,
            "b_ocv": cls.b_ocv,
            "cap_slope": cls.cap_slope,
            "A_tortuosity": cls.A_tortuosity,
            "gamma_b": cls.gamma_b,
            "dc_resistance_increase_rate": cls.dc_resistance_increase_rate,
            "dc_capacity_fade_rate": cls.dc_capacity_fade_rate,
            "dc_electrolyte_diffusion": cls.dc_electrolyte_diffusion,
            "dc_pos_tortuosity": cls.dc_pos_tortuosity,
            "dc_A_coefficient": cls.dc_A_coefficient,
            "p_tau": cls.p_tau,
            "n_tau": cls.n_tau,
            "sepa_tau": cls.sepa_tau,
            "p_tab_N": cls.p_tab_N,
            "n_tab_N": cls.n_tab_N,
            "K0_ely": cls.K0_ely,
        }


# ============================================================
# Thermal Model Defaults (SC temperature solver)
# ============================================================

class ThermalDefaults:
    """
    熱モデルのデフォルト定数。

    根拠
    ----
    - h_t   : 90 W/(m²·K)  — 複数セル実測データからの同定値
    - C_th  : 48.0  J/K    — ΔT=H(t)/48 (★蓄電 xlsx と一致)
    - A_surf: 0.00545 m²   — 2270H セル外表面積
                              φ21.5 mm × 70 mm → ≈54.5 cm²
    - T_amb : 25.0 °C      — 環境初期温度
    - alpha_K: 0.01754 1/°C — イオン伝導率温度係数 (SC solver)
    - T_base : 25.0 °C     — 基準温度 (SC solver)

    派生量
    ------
    - hA     = h_t × A_surf = 0.4905 W/K
    - tau_th = C_th / hA    ≈ 97.9 s

    Usage::

        from core.config import ThermalDefaults
        hA = ThermalDefaults.h_t * ThermalDefaults.A_surf
    """
    C_th: float    = 48.0      # セル熱容量 [J/K]  (ΔT=H(t)/48, ★蓄電 xlsx 一致)
    h_t: float     = 90.0      # 熱伝達係数 [W/(m²·K)]  (実測同定)
    A_surf: float  = 0.00545   # セル外表面積 [m²]  (2270H: φ21.5×70mm)
    T_amb: float   = 25.0      # 雰囲気温度 [°C]
    alpha_K: float = 0.01754   # イオン伝導率温度係数 [1/°C]
    T_base: float  = 25.0      # 基準温度 [°C]

    @classmethod
    def hA(cls) -> float:
        """総合熱伝達 [W/K] = h_t × A_surf"""
        return cls.h_t * cls.A_surf

    @classmethod
    def tau_th(cls) -> float:
        """熱時定数 [s] = C_th / hA"""
        return cls.C_th / cls.hA()

"""explorer/config.py — 独立上流変数の仕様と分布モード（HANDOVER B-4①②）

Sobol 指標は「与えた入力分布のもとでの寄与度」であってモデル固有の性質では
ないため、次の 2 モードを切り替え可能にする（B-4①）。図中にどちらのモードで
出したかを明記すること。

  - design    : 設定上下限の一様分布 → 設計探索用
  - variation : 実工程 3σ の正規分布 → ばらつきリスク評価用

DOE を張るのは真に独立な上流変数のみ（B-4②）。派生量（eps/K/L/Typ…）は
cell_design.py（評価関数内部）で計算する。
"""
from __future__ import annotations

# 変数仕様: name -> dict
#   label    : 図中表示名（日本語）
#   category : 設計因子 / 材料物性 / 使用条件 / 劣化速度
#   design   : (lo, hi) 一様分布の上下限
#   mean     : variation モードの平均（公称値）
#   cv       : variation モードの変動係数（std = mean*cv）。std_abs があればそちら優先
#   std_abs  : variation モードの絶対 std（cv より優先。T_use 等）
#   phys     : (lo, hi) 物理妥当域（外は無効サンプル: B-4④ マスキング）
VARSPEC = {
    "coat_load":  {"label": "塗布量\n[mg/cm²]", "category": "設計因子",
                   "design": (6.0, 14.0), "mean": 8.1, "cv": 0.05,
                   "phys": (3.0, 20.0)},
    "mix_density": {"label": "合剤密度\n[g/cm³]", "category": "設計因子",
                    "design": (3.0, 3.8), "mean": 3.40, "cv": 0.03,
                    "phys": (2.5, 4.5)},
    "am_frac":    {"label": "活物質比\n[-]", "category": "材料物性",
                   "design": (0.94, 0.99), "mean": 0.985, "cv": 0.01,
                   "phys": (0.80, 0.999)},
    "am_cap":     {"label": "比容量\n[Ah/g]", "category": "材料物性",
                   "design": (0.19, 0.22), "mean": 0.21, "cv": 0.02,
                   "phys": (0.15, 0.24)},
    "T_use":      {"label": "使用温度\n[°C]", "category": "使用条件",
                   "design": (25.0, 60.0), "mean": 45.0, "std_abs": 5.0,
                   "phys": (10.0, 70.0)},
    "k_fade_ref": {"label": "容量劣化速度\n[V/Ah/√yr]", "category": "劣化速度",
                   "design": (0.004, 0.016), "mean": 0.0085, "cv": 0.15,
                   "phys": (0.0, 0.05)},
    "r_inc_ref":  {"label": "抵抗上昇率\n[mΩ/yr]", "category": "劣化速度",
                   "design": (0.10, 0.50), "mean": 0.24, "cv": 0.15,
                   "phys": (0.0, 1.5)},
}
XKEYS = list(VARSPEC)
LABEL = {k: v["label"].replace("\n", " ") for k, v in VARSPEC.items()}
CATEGORY = {k: v["category"] for k, v in VARSPEC.items()}

# 温度計算の較正域（外挿はマスキング対象: B-4④）
T_CALIB_C = (10.0, 70.0)

# 保存時点グリッド [year]（B-4③ 時間依存）
TIME_GRID = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0]

SEED = 20260719


def make_problem(mode: str = "design", keys=None, override_bounds=None) -> dict:
    """SALib problem を分布モード別に構築。

    design    : 一様分布（bounds=[lo,hi]）
    variation : 正規分布（dists='norm', bounds=[mean,std]）
    override_bounds : {name: (lo, hi)} 領域ブラッシング用に design 範囲を上書き。
    """
    keys = keys or XKEYS
    override_bounds = override_bounds or {}
    names, bounds, dists = [], [], []
    for k in keys:
        s = VARSPEC[k]
        names.append(k)
        if mode == "design":
            bounds.append(list(override_bounds.get(k, s["design"])))
            dists.append("unif")
        elif mode == "variation":
            std = s.get("std_abs", s["mean"] * s.get("cv", 0.1))
            bounds.append([s["mean"], std])
            dists.append("norm")
        else:
            raise ValueError(f"unknown mode: {mode}")
    return {"num_vars": len(names), "names": names,
            "bounds": bounds, "dists": dists}

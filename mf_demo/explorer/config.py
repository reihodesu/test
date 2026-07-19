"""explorer/config.py — 独立上流変数の仕様・分布モード・応答/制約（報告書準拠 v2）

社内テクニカルレポート（T0073-2025-00305「保存後出力劣化-理論とDC向け18機種」/
NCR2170JB Step2 設計探索）に整合させた版。

■ 主応答（報告書の設計成立条件そのもの）
  - y_end : 放電後電圧 [V]（制約 >= 2.5V）      ← 抵抗劣化モードの指標
  - Cli   : 限界Li塩濃度 [mol/L]（制約 <= 1.4M） ← 電解液Li+濃度拡散劣化モードの指標
  DC 向け目標: 300W / 90sec / 5年保存後。

■ 独立変数（報告書 NCR2170JB Step2 の探索6因子 ＋ 使用温度）
  セル抵抗 R0 / 正極塗布量 / 正極利用率 / 正極活物質密度 / 電解液拡散係数 /
  正極曲路率 / 使用温度。派生量（K/eps/L/Typ/a0）は cell_design.py で計算（B-4②）。

■ 分布モード（B-4①）: design=一様（設計探索） / variation=3σ正規（ばらつき）
"""
from __future__ import annotations

# name -> 仕様
#   label/category/design(lo,hi)/mean/cv or std_abs/phys(lo,hi)
VARSPEC = {
    "R0_init":    {"label": "セル抵抗\n[mΩ]", "category": "設計因子",
                   "design": (3.0, 8.0), "mean": 5.3, "cv": 0.08,
                   "phys": (1.0, 15.0)},
    "coat_load":  {"label": "正極塗布量\n[mg/cm²]", "category": "設計因子",
                   "design": (6.0, 13.0), "mean": 8.2, "cv": 0.05,
                   "phys": (2.0, 20.0)},
    "am_cap":     {"label": "正極利用率\n[Ah/g]", "category": "材料物性",
                   "design": (0.190, 0.215), "mean": 0.205, "cv": 0.02,
                   "phys": (0.15, 0.24)},
    "mix_density": {"label": "活物質密度\n[g/cm³]", "category": "設計因子",
                    "design": (3.2, 3.7), "mean": 3.5, "cv": 0.03,
                    "phys": (2.5, 4.2)},
    "Dely":       {"label": "電解液拡散係数\n[m²/s]", "category": "材料物性",
                   "design": (3.2e-10, 4.8e-10), "mean": 4.0e-10, "cv": 0.10,
                   "phys": (0.5e-10, 1.0e-9)},
    "gamma":      {"label": "正極曲路率\n[-]", "category": "材料物性",
                   "design": (1.4, 2.0), "mean": 1.6, "cv": 0.06,
                   "phys": (1.0, 3.0)},
    "T_use":      {"label": "使用温度\n[°C]", "category": "使用条件",
                   "design": (25.0, 50.0), "mean": 38.0, "std_abs": 6.0,
                   "phys": (20.0, 90.0)},
}
XKEYS = list(VARSPEC)
LABEL = {k: v["label"].replace("\n", " ") for k, v in VARSPEC.items()}
CATEGORY = {k: v["category"] for k, v in VARSPEC.items()}

# 応答定義: name -> (label, 制約種別, 閾値)
#   'min' = 下限制約（value >= thr で OK）/ 'max' = 上限制約（value <= thr で OK）
RESPONSES = {
    "y_end": {"label": "放電後電圧 [V]", "constraint": "min", "thr": 2.5,
              "mode": "抵抗劣化モード"},
    "Cli":   {"label": "限界Li塩濃度 [mol/L]", "constraint": "max", "thr": 1.4,
              "mode": "電解液Li+濃度拡散劣化モード"},
    # 二値応答: 300W維持可否（1=維持可, 0=不可）。全域で定義されるため代入不要。
    "feasible": {"label": "300W維持可否 [0/1]", "constraint": None, "thr": None,
                 "mode": "電力維持の成否"},
}
# 無効サンプル代入時の worst-case ペナルティ値（penalty ポリシー用, 物理的な失敗側）
RESP_PENALTY = {"y_end": 0.0, "Cli": 5.0}

# 設計 Li 塩濃度（初期）[mol/L]。無次元C-rate = Cli / C_Li_DESIGN の分母。
C_LI_DESIGN = 1.4       # 目標: 劣化後も限界Li塩濃度がこれを超えない設計
T_CALIB_C = (20.0, 90.0)  # 温度較正域（外は外挿→マスキング, B-4④）

TIME_GRID = [0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0]  # 保存時点 [year]（B-4③）
T_REF = 5.0             # 主要図の基準時点 [year]（報告書: 5年保存後）
SEED = 20260719


def make_problem(mode: str = "design", keys=None, override_bounds=None) -> dict:
    """SALib problem を分布モード別に構築。

    design    : 一様分布（bounds=[lo,hi]）
    variation : 正規分布（dists='norm', bounds=[mean,std]）
    override_bounds : {name:(lo,hi)} 領域ブラッシング用に design 範囲を上書き。
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

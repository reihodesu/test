"""explorer/run_figures_v3.py — 改訂第3版で追加した図（D群・E-6・F-1）の一括生成

run_sensitivity（sobol_*）／run_explorer（explore_*）で作られる基本図に加え、
改訂第3版で新設・強化した以下を生成する:
  - D-1  explore_contour.png        セル抵抗×塗布量（y_end基準, 固定値注記つき）
  - D-2  explore_contour_cli.png    塗布量×活物質密度（Cli基準の追加断面）
  - D-3  explore_contour_gamma3.png 曲路率 低1.4/中1.7/高2.0 の3枚比較
  - D-4  sobol_conditional.png      段階的3領域の領域条件付き感度（色分け・有効率/代入率）
  - E-6  sobol_mode_stacked.png     劣化モード内訳の100%積み上げ面グラフ
  - F-1  sobol_f1_robustness.png    §5.4 のロバスト性検証（median/penalty/Spearman）

実行:  python -m mf_demo.explorer.run_figures_v3
出力:  mf_demo/output/explorer/*.png
"""
from __future__ import annotations

import os

from . import viz_explorer as viz
from . import plots
from .sensitivity import conditional_staged, mode_fraction_over_time, f1_robustness
from .config import TIME_GRID, T_REF

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "explorer")
os.makedirs(OUT, exist_ok=True)
def _p(n): return os.path.normpath(os.path.join(OUT, n))

# 領域定義（全域→中間→拡散モード頻発域）。F-1 と図5で共有する。
REGIONS = [
    ("全域", {}),
    ("中間", {"coat_load": (8.0, 13.0), "gamma": (1.6, 2.0)}),
    ("拡散頻発域", {"coat_load": (10.0, 13.0), "gamma": (1.7, 2.0)}),
]


def main(N_cond=2048, N_mode=1024, N_f1_sobol=2048, N_f1_lhs=6000):
    print("=== 改訂第3版 追加図の生成 ===")

    print("[D-1] 制約つきコンター（セル抵抗×塗布量, y_end基準）")
    viz.contour_2axis(_p("explore_contour.png"), "R0_init", "coat_load",
                      color_by="y_end", axis_basis="y_end 上位2軸(塗布量・セル抵抗)")

    print("[D-2] 追加断面（塗布量×活物質密度, Cli基準）")
    viz.contour_2axis(_p("explore_contour_cli.png"), "coat_load", "mix_density",
                      color_by="Cli", axis_basis="Cli 上位2軸(塗布量・活物質密度)")

    print("[D-3] コンター条件比較（曲路率 低1.4/中1.7/高2.0）")
    viz.contour_gamma3(_p("explore_contour_gamma3.png"))

    print("[D-4] 段階的3領域の領域条件付き感度（限界Li塩濃度）")
    st = conditional_staged("Cli", T_REF, N_cond, REGIONS)
    plots.fig_conditional_staged(st, "Cli", _p("sobol_conditional.png"))

    print("[E-6] 劣化モード内訳の100%積み上げ面グラフ")
    mf = mode_fraction_over_time("design", N_mode, TIME_GRID)
    plots.fig_mode_stacked(mf, _p("sobol_mode_stacked.png"))

    print("[F-1] §5.4 ロバスト性検証（median/penalty/Spearman|ρ|）")
    f1 = f1_robustness(REGIONS, T_REF, N_sobol=N_f1_sobol, N_lhs=N_f1_lhs)
    for r in f1:
        print(f"    {r['name']}: 有効{r['valid_rate']:.2f} 代入{r['impute_rate']:.2f} "
              f"（Saltelli {r['n_saltelli']}点 / 有効LHS {r['n_valid_lhs']}点）")
    plots.fig_f1_robustness(f1, _p("sobol_f1_robustness.png"))

    print(f"[done] 追加6図 -> {OUT}")


if __name__ == "__main__":
    main()

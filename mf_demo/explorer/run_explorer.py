"""explorer/run_explorer.py — ①②③ 設計探索アーキテクチャの一括実行＋作図（v2）

感度スクリーニング → 並行座標(自動反映) → 交互作用ネットワーク → 制約つきコンター。
実行:  python -m mf_demo.explorer.run_explorer [N_pop]
出力:  mf_demo/output/explorer/explore_*.png
"""
from __future__ import annotations

import os
import sys
import numpy as np

from .config import XKEYS, T_REF
from .sensitivity import analyze_mode
from .screening import generate_population, screen_by_sensitivity
from . import viz_explorer as viz

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "explorer")
os.makedirs(OUT, exist_ok=True)
def _p(n): return os.path.normpath(os.path.join(OUT, n))


def main(N_pop=600, N_sobol=256):
    print(f"=== ①②③ 設計探索アーキテクチャ v2 (母集団={N_pop}, Sobol N={N_sobol}) ===")

    print("[1] ① 感度解析（design, 放電後電圧 @ 基準年）")
    _res = analyze_mode("design", T_REF, N_sobol, calc_second_order=True)
    res_y, res_c = _res["y_end"], _res["Cli"]
    STy = dict(zip(XKEYS, res_y["ST"]))
    print("    ST(y_end):", {k: round(v, 2) for k, v in STy.items()})

    print("[2] ① 感度スクリーニング（能動軸の自動抽出）")
    active = screen_by_sensitivity(STy, method="cumulative", thresh=0.90, st_floor=0.05)
    print(f"    能動軸 = {active}")

    print("[3] 設計母集団を評価")
    df = generate_population(N_pop, t=T_REF)
    print(f"    有効={df['valid'].mean():.2f} 成立={df['ok'].mean():.2f} "
          f"（電圧OK={df['c_volt'].mean():.2f}, Li塩OK={df['c_cli'].mean():.2f}）")

    print("[4] 作図")
    viz.parallel_coordinates(df, active, STy, _p("explore_parallel.png"), color_col="y_end")
    # ブラッシング: 能動軸トップを高感度帯に絞る
    k0 = active[0]
    a, b = np.percentile(df[k0], [55, 95])
    viz.parallel_coordinates(df, active, STy, _p("explore_parallel_brush.png"),
                             brush={k0: (float(a), float(b))}, color_col="y_end")
    # ② 交互作用ネットワーク（2応答）
    from .plots import fig_network
    fig_network(res_y, res_c, _p("explore_network.png"))
    # ③ 制約つきコンター（セル抵抗 × 塗布量, 報告書 Step2 形式）
    viz.contour_2axis(_p("explore_contour.png"), xkey="R0_init", ykey="coat_load")
    # ③ アーキテクチャ図
    viz.architecture_diagram(active, _p("explore_architecture.png"))

    print(f"[done] 図5枚 -> {OUT}")


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    main(N)

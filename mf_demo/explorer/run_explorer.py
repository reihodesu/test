"""explorer/run_explorer.py — ①②③ 設計探索アーキテクチャの一括実行＋作図

感度スクリーニング → 並行座標(自動反映) → 交互作用ネットワーク → 制約つきコンター
までを通しで実行する。

実行:  python -m mf_demo.explorer.run_explorer [N_pop]
出力:  mf_demo/output/explorer/explore_*.png
"""
from __future__ import annotations

import os
import sys
import numpy as np

from .config import XKEYS
from .sensitivity import analyze_at, T_REF
from .screening import generate_population, screen_by_sensitivity
from . import viz_explorer as viz

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "explorer")
os.makedirs(OUT, exist_ok=True)
def _p(name): return os.path.normpath(os.path.join(OUT, name))


def main(N_pop=600, N_sobol=256):
    print(f"=== ①②③ 設計探索アーキテクチャ (母集団={N_pop}, Sobol N={N_sobol}) ===")

    print("[1] ① 感度解析（design, 容量維持率 @ 基準年）")
    res = analyze_at("design", T_REF, N_sobol, calc_second_order=True)
    ST = dict(zip(XKEYS, res["ST"]))
    S2 = res["S2"]
    print("    ST:", {k: round(v, 3) for k, v in ST.items()})

    print("[2] ① 感度スクリーニング（能動軸の自動抽出）")
    active = screen_by_sensitivity(ST, method="cumulative", thresh=0.90, st_floor=0.05)
    top2 = sorted(active, key=lambda k: -ST[k])[:2]
    print(f"    能動軸 = {active}")
    print(f"    コンター2軸 = {top2}")

    print("[3] 設計母集団を評価（並行座標・コンターの元データ）")
    df = generate_population(N_pop, t=T_REF)
    print(f"    有効={df['valid'].mean():.2f} / 制約OK={df['ok'].mean():.2f} "
          f"（寿命OK={df['c_life'].mean():.2f}, 容量OK={df['c_cap'].mean():.2f}）")

    print("[4] 作図")
    # ① 並行座標（制約OK個体を強調）
    viz.parallel_coordinates(df, active, ST, _p("explore_parallel.png"))
    # ① 並行座標（ブラッシング: 能動軸トップを高感度帯に絞る）
    k0 = top2[0]
    a, b = np.percentile(df[k0], [55, 95])
    viz.parallel_coordinates(df, active, ST, _p("explore_parallel_brush.png"),
                             brush={k0: (float(a), float(b))})
    # ② 交互作用ネットワーク（design のみ・単独図）
    from .plots import _network
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 7))
    _network(ax, np.array(res["ST"]), S2, "交互作用ネットワーク（design）")
    fig.suptitle("② Sobol指標・交互作用の可視化：ノード径=ST / 線=2次S2", fontsize=12)
    fig.tight_layout(); fig.savefig(_p("explore_network.png"), bbox_inches="tight")
    plt.close(fig)
    # ③ 制約つきコンター（感度上位2軸）
    viz.contour_2axis(top2[0], top2[1], _p("explore_contour.png"))
    # ③ アーキテクチャ図
    viz.architecture_diagram(active, top2, _p("explore_architecture.png"))

    print(f"[done] 図5枚 -> {OUT}")
    print("       explore_parallel.png / explore_parallel_brush.png /")
    print("       explore_network.png / explore_contour.png / explore_architecture.png")


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    main(N)

"""explorer/run_sensitivity.py — 保存劣化 Sobol 感度解析の一括実行＋作図

実行:  python -m mf_demo.explorer.run_sensitivity [N]
出力:  mf_demo/output/explorer/sobol_*.png, sobol_result.json
"""
from __future__ import annotations

import os
import sys
import json
import numpy as np

from .config import XKEYS, make_problem, TIME_GRID
from .sensitivity import analyze_at, time_evolution, convergence, T_REF, _sobol_of_Y
from .degradation import evaluate
from SALib.sample import sobol as sobol_sample
from . import plots

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "explorer")
os.makedirs(OUT, exist_ok=True)
def _p(name): return os.path.normpath(os.path.join(OUT, name))

# 領域ブラッシング（並行座標で塗布量・使用温度を絞った状態に相当）
REGION_OVERRIDE = {"coat_load": (7.5, 8.7), "T_use": (25.0, 35.0)}
REGION_DESC = "塗布量7.5-8.7, 使用温度25-35℃"


def analyze_region(t, N, override):
    prob = make_problem("design", XKEYS, override_bounds=override)
    X = sobol_sample.sample(prob, N, calc_second_order=True, seed=7)
    ret, ok = evaluate(X, XKEYS, t)
    d = _sobol_of_Y(prob, ret, ok, True)
    d["n_samples"] = int(len(X))
    return d


def main(N=256):
    print(f"=== 保存劣化 Sobol 感度解析 (N={N}, 応答=容量維持率 @ {T_REF:.0f}年) ===")
    print("[1] 主要感度: design / variation @ t_ref")
    res_design = analyze_at("design", T_REF, N, calc_second_order=True)
    res_var = analyze_at("variation", T_REF, N, calc_second_order=True)
    for m, r in [("design", res_design), ("variation", res_var)]:
        top = sorted(zip(XKEYS, r["ST"]), key=lambda z: -z[1])[:3]
        print(f"    [{m}] 有効率={r['valid_rate']:.2f} 除外率={r['nan_rate']:.2f} "
              f"ST上位={[f'{k}:{v:.2f}' for k,v in top]}")

    print("[2] 時間推移 (B-4③): design / variation")
    te_design = time_evolution("design", N, TIME_GRID)
    te_var = time_evolution("variation", N, TIME_GRID)

    print("[3] 領域条件付き感度 (ブラッシング相当)")
    rc_global = res_design
    rc_region = analyze_region(T_REF, N, REGION_OVERRIDE)
    print(f"    全域 有効率={rc_global['valid_rate']:.2f} → 領域 有効率={rc_region['valid_rate']:.2f}")

    print("[4] 収束確認")
    conv = convergence("design", T_REF)

    # --- 図 ---
    print("[5] 作図")
    plots.fig_main(res_design, res_var, T_REF, _p("sobol_main.png"))
    plots.fig_gap(res_design, res_var, _p("sobol_interaction_gap.png"))
    plots.fig_network(res_design, res_var, _p("sobol_network.png"))
    plots.fig_time_evolution(te_design, te_var, _p("sobol_time_evolution.png"))
    plots.fig_conditional(rc_global, rc_region, REGION_DESC, T_REF,
                          _p("sobol_conditional.png"))
    plots.fig_convergence(conv, T_REF, _p("sobol_convergence.png"))

    result = {"N": N, "t_ref": T_REF, "keys": XKEYS,
              "design": res_design, "variation": res_var,
              "time_evolution": {"design": te_design, "variation": te_var},
              "conditional": {"global": rc_global, "region": rc_region,
                              "region_override": REGION_OVERRIDE, "desc": REGION_DESC},
              "convergence": conv}
    with open(_p("sobol_result.json"), "w") as f:
        json.dump(result, f, indent=1, default=float)
    print(f"[done] 図6枚 + sobol_result.json -> {OUT}")
    return result


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 256
    main(N)

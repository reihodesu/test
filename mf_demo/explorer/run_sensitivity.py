"""explorer/run_sensitivity.py — 保存劣化 Sobol 感度解析の一括実行＋作図（v2）

実行:  python -m mf_demo.explorer.run_sensitivity [N]
出力:  mf_demo/output/explorer/sobol_*.png, sobol_result.json
"""
from __future__ import annotations

import os
import sys
import json
import numpy as np

from .config import XKEYS, VARSPEC, TIME_GRID, T_REF
from .sensitivity import (analyze_at, time_evolution, convergence,
                          mode_fraction_over_time)
from .degradation import responses_at
from . import plots

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "explorer")
os.makedirs(OUT, exist_ok=True)
def _p(n): return os.path.normpath(os.path.join(OUT, n))

# 領域ブラッシング（拡散劣化モードが出やすい: 高塗布量・高曲路率）
REGION_OVERRIDE = {"coat_load": (10.0, 13.0), "gamma": (1.7, 2.0)}
REGION_DESC = "塗布量10-13, 曲路率1.7-2.0"


def _trajectory(fine_t):
    x0 = {k: VARSPEC[k]["mean"] for k in XKEYS}
    ye, cli, ndc = [], [], []
    for t in fine_t:
        r = responses_at(x0, t)
        ye.append(r["y_end"]); cli.append(r["Cli"]); ndc.append(r["ndc"])
    ndc = np.array(ndc)
    t_switch = None
    cross = np.where(np.isfinite(ndc) & (ndc >= 1.0))[0]
    if len(cross):
        t_switch = float(fine_t[cross[0]])
    return {"times": list(fine_t), "y_end": ye, "Cli": cli, "t_switch": t_switch}


def _region(response, t, N):
    from .config import make_problem
    from .sensitivity import _sobol_of_Y
    from .degradation import evaluate
    from SALib.sample import sobol as ss
    prob = make_problem("design", XKEYS, override_bounds=REGION_OVERRIDE)
    X = ss.sample(prob, N, calc_second_order=True, seed=7)
    Y = evaluate(X, XKEYS, t)
    d = _sobol_of_Y(prob, Y[response], Y["valid"], True); d["n_samples"] = int(len(X))
    return d


def main(N=256):
    print(f"=== 保存劣化 Sobol 感度解析 v2 (N={N}, @ {T_REF:.0f}年) ===")
    print("[1] 主要感度: 2応答 × 2分布モード")
    res = {}
    for rp in ["y_end", "Cli"]:
        res[rp] = {}
        for md in ["design", "variation"]:
            res[rp][md] = analyze_at(md, T_REF, N, response=rp, calc_second_order=True)
            top = sorted(zip(XKEYS, res[rp][md]["ST"]), key=lambda z: -z[1])[:3]
            print(f"    [{rp}/{md}] 有効{res[rp][md]['valid_rate']:.2f} "
                  f"ST上位={[f'{k}:{v:.2f}' for k,v in top]}")

    print("[2] 時間推移（B-4③）")
    te_yend = time_evolution("design", N, "y_end")
    te_cli = time_evolution("design", N, "Cli")

    print("[3] 支配モードの変遷")
    fine_t = list(np.linspace(0.1, 8.0, 30))
    traj = _trajectory(fine_t)
    modefrac = mode_fraction_over_time("design", 512, TIME_GRID)
    print(f"    公称モード遷移点 t≈{traj['t_switch']}年")

    print("[4] 領域条件付き感度（Cli, 拡散モード領域）")
    rc_global = res["Cli"]["design"]
    rc_region = _region("Cli", T_REF, N)

    print("[5] 収束確認（y_end）")
    conv = convergence("design", T_REF, "y_end")

    print("[6] 作図")
    plots.fig_sensitivity_grid(res, T_REF, _p("sobol_main.png"))
    plots.fig_time_evolution(te_yend, te_cli, _p("sobol_time_evolution.png"))
    plots.fig_mode_transition(traj, modefrac, _p("sobol_mode_transition.png"))
    plots.fig_network(res["y_end"]["design"], res["Cli"]["design"], _p("sobol_network.png"))
    plots.fig_conditional(rc_global, rc_region, REGION_DESC, "Cli", T_REF,
                          _p("sobol_conditional.png"))
    plots.fig_convergence(conv, "y_end", T_REF, _p("sobol_convergence.png"))

    result = {"N": N, "t_ref": T_REF, "keys": XKEYS, "sensitivity": res,
              "time_evolution": {"y_end": te_yend, "Cli": te_cli},
              "trajectory": traj, "mode_fraction": modefrac,
              "conditional": {"global": rc_global, "region": rc_region,
                              "override": REGION_OVERRIDE, "desc": REGION_DESC},
              "convergence": conv}
    with open(_p("sobol_result.json"), "w") as f:
        json.dump(result, f, indent=1, default=float)
    print(f"[done] 図6枚 + sobol_result.json -> {OUT}")
    return result


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 256
    main(N)

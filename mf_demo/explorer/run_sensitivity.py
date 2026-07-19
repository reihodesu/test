"""explorer/run_sensitivity.py — 保存劣化 Sobol 感度解析の一括実行＋作図（v3, P1）

実行:  python -m mf_demo.explorer.run_sensitivity [N_main] [N_time]
出力:  mf_demo/output/explorer/sobol_*.png, sobol_result.json
"""
from __future__ import annotations

import os
import sys
import json
import numpy as np

from .config import XKEYS, VARSPEC, TIME_GRID, T_REF
from .sensitivity import (analyze_mode, time_evolution, convergence,
                          mode_fraction_over_time, imputation_robustness, RESP_MAIN)
from .degradation import responses_at
from . import plots

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "explorer")
os.makedirs(OUT, exist_ok=True)
def _p(n): return os.path.normpath(os.path.join(OUT, n))


def _trajectory(fine_t):
    x0 = {k: VARSPEC[k]["mean"] for k in XKEYS}
    ye, cli, ndc = [], [], []
    for t in fine_t:
        r = responses_at(x0, t)
        ye.append(r["y_end"]); cli.append(r["Cli"]); ndc.append(r["ndc"])
    ndc = np.array(ndc)
    cross = np.where(np.isfinite(ndc) & (ndc >= 1.0))[0]
    return {"times": list(fine_t), "y_end": ye, "Cli": cli,
            "t_switch": float(fine_t[cross[0]]) if len(cross) else None}


def main(N=4096, N_time=2048):
    print(f"=== 保存劣化 Sobol 感度解析 v3 (N_main={N}, N_time={N_time}, @ {T_REF:.0f}年) ===")

    print("[1] 主要感度: 3応答 × 2分布モード（2次指標込, 誤差棒つき）")
    res = {md: analyze_mode(md, T_REF, N, calc_second_order=True, invalid_policy="median")
           for md in ["design", "variation"]}
    for md in ["design", "variation"]:
        for rp in RESP_MAIN:
            d = res[md][rp]
            top = sorted(zip(XKEYS, d["ST"]), key=lambda z: -z[1])[:3]
            print(f"    [{rp}/{md}] 有効{d['valid_rate']:.2f} 除外{d['nan_rate']:.2f} "
                  f"ST上位={[f'{k}:{v:.2f}' for k,v in top]}")

    print("[2] 時間推移（B-4③, 3応答, 95%CI）")
    te = time_evolution("design", N_time, RESP_MAIN)

    print("[3] 支配モードの変遷（分母2種）")
    traj = _trajectory(list(np.linspace(0.1, 8.0, 30)))
    modefrac = mode_fraction_over_time("design", 1024, TIME_GRID)
    print(f"    公称モード遷移点 t≈{traj['t_switch']}年 / "
          f"拡散割合(全)={modefrac['diffusion_frac_all'][-1]:.2f} "
          f"(有効基準)={modefrac['diffusion_frac_valid'][-1]:.2f}")

    print("[4] 収束確認（Cli, N=128..4096）")
    conv = convergence("design", T_REF, "Cli")

    print("[5] 代入方針ロバスト性（Cli: median vs penalty）")
    rob = imputation_robustness("design", T_REF, N, "Cli")
    print(f"    top3安定={rob['top_stable']}  median={rob['rank_median'][:3]}  "
          f"penalty={rob['rank_penalty'][:3]}")

    print("[6] 作図")
    plots.fig_sensitivity_grid(res, _p("sobol_main.png"))
    plots.fig_time_evolution(te, _p("sobol_time_evolution.png"))
    plots.fig_mode_transition(traj, modefrac, _p("sobol_mode_transition.png"))
    plots.fig_network(res["design"]["y_end"], res["design"]["Cli"], _p("sobol_network.png"))
    plots.fig_convergence(conv, _p("sobol_convergence.png"))

    result = {"N": N, "N_time": N_time, "t_ref": T_REF, "keys": XKEYS,
              "sensitivity": res, "time_evolution": te, "trajectory": traj,
              "mode_fraction": modefrac, "convergence": conv,
              "imputation_robustness": {k: rob[k] for k in
                                        ["rank_median", "rank_penalty", "top_stable"]}}
    with open(_p("sobol_result.json"), "w") as f:
        json.dump(result, f, indent=1, default=float)
    print(f"[done] 図5枚 + sobol_result.json -> {OUT}")
    return result


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 4096
    Nt = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
    main(N, Nt)

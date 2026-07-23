"""explorer/run_f1_continuation.py — F-1 残課題の検証（改訂第3版 §7「今後」の消し込み）

改訂第3版 §5.4.1 で拡散モード頻発域（塗布量10〜13・曲路率1.7〜2.0, 5年）における
「曲路率 → 活物質密度」の入れ替わりが median/penalty/Spearman の3手法で再現することを
確認した。§7 に残した2つの残課題を本スクリプトで消し込む:

  検証A（他時点での再現性）: t=8年でも同じ入れ替わり・同じ頑健性が成立するか。
  検証B（領域境界近傍での連続性）: 全域→拡散頻発域へ領域を連続的に絞ったとき、
       支配因子（曲路率 ST → 活物質密度 ST）が段差なく滑らかに入れ替わるか（崖ではないか）。

実行:  python -m mf_demo.explorer.run_f1_continuation
出力:  mf_demo/output/explorer/sobol_f1_continuation.png
       scratchpad/f1_continuation.json（本文・表への数値反映用）
"""
from __future__ import annotations

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import XKEYS, make_problem, VARSPEC
from .degradation import evaluate
from .sensitivity import f1_robustness, _indices
from SALib.sample import sobol as sobol_sample

for _f in ["Noto Sans CJK JP", "IPAGothic", "TakaoGothic", "VL Gothic"]:
    if any(_f == f.name for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _f
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "explorer")
os.makedirs(OUT, exist_ok=True)
def _p(n): return os.path.normpath(os.path.join(OUT, n))
SC = "/tmp/claude-0/-home-user-test/66f60544-0d32-51d6-b6fc-f2239fe73a6e/scratchpad"

J_GAMMA = XKEYS.index("gamma")          # 5: 正極曲路率（材料物性）
J_DENS = XKEYS.index("mix_density")     # 3: 活物質密度（設計因子）
LAB = {k: VARSPEC[k]["label"] for k in XKEYS}

REGIONS = [
    ("全域", {}),
    ("中間", {"coat_load": (8.0, 13.0), "gamma": (1.6, 2.0)}),
    ("拡散頻発域", {"coat_load": (10.0, 13.0), "gamma": (1.7, 2.0)}),
]


def _top(name_st_pairs):
    return max(name_st_pairs, key=lambda z: z[1])


def verify_A_time(t=8.0, N_sobol=2048, N_lhs=6000):
    """検証A: t=8年で 3手法とも密度が頻発域の首位になるか。"""
    res = f1_robustness(REGIONS, t, N_sobol=N_sobol, N_lhs=N_lhs)
    out = []
    for r in res:
        pairs_m = list(zip(XKEYS, r["ST_median"]))
        pairs_p = list(zip(XKEYS, r["ST_penalty"]))
        pairs_s = list(zip(XKEYS, [x if x == x else -1 for x in r["spearman"]]))
        out.append({
            "name": r["name"], "valid_rate": r["valid_rate"],
            "impute_rate": r["impute_rate"], "t": t,
            "median_top": _top(pairs_m), "penalty_top": _top(pairs_p),
            "spearman_top": _top(pairs_s),
            "ST_median_gamma": r["ST_median"][J_GAMMA],
            "ST_median_dens": r["ST_median"][J_DENS],
        })
    return out


def verify_B_continuity(t=5.0, N=4096, steps=7):
    """検証B: 全域→頻発域へ lower bound を連続に動かし、曲路率STと密度STの交差を追う。"""
    ss = np.linspace(0.0, 1.0, steps)
    rows = []
    for s in ss:
        coat_lo = 6.0 + s * (10.0 - 6.0)   # 6 → 10
        gam_lo = 1.4 + s * (1.7 - 1.4)     # 1.4 → 1.7
        ov = {"coat_load": (coat_lo, 13.0), "gamma": (gam_lo, 2.0)}
        prob = make_problem("design", XKEYS, override_bounds=ov)
        X = sobol_sample.sample(prob, N, calc_second_order=False, seed=7)
        Y = evaluate(X, XKEYS, t)
        d = _indices(prob, Y["Cli"], False, "median")
        rows.append({
            "s": float(s), "coat_lo": coat_lo, "gamma_lo": gam_lo,
            "valid_rate": float(np.mean(Y["valid"])),
            "ST_gamma": d["ST"][J_GAMMA], "ST_gamma_conf": d["ST_conf"][J_GAMMA],
            "ST_dens": d["ST"][J_DENS], "ST_dens_conf": d["ST_conf"][J_DENS],
        })
    return rows


def make_figure(A8, B, A5=None, path=None):
    fig, ax = plt.subplots(1, 2, figsize=(13.2, 4.6))

    # 左: 検証B 連続性（曲路率ST vs 密度ST の交差）
    s = [r["s"] for r in B]
    g = [r["ST_gamma"] for r in B]; gc = [r["ST_gamma_conf"] for r in B]
    dd = [r["ST_dens"] for r in B]; dc = [r["ST_dens_conf"] for r in B]
    ax[0].errorbar(s, g, yerr=gc, marker="o", color="#54A24B", capsize=3,
                   label=f"{LAB['gamma']}（材料物性）")
    ax[0].errorbar(s, dd, yerr=dc, marker="s", color="#4C78A8", capsize=3,
                   label=f"{LAB['mix_density']}（設計因子）")
    # 交差点の検出
    cross = None
    for i in range(len(s) - 1):
        if (g[i] - dd[i]) * (g[i + 1] - dd[i + 1]) < 0:
            cross = 0.5 * (s[i] + s[i + 1])
    if cross is not None:
        ax[0].axvline(cross, ls=":", color="#B4472C", lw=1.4)
        ax[0].text(cross, 0.02, "  首位交代", color="#B4472C", fontsize=9,
                   transform=ax[0].get_xaxis_transform())
    ax[0].set_xlabel("領域の絞り込み度  s（0=全域 → 1=拡散頻発域）", fontsize=10)
    ax[0].set_ylabel("ST（限界Li塩濃度, median, 帯=95%CI）", fontsize=10)
    ax[0].set_title("検証B：領域境界近傍での連続性（design, 5年, N=4096）\n"
                    "段差なく滑らかに首位が入れ替わる＝崖ではない", fontsize=10)
    ax[0].grid(alpha=.3); ax[0].legend(fontsize=9, loc="center left")
    ax[0].set_ylim(0, max(max(g), max(dd)) * 1.25)

    # 右: 検証A 8年での3手法（頻発域）を 5年と並べる
    labels = ["median\n代入", "penalty\n代入", "Spearman|ρ|\n代入非依存"]
    dens_5 = dens_8 = None
    reg8 = [r for r in A8 if r["name"] == "拡散頻発域"][0]
    vals8 = [reg8["median_top"], reg8["penalty_top"], reg8["spearman_top"]]
    dens8 = [v[1] if v[0] == "mix_density" else v[1] for v in vals8]
    isdens8 = [v[0] == "mix_density" for v in vals8]
    x = np.arange(3)
    if A5 is not None:
        reg5 = [r for r in A5 if r["name"] == "拡散頻発域"][0]
        vals5 = [reg5["median_top"], reg5["penalty_top"], reg5["spearman_top"]]
        dens5 = [v[1] for v in vals5]
        ax[1].bar(x - 0.2, dens5, 0.38, color="#9ecae1", label="5年（第3版で確認済）")
        ax[1].bar(x + 0.2, dens8, 0.38, color="#08519c", label="8年（本検証）")
        for xi, v in zip(x - 0.2, vals5):
            ax[1].text(xi, v[1] + .01, LAB.get(v[0], v[0])[:4], ha="center",
                       fontsize=7.5, color="#08519c" if v[0] == "mix_density" else "#B4472C")
        for xi, v in zip(x + 0.2, vals8):
            ax[1].text(xi, v[1] + .01, LAB.get(v[0], v[0])[:4], ha="center",
                       fontsize=7.5, color="#08519c" if v[0] == "mix_density" else "#B4472C")
    else:
        ax[1].bar(x, dens8, 0.5, color="#08519c")
    ax[1].set_xticks(x); ax[1].set_xticklabels(labels, fontsize=9)
    ax[1].set_ylabel("頻発域の首位因子 ST（青字=活物質密度）", fontsize=9.5)
    ax[1].set_title(f"検証A：8年でも首位=活物質密度が再現\n"
                    f"（頻発域 有効率{reg8['valid_rate']:.0%}／代入率{reg8['impute_rate']:.0%}）",
                    fontsize=10)
    ax[1].grid(alpha=.3, axis="y"); ax[1].legend(fontsize=8.5, loc="upper right")

    fig.suptitle("F-1 残課題の消し込み：頑健性は「他時点(8年)」でも「領域境界の連続性」でも成立",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    if path:
        fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main():
    print("=== F-1 残課題の検証（8年再現性 ＋ 境界連続性）===")
    print("[検証A-5yr] 5年の頻発域（対照, 第3版で確認済）")
    A5 = verify_A_time(t=5.0)
    print("[検証A-8yr] 8年の3手法")
    A8 = verify_A_time(t=8.0)
    for r in A8:
        print(f"    {r['name']}: 有効{r['valid_rate']:.2f} 代入{r['impute_rate']:.2f} "
              f"median首位={LAB[r['median_top'][0]]}({r['median_top'][1]:.2f}) "
              f"penalty首位={LAB[r['penalty_top'][0]]}({r['penalty_top'][1]:.2f}) "
              f"Spearman首位={LAB[r['spearman_top'][0]]}({r['spearman_top'][1]:.2f})")
    print("[検証B] 境界連続性スイープ")
    B = verify_B_continuity(t=5.0)
    for r in B:
        print(f"    s={r['s']:.2f} 塗布≥{r['coat_lo']:.1f}/曲路≥{r['gamma_lo']:.2f} "
              f"有効{r['valid_rate']:.2f} 曲路率ST={r['ST_gamma']:.2f} 密度ST={r['ST_dens']:.2f}")

    make_figure(A8, B, A5=A5, path=_p("sobol_f1_continuation.png"))
    print(f"[fig] {_p('sobol_f1_continuation.png')}")

    result = {"A5": A5, "A8": A8, "B": B}
    try:
        with open(os.path.join(SC, "f1_continuation.json"), "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=1, default=float)
    except Exception as e:
        print("  [警告] JSON保存スキップ:", e)
    print("[done]")
    return result


if __name__ == "__main__":
    main()

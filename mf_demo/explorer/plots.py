"""explorer/plots.py — 保存劣化 Sobol 感度の可視化（報告書準拠 v2, 図中は日本語）

主応答 2 つ（放電後電圧 y_end / 限界Li塩濃度 Cli）で支配因子が異なること、
保存時間で支配因子・支配モードが変遷することを主眼に置く。
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from .config import XKEYS, VARSPEC, CATEGORY, RESPONSES, C_LI_DESIGN

for _f in ["IPAGothic", "Noto Sans CJK JP", "TakaoGothic", "VL Gothic"]:
    if any(_f == f.name for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _f
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

SHORT = {k: VARSPEC[k]["label"] for k in XKEYS}
CAT_COLOR = {"設計因子": "#4C78A8", "材料物性": "#54A24B", "使用条件": "#E45756"}
C_S1, C_ST = "#4C78A8", "#F58518"
RLABEL = {"y_end": "放電後電圧 y_end", "Cli": "限界Li塩濃度 Cli"}
MODE_JP = {"design": "design（設計探索・一様）", "variation": "variation（ばらつき・3σ正規）"}


def fig_sensitivity_grid(res, t_ref, path):
    """2応答 × 2分布モード の S1/ST 棒グラフ（4パネル）。"""
    resps, modes = ["y_end", "Cli"], ["design", "variation"]
    x = np.arange(len(XKEYS)); w = 0.38
    fig, axes = plt.subplots(2, 2, figsize=(15, 8.5), sharey=True)
    for i, rp in enumerate(resps):
        for j, md in enumerate(modes):
            ax = axes[i, j]; d = res[rp][md]
            ax.bar(x - w/2, d["S1"], w, yerr=d["S1_conf"], color=C_S1,
                   label="S1（主効果）", capsize=2)
            ax.bar(x + w/2, d["ST"], w, yerr=d["ST_conf"], color=C_ST,
                   label="ST（総合効果）", capsize=2)
            ax.set_xticks(x); ax.set_xticklabels([SHORT[k] for k in XKEYS], fontsize=7.5)
            ax.set_ylim(0, 1.05); ax.grid(axis="y", alpha=.3)
            ax.set_title(f"{RLABEL[rp]} / {MODE_JP[md]}  除外率{d['nan_rate']:.0%}",
                         fontsize=9.5)
            if j == 0:
                ax.set_ylabel(f"{RESPONSES[rp]['mode']}\nSobol 指標", fontsize=9)
            if i == 0 and j == 0:
                ax.legend(fontsize=8, loc="upper right")
    fig.suptitle(f"Sobol 感度: 応答ごとに支配因子が異なる（@ {t_ref:.0f}年 / DC_v5 実式直接MC）\n"
                 "放電後電圧←抵抗・温度（抵抗劣化モード） ／ 限界Li塩濃度←塗布量・曲路率・拡散係数（拡散劣化モード, 報告書S28と一致）",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_time_evolution(te_yend, te_cli, path):
    """感度指標の時間推移（B-4③）: 応答ごと ST vs t。支配因子の変遷。"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), sharey=True)
    cols = plt.cm.tab10(np.linspace(0, 1, 10))
    for ax, te in zip(axes, [te_yend, te_cli]):
        ST = np.array(te["ST"])
        for j, k in enumerate(XKEYS):
            ax.plot(te["times"], ST[:, j], marker="o", ms=4, lw=1.9,
                    color=cols[j], label=SHORT[k].replace("\n", " "))
        ax.set_xlabel("保存時点 t [year]", fontsize=10)
        ax.grid(alpha=.3); ax.set_ylim(0, 1.05)
        ax.set_title(f"{RLABEL[te['response']]}（{te['mode']}）", fontsize=10.5)
    axes[0].set_ylabel("ST（総合効果）", fontsize=11)
    axes[1].legend(fontsize=7.5, ncol=2, loc="upper right")
    fig.suptitle("感度指標の時間推移：放電後電圧は温度・抵抗が時間とともに支配拡大／"
                 "限界Li塩濃度は塗布量・曲路率が一貫支配（B-4③）", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_mode_transition(traj, modefrac, path):
    """支配モードの変遷（本テーマの核）: 公称軌跡＋母集団のモード割合。"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    # (左) 公称点の y_end / Cli 軌跡と閾値交差 → モード遷移
    ax = axes[0]; t = traj["times"]
    ax.plot(t, traj["y_end"], "-o", color="#1f77b4", label="放電後電圧 y_end [V]")
    ax.axhline(RESPONSES["y_end"]["thr"], color="#1f77b4", ls=":", lw=1.2)
    ax.set_xlabel("保存時点 t [year]"); ax.set_ylabel("放電後電圧 [V]", color="#1f77b4")
    ax.tick_params(axis="y", labelcolor="#1f77b4")
    ax2 = ax.twinx()
    ax2.plot(t, traj["Cli"], "-s", color="#d62728", label="限界Li塩濃度 Cli [M]")
    ax2.axhline(RESPONSES["Cli"]["thr"], color="#d62728", ls=":", lw=1.2)
    ax2.set_ylabel("限界Li塩濃度 [mol/L]", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")
    # モード遷移点（ndc=1 交差）
    tsw = traj.get("t_switch")
    if tsw:
        ax.axvline(tsw, color="gray", ls="--", lw=1.5)
        ax.text(tsw, ax.get_ylim()[0], f" モード遷移\n t≈{tsw:.1f}年", fontsize=9,
                va="bottom", color="#555")
    ax.set_title("公称設計の軌跡：抵抗劣化モード → 限界Li塩濃度が設計budgetを超え拡散劣化モードへ",
                 fontsize=10)
    # (右) 母集団の 拡散モード割合 / 成立率 vs t
    ax = axes[1]; mt = modefrac["times"]
    ax.plot(mt, np.array(modefrac["diffusion_frac"]) * 100, "-o", color="#d62728",
            label="拡散劣化モードの個体割合")
    ax.plot(mt, np.array(modefrac["ok_frac"]) * 100, "-^", color="#2ca02c",
            label="設計成立率（y>=2.5 & Cli<=1.4）")
    ax.plot(mt, np.array(modefrac["valid_frac"]) * 100, "-x", color="#888",
            label="有効率（300W維持可）")
    ax.set_xlabel("保存時点 t [year]"); ax.set_ylabel("割合 [%]")
    ax.set_ylim(0, 100); ax.grid(alpha=.3); ax.legend(fontsize=8.5)
    ax.set_title("母集団の支配モード変遷：保存が進むと拡散劣化モードが増え成立率が低下",
                 fontsize=10)
    fig.suptitle("保存劣化過程での支配因子・支配モードの変遷（本検討の核心）", fontsize=12.5)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def _network(ax, ST, S2, title):
    n = len(XKEYS)
    ang = np.linspace(np.pi/2, np.pi/2 + 2*np.pi, n, endpoint=False)
    pos = np.c_[np.cos(ang), np.sin(ang)]
    S2 = np.array(S2); s2max = max(np.nanmax(np.abs(S2)) if np.isfinite(S2).any() else 1.0, 1e-9)
    for a in range(n):
        for b in range(a + 1, n):
            v = S2[a, b]
            if not np.isfinite(v) or v <= 0.01:
                continue
            ax.plot(*zip(pos[a], pos[b]), color="#555", lw=0.4 + 7.0 * (v / s2max),
                    alpha=.55, zorder=1, solid_capstyle="round")
            if v / s2max > 0.45:
                mid = (pos[a] + pos[b]) / 2
                ax.text(*mid, f"{v:.2f}", fontsize=7.5, ha="center", va="center",
                        zorder=4, bbox=dict(fc="white", ec="none", alpha=.75, pad=1))
    stmax = max(np.max(ST), 1e-9)
    for i in range(n):
        rad = 0.05 + 0.16 * (ST[i] / stmax)
        ax.add_patch(Circle(pos[i], rad, fc=CAT_COLOR[CATEGORY[XKEYS[i]]],
                            ec="#33405e", lw=1.0, zorder=2, alpha=.9))
        ax.text(*(pos[i] * (1 + rad + 0.22)), f"{SHORT[XKEYS[i]]}\nST={ST[i]:.2f}",
                fontsize=7.6, ha="center", va="center", zorder=5)
    ax.set_xlim(-1.8, 1.8); ax.set_ylim(-1.7, 1.7)
    ax.set_aspect("equal"); ax.axis("off"); ax.set_title(title, fontsize=10.5)


def fig_network(res_yend, res_cli, path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.2))
    _network(axes[0], np.array(res_yend["ST"]), res_yend["S2"], RLABEL["y_end"] + "（design）")
    _network(axes[1], np.array(res_cli["ST"]), res_cli["S2"], RLABEL["Cli"] + "（design）")
    handles = [plt.Line2D([0], [0], marker="o", ls="", ms=10, mfc=CAT_COLOR[c],
                          mec="#33405e", label=c) for c in CAT_COLOR]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9,
               frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("交互作用ネットワーク：ノード径＝ST／線＝2次Sobol指標 S2（並行座標が苦手な交互作用を補完）",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_conditional(rc_global, rc_region, region_desc, response, t_ref, path):
    x = np.arange(len(XKEYS)); w = 0.38
    fig, ax = plt.subplots(figsize=(11, 4.6))
    for i, (rc, lab, c) in enumerate([(rc_global, "全域", "#bdbdbd"),
                                      (rc_region, f"領域: {region_desc}", "#d62728")]):
        ax.bar(x + (i - .5) * w, rc["ST"], w, color=c, yerr=rc["ST_conf"],
               capsize=2, label=lab)
    ax.set_xticks(x); ax.set_xticklabels([SHORT[k] for k in XKEYS], fontsize=8)
    ax.grid(axis="y", alpha=.3); ax.set_ylim(0, 1.05)
    ax.set_ylabel("ST（総合効果）", fontsize=10); ax.legend(fontsize=9)
    ax.set_title(f"領域条件付き感度（{RLABEL[response]} @ {t_ref:.0f}年, design）："
                 f"有効率 {rc_global['valid_rate']:.0%} → {rc_region['valid_rate']:.0%}",
                 fontsize=10.5)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_convergence(rows, response, t_ref, path):
    Ns = [r["n_samples"] for r in rows]
    ST = np.array([r["ST"] for r in rows]); CF = np.array([r["ST_conf"] for r in rows])
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    cols = plt.cm.tab10(np.linspace(0, 1, 10))
    for i, k in enumerate(XKEYS):
        ax.errorbar(Ns, ST[:, i], yerr=CF[:, i], marker="o", ms=4, capsize=3,
                    lw=1.6, color=cols[i], label=SHORT[k].replace("\n", " "))
    ax.set_xscale("log")
    ax.set_xlabel("直接評価したサンプル数（対数）"); ax.set_ylabel("ST（総合効果）")
    ax.set_title(f"Sobol 指標の収束と 95% 信頼区間（{RLABEL[response]} @ {t_ref:.0f}年, design）",
                 fontsize=10.5)
    ax.grid(alpha=.3); ax.legend(ncol=2, fontsize=7.5)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)

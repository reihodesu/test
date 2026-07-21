"""explorer/plots.py — 保存劣化 Sobol 感度の可視化（v3, 数値信頼性強化, 図中は日本語）

各図に「分布モード / 評価時点 / N（実評価点数）/ 無効サンプル処理方針」を明記する。
棒グラフには 95%信頼区間を誤差棒で表示。ネットワークは S2 の有意性で描き分ける。
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from .config import XKEYS, VARSPEC, CATEGORY, RESPONSES

for _f in ["Noto Sans CJK JP", "IPAGothic", "TakaoGothic", "VL Gothic"]:
    if any(_f == f.name for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _f
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

SHORT = {k: VARSPEC[k]["label"] for k in XKEYS}
CAT_COLOR = {"設計因子": "#4C78A8", "材料物性": "#54A24B", "使用条件": "#E45756"}
C_S1, C_ST = "#4C78A8", "#F58518"
RLABEL = {"y_end": "放電後電圧 y_end", "Cli": "限界Li塩濃度 Cli", "feasible": "300W維持可否"}
MODE_JP = {"design": "design(設計探索・一様)", "variation": "variation(ばらつき・3σ正規)"}


def _meta(d):
    """図注用メタ文字列: モード / 時点 / N / policy / 有効率。"""
    pol = d.get("invalid_policy", "median")
    poltxt = "" if d["response"] == "feasible" else f" / 代入={pol}"
    return (f"{MODE_JP.get(d['mode'], d['mode'])} / t={d['t']:.0f}年 / "
            f"N={d['N']}({d['n_samples']:,}点){poltxt} / 有効率{d['valid_rate']:.0%}")


def fig_sensitivity_grid(res, path):
    """3応答 × 2分布モード の S1/ST 棒グラフ（誤差棒=95%CI）。"""
    resps, modes = ["y_end", "Cli", "feasible"], ["design", "variation"]
    x = np.arange(len(XKEYS)); w = 0.38
    fig, axes = plt.subplots(3, 2, figsize=(15, 11), sharey=True)
    for i, rp in enumerate(resps):
        for j, md in enumerate(modes):
            ax = axes[i, j]; d = res[md][rp]
            ax.bar(x - w/2, d["S1"], w, yerr=d["S1_conf"], color=C_S1,
                   label="S1（主効果）", capsize=2, error_kw={"lw": 0.8})
            ax.bar(x + w/2, d["ST"], w, yerr=d["ST_conf"], color=C_ST,
                   label="ST（総合効果）", capsize=2, error_kw={"lw": 0.8})
            ax.set_xticks(x); ax.set_xticklabels([SHORT[k] for k in XKEYS], fontsize=7)
            ax.set_ylim(0, 1.08); ax.grid(axis="y", alpha=.3)
            ax.set_title(f"{RLABEL[rp]}／{_meta(d)}", fontsize=8.5)
            if j == 0:
                ax.set_ylabel(f"{RESPONSES[rp]['mode']}\nSobol 指標", fontsize=9)
            if i == 0 and j == 0:
                ax.legend(fontsize=8, loc="upper right")
    fig.suptitle("Sobol 感度（誤差棒=95%信頼区間）：応答ごとに支配因子が異なる／二値応答=電力維持の成否\n"
                 "放電後電圧←抵抗・塗布量・温度 ／ 限界Li塩濃度←曲路率・塗布量・拡散 ／ 維持可否←塗布量・温度",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_time_evolution(te, path):
    """感度指標の時間推移（B-4③）: 応答別 ST vs t（薄い95%CI帯つき）。"""
    resps = list(te["by_response"].keys())
    fig, axes = plt.subplots(1, len(resps), figsize=(5.2 * len(resps), 5.2), sharey=True)
    if len(resps) == 1:
        axes = [axes]
    cols = plt.cm.tab10(np.linspace(0, 1, 10))
    for ax, rp in zip(axes, resps):
        ST = np.array(te["by_response"][rp]["ST"])
        CF = np.array(te["by_response"][rp]["ST_conf"])
        for j, k in enumerate(XKEYS):
            ax.plot(te["times"], ST[:, j], marker="o", ms=3.5, lw=1.8, color=cols[j],
                    label=SHORT[k].replace("\n", " "))
            ax.fill_between(te["times"], ST[:, j] - CF[:, j], ST[:, j] + CF[:, j],
                            color=cols[j], alpha=0.10)
        ax.set_xlabel("保存時点 t [year]", fontsize=10); ax.grid(alpha=.3)
        ax.set_ylim(0, 1.08); ax.set_title(RLABEL[rp], fontsize=10.5)
    axes[0].set_ylabel("ST（総合効果, 帯=95%CI）", fontsize=10)
    axes[-1].legend(fontsize=7.5, ncol=2, loc="upper right")
    fig.suptitle(f"感度指標の時間推移（{MODE_JP[te['mode']]} / N={te['N']} / 代入={te['invalid_policy']}）："
                 "放電後電圧は温度・抵抗の寄与が時間で拡大／限界Li塩濃度は曲路率・塗布量が一貫支配",
                 fontsize=11.5)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_mode_transition(traj, modefrac, path):
    """支配モードの変遷: 公称軌跡＋母集団のモード割合（分母2種を明示）。"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.3))
    ax = axes[0]; t = traj["times"]
    ax.plot(t, traj["y_end"], "-o", ms=3, color="#1f77b4", label="放電後電圧 y_end [V]")
    ax.axhline(RESPONSES["y_end"]["thr"], color="#1f77b4", ls=":", lw=1.2)
    ax.set_xlabel("保存時点 t [year]"); ax.set_ylabel("放電後電圧 [V]", color="#1f77b4")
    ax.tick_params(axis="y", labelcolor="#1f77b4")
    ax2 = ax.twinx()
    ax2.plot(t, traj["Cli"], "-s", ms=3, color="#d62728", label="限界Li塩濃度 Cli [M]")
    ax2.axhline(RESPONSES["Cli"]["thr"], color="#d62728", ls=":", lw=1.2)
    ax2.set_ylabel("限界Li塩濃度 [mol/L]", color="#d62728"); ax2.tick_params(axis="y", labelcolor="#d62728")
    if traj.get("t_switch"):
        ax.axvline(traj["t_switch"], color="gray", ls="--", lw=1.5)
        ax.text(traj["t_switch"], ax.get_ylim()[0], f" モード遷移\n t≈{traj['t_switch']:.1f}年",
                fontsize=9, va="bottom", color="#555")
    ax.set_title("公称設計の軌跡（不確かさ伝播ではなく単一設計の代数的帰結）：抵抗劣化→拡散劣化", fontsize=9.5)
    # 右: モード割合（分母2種）
    ax = axes[1]; mt = modefrac["times"]
    ax.plot(mt, np.array(modefrac["diffusion_frac_all"]) * 100, "-o", color="#d62728",
            label="拡散モード割合（分母=全サンプル）")
    ax.plot(mt, np.array(modefrac["diffusion_frac_valid"]) * 100, "--o", color="#ff9896",
            label="拡散モード割合（分母=有効サンプルのみ）")
    ax.plot(mt, np.array(modefrac["ok_frac"]) * 100, "-^", color="#2ca02c",
            label="設計成立率（分母=全サンプル）")
    ax.plot(mt, np.array(modefrac["valid_frac"]) * 100, "-x", color="#888",
            label="有効率=300W維持可（分母=全サンプル）")
    ax.set_xlabel("保存時点 t [year]"); ax.set_ylabel("割合 [%]")
    ax.set_ylim(0, 100); ax.grid(alpha=.3); ax.legend(fontsize=8)
    ax.set_title(f"母集団の支配モード変遷（{MODE_JP[modefrac['mode']]} / N={modefrac['N']}／{modefrac['n_samples']:,}点）",
                 fontsize=9.5)
    fig.suptitle("保存劣化過程での支配モードの変遷（不確かさ伝播の成果／分母を明示）", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def _network(ax, ST, S2, S2_conf, title):
    """S2 有意性で描き分け: CI が 0 を跨がない=実線, 跨ぐ=破線・淡色。"""
    n = len(XKEYS)
    ang = np.linspace(np.pi/2, np.pi/2 + 2*np.pi, n, endpoint=False)
    pos = np.c_[np.cos(ang), np.sin(ang)]
    S2 = np.array(S2); S2c = np.array(S2_conf)
    sig = S2 - S2c > 0            # 95%CI 下限が 0 超 → 有意
    s2max = max(np.nanmax(np.abs(S2[np.isfinite(S2)])) if np.isfinite(S2).any() else 1.0, 1e-9)
    for a in range(n):
        for b in range(a + 1, n):
            v = S2[a, b]
            if not np.isfinite(v) or v <= 0.01:
                continue
            is_sig = bool(sig[a, b])
            ax.plot(*zip(pos[a], pos[b]), color="#555" if is_sig else "#bbb",
                    lw=(0.4 + 7.0 * (v / s2max)) if is_sig else 1.0,
                    ls="-" if is_sig else "--", alpha=.6 if is_sig else .35,
                    zorder=1 if is_sig else 0.5, solid_capstyle="round")
            if is_sig and v / s2max > 0.45:
                mid = (pos[a] + pos[b]) / 2
                ax.text(*mid, f"{v:.2f}", fontsize=7.5, ha="center", va="center",
                        zorder=4, bbox=dict(fc="white", ec="none", alpha=.75, pad=1))
    stmax = max(np.max(ST), 1e-9)
    for i in range(n):
        rad = 0.05 + 0.16 * (ST[i] / stmax)
        ax.add_patch(Circle(pos[i], rad, fc=CAT_COLOR[CATEGORY[XKEYS[i]]],
                            ec="#33405e", lw=1.0, zorder=2, alpha=.9))
        ax.text(*(pos[i] * (1 + rad + 0.22)), f"{SHORT[XKEYS[i]]}\nST={ST[i]:.2f}",
                fontsize=7.4, ha="center", va="center", zorder=5)
    ax.set_xlim(-1.8, 1.8); ax.set_ylim(-1.7, 1.7)
    ax.set_aspect("equal"); ax.axis("off"); ax.set_title(title, fontsize=9.5)


def fig_network(res_y, res_c, path):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4))
    _network(axes[0], np.array(res_y["ST"]), res_y["S2"], res_y["S2_conf"],
             RLABEL["y_end"] + "\n" + _meta(res_y))
    _network(axes[1], np.array(res_c["ST"]), res_c["S2"], res_c["S2_conf"],
             RLABEL["Cli"] + "\n" + _meta(res_c))
    handles = [plt.Line2D([0], [0], marker="o", ls="", ms=10, mfc=CAT_COLOR[c],
                          mec="#33405e", label=c) for c in CAT_COLOR]
    handles += [plt.Line2D([0], [0], color="#555", lw=3, label="S2 有意（95%CI>0）"),
                plt.Line2D([0], [0], color="#bbb", lw=1.2, ls="--", label="S2 非有意（CIが0を跨ぐ）")]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=8.5,
               frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("交互作用ネットワーク：ノード径＝ST／線＝2次Sobol指標 S2（有意なもののみ実線・太線）",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_f1_robustness(res, path):
    """F-1: 3手法（median/penalty代入 Sobol・代入非依存 Spearman）で
    領域を絞ると 曲路率→活物質密度 の入れ替わりが再現するかを示す。"""
    methods = [("ST_median", "Sobol ST（median代入）"),
               ("ST_penalty", "Sobol ST（penalty代入=worst-case）"),
               ("spearman", "Spearman |ρ|（有効サンプルのみ・代入非依存）")]
    names = [r["name"] for r in res]
    x = np.arange(len(XKEYS)); nb = len(res); w = 0.8 / nb
    shades = plt.cm.Reds(np.linspace(0.35, 0.85, nb))
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.4))
    for ax, (key, title) in zip(axes, methods):
        for i, r in enumerate(res):
            lab = f"{names[i]}（有効{r['valid_rate']:.0%}/代入{r['impute_rate']:.0%}）"
            ax.bar(x + (i - (nb - 1) / 2) * w, r[key], w, color=shades[i], label=lab)
        ax.set_xticks(x)
        ax.set_xticklabels([SHORT[k].splitlines()[0] for k in XKEYS], fontsize=7.5, rotation=30, ha="right")
        for tick, k in zip(ax.get_xticklabels(), XKEYS):
            tick.set_color(CAT_COLOR[CATEGORY[k]])
        ax.grid(axis="y", alpha=.3)
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=7.5, loc="upper right")
    axes[0].set_ylabel("感度指標（手法ごとにスケール異なる）", fontsize=9.5)
    handles = [plt.Line2D([0], [0], marker="s", ls="", ms=9, mfc=CAT_COLOR[c],
                          mec="none", label=c) for c in CAT_COLOR]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9, frameon=False,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("F-1 §5.4 ロバスト性検証（限界Li塩濃度, design, 5年）：全域→拡散頻発域で 曲路率(材料物性)→活物質密度(設計因子) の入れ替わりが3手法とも再現\n"
                 "頻発域は有効率98%（代入率2%）＝代入の影響が最小の領域。因子ラベル色＝分類（青=設計因子/緑=材料物性/赤=使用条件）",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0.03, 1, 0.92])
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_mode_stacked(modefrac, path):
    """E-6: 抵抗劣化/拡散劣化/300W維持不可 の3区分・合計100%積み上げ面グラフ。

    全サンプル基準なので分母の議論が不要。個体がどこへ流れたかが一目で分かる。
    """
    t = np.array(modefrac["times"])
    valid = np.array(modefrac["valid_frac"])
    diff = np.array(modefrac["diffusion_frac_all"])   # 全サンプル基準
    infeasible = (1.0 - valid) * 100
    diffusion = diff * 100
    resistance = (valid - diff) * 100                 # 有効 かつ 非拡散
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    ax.stackplot(t, resistance, diffusion, infeasible,
                 labels=["抵抗劣化モード（有効・非拡散）", "拡散劣化モード（有効・拡散）",
                         "300W維持不可（無効）"],
                 colors=["#4C78A8", "#d62728", "#999999"], alpha=0.85)
    ax.set_xlabel("保存時点 t [year]"); ax.set_ylabel("母集団に占める割合 [%]（合計100%）")
    ax.set_ylim(0, 100); ax.set_xlim(t.min(), t.max())
    ax.legend(loc="lower center", fontsize=9, ncol=1, framealpha=0.9)
    ax.set_title(f"母集団の3区分推移（全サンプル基準・合計100% / {MODE_JP[modefrac['mode']]} / N={modefrac['N']}）：\n"
                 "維持不可(灰)が16→39%へ増加し両モードを希釈。拡散劣化(赤)は47%を頂点に減少に転じる",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_conditional_staged(staged, response, path):
    """領域条件付き感度（段階的に絞った領域）。因子を分類色でラベル、領域を濃淡で。"""
    x = np.arange(len(XKEYS)); nb = len(staged); w = 0.8 / nb
    fig, ax = plt.subplots(figsize=(12.5, 5.2))
    shades = plt.cm.Reds(np.linspace(0.35, 0.85, nb))
    for i, s in enumerate(staged):
        lab = (f"{s['name']}（{s['n_samples']:,}点/有効{s['valid_rate']:.0%}"
               f"/代入{s.get('nan_rate', 0):.0%}）")
        ax.bar(x + (i - (nb - 1) / 2) * w, s["ST"], w, yerr=s["ST_conf"],
               color=shades[i], capsize=2, error_kw={"lw": 0.7}, label=lab)
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT[k] for k in XKEYS], fontsize=8.5)
    for tick, k in zip(ax.get_xticklabels(), XKEYS):
        tick.set_color(CAT_COLOR[CATEGORY[k]])       # 因子ラベルを分類色に
    ax.set_ylim(0, 1.05); ax.grid(axis="y", alpha=.3)
    ax.set_ylabel("ST（総合効果, 誤差棒=95%CI）", fontsize=10)
    ax.legend(fontsize=8.5, loc="upper right", title="絞り込み領域（全域→頻発域）")
    handles = [plt.Line2D([0], [0], marker="s", ls="", ms=9, mfc=CAT_COLOR[c],
                          mec="none", label=c) for c in CAT_COLOR]
    leg2 = ax.legend(handles=handles, fontsize=8, loc="upper left", title="因子分類（ラベル色）")
    ax.add_artist(leg2)
    ax.legend(fontsize=8, loc="upper right", title="絞り込み領域")
    ax.set_title(f"領域条件付き感度（{RLABEL[response]} / design / t={staged[0]['t']:.0f}年）："
                 "全域では材料因子=曲路率が支配 → 拡散モード頻発域では制御可能な設計因子=活物質密度が浮上",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)


def fig_convergence(conv, path):
    rows = conv["rows"]
    Ns = [r["n_samples"] for r in rows]
    ST = np.array([r["ST"] for r in rows]); CF = np.array([r["ST_conf"] for r in rows])
    fig, ax = plt.subplots(figsize=(8, 4.8))
    cols = plt.cm.tab10(np.linspace(0, 1, 10))
    for i, k in enumerate(XKEYS):
        ax.errorbar(Ns, ST[:, i], yerr=CF[:, i], marker="o", ms=4, capsize=3,
                    lw=1.6, color=cols[i], label=SHORT[k].replace("\n", " "))
    ax.set_xscale("log")
    ax.set_xlabel("実際に評価した点数（対数）", fontsize=10)
    ax.set_ylabel("ST（総合効果, 誤差棒=95%CI）", fontsize=10)
    ax.set_title(f"Sobol 指標の収束（{RLABEL[conv['response']]} / {MODE_JP[conv['mode']]} / t={conv['t']:.0f}年）："
                 "点数を増やすと信頼区間が縮小し順位が確定", fontsize=10)
    ax.grid(alpha=.3); ax.legend(ncol=2, fontsize=8)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)

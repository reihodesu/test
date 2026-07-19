"""explorer/viz_explorer.py — ①②③ 可視化（並行座標・コンター・アーキテクチャ, v2）

報告書 NCR2170JB Step2 準拠:
  - contour_2axis : セル抵抗 × 正極塗布量 の制約つき2軸コンター
                    （放電後電圧>=2.5V ／ 限界Li塩濃度<=1.4M で OK/NG）③
  - parallel_coordinates : 感度スクリーニングを軸選択へ自動反映した擬似並行座標 ①
  - architecture_diagram : 感度→絞り込み→並行座標→コンターの設計探索アーキテクチャ ③
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from .config import XKEYS, VARSPEC, RESPONSES
from .degradation import responses_at
from .screening import Y_MIN, CLI_MAX, T_REF

for _f in ["IPAGothic", "Noto Sans CJK JP", "TakaoGothic", "VL Gothic"]:
    if any(_f == f.name for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _f
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

SHORT = {k: VARSPEC[k]["label"] for k in XKEYS}


# ---------------------------------------------------------------------------
# ① 擬似並行座標（感度スクリーニング自動反映）
# ---------------------------------------------------------------------------
def parallel_coordinates(df, active_keys, ST, path, brush=None, t_ref=T_REF,
                         color_col="y_end"):
    st = ST if isinstance(ST, dict) else dict(zip(XKEYS, ST))
    inactive = [k for k in XKEYS if k not in active_keys]
    order = sorted(active_keys, key=lambda k: -st[k]) + \
        sorted(inactive, key=lambda k: -st[k])
    nax = len(order)
    lo = np.array([VARSPEC[k]["design"][0] for k in order])
    hi = np.array([VARSPEC[k]["design"][1] for k in order])
    Vn = (df[order].to_numpy() - lo) / (hi - lo)

    if brush:
        sel = np.ones(len(df), bool)
        for k, (a, b) in brush.items():
            sel &= (df[k] >= a) & (df[k] <= b)
    else:
        sel = df["ok"].to_numpy()

    fig, ax = plt.subplots(figsize=(13, 6))
    xax = np.arange(nax)
    for i in np.where(~sel)[0]:
        ax.plot(xax, Vn[i], color="#cccccc", lw=0.4, alpha=0.35, zorder=1)
    cval = df[color_col].to_numpy()
    cmap = plt.cm.viridis
    fin = np.isfinite(cval)
    cmin, cmax = (np.nanmin(cval[fin]), np.nanmax(cval[fin])) if fin.any() else (0, 1)
    for i in np.where(sel)[0]:
        c = cmap((cval[i] - cmin) / (cmax - cmin + 1e-9)) if np.isfinite(cval[i]) else "#999"
        ax.plot(xax, Vn[i], color=c, lw=0.8, alpha=0.6, zorder=2)

    for j, k in enumerate(order):
        act = k in active_keys
        ax.axvline(j, color="#333" if act else "#bbb", lw=2.2 if act else 1.0, zorder=3)
        col = "#1a1a1a" if act else "#999"
        ax.text(j, 1.06, f"{SHORT[k]}\nST={st[k]:.2f}{'  ★能動' if act else ''}",
                ha="center", va="bottom", fontsize=8.5, color=col,
                fontweight="bold" if act else "normal")
        ax.text(j, -0.04, f"{lo[j]:.3g}", ha="center", va="top", fontsize=7, color=col)
        ax.text(j, 1.005, f"{hi[j]:.3g}", ha="center", va="bottom", fontsize=7, color=col)

    ax.set_xlim(-0.5, nax - 0.5); ax.set_ylim(-0.08, 1.18)
    ax.set_yticks([]); ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(cmin, cmax))
    fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.01).set_label(
        RESPONSES.get(color_col, {}).get("label", color_col) + f" @ {t_ref:.0f}年", fontsize=9)
    sub = "設計成立個体" if not brush else "ブラッシング選択個体"
    ax.set_title("擬似 並行座標プロット：感度スクリーニングを軸選択へ自動反映"
                 f"（★能動軸＝ST上位を左に集約・強調 / {sub} {int(sel.sum())}個体を強調）\n"
                 "並行座標が苦手な交互作用は別途ネットワーク図で補完（②）", fontsize=11)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)


# ---------------------------------------------------------------------------
# ③ 制約つき2軸コンター（セル抵抗 × 正極塗布量, 報告書 NCR2170JB Step2）
# ---------------------------------------------------------------------------
def contour_2axis(path, xkey="R0_init", ykey="coat_load", nominal=None, ng=60,
                  t_ref=T_REF):
    if nominal is None:
        nominal = {k: VARSPEC[k]["mean"] for k in XKEYS}
    xr = np.linspace(*VARSPEC[xkey]["design"], ng)
    yr = np.linspace(*VARSPEC[ykey]["design"], ng)
    XX, YY = np.meshgrid(xr, yr)
    YEND = np.full_like(XX, np.nan); CLI = np.full_like(XX, np.nan)
    for a in range(ng):
        for b in range(ng):
            x = dict(nominal); x[xkey] = XX[a, b]; x[ykey] = YY[a, b]
            r = responses_at(x, t_ref)
            YEND[a, b] = r["y_end"]; CLI[a, b] = r["Cli"]

    fig, ax = plt.subplots(figsize=(9.2, 7))
    cf = ax.contourf(XX, YY, YEND, levels=14, cmap="viridis", alpha=0.92)
    fig.colorbar(cf, ax=ax, fraction=0.045, pad=0.02).set_label(
        f"放電後電圧 y_end @ {t_ref:.0f}年 [V]", fontsize=10)
    cl = ax.contour(XX, YY, YEND, levels=[Y_MIN], colors="red", linewidths=2.4)
    ax.clabel(cl, fmt=f"電圧={Y_MIN:.1f}V(下限)", fontsize=9)
    ct = ax.contour(XX, YY, CLI, levels=[CLI_MAX], colors="white", linewidths=2.4,
                    linestyles="--")
    ax.clabel(ct, fmt=f"Li塩={CLI_MAX:.1f}M(上限)", fontsize=9)
    NG = (~(YEND >= Y_MIN)) | (~(CLI <= CLI_MAX)) | ~np.isfinite(YEND)
    ax.contourf(XX, YY, NG.astype(float), levels=[0.5, 1.5], colors=["#555"],
                alpha=0.42, zorder=3)
    ax.contourf(XX, YY, NG.astype(float), levels=[0.5, 1.5], colors="none",
                hatches=["//"], zorder=3.1)
    ax.set_xlabel(SHORT[xkey].replace("\n", " "), fontsize=11)
    ax.set_ylabel(SHORT[ykey].replace("\n", " "), fontsize=11)
    ax.set_title("制約つき2軸コンター（局所地形の設計OK/NG, 報告書 NCR2170JB Step2 と同形式）\n"
                 f"横={SHORT[xkey].splitlines()[0]} 縦={SHORT[ykey].splitlines()[0]}（他は公称固定, {t_ref:.0f}年後）"
                 "／ 赤=電圧下限 白破線=Li塩上限 網掛=NG", fontsize=10)
    handles = [Line2D([0], [0], color="red", lw=2.4, label=f"放電後電圧 >= {Y_MIN}V"),
               Line2D([0], [0], color="white", lw=2.4, ls="--", label=f"限界Li塩濃度 <= {CLI_MAX}M"),
               plt.Rectangle((0, 0), 1, 1, fc="#55555588", label="NG（制約違反/維持不可）")]
    ax.legend(handles=handles, fontsize=9, loc="upper right", framealpha=0.9)
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)


# ---------------------------------------------------------------------------
# ③ 設計探索アーキテクチャ図
# ---------------------------------------------------------------------------
def architecture_diagram(active_keys, path):
    fig, ax = plt.subplots(figsize=(13.5, 6.8))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    def box(x, y, w, h, title, body, fc):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=1.4",
                     fc=fc, ec="#33405e", lw=1.6, zorder=2))
        ax.text(x + w/2, y + h - 5, title, ha="center", va="top", fontsize=11,
                fontweight="bold", zorder=3)
        ax.text(x + w/2, y + h - 12.5, body, ha="center", va="top", fontsize=8.4, zorder=3)

    def arrow(x0, y0, x1, y1, label=""):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                     mutation_scale=18, lw=2, color="#444", zorder=1))
        if label:
            ax.text((x0+x1)/2, (y0+y1)/2 + 3, label, ha="center", fontsize=8.3,
                    color="#a11", fontweight="bold")

    box(1, 52, 27, 38, "① 感度解析（理論式 直接MC）",
        "DC_v5 実式を Sobol 直接評価\n2応答: 放電後電圧 / 限界Li塩濃度\n"
        "分布モード design/variation\n時間推移＝支配因子の変遷(B-4③)\n"
        "物理妥当域マスキング(B-4④)", "#dbe7f3")
    box(37, 67, 27, 23, "② 交互作用の可視化",
        "S2 ネットワーク図（応答別）\nST−S1 で交互作用抽出\n"
        "並行座標が苦手な多変数関係を補完", "#e5dcef")
    box(37, 30, 27, 24, "① 絞り込み→並行座標",
        f"ST上位を能動軸に自動選択\n能動={'/'.join(SHORT[k].splitlines()[0] for k in active_keys[:4])}\n"
        "並行座標へ反映・領域ブラッシング", "#dcecdc")
    box(72, 46, 27, 32, "③ 制約つきコンター",
        "感度上位2軸=セル抵抗×塗布量\n放電後電圧>=2.5V(赤)\n"
        "限界Li塩濃度<=1.4M(白)\nOK/NG 局所地形\n(NCR2170JB Step2 と同形式)", "#f3e2dc")

    arrow(28, 76, 37, 78, "ST上位で交互作用確認")
    arrow(28, 66, 37, 42, "ST→能動軸 自動反映")
    arrow(64, 40, 72, 55, "上位2軸を選定")
    arrow(64, 76, 72, 64, "交互作用の強い対を優先")
    ax.add_patch(FancyArrowPatch((85, 46), (50, 28), connectionstyle="arc3,rad=0.3",
                 arrowstyle="-|>", mutation_scale=16, lw=1.6, color="#888", ls="--", zorder=1))
    ax.text(70, 21, "成立域が狭い/支配モードが変われば範囲を絞って感度を再計算（領域条件付き・時点別）",
            ha="center", fontsize=8.2, color="#666")

    ax.set_title("設計探索アーキテクチャ：感度スクリーニング → 並行座標(絞り込み) ＋ 交互作用ネットワーク "
                 "→ 制約つきコンター(局所地形OK/NG)\n保存劣化＝抵抗劣化モード⇄拡散劣化モードの変遷を時点別感度で追跡",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(); fig.savefig(path, bbox_inches="tight"); plt.close(fig)

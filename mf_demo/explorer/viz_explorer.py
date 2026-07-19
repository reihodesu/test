"""explorer/viz_explorer.py — ②③ 可視化（並行座標・コンター・アーキテクチャ図）

- parallel_coordinates : 擬似並行座標（matplotlib）。感度スクリーニング結果を
                         自動反映（能動軸を強調・降順配置、非能動軸を淡色）。①
- contour_2axis        : 制約線つき2軸コンター（局所地形の設計OK/NG領域）。③
- architecture_diagram : 感度→絞り込み→並行座標→コンターの設計探索アーキテクチャ。③
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from .config import XKEYS, VARSPEC
from .cell_design import cell_design
from .degradation import retention_at
from .screening import RET_TARGET, TYP_MIN, T_REF

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
def parallel_coordinates(df, active_keys, ST, path, brush=None, t_ref=T_REF):
    """並行座標。軸順＝ST降順、能動軸を強調・非能動軸を淡色。

    df       : generate_population の DataFrame
    active_keys : screen_by_sensitivity の能動軸（強調対象）
    ST       : dict or list（軸ラベルに ST を併記）
    brush    : {key:(lo,hi)} 領域選択（該当個体を強調、他を灰色）
    """
    st = ST if isinstance(ST, dict) else dict(zip(XKEYS, ST))
    # 軸順: 能動軸(ST降順) → 非能動軸(ST降順)
    inactive = [k for k in XKEYS if k not in active_keys]
    order = sorted(active_keys, key=lambda k: -st[k]) + \
        sorted(inactive, key=lambda k: -st[k])
    nax = len(order)

    lo = np.array([VARSPEC[k]["design"][0] for k in order])
    hi = np.array([VARSPEC[k]["design"][1] for k in order])
    V = df[order].to_numpy()
    Vn = (V - lo) / (hi - lo)  # 0-1 正規化

    # ブラッシング判定
    if brush:
        sel = np.ones(len(df), bool)
        for k, (a, b) in brush.items():
            sel &= (df[k] >= a) & (df[k] <= b)
    else:
        sel = df["ok"].to_numpy()  # 既定は制約OK個体を強調

    fig, ax = plt.subplots(figsize=(13, 6))
    xax = np.arange(nax)
    # 背景（非強調個体）
    for i in np.where(~sel)[0]:
        ax.plot(xax, Vn[i], color="#cccccc", lw=0.4, alpha=0.35, zorder=1)
    # 強調個体（維持率でカラー）
    ret = df["retention"].to_numpy()
    cmap = plt.cm.viridis
    rmin, rmax = np.nanmin(ret), np.nanmax(ret)
    for i in np.where(sel)[0]:
        c = cmap((ret[i] - rmin) / (rmax - rmin + 1e-9)) if np.isfinite(ret[i]) else "#999"
        ax.plot(xax, Vn[i], color=c, lw=0.8, alpha=0.6, zorder=2)

    # 軸
    for j, k in enumerate(order):
        is_active = k in active_keys
        ax.axvline(j, color="#333" if is_active else "#bbb",
                   lw=2.2 if is_active else 1.0, zorder=3)
        # 軸ラベル（能動軸は強調＋ST値、目盛）
        col = "#1a1a1a" if is_active else "#999"
        weight = "bold" if is_active else "normal"
        tag = "  ★能動" if is_active else ""
        ax.text(j, 1.06, f"{SHORT[k]}\nST={st[k]:.2f}{tag}", ha="center",
                va="bottom", fontsize=8.5, color=col, fontweight=weight)
        ax.text(j, -0.04, f"{lo[j]:.3g}", ha="center", va="top", fontsize=7, color=col)
        ax.text(j, 1.005, f"{hi[j]:.3g}", ha="center", va="bottom", fontsize=7, color=col)

    ax.set_xlim(-0.5, nax - 0.5); ax.set_ylim(-0.08, 1.18)
    ax.set_yticks([]); ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(rmin, rmax))
    cb = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label(f"容量維持率 @ {t_ref:.0f}年", fontsize=9)
    n_hl = int(sel.sum())
    sub = "制約OK個体" if not brush else "ブラッシング選択個体"
    ax.set_title(
        "擬似 並行座標プロット：感度スクリーニングを軸選択へ自動反映"
        f"（★能動軸＝ST上位を左に集約・強調 / {sub} {n_hl}個体を強調）\n"
        "並行座標が苦手な交互作用は別途ネットワーク図で補完（②）", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


# ---------------------------------------------------------------------------
# ③ 制約線つき2軸コンター（局所地形 OK/NG）
# ---------------------------------------------------------------------------
def contour_2axis(xkey, ykey, path, nominal=None, ng=60, t_ref=T_REF):
    """2軸コンター＋制約線＋OK/NG塗り分け（局所地形）。

    xkey, ykey : 横・縦軸に取る設計変数（通常は感度上位2変数）
    nominal    : 他変数の固定値 dict（無指定は design 中央）
    """
    if nominal is None:
        nominal = {k: sum(VARSPEC[k]["design"]) / 2 for k in XKEYS}
    xr = np.linspace(*VARSPEC[xkey]["design"], ng)
    yr = np.linspace(*VARSPEC[ykey]["design"], ng)
    XX, YY = np.meshgrid(xr, yr)
    RET = np.full_like(XX, np.nan)
    TYP = np.full_like(XX, np.nan)
    for a in range(ng):
        for b in range(ng):
            x = dict(nominal); x[xkey] = XX[a, b]; x[ykey] = YY[a, b]
            cell = cell_design(x["coat_load"], x["mix_density"], x["am_frac"], x["am_cap"])
            ret, _ = retention_at(x, t_ref)
            RET[a, b] = ret; TYP[a, b] = cell.Typ

    fig, ax = plt.subplots(figsize=(9, 7))
    # 維持率コンター
    cf = ax.contourf(XX, YY, RET, levels=14, cmap="viridis", alpha=0.9)
    cb = fig.colorbar(cf, ax=ax, fraction=0.045, pad=0.02)
    cb.set_label(f"容量維持率 @ {t_ref:.0f}年", fontsize=10)
    # 制約線
    cl = ax.contour(XX, YY, RET, levels=[RET_TARGET], colors="red", linewidths=2.2)
    ax.clabel(cl, fmt=f"維持率={RET_TARGET:.2f}", fontsize=9)
    ct = ax.contour(XX, YY, TYP, levels=[TYP_MIN], colors="white",
                    linewidths=2.2, linestyles="--")
    ax.clabel(ct, fmt=f"容量={TYP_MIN:.1f}Ah", fontsize=9)
    # NG 領域を灰色マスク＋斜線でマスク（どちらかの制約を満たさない）
    NG = (~(RET >= RET_TARGET)) | (~(TYP >= TYP_MIN)) | ~np.isfinite(RET)
    ax.contourf(XX, YY, NG.astype(float), levels=[0.5, 1.5],
                colors=["#555555"], alpha=0.42, zorder=3)
    ax.contourf(XX, YY, NG.astype(float), levels=[0.5, 1.5],
                colors="none", hatches=["//"], zorder=3.1)

    ax.set_xlabel(SHORT[xkey].replace("\n", " "), fontsize=11)
    ax.set_ylabel(SHORT[ykey].replace("\n", " "), fontsize=11)
    ax.set_title(
        f"制約線つき2軸コンター（局所地形の設計OK/NG）\n"
        f"横={SHORT[xkey].splitlines()[0]} 縦={SHORT[ykey].splitlines()[0]}、"
        "他変数は公称固定。赤=寿命制約 / 白破線=容量制約 / 網掛=NG領域", fontsize=10.5)
    handles = [Line2D([0], [0], color="red", lw=2.2, label=f"維持率 >= {RET_TARGET}"),
               Line2D([0], [0], color="white", lw=2.2, ls="--", label=f"容量 >= {TYP_MIN}Ah"),
               plt.Rectangle((0, 0), 1, 1, fc="#00000022", label="NG（制約違反）")]
    ax.legend(handles=handles, fontsize=9, loc="upper right", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)


# ---------------------------------------------------------------------------
# ③ 設計探索アーキテクチャ図（フロー）
# ---------------------------------------------------------------------------
def architecture_diagram(active_keys, top2, path):
    fig, ax = plt.subplots(figsize=(13, 6.4))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    def box(x, y, w, h, title, body, fc):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=1.4",
                     fc=fc, ec="#33405e", lw=1.6, zorder=2))
        ax.text(x + w/2, y + h - 5.5, title, ha="center", va="top",
                fontsize=11, fontweight="bold", zorder=3)
        ax.text(x + w/2, y + h - 13, body, ha="center", va="top",
                fontsize=8.6, zorder=3)

    def arrow(x0, y0, x1, y1, label=""):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1),
                     arrowstyle="-|>", mutation_scale=18, lw=2, color="#444", zorder=1))
        if label:
            ax.text((x0+x1)/2, (y0+y1)/2 + 3, label, ha="center", fontsize=8.5,
                    color="#a11", fontweight="bold")

    box(2, 55, 26, 34,
        "① 感度解析\n(理論式 直接MC)",
        "DC_v5 実式を Sobol\nで直接評価\nST / S1 を算出\n分布モード design/variation\n時間推移(B-4③)", "#dbe7f3")
    box(37, 66, 26, 23,
        "② 交互作用の可視化",
        "S2 ネットワーク図\nST−S1 で交互作用抽出\n並行座標が苦手な\n多変数関係を補完", "#e5dcef")
    box(37, 30, 26, 23,
        "① 絞り込み→並行座標",
        f"ST上位を能動軸に自動選択\n能動={'/'.join(SHORT[k].splitlines()[0] for k in active_keys)}\n"
        "並行座標へ反映\n領域ブラッシング", "#dcecdc")
    box(72, 47, 26, 30,
        "③ 制約つきコンター",
        f"感度上位2軸で局所地形\n{SHORT[top2[0]].splitlines()[0]} × {SHORT[top2[1]].splitlines()[0]}\n"
        "寿命/容量の制約線\nOK/NG 領域を塗り分け", "#f3e2dc")

    arrow(28, 74, 37, 76, "ST上位で交互作用確認")
    arrow(28, 68, 37, 42, "ST→能動軸 自動反映")
    arrow(63, 40, 72, 55, "上位2軸を選定")
    arrow(63, 76, 72, 66, "交互作用の強い対を優先")
    # フィードバックループ
    ax.add_patch(FancyArrowPatch((85, 47), (50, 28), connectionstyle="arc3,rad=0.3",
                 arrowstyle="-|>", mutation_scale=16, lw=1.6, color="#888",
                 ls="--", zorder=1))
    ax.text(70, 22, "OK域が狭ければ範囲を絞って感度を再計算（領域条件付き）",
            ha="center", fontsize=8.5, color="#666")

    ax.set_title("設計探索アーキテクチャ：感度スクリーニング → 並行座標(絞り込み) "
                 "＋ 交互作用ネットワーク → 制約つきコンター(局所地形OK/NG)",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight"); plt.close(fig)

"""antenna/check_a4.py  —  A-4 疑似ソルバの確認用プロット＋数値レポート

HANDOVER「進め方 1.」の確認ゲート用。以下を生成する:
  fig1: HF vs LF の応答曲線（3応答 × 6変数のスイープ）
  fig2: delta の性質確認（X4 の dip / 小振幅 / 滑らかさ / 非単調）
そして delta が「滑らか・小振幅・X4 に非単調」かを数値でも要約する。

実行:  python -m mf_demo.antenna.check_a4
"""
from __future__ import annotations

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import (
    VAR_NAMES, VAR_LABELS, RESP_NAMES, RESP_LABELS, RESP_TARGET,
    LOWER, UPPER, NOMINAL, SPAN, setup_japanese_font, SEED,
)
from .solvers import hf_response, lf_response, delta

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUT_DIR, exist_ok=True)

N_SWEEP = 300


def _sweep_axis(j: int, n: int = N_SWEEP) -> np.ndarray:
    """変数 j をスイープ、他は公称点で固定した (n,6) を返す。"""
    X = np.tile(NOMINAL, (n, 1))
    X[:, j] = np.linspace(LOWER[j], UPPER[j], n)
    return X


def _shade_target(ax, resp: str):
    lo, hi = RESP_TARGET[resp]
    if lo is not None and hi is not None:
        ax.axhspan(lo, hi, color="tab:green", alpha=0.12, zorder=0)
    elif hi is not None:
        ax.axhspan(ax.get_ylim()[0], hi, color="tab:green", alpha=0.10, zorder=0)


# ---------------------------------------------------------------------------
# fig1: HF vs LF スイープ
# ---------------------------------------------------------------------------
def make_fig1(path: str):
    nr, nc = len(RESP_NAMES), len(VAR_NAMES)
    fig, axes = plt.subplots(nr, nc, figsize=(19, 8.5), sharex="col")
    for jr, resp in enumerate(RESP_NAMES):
        for jc, var in enumerate(VAR_NAMES):
            ax = axes[jr, jc]
            X = _sweep_axis(jc)
            xs = X[:, jc]
            hf = hf_response(X)[resp]
            lf = lf_response(X)[resp]
            ax.plot(xs, lf, "--", color="tab:orange", lw=1.8, label="LF（低忠実度）")
            ax.plot(xs, hf, "-", color="tab:blue", lw=1.8, label="HF（真値）")
            _shade_target(ax, resp)
            ax.axvline(NOMINAL[jc], color="gray", ls=":", lw=0.8)
            if jr == 0:
                ax.set_title(VAR_LABELS[var], fontsize=9)
            if jc == 0:
                ax.set_ylabel(RESP_LABELS[resp], fontsize=9)
            ax.tick_params(labelsize=7)
            ax.grid(alpha=0.25)
    axes[0, 0].legend(fontsize=8, loc="best")
    fig.suptitle(
        "A-4 疑似ソルバ: HF（真値）と LF（=HF−delta）の応答曲線\n"
        "各パネルは1変数スイープ（他は公称点固定）。緑帯=目標域、点線=公称値。"
        "線が途切れる区間=数値的に無効なサンプル（帯域外共振など）",
        fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------------------
# fig2: delta の性質確認
# ---------------------------------------------------------------------------
def make_fig2(path: str):
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    # (A) X4 に対する log10QL: LF は単調、HF は dip を持つ ------------------
    ax = axes[0, 0]
    X = _sweep_axis(3)  # X4
    x4 = X[:, 3]
    ax.plot(x4, lf_response(X)["log10QL"], "--", color="tab:orange", lw=2,
            label="LF: log10(QL)（単調・dip無し）")
    ax.plot(x4, hf_response(X)["log10QL"], "-", color="tab:blue", lw=2,
            label="HF: log10(QL)（X4≈0.10 に dip）")
    ax.axvspan(0.04, 0.16, color="tab:red", alpha=0.08)
    ax.set_title("(A) X4 依存の dip: LF単独では見えず、MF(=LF+delta)で再現できる構造",
                 fontsize=10)
    ax.set_xlabel(VAR_LABELS["X4"]); ax.set_ylabel("log10(QL)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # (B) 3応答の delta を X4 に対して: 非単調・小振幅 ----------------------
    ax = axes[0, 1]
    d = delta(X)
    for r, c in zip(RESP_NAMES, ["tab:green", "tab:purple", "tab:blue"]):
        ax.plot(x4, d[r], lw=2, color=c, label=f"delta[{r}]")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title("(B) delta の X4 依存（非単調）。log10QL に主役の dip", fontsize=10)
    ax.set_xlabel(VAR_LABELS["X4"]); ax.set_ylabel("delta 値")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # (C) delta[log10QL] を全変数に対して: 滑らか・低周波 -------------------
    ax = axes[1, 0]
    for j, var in enumerate(VAR_NAMES):
        X = _sweep_axis(j)
        xs_norm = (X[:, j] - LOWER[j]) / SPAN[j]  # 0-1 正規化で重ね描き
        ax.plot(xs_norm, delta(X)["log10QL"], lw=1.8, label=var)
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title("(C) delta[log10QL] の各変数依存（正規化軸）: 滑らか・低周波",
                 fontsize=10)
    ax.set_xlabel("各変数（下限0→上限1に正規化）"); ax.set_ylabel("delta[log10QL]")
    ax.legend(fontsize=8, ncol=2); ax.grid(alpha=0.3)

    # (D) 振幅比較: |delta| は HF 変動幅より十分小さい ----------------------
    ax = axes[1, 1]
    rng = np.random.default_rng(SEED)
    Xr = LOWER + rng.random((4000, 6)) * SPAN
    hf = hf_response(Xr)
    d = delta(Xr)
    labels, hf_rng, d_amp = [], [], []
    for r in RESP_NAMES:
        v = hf[r][np.isfinite(hf[r])]
        labels.append(r)
        hf_rng.append(np.nanmax(v) - np.nanmin(v))
        d_amp.append(np.nanmax(np.abs(d[r])))
    xpos = np.arange(len(labels))
    ax.bar(xpos - 0.2, hf_rng, 0.4, color="tab:blue", label="HF 変動幅(range)")
    ax.bar(xpos + 0.2, d_amp, 0.4, color="tab:red", label="max|delta|")
    for i, (h, dd) in enumerate(zip(hf_rng, d_amp)):
        ax.text(i + 0.2, dd, f"{dd/h*100:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(xpos); ax.set_xticklabels(labels)
    ax.set_title("(D) 小振幅の確認: max|delta| / HF変動幅（%表示）", fontsize=10)
    ax.set_ylabel("大きさ"); ax.legend(fontsize=8); ax.grid(alpha=0.3, axis="y")

    fig.suptitle("A-4 delta の性質確認: 滑らか・低周波・小振幅・X4に非単調（dip）",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 数値レポート
# ---------------------------------------------------------------------------
def numeric_report():
    print("=" * 70)
    print("A-4 疑似ソルバ 数値レポート")
    print("=" * 70)

    # 公称点
    hf, lf, d = hf_response(NOMINAL), lf_response(NOMINAL), delta(NOMINAL)
    print("[公称点 x0]")
    for r in RESP_NAMES:
        print(f"  {r:8s}: HF={hf[r][0]:+.4f}  LF={lf[r][0]:+.4f}  "
              f"delta={d[r][0]:+.4f}")

    # 小振幅比
    rng = np.random.default_rng(SEED)
    Xr = LOWER + rng.random((5000, 6)) * SPAN
    HF, D = hf_response(Xr), delta(Xr)
    print("\n[小振幅: max|delta| / HF変動幅]")
    for r in RESP_NAMES:
        v = HF[r][np.isfinite(HF[r])]
        hf_rng = np.nanmax(v) - np.nanmin(v)
        ratio = np.nanmax(np.abs(D[r])) / hf_rng
        flag = "OK(<40%)" if ratio < 0.40 else "要確認"
        print(f"  {r:8s}: {ratio*100:5.1f}%   {flag}")

    # X4 非単調性（delta[log10QL] の符号変化数）
    X = _sweep_axis(3, 400)
    dql = delta(X)["log10QL"]
    dder = np.diff(dql)
    sign_changes = int(np.sum(np.diff(np.sign(dder)) != 0))
    x4 = X[:, 3]
    x4_min = float(x4[np.argmin(dql)])
    print("\n[X4 非単調性: delta[log10QL]]")
    print(f"  傾きの符号変化数 = {sign_changes}（>0 なら非単調 → dip 構造あり）")
    print(f"  dip 最深の X4    = {x4_min:.3f}（設計値 0.10 近傍）")

    # 滑らかさ（2階差分の相対大きさ; 小さいほど低周波・滑らか）
    print("\n[滑らかさ: delta[log10QL] の各変数スイープ 2階差分相対値]")
    for j, var in enumerate(VAR_NAMES):
        Xj = _sweep_axis(j, 300)
        y = delta(Xj)["log10QL"]
        d2 = np.diff(y, 2)
        rel = np.max(np.abs(d2)) / (np.ptp(y) + 1e-12)
        print(f"  {var}: max|Δ²|/range = {rel:.4f}")

    # エラーデータ（無効サンプル）割合
    print("\n[数値的暴れ: 無効サンプル割合（LHS 5000点）]")
    for fid, resp in (("LF", lf_response), ("HF", hf_response)):
        valid = resp(Xr)["valid"]
        print(f"  {fid}: {(~valid).mean()*100:5.1f}% 無効 "
              f"（HF は薄基板×高誘電率の隅で追加無効）")
    print("=" * 70)


def main():
    font = setup_japanese_font()
    print(f"[font] using: {font}")
    f1 = os.path.normpath(os.path.join(OUT_DIR, "a4_fig1_hf_vs_lf.png"))
    f2 = os.path.normpath(os.path.join(OUT_DIR, "a4_fig2_delta_check.png"))
    make_fig1(f1)
    make_fig2(f2)
    print(f"[saved] {f1}")
    print(f"[saved] {f2}")
    numeric_report()


if __name__ == "__main__":
    main()

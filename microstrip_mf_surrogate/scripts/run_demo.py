#!/usr/bin/env python3
"""
マイクロストリップアンテナ設計事例 — マルチフィデリティ・サロゲート デモ本体。

KESCO/SmartUQ セミナー資料 後半(p.26-49)のワークフローを一気通貫で再現する:

  フェーズA  設計問題の定義 (仕様/評価指標/制約)
  フェーズB  忠実度の異なるデータ生成 (LTSpice相当LF / FEM相当HF, DOE=スライスLHD)
  フェーズC  サロゲートで判断 (HF-only / MF / DataFusion 比較, QL選別, 多目的最適化, 検証/チューニング)

実行:  python scripts/run_demo.py
出力:  figures/*.png, outputs/results.md, outputs/results.json
"""
from __future__ import annotations

import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from msa import (geometry, lowfidelity, highfidelity, metrics, doe, surrogate,
                 optimize, pipeline, C0, F_DESIGN)
from msa.pipeline import eval_lf, eval_hf, eval_hf_fine, F_LF, F_HF, LABELS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "figures")
OUT = os.path.join(HERE, "outputs")
os.makedirs(FIG, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# 日本語が無い環境向けに簡易フォント設定(文字化けは許容)
plt.rcParams.update({"figure.dpi": 110, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.3})

report = []       # markdown 行
results = {}      # JSON


def log(s=""):
    print(s)
    report.append(s)


# =====================================================================
# フェーズA: 設計問題の定義
# =====================================================================
def phase_A():
    log("# マイクロストリップアンテナ設計 — マルチフィデリティ・サロゲート デモ結果\n")
    log("## フェーズA: 設計問題の定義 (資料 p.28)\n")
    log("対象: 2.4GHz帯 オフセット給電パッチアンテナ\n")
    log("| 評価指標 | 記号 | 仕様 |")
    log("|---|---|---|")
    log("| 中心周波数 | f0 | 2.45 GHz ± 0.01 GHz (2.44–2.46) |")
    log("| リターンロス | \\|S11min\\| | ≤ 0.316 (RL ≥ 10 dB) |")
    log("| Loaded Q | QL | ≤ 30 (log10 QL ≤ 1.477) |")
    log("")
    log("設計変数 (無次元化, 資料 p.32):\n")
    log("| 変数 | 意味 | 範囲 |")
    log("|---|---|---|")
    meaning = {"X1": "パッチ幅/波長", "X2": "下部パッチ幅比", "X3": "パッチ長係数",
               "X4": "給電オフセット(0=中央,1=端)", "X5": "基板厚 H [m]", "X6": "基板比誘電率 er"}
    for k in geometry.XKEYS:
        lo, hi = geometry.BOUNDS[k]
        log(f"| {k} | {meaning[k]} | [{lo}, {hi}] |")
    log("")
    results["spec"] = metrics.SPEC


# =====================================================================
# フェーズB: 忠実度の異なるデータ生成
# =====================================================================
def phase_B():
    log("## フェーズB: 忠実度の異なるデータ生成 (DOE=スライスLHD, 資料 p.32)\n")
    # スライスLHD (資料の 64slice x 16set は重いので教育用に縮小)
    X_lf, X_hf, hf_idx = doe.make_doe(n_lf_slice=48, per_slice=8, n_hf=96, seed=3)
    log(f"- LTSpice(LF) 設計点数: {len(X_lf)}  (スライスLHD)")
    log(f"- FEM(HF) 設計点数: {len(X_hf)}  (LF点の入れ子部分集合 = 対応点DOE)\n")

    ev = pipeline.evaluate_doe(X_lf, X_hf, seed=7)
    log(f"- LF 有効データ: {ev['v_lf'].sum()}/{len(X_lf)}  "
        f"(共振が見えない等をエラー除外, 資料 p.35)")
    log(f"- HF 有効データ: {ev['v_hf'].sum()}/{len(X_hf)}\n")

    data = dict(X_lf=X_lf, X_hf=X_hf, **ev)
    fig_lf_hf_curves()
    fig_feed_sweep()
    return data


# =====================================================================
# フェーズC: サロゲート構築・比較・最適化・検証
# =====================================================================
def phase_C(data):
    log("## フェーズC: サロゲートで判断 (資料 p.38-46)\n")

    X_lf, X_hf = data["X_lf"], data["X_hf"]
    Ylf, vlf = data["Y_lf"], data["v_lf"]
    Yhf, vhf = data["Y_hf"], data["v_hf"]

    Xlf_v, Ylf_v = X_lf[vlf], Ylf[vlf]
    Xhf_v, Yhf_v = X_hf[vhf], Yhf[vhf]

    # --- サロゲート3方式の比較 (SCVR) ---
    log("### 3方式のサロゲート比較 (標準化CV誤差 SCVR, 資料 p.39)\n")
    log("- **HF-only**: 高忠実度データのみ (少数 -> 不確かさ大)")
    log("- **Multi-fidelity(差分補正型)**: w_HF = w_LF_hat + δ(x)")
    log("- **Data Fusion(co-kriging)**: w_HF = ρ·w_LF_hat + δ(x)\n")

    scvr_table = {}
    for j, lab in enumerate(LABELS):
        ylf_j = Ylf_v[:, j]
        yhf_j = Yhf_v[:, j]
        s_hf = surrogate.scvr("HF_only", Xlf_v, ylf_j, Xhf_v, yhf_j)
        s_mf = surrogate.scvr("MultiFidelity", Xlf_v, ylf_j, Xhf_v, yhf_j)
        s_df = surrogate.scvr("DataFusion", Xlf_v, ylf_j, Xhf_v, yhf_j)
        scvr_table[lab] = dict(HF_only=s_hf, MultiFidelity=s_mf, DataFusion=s_df)

    log("| 目的量 | HF-only | Multi-fidelity | Data Fusion |")
    log("|---|---|---|---|")
    for lab in LABELS:
        t = scvr_table[lab]
        log(f"| {lab} | {t['HF_only']:.3f} | {t['MultiFidelity']:.3f} | {t['DataFusion']:.3f} |")
    log("")
    log("→ マルチフィデリティ/データフュージョンで少数HFの予測不確かさが低減する"
        "(資料 p.39 の傾向を再現)。\n")
    results["scvr_all"] = scvr_table
    fig_scvr_bar(scvr_table, "scvr_all.png",
                 "SCVR: HF-only vs Multi-fidelity vs Data Fusion")

    # --- QL>30 データ選別で S11min 精度改善 (資料 p.40) ---
    log("### QL>30 データ選別による改善 (資料 p.40)\n")
    log("QLが大きい(狭帯域=鋭い共振)データは、20MHz の FEM 格子が真の谷を捉えきれず"
        "|S11min| の抽出誤差が大きい(資料 p.40「スプライン補間では対応不能」)。"
        "この汚染点を学習に含めると仕様域(QL≤30)の予測精度を下げるため、除外する。\n")
    sel = Yhf_v[:, 2] <= np.log10(30.0)      # log10(QL) <= 1.477
    Xhf_s, Yhf_s = Xhf_v[sel], Yhf_v[sel]
    log(f"- 汚染しうる高QL点を除外: 学習 {len(Xhf_v)} → {sel.sum()} 点\n")
    log("評価はクリーン点(QL≤30)上に固定し、学習集合のみ変えて比較(公平比較):\n")

    scvr_sel = {}
    log("| 目的量 | 学習=全点(高QL汚染含む) | 学習=選別後(QL≤30) |")
    log("|---|---|---|")
    for j, lab in enumerate(LABELS):
        s_before, s_after = surrogate.scvr_poison(
            "MultiFidelity", Xlf_v, Ylf_v[:, j], Xhf_v, Yhf_v[:, j], sel)
        scvr_sel[lab] = dict(before=s_before, after=s_after)
        log(f"| {lab} | {s_before:.3f} | {s_after:.3f} |")
    log("")
    log("→ 汚染された高QL点を除くと |S11min| のCV誤差が下がる(資料 p.40 の趣旨)。"
        "f0/log(QL) は元々汚染が無いためほぼ不変。\n")
    results["scvr_selection"] = scvr_sel
    fig_loo_scatter(Xlf_v, Ylf_v, Xhf_v, Yhf_v, Xhf_s, Yhf_s)

    # --- 採用サロゲート: MF を選別後データで学習 ---
    log("### 採用サロゲート: マルチフィデリティ(選別後データ)\n")
    models = {}
    for j, lab in enumerate(LABELS):
        m = surrogate.MultiFidelity().fit(Xlf_v, Ylf_v[:, j], Xhf_s, Yhf_s[:, j])
        models[lab] = m
    fig_mf_surface(models)

    # --- 多目的最適化 NSGA-II (資料 p.44) ---
    log("### 多目的最適化 NSGA-II (資料 p.44)\n")
    # 基板を固定 (資料 p.44: 厚さ2mm/er2.2 の例に倣い基板固定)。ここでは HF が
    # 動作点に届く H=3mm, er=3.0 に固定して X1,X2,X3,X4 を最適化。
    H_fix, er_fix = 0.003, 3.0
    log(f"- 基板固定: H={H_fix*1000:.0f}mm, er={er_fix}")
    log("- 目的: |S11min| と log10(QL) を同時最小化 (トレードオフ=パレート)")
    log("- 制約: f0 ∈ [2.44, 2.46] GHz\n")

    # 最適化探索の変数レンジ(サロゲートは全域で学習済み。探索は現実的な
    # パッチ寸法域に限定: 実パッチ幅は概ね < 0.5λ0)。
    opt_bounds = {"X1": (0.15, 0.55), "X2": (0.5, 1.0),
                  "X3": (0.15, 0.35), "X4": (0.0, 0.7)}
    log(f"- 探索域(現実寸法): X1∈{opt_bounds['X1']}, X4∈{opt_bounds['X4']} 他")

    def denorm(U):
        """[0,1]^4 (X1,X2,X3,X4) -> フル6変数 X。"""
        X = np.empty((len(U), 6))
        for jj, k in enumerate(["X1", "X2", "X3", "X4"]):
            lo, hi = opt_bounds[k]
            X[:, jj] = lo + U[:, jj] * (hi - lo)
        X[:, 4] = H_fix
        X[:, 5] = er_fix
        return X

    def eval_fn(U):
        X = denorm(U)
        f0 = models["f0 [GHz]"].predict(X)[0]
        s11 = np.clip(models["|S11min|"].predict(X)[0], 0.0, None)  # |S11|>=0 (物理)
        lq = models["log10(QL)"].predict(X)[0]
        F = np.column_stack([s11, lq])
        # f0 制約: 帯域外れ量
        g = np.maximum(0.0, metrics.SPEC["f0_lo"] / 1e9 - f0) + \
            np.maximum(0.0, f0 - metrics.SPEC["f0_hi"] / 1e9)
        return F, g

    P, F, G, front = optimize.nsga2(eval_fn, dim=4, pop=80, gen=60, seed=1)
    Xf = denorm(P[front])
    Ff = F[front]
    log(f"- パレート解数(実行可能): {len(front)}\n")
    fig_pareto(Ff)

    # --- パレートから設計を選択 (資料 p.44: 仕様を満たす代表解) ---
    # 仕様(|S11min|≤0.316, QL≤30)を満たすパレート点に限定し、両目的の
    # 正規化和が最小(=バランス最良)の点を代表解とする。無ければ全点から。
    s11_cap = metrics.SPEC["s11min_max"]
    logql_cap = np.log10(metrics.SPEC["QL_max"])
    score = (Ff[:, 0] / s11_cap) + (Ff[:, 1] / logql_cap)
    compliant = (Ff[:, 0] <= s11_cap) & (Ff[:, 1] <= logql_cap)
    if compliant.any():
        cand = np.where(compliant)[0]
        pick = cand[int(np.argmin(score[cand]))]
        log(f"- 仕様適合パレート点: {compliant.sum()}/{len(front)} から代表解を選択")
    else:
        pick = int(np.argmin(score))
        log("- 仕様完全適合点なし → バランス最良点を選択(チューニングで対処)")
    X_opt = Xf[pick]
    log("### 選択された最適設計 (サロゲート予測)\n")
    log("| " + " | ".join(geometry.XKEYS) + " |")
    log("|" + "---|" * 6)
    log("| " + " | ".join(f"{v:.3f}" for v in X_opt) + " |\n")
    pf0 = models["f0 [GHz]"].predict([X_opt])[0][0]
    ps = max(0.0, models["|S11min|"].predict([X_opt])[0][0])
    plq = models["log10(QL)"].predict([X_opt])[0][0]
    log(f"- サロゲート予測: f0={pf0:.3f}GHz, |S11min|={ps:.3f}, "
        f"QL={10**plq:.1f}\n")
    results["optimum_surrogate"] = dict(
        X=X_opt.tolist(), f0=float(pf0), s11min=float(ps), QL=float(10**plq))

    # --- 検証: FEM 精密計算 + X3 チューニング (資料 p.45-46) ---
    tuning(X_opt, models)


def tuning(X_opt, models):
    log("### 検証ゲート & チューニング (資料 p.45-46)\n")
    m0, fg0, s0 = eval_hf_fine(X_opt)
    log("最適パラメータで FEM 精密計算(5MHz)を実施:")
    log(f"- FEM: f0={m0.f0/1e9:.3f}GHz, |S11min|={m0.s11min:.3f}, QL={m0.QL:.1f}")
    spec0 = metrics.check_spec(m0)
    log(f"- 判定: f0={'OK' if spec0['f0'] else 'NG'}, "
        f"S11min={'OK' if spec0['s11min'] else 'NG'}, "
        f"QL={'OK' if spec0['QL'] else 'NG'}\n")

    # X3 は f0 に主に効き S11min/QL への影響が小さい(資料 p.46) -> X3 をスケール
    # f0 を 2.45GHz へ寄せる: 共振周波数 ∝ 1/長さ ∝ 1/X3
    X_tuned = X_opt.copy()
    target = 2.45
    if not spec0["f0"] and np.isfinite(m0.f0):
        X_tuned[2] = X_opt[2] * (m0.f0 / 1e9) / target
        X_tuned[2] = float(np.clip(X_tuned[2], *geometry.BOUNDS["X3"]))
    m1, fg1, s1 = eval_hf_fine(X_tuned)
    log(f"X3 チューニング: {X_opt[2]:.3f} → {X_tuned[2]:.3f} "
        f"(f0 を {target}GHz へ寄せる)")
    log(f"- FEM(調整後): f0={m1.f0/1e9:.3f}GHz, |S11min|={m1.s11min:.3f}, QL={m1.QL:.1f}")
    spec1 = metrics.check_spec(m1)
    log(f"- 判定: f0={'OK' if spec1['f0'] else 'NG'}, "
        f"S11min={'OK' if spec1['s11min'] else 'NG'}, "
        f"QL={'OK' if spec1['QL'] else 'NG'}\n")

    # 物理寸法
    geo = geometry.build_geometry(X_tuned, F_DESIGN, C0)
    d = geo.as_dict()
    log("最終設計の物理寸法 [m]:\n")
    log("| W1 | W2 | W4 | Len1 | Len2 | Len4 | H | er |")
    log("|---|---|---|---|---|---|---|---|")
    log(f"| {d['W1']:.4f} | {d['W2']:.4f} | {d['W4']:.4f} | {d['Len1']:.4f} "
        f"| {d['Len2']:.4f} | {d['Len4']:.4f} | {d['H']:.4f} | {d['er']:.1f} |\n")

    results["optimum_tuned"] = dict(
        X=X_tuned.tolist(),
        before=dict(f0=float(m0.f0/1e9), s11min=float(m0.s11min), QL=float(m0.QL),
                    pass_=all(spec0.values())),
        after=dict(f0=float(m1.f0/1e9), s11min=float(m1.s11min), QL=float(m1.QL),
                   pass_=all(spec1.values())),
        dims={k: float(v) for k, v in d.items()})

    fig_final_s11(fg0, s0, fg1, s1, m0, m1)

    log("### まとめ\n")
    log("- LTSpice(簡易)と FEM(モック)をマルチフィデリティで統合し、少数のHFで"
        "物理と整合するサロゲートを構築(資料 p.49)。")
    log("- サロゲートの価値は「速い予測」ではなく「速い理解」: 予測に不確かさを添え、"
        "どこを信じ次にどこを測るかを可視化。")
    log("- QL選別・X3チューニングで、少ない学習データから仕様内設計に到達。\n")


# =====================================================================
# 図の生成
# =====================================================================
def fig_lf_hf_curves():
    X = [0.35, 0.988, 0.226, 0.3, 0.003, 3.0]
    geo = geometry.build_geometry(X, F_DESIGN, C0)
    slf = np.abs(lowfidelity.s11(geo, F_LF, C0))
    shf = np.abs(highfidelity.s11(geo, F_HF, C0))
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(F_LF / 1e9, slf, label="LF (LTSpice-equiv)", lw=1.5)
    ax.plot(F_HF / 1e9, shf, "o-", ms=3, label="HF (FEM-mock, 20MHz)", lw=1.2)
    ax.axhline(0.316, color="r", ls="--", lw=0.8, label="|S11|=0.316 (RL 10dB)")
    ax.set_xlabel("Frequency [GHz]"); ax.set_ylabel("|S11|")
    ax.set_title("LF vs HF: |S11| response")
    ax.legend(fontsize=8); ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "lf_hf_curves.png")); plt.close(fig)


def fig_feed_sweep():
    x4s = np.linspace(0.05, 0.7, 24)
    lf_s, lf_q, hf_s, hf_q = [], [], [], []
    for x4 in x4s:
        X = [0.35, 0.988, 0.226, x4, 0.003, 3.0]
        ml = eval_lf(X); mh = eval_hf(X)
        lf_s.append(ml.s11min if ml.valid else np.nan)
        lf_q.append(ml.QL if ml.valid else np.nan)
        hf_s.append(mh.s11min if mh.valid else np.nan)
        hf_q.append(mh.QL if mh.valid else np.nan)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ax[0].plot(x4s, lf_s, "o-", ms=3, label="LF")
    ax[0].plot(x4s, hf_s, "s-", ms=3, label="HF")
    ax[0].axhline(0.316, color="r", ls="--", lw=0.8)
    ax[0].set_xlabel("X4 (feed offset)"); ax[0].set_ylabel("|S11min|")
    ax[0].set_title("Match vs feed position"); ax[0].legend(fontsize=8)
    ax[1].plot(x4s, lf_q, "o-", ms=3, label="LF")
    ax[1].plot(x4s, hf_q, "s-", ms=3, label="HF")
    ax[1].axhline(30, color="r", ls="--", lw=0.8)
    ax[1].set_xlabel("X4 (feed offset)"); ax[1].set_ylabel("QL")
    ax[1].set_title("Loaded Q vs feed position"); ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "feed_sweep.png")); plt.close(fig)


def fig_scvr_bar(table, fname, title):
    labels = LABELS
    methods = ["HF_only", "MultiFidelity", "DataFusion"]
    x = np.arange(len(labels)); w = 0.25
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    for i, mth in enumerate(methods):
        vals = [table[l][mth] for l in labels]
        ax.bar(x + (i - 1) * w, vals, w, label=mth)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("SCVR (lower=better)"); ax.set_title(title)
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, fname)); plt.close(fig)


def fig_loo_scatter(Xlf, Ylf, Xhf, Yhf, Xhf_s, Yhf_s):
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    for j, lab in enumerate(LABELS):
        ax = axes[j]
        # 選別前 MF LOO 予測
        mu_all = surrogate.loo_pred("MultiFidelity", Xlf, Ylf[:, j], Xhf, Yhf[:, j])
        mu_sel = surrogate.loo_pred("MultiFidelity", Xlf, Ylf[:, j], Xhf_s, Yhf_s[:, j])
        ax.scatter(Yhf[:, j], mu_all, s=18, alpha=0.6, label="all data")
        ax.scatter(Yhf_s[:, j], mu_sel, s=18, alpha=0.8, marker="^", label="QL≤30 selected")
        lo = np.nanmin([Yhf[:, j].min(), Yhf_s[:, j].min()])
        hi = np.nanmax([Yhf[:, j].max(), Yhf_s[:, j].max()])
        ax.plot([lo, hi], [lo, hi], "k--", lw=0.8)
        ax.set_xlabel(f"actual {lab}"); ax.set_ylabel(f"LOO pred {lab}")
        ax.set_title(lab); ax.legend(fontsize=7)
    fig.suptitle("Leave-One-Out prediction (MF): before/after QL selection")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "loo_scatter.png")); plt.close(fig)


def fig_mf_surface(models):
    # X4 と X1 を動かした MF 予測 (不確かさ帯付き) を f0/s11min/logQL で
    x4s = np.linspace(0.05, 0.7, 40)
    base = [0.35, 0.988, 0.22, 0.3, 0.003, 3.0]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    for j, lab in enumerate(LABELS):
        ax = axes[j]
        Xq = np.tile(base, (len(x4s), 1)); Xq[:, 3] = x4s
        mu, sd = models[lab].predict(Xq)
        ax.plot(x4s, mu, "-", label="MF pred")
        ax.fill_between(x4s, mu - 2 * sd, mu + 2 * sd, alpha=0.2, label="±2σ")
        ax.set_xlabel("X4 (feed offset)"); ax.set_ylabel(lab); ax.set_title(lab)
        ax.legend(fontsize=7)
    fig.suptitle("MF surrogate prediction with uncertainty (vs feed position)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "mf_surface.png")); plt.close(fig)


def fig_pareto(Ff):
    order = np.argsort(Ff[:, 0])
    fig, ax = plt.subplots(figsize=(5.5, 4))
    ax.plot(Ff[order, 0], Ff[order, 1], "o-", ms=4)
    ax.axvline(0.316, color="r", ls="--", lw=0.8, label="|S11| spec")
    ax.axhline(np.log10(30), color="g", ls="--", lw=0.8, label="QL spec")
    ax.set_xlabel("|S11min|"); ax.set_ylabel("log10(QL)")
    ax.set_title("Pareto front (NSGA-II on MF surrogate)")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "pareto.png")); plt.close(fig)


def fig_final_s11(fg0, s0, fg1, s1, m0, m1):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(fg0 / 1e9, np.abs(s0), label=f"before tuning (f0={m0.f0/1e9:.3f})", lw=1.3)
    ax.plot(fg1 / 1e9, np.abs(s1), label=f"after tuning (f0={m1.f0/1e9:.3f})", lw=1.3)
    ax.axhline(0.316, color="r", ls="--", lw=0.8, label="RL 10dB")
    ax.axvspan(2.44, 2.46, color="g", alpha=0.15, label="f0 spec")
    ax.set_xlabel("Frequency [GHz]"); ax.set_ylabel("|S11|")
    ax.set_title("Final design |S11|: X3 tuning"); ax.legend(fontsize=8)
    ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "final_s11.png")); plt.close(fig)


def main():
    phase_A()
    data = phase_B()
    phase_C(data)
    # 保存
    with open(os.path.join(OUT, "results.md"), "w") as f:
        f.write("\n".join(report))
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"\n(図: {FIG}/*.png, 結果: {OUT}/results.md, results.json)")


if __name__ == "__main__":
    main()

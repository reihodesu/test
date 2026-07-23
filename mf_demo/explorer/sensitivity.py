"""explorer/sensitivity.py — 保存劣化モデルの Sobol 感度解析（v3, 数値信頼性強化）

改善（P1）:
  - 1評価で全応答（放電後電圧 y_end / 限界Li塩濃度 Cli / 二値=300W維持可否 feasible）を取得
  - S1_conf / ST_conf / S2_conf を保持（誤差棒・S2有意性判定に使用）
  - 無効サンプルの処理を明示的な invalid_policy で選択:
      "median"  : 中央値代入（既定）
      "penalty" : worst-case 代入（物理的な失敗側; robustness 比較用）
      "report_only": 中央値代入だが「代入値である」ことをフラグ
  - feasible（二値）は全域で定義されるため代入不要 → 欠測バイアスの影響を受けない

MOP（サロゲート）非経由の直接モンテカルロ。物理妥当域マスキングは degradation 側。
"""
from __future__ import annotations

import numpy as np
from SALib.sample import sobol as sobol_sample
from SALib.analyze import sobol as sobol_analyze

from .config import (XKEYS, make_problem, TIME_GRID, T_REF, RESPONSES,
                     RESP_PENALTY)
from .degradation import evaluate

NAN_WARN = 0.30
RESP_MAIN = ["y_end", "Cli", "feasible"]


def _indices(problem, y_raw, calc_second_order, invalid_policy="median",
             penalty=0.0):
    """応答配列 → Sobol 指標（信頼区間つき）。無効サンプルは policy で処理。"""
    y = np.asarray(y_raw, float).copy()
    nan_rate = float(np.mean(~np.isfinite(y)))
    if nan_rate > 0:
        if invalid_policy == "penalty":
            fill = penalty
        else:  # median / report_only
            fill = np.nanmedian(y)
        y = np.where(np.isfinite(y), y, fill)
    Si = sobol_analyze.analyze(problem, y, calc_second_order=calc_second_order,
                               print_to_console=False, seed=3)
    out = {"S1": Si["S1"].tolist(), "S1_conf": Si["S1_conf"].tolist(),
           "ST": Si["ST"].tolist(), "ST_conf": Si["ST_conf"].tolist(),
           "nan_rate": nan_rate, "invalid_policy": invalid_policy,
           "var": float(np.nanvar(y_raw))}
    if calc_second_order:
        out["S2"] = np.nan_to_num(np.array(Si["S2"])).tolist()
        out["S2_conf"] = np.nan_to_num(np.array(Si["S2_conf"]), nan=1e9).tolist()
    return out


def analyze_mode(mode: str, t: float, N: int, keys=None,
                 calc_second_order=True, invalid_policy="median"):
    """1回のサンプリング＋評価で 3 応答の Sobol 指標を返す（効率化）。"""
    keys = keys or XKEYS
    problem = make_problem(mode, keys)
    X = sobol_sample.sample(problem, N, calc_second_order=calc_second_order, seed=3)
    Y = evaluate(X, keys, t)
    valid_rate = float(np.mean(Y["valid"]))
    out = {}
    for rp in ["y_end", "Cli"]:
        out[rp] = _indices(problem, Y[rp], calc_second_order, invalid_policy,
                           RESP_PENALTY[rp])
    # feasible: 二値（1=維持可）。全域定義 → 代入不要
    out["feasible"] = _indices(problem, Y["valid"].astype(float),
                               calc_second_order, "none", 0.0)
    for rp, d in out.items():
        d.update({"n_samples": int(len(X)), "N": N, "t": t, "mode": mode,
                  "valid_rate": valid_rate, "response": rp})
        if d["nan_rate"] > NAN_WARN and rp != "feasible":
            print(f"  [警告] {mode}/{rp} t={t}yr 除外率 {d['nan_rate']:.1%}"
                  f"（policy={invalid_policy}）— 二値応答 feasible も併せて解釈のこと(B-4④)")
    return out


def time_evolution(mode: str, N: int, responses=RESP_MAIN, times=None, keys=None,
                   invalid_policy="median"):
    """感度指標の時間推移（B-4③）: 各時点で ST（＋95%CI）を応答別に算出。"""
    keys = keys or XKEYS
    times = times or TIME_GRID
    res = {rp: {"ST": [], "ST_conf": [], "nan_rate": []} for rp in responses}
    for t in times:
        a = analyze_mode(mode, t, N, keys, calc_second_order=False,
                         invalid_policy=invalid_policy)
        for rp in responses:
            res[rp]["ST"].append(a[rp]["ST"])
            res[rp]["ST_conf"].append(a[rp]["ST_conf"])
            res[rp]["nan_rate"].append(a[rp]["nan_rate"])
    return {"times": list(times), "keys": keys, "mode": mode, "N": N,
            "invalid_policy": invalid_policy, "by_response": res}


def mode_fraction_over_time(mode: str, N: int, times=None, keys=None):
    """拡散劣化モード割合を『全サンプル基準』と『有効サンプル基準』の2分母で算出。"""
    keys = keys or XKEYS
    times = times or TIME_GRID
    problem = make_problem(mode, keys)
    X = sobol_sample.sample(problem, N, calc_second_order=False, seed=9)
    n = len(X)
    diff_all, diff_valid, ok_frac, valid_frac = [], [], [], []
    for t in times:
        Y = evaluate(X, keys, t)
        v = Y["valid"]
        diff = np.where(v, Y["ndc"] > 1.0, False)
        ok = v & (Y["y_end"] >= RESPONSES["y_end"]["thr"]) & \
            (Y["Cli"] <= RESPONSES["Cli"]["thr"])
        diff_all.append(float(np.mean(diff)))                       # 全サンプル基準
        diff_valid.append(float(np.mean(diff[v])) if v.any() else np.nan)  # 有効基準
        ok_frac.append(float(np.mean(ok)))
        valid_frac.append(float(np.mean(v)))
    return {"times": list(times), "n_samples": n,
            "diffusion_frac_all": diff_all, "diffusion_frac_valid": diff_valid,
            "ok_frac": ok_frac, "valid_frac": valid_frac, "mode": mode, "N": N}


def convergence(mode: str, t: float, response: str = "Cli",
                Ns=(128, 256, 512, 1024, 2048, 4096), keys=None,
                invalid_policy="median"):
    """ST の収束と 95%CI（既定は Cli=2次指標を使う図の土台）。x=実評価点数。"""
    keys = keys or XKEYS
    problem = make_problem(mode, keys)
    rows = []
    for N in Ns:
        X = sobol_sample.sample(problem, N, calc_second_order=False, seed=5)
        Y = evaluate(X, keys, t)
        d = _indices(problem, Y[response] if response != "feasible"
                     else Y["valid"].astype(float), False, invalid_policy,
                     RESP_PENALTY.get(response, 0.0))
        rows.append({"N": N, "n_samples": int(len(X)),
                     "ST": d["ST"], "ST_conf": d["ST_conf"]})
    return {"rows": rows, "response": response, "mode": mode, "t": t}


MIN_SAMPLES = 200  # 領域条件付き感度の最小サンプル数ガード


def _region_bounds(ov):
    from .config import VARSPEC
    lo = np.array([(ov.get(k, VARSPEC[k]["design"]))[0] for k in XKEYS])
    hi = np.array([(ov.get(k, VARSPEC[k]["design"]))[1] for k in XKEYS])
    return lo, hi


def f1_robustness(regions, t: float, N_sobol=2048, N_lhs=6000):
    """F-1: §5.4 の入れ替わりが代入方針/代入非依存手法で再現するかを検証。

    各領域で 限界Li塩濃度 Cli の感度を 3手法で算出:
      - Sobol ST（median 代入）
      - Sobol ST（penalty=worst-case 代入）
      - Spearman |ρ|（有効サンプルのみ, 代入非依存の順位相関ベース簡易感度）
        ※ Saltelli 行列を使わないため厳密な Sobol ではない（分散分解でなく単調性の指標）。
    併せて各領域の有効率・代入率を実測する。
    """
    from scipy.stats import qmc, spearmanr
    out = []
    for name, ov in regions:
        prob = make_problem("design", XKEYS, override_bounds=ov)
        X = sobol_sample.sample(prob, N_sobol, calc_second_order=False, seed=7)
        Y = evaluate(X, XKEYS, t)
        vr = float(np.mean(Y["valid"]))
        med = _indices(prob, Y["Cli"], False, "median")["ST"]
        pen = _indices(prob, Y["Cli"], False, "penalty",
                       RESP_PENALTY["Cli"])["ST"]
        # 代入非依存: 領域内 LHS の有効サンプルのみで Spearman |ρ|
        lo, hi = _region_bounds(ov)
        XL = lo + qmc.LatinHypercube(d=len(XKEYS), seed=11).random(N_lhs) * (hi - lo)
        YL = evaluate(XL, XKEYS, t)
        v = YL["valid"]; cli = YL["Cli"]
        rho = []
        for j in range(len(XKEYS)):
            if v.sum() > MIN_SAMPLES and np.ptp(XL[v, j]) > 0:
                r = spearmanr(XL[v, j], cli[v]).correlation
                rho.append(abs(r) if np.isfinite(r) else 0.0)
            else:
                rho.append(np.nan)
        out.append({"name": name, "override": ov, "valid_rate": vr,
                    "impute_rate": 1.0 - vr, "n_saltelli": int(len(X)),
                    "n_valid_lhs": int(v.sum()), "t": t,
                    "ST_median": med, "ST_penalty": pen, "spearman": rho})
    return out


def conditional_staged(response: str, t: float, N: int, regions, keys=None,
                       invalid_policy="median"):
    """段階的に絞った複数領域で ST を算出（並行座標ブラッシング相当・領域条件付き）。

    regions: [(name, override_bounds_dict), ...]（全域→中間→頻発域 の順を想定）
    """
    keys = keys or XKEYS
    out = []
    for name, ov in regions:
        problem = make_problem("design", keys, override_bounds=ov)
        X = sobol_sample.sample(problem, N, calc_second_order=False, seed=7)
        if len(X) < MIN_SAMPLES:
            print(f"  [警告] 領域『{name}』サンプル数不足 → スキップ")
            continue
        Y = evaluate(X, keys, t)
        d = _indices(problem, Y[response] if response != "feasible"
                     else Y["valid"].astype(float), False, invalid_policy,
                     RESP_PENALTY.get(response, 0.0))
        d.update({"name": name, "n_samples": int(len(X)),
                  "valid_rate": float(np.mean(Y["valid"])), "response": response,
                  "t": t, "override": ov})
        out.append(d)
    return out


def imputation_robustness(mode: str, t: float, N: int, response="Cli", keys=None):
    """代入方針（median vs penalty）で ST 順位が変わらないか比較。"""
    keys = keys or XKEYS
    a_med = analyze_mode(mode, t, N, keys, True, "median")[response]
    a_pen = analyze_mode(mode, t, N, keys, True, "penalty")[response]
    def rank(d): return [keys[i] for i in np.argsort(-np.array(d["ST"]))]
    return {"median": a_med, "penalty": a_pen,
            "rank_median": rank(a_med), "rank_penalty": rank(a_pen),
            "top_stable": rank(a_med)[:3] == rank(a_pen)[:3]}

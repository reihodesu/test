"""explorer/sensitivity.py — 保存劣化モデルの Sobol 感度解析（報告書準拠 v2, 多応答）

microstrip_sobol_analysis の sobol_analysis.py を転用し、evaluate() を DC_v5 実式
（degradation.py）に差し替え。主応答は 放電後電圧 y_end と 限界Li塩濃度 Cli の 2 つ。

README「保存劣化モデルへの転用」の 3 追加:
  ① 時間依存（B-4③）: 応答ごとの ST 時間推移 → 支配因子の変遷
  ② 独立性（B-4②）  : 独立上流変数のみ DOE、セル設計計算は評価関数内部
  ③ 分布モード（B-4①）: design=一様 / variation=3σ正規

MOP（サロゲート）非経由の直接モンテカルロ（CoP 品質非依存）。
物理妥当域マスキング（B-4④）は degradation 側で無効化し、除外率を記録・警告。
"""
from __future__ import annotations

import numpy as np
from SALib.sample import sobol as sobol_sample
from SALib.analyze import sobol as sobol_analyze

from .config import XKEYS, make_problem, TIME_GRID, T_REF, RESPONSES
from .degradation import evaluate

NAN_WARN = 0.30


def _sobol_of_Y(problem, y_raw, ok, calc_second_order=True):
    y = y_raw.copy()
    nan_rate = float(np.mean(~np.isfinite(y)))
    if nan_rate > 0:
        y = np.where(np.isfinite(y), y, np.nanmedian(y))
    Si = sobol_analyze.analyze(problem, y, calc_second_order=calc_second_order,
                               print_to_console=False, seed=3)
    return {
        "S1": Si["S1"].tolist(), "S1_conf": Si["S1_conf"].tolist(),
        "ST": Si["ST"].tolist(), "ST_conf": Si["ST_conf"].tolist(),
        "S2": np.nan_to_num(np.array(Si["S2"])).tolist() if calc_second_order else None,
        "nan_rate": nan_rate, "valid_rate": float(np.mean(ok)),
        "var": float(np.nanvar(y_raw)),
    }


def analyze_at(mode: str, t: float, N: int, response: str = "y_end",
               calc_second_order=True, keys=None, problem=None):
    """指定モード・時点・応答で Sobol 指標を算出。"""
    keys = keys or XKEYS
    problem = problem or make_problem(mode, keys)
    X = sobol_sample.sample(problem, N, calc_second_order=calc_second_order, seed=3)
    Y = evaluate(X, keys, t)
    d = _sobol_of_Y(problem, Y[response], Y["valid"], calc_second_order)
    d["n_samples"] = int(len(X))
    d["response"] = response
    if d["nan_rate"] > NAN_WARN:
        print(f"  [警告] {mode}/{response} t={t}yr 除外率 {d['nan_rate']:.1%}"
              f" — 指標が外挿/非物理領域に引っ張られている可能性(B-4④)")
    return d


def time_evolution(mode: str, N: int, response: str = "y_end",
                   times=None, keys=None):
    """感度指標の時間推移（B-4③）: 各時点で ST を算出（応答別）。"""
    keys = keys or XKEYS
    times = times or TIME_GRID
    problem = make_problem(mode, keys)
    ST, STc, nanr = [], [], []
    for t in times:
        X = sobol_sample.sample(problem, N, calc_second_order=False, seed=3)
        Y = evaluate(X, keys, t)
        d = _sobol_of_Y(problem, Y[response], Y["valid"], calc_second_order=False)
        ST.append(d["ST"]); STc.append(d["ST_conf"]); nanr.append(d["nan_rate"])
    return {"times": list(times), "ST": ST, "ST_conf": STc, "nan_rate": nanr,
            "keys": keys, "mode": mode, "response": response}


def mode_fraction_over_time(mode: str, N: int, times=None, keys=None):
    """保存時間に対する『拡散劣化モード』個体割合と成立率（支配モードの変遷）。"""
    keys = keys or XKEYS
    times = times or TIME_GRID
    problem = make_problem(mode, keys)
    X = sobol_sample.sample(problem, N, calc_second_order=False, seed=9)
    diff_frac, ok_frac, valid_frac = [], [], []
    for t in times:
        Y = evaluate(X, keys, t)
        v = Y["valid"]
        diff = np.where(v, Y["ndc"] > 1.0, False)
        ok = v & (Y["y_end"] >= RESPONSES["y_end"]["thr"]) & \
            (Y["Cli"] <= RESPONSES["Cli"]["thr"])
        diff_frac.append(float(np.mean(diff[v])) if v.any() else np.nan)
        ok_frac.append(float(np.mean(ok)))
        valid_frac.append(float(np.mean(v)))
    return {"times": list(times), "diffusion_frac": diff_frac,
            "ok_frac": ok_frac, "valid_frac": valid_frac, "mode": mode}


def convergence(mode: str, t: float, response: str = "y_end",
                Ns=(64, 128, 256, 512, 1024), keys=None):
    keys = keys or XKEYS
    problem = make_problem(mode, keys)
    rows = []
    for N in Ns:
        X = sobol_sample.sample(problem, N, calc_second_order=False, seed=5)
        Y = evaluate(X, keys, t)
        y = np.where(np.isfinite(Y[response]), Y[response], np.nanmedian(Y[response]))
        Si = sobol_analyze.analyze(problem, y, calc_second_order=False,
                                   print_to_console=False, seed=5)
        rows.append({"N": N, "n_samples": int(len(X)),
                     "ST": Si["ST"].tolist(), "ST_conf": Si["ST_conf"].tolist()})
    return rows

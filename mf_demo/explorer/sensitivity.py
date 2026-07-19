"""explorer/sensitivity.py — 保存劣化モデルの Sobol 感度解析

microstrip_sobol_analysis の sobol_analysis.py を転用し、evaluate() を DC_v5 実式
（degradation.py）に差し替えたもの。README「保存劣化モデルへの転用」の 3 追加を実装:

  ① 時間依存性（B-4③）: 評価時点ごとの感度＋感度指標の時間推移
  ② 独立性（B-4②）    : 独立上流変数のみ DOE、セル設計計算は評価関数内部
  ③ 分布モード（B-4①）: design=一様 / variation=正規3σ を切替（config.make_problem）
  ④ 物理妥当域マスク（B-4④）: 無効サンプルを除外率として記録・警告

MOP（サロゲート）は経由せず理論式を直接モンテカルロで叩く（CoP 品質非依存）。
"""
from __future__ import annotations

import numpy as np
from SALib.sample import sobol as sobol_sample
from SALib.analyze import sobol as sobol_analyze

from .config import XKEYS, make_problem, TIME_GRID, SEED
from .degradation import evaluate

T_REF = 5.0            # 主要図の基準時点 [year]
NAN_WARN = 0.30        # 除外率がこれを超えたら警告（B-4④）


def _sobol_of_Y(problem, ret, ok, calc_second_order=True):
    """応答配列 → Sobol 指標。無効サンプルは中央値代入（除外率を記録）。"""
    y = ret.copy()
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
        "var": float(np.nanvar(ret)),
    }


def analyze_at(mode: str, t: float, N: int, calc_second_order=True,
               keys=None, problem=None):
    """指定モード・時点で Sobol 指標を算出。"""
    keys = keys or XKEYS
    problem = problem or make_problem(mode, keys)
    X = sobol_sample.sample(problem, N, calc_second_order=calc_second_order, seed=3)
    ret, ok = evaluate(X, keys, t)
    d = _sobol_of_Y(problem, ret, ok, calc_second_order)
    d["n_samples"] = int(len(X))
    if d["nan_rate"] > NAN_WARN:
        print(f"  [警告] {mode} t={t}yr 除外率 {d['nan_rate']:.1%} > {NAN_WARN:.0%}"
              f" — 指標が外挿/非物理領域に引っ張られている可能性")
    return d


def time_evolution(mode: str, N: int, times=None, keys=None):
    """感度指標の時間推移（B-4③）: 各時点で ST を算出。"""
    keys = keys or XKEYS
    times = times or TIME_GRID
    problem = make_problem(mode, keys)
    ST, STc, nanr = [], [], []
    for t in times:
        d = analyze_at(mode, t, N, calc_second_order=False, keys=keys, problem=problem)
        ST.append(d["ST"]); STc.append(d["ST_conf"]); nanr.append(d["nan_rate"])
    return {"times": list(times), "ST": ST, "ST_conf": STc, "nan_rate": nanr,
            "keys": keys, "mode": mode}


def convergence(mode: str, t: float, Ns=(64, 128, 256, 512, 1024), keys=None):
    """ST の収束と 95% 信頼区間。"""
    keys = keys or XKEYS
    problem = make_problem(mode, keys)
    rows = []
    for N in Ns:
        X = sobol_sample.sample(problem, N, calc_second_order=False, seed=5)
        ret, ok = evaluate(X, keys, t)
        y = np.where(np.isfinite(ret), ret, np.nanmedian(ret))
        Si = sobol_analyze.analyze(problem, y, calc_second_order=False,
                                   print_to_console=False, seed=5)
        rows.append({"N": N, "n_samples": int(len(X)),
                     "ST": Si["ST"].tolist(), "ST_conf": Si["ST_conf"].tolist()})
    return rows

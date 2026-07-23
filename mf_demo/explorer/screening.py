"""explorer/screening.py — ①感度スクリーニング＋制約評価（報告書準拠 v2）

- generate_population : 設計母集団（LHS）を評価（放電後電圧・限界Li塩濃度・成立OK/NG）
- screen_by_sensitivity : Sobol ST から「効く変数」を自動抽出（→並行座標へ反映）

設計成立条件（報告書 NCR2170JB Step2）:
    放電後電圧 y_end >= 2.5V  かつ  限界Li塩濃度 Cli <= 1.4M   @ 5年保存後

「並行座標は交互作用の表現が構造的に苦手」なので、どの軸に注目すべきかを
感度解析（ST）で決め、並行座標へ自動反映するのが①の狙い。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .config import XKEYS, VARSPEC, SEED, T_REF, RESPONSES
from .degradation import responses_at

Y_MIN = RESPONSES["y_end"]["thr"]   # 放電後電圧 >= 2.5V
CLI_MAX = RESPONSES["Cli"]["thr"]   # 限界Li塩濃度 <= 1.4M


def eval_design(x: dict, t: float = T_REF) -> dict:
    r = responses_at(x, t)
    c_volt = bool(r["valid"] and np.isfinite(r["y_end"]) and r["y_end"] >= Y_MIN)
    c_cli = bool(r["valid"] and np.isfinite(r["Cli"]) and r["Cli"] <= CLI_MAX)
    return {"y_end": r["y_end"], "Cli": r["Cli"], "ndc": r["ndc"],
            "mode": r["mode"], "valid": r["valid"],
            "c_volt": c_volt, "c_cli": c_cli,
            "ok": bool(r["valid"] and c_volt and c_cli)}


def generate_population(N: int = 600, t: float = T_REF, seed: int = SEED) -> pd.DataFrame:
    """設計母集団（LHS）を生成して評価。並行座標・コンターの元データ。"""
    lo = np.array([VARSPEC[k]["design"][0] for k in XKEYS])
    hi = np.array([VARSPEC[k]["design"][1] for k in XKEYS])
    U = qmc.LatinHypercube(d=len(XKEYS), seed=seed).random(N)
    X = lo + U * (hi - lo)
    rows = []
    for row in X:
        x = {k: float(v) for k, v in zip(XKEYS, row)}
        rows.append({**x, **eval_design(x, t)})
    return pd.DataFrame(rows)


def screen_by_sensitivity(ST, keys=None, method="cumulative",
                          thresh=0.90, st_floor=0.05) -> list[str]:
    """Sobol ST から「効く変数」を自動抽出（並行座標の能動軸）。"""
    keys = keys or XKEYS
    st = np.array([ST[k] for k in keys]) if isinstance(ST, dict) \
        else np.array(ST, dtype=float)
    order = np.argsort(-st)
    if method == "threshold":
        return [keys[i] for i in order if st[i] >= st_floor]
    total = st.sum() if st.sum() > 0 else 1.0
    acc, active = 0.0, []
    for i in order:
        if st[i] < st_floor and active:
            break
        active.append(keys[i]); acc += st[i]
        if acc / total >= thresh:
            break
    return active

"""explorer/screening.py — ①感度スクリーニング＋制約評価

設計探索アーキテクチャの中核ロジック:
  - generate_population : 設計母集団（LHS）を評価（維持率・容量・制約OK/NG）
  - screen_by_sensitivity : Sobol ST から「効く変数」を自動抽出（→並行座標へ反映）
  - 制約定義（寿命・容量）→ OK/NG（コンター/並行座標で共通利用）

「並行座標は交互作用の表現が構造的に苦手」なので、どの軸に注目すべきかを
感度解析（ST）で決め、並行座標へ自動反映するのが①の狙い。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .config import XKEYS, VARSPEC, SEED
from .cell_design import cell_design
from .degradation import retention_at

# --- 設計制約（局所地形の OK/NG 判定に共通利用） ---------------------------
RET_TARGET = 0.70        # 容量維持率 @ 基準年 >= 0.70（寿命要件）
TYP_MIN = 3.5            # セル容量 Typ ≥ 3.5 Ah（容量要件）
T_REF = 5.0              # 制約評価の基準保存年


def eval_design(x: dict, t: float = T_REF) -> dict:
    """設計 1 点 → 維持率・容量・制約OK/NG。"""
    cell = cell_design(x["coat_load"], x["mix_density"], x["am_frac"], x["am_cap"])
    ret, valid = retention_at(x, t)
    c_life = np.isfinite(ret) and ret >= RET_TARGET
    c_cap = cell.Typ >= TYP_MIN
    return {"retention": ret, "Typ": cell.Typ, "valid": valid,
            "c_life": bool(c_life), "c_cap": bool(c_cap),
            "ok": bool(valid and c_life and c_cap)}


def generate_population(N: int = 600, t: float = T_REF, seed: int = SEED) -> pd.DataFrame:
    """設計母集団（LHS）を生成して評価。並行座標・コンターの元データ。"""
    lo = np.array([VARSPEC[k]["design"][0] for k in XKEYS])
    hi = np.array([VARSPEC[k]["design"][1] for k in XKEYS])
    sampler = qmc.LatinHypercube(d=len(XKEYS), seed=seed)
    U = sampler.random(N)
    X = lo + U * (hi - lo)
    rows = []
    for row in X:
        x = {k: float(v) for k, v in zip(XKEYS, row)}
        m = eval_design(x, t)
        rows.append({**x, **m})
    return pd.DataFrame(rows)


def screen_by_sensitivity(ST: dict | list, keys=None,
                          method: str = "cumulative", thresh: float = 0.90,
                          st_floor: float = 0.05) -> list[str]:
    """Sobol ST から「効く変数」を自動抽出（並行座標に反映する能動軸）。

    method:
      cumulative : ST 降順で累積寄与が thresh に達するまで採用（かつ ST≥st_floor）
      threshold  : ST ≥ st_floor の変数を採用
    """
    keys = keys or XKEYS
    st = np.array(ST, dtype=float) if not isinstance(ST, dict) \
        else np.array([ST[k] for k in keys])
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

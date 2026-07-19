"""
設計変数 -> 評価指標 の評価ヘルパ (LF/HF 共通窓口)。
DOE 評価・最適化目的関数・検証で共通利用する。
"""
from __future__ import annotations

import numpy as np

from . import geometry, lowfidelity, highfidelity, metrics
from . import C0, F_DESIGN

# 周波数格子
F_LF = np.linspace(2.0e9, 3.0e9, 501)          # LTSpice: 2MHz 分解能
F_HF = np.arange(2.0e9, 3.0001e9, 20e6)        # FEM: 20MHz 分解能(粗い)


def eval_lf(X):
    geo = geometry.build_geometry(X, F_DESIGN, C0)
    s = lowfidelity.s11(geo, F_LF, C0)
    return metrics.extract_metrics(F_LF, s, refine=False)


def eval_hf(X, rng=None, noise_db=0.0015):
    """高忠実度評価。FEM の 20MHz 格子 + 後処理スプライン補間 + 微小離散化ノイズ。

    資料 p.40「スプライン補完してもなお QL が大きい(=鋭い共振)は S11 最低値に
    大きな誤差が含まれる」を再現するため、高QL点では 20MHz 格子が真の谷を捉え
    きれず |S11min| が浅く見える系統誤差を付与する(undersampling failure)。
    この誤差は QL>30 データ選別(資料 p.40)で除去される。
    """
    geo = geometry.build_geometry(X, F_DESIGN, C0)
    s = highfidelity.s11(geo, F_HF, C0, rng=rng, noise_db=noise_db)
    m = metrics.extract_metrics(F_HF, s, refine=True)
    if m.valid and np.isfinite(m.QL) and m.QL > 30 and rng is not None:
        # 谷幅 Δf=f0/QL が格子間隔(20MHz)に近づくほど真の谷を外し、浅く見える。
        df_grid = 20e6
        bw = m.f0 / m.QL                      # 半電力帯域幅
        severity = np.clip(df_grid / bw, 0.0, 1.0)   # 0(緩)〜1(格子で解像不能)
        bias = severity * (1.0 - m.s11min) * (0.3 + 0.7 * rng.random())
        s11_meas = float(np.clip(m.s11min + bias, 0.0, 1.0))
        m = metrics.Metrics(m.f0, s11_meas, m.QL, m.valid, m.reason)
    return m


def eval_hf_fine(X, df=5e6):
    """FEM 精密計算 (資料 p.46「周波数分解能5MHzのFEM精密計算」)。"""
    geo = geometry.build_geometry(X, F_DESIGN, C0)
    fgrid = np.arange(2.0e9, 3.0001e9, df)
    s = highfidelity.s11(geo, fgrid, C0)
    return metrics.extract_metrics(fgrid, s, refine=False), fgrid, s


def _row(m):
    """Metrics -> (f0[GHz], s11min, log10(QL), valid)。"""
    if not m.valid or not np.isfinite(m.QL) or m.QL <= 0:
        return np.nan, np.nan, np.nan, False
    return m.f0 / 1e9, m.s11min, np.log10(m.QL), True


def evaluate_doe(X_lf, X_hf, seed=7):
    """DOE 全点を評価し、目的量の配列と有効マスクを返す。

    戻り値 dict:
        Y_lf, Y_hf : (n,3) [f0GHz, s11min, log10QL]
        v_lf, v_hf : 有効マスク
    """
    rng = np.random.default_rng(seed)
    Ylf, vlf = [], []
    for x in X_lf:
        r = _row(eval_lf(x))
        Ylf.append(r[:3]); vlf.append(r[3])
    Ylf, vlf = np.array(Ylf, float), np.array(vlf, bool)
    Yhf, vhf = [], []
    for x in X_hf:
        r = _row(eval_hf(x, rng=rng))
        Yhf.append(r[:3]); vhf.append(r[3])
    return {
        "Y_lf": Ylf, "v_lf": vlf,
        "Y_hf": np.array(Yhf, float), "v_hf": np.array(vhf, bool),
    }


LABELS = ["f0 [GHz]", "|S11min|", "log10(QL)"]

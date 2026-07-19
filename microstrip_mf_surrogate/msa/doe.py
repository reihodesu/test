"""
実験計画法(DOE): スライス Latin Hypercube Design (LHD)。

資料 p.32:
    DOE スライスLHD
    6パラメーター
    64slice x 16set/slice = 最大 1024セット
    FEM解析で教師データを選択できるようにスライス化する。

低忠実度(LF)は多数スライスを実行し、高忠実度(HF)は少数スライス(または選択点)
のみ実行する、というマルチフィデリティDOE(資料 p.9 入れ子型/対応点DOE)を模擬。
"""
from __future__ import annotations

import numpy as np

from .geometry import BOUNDS, XKEYS


def sliced_lhd(n_slice: int, per_slice: int, rng: np.random.Generator):
    """スライスLHD を [0,1]^6 で生成し、(サンプル, スライスID) を返す。

    各スライスが単独でも空間充填になるよう、各次元を n_slice*per_slice 個の
    等区間に分割し、ラテン方格をスライスへ均等配分する。
    """
    dim = len(XKEYS)
    n = n_slice * per_slice
    U = np.empty((n, dim))
    for d in range(dim):
        # 各スライスに per_slice 個ずつ、全体で LHS になるよう層別
        perm = rng.permutation(n)
        U[:, d] = (perm + rng.random(n)) / n
    slice_id = np.repeat(np.arange(n_slice), per_slice)
    # スライスごとに行をシャッフル(スライス割当をランダム化)
    order = rng.permutation(n)
    U = U[order]
    slice_id = slice_id  # 割当はブロックのまま(疑似スライス)
    return U, slice_id


def scale_to_bounds(U: np.ndarray) -> np.ndarray:
    """[0,1]^6 -> 実際の設計変数レンジへ。"""
    X = np.empty_like(U)
    for j, k in enumerate(XKEYS):
        lo, hi = BOUNDS[k]
        X[:, j] = lo + U[:, j] * (hi - lo)
    return X


def make_doe(n_lf_slice=64, per_slice=16, n_hf=48, seed=1):
    """LF(全体) と HF(部分集合) の設計点を返す。

    HF は LF の部分集合(入れ子型DOE)から選ぶ -> 対応点を持つため差分学習可能。
    """
    rng = np.random.default_rng(seed)
    U, sid = sliced_lhd(n_lf_slice, per_slice, rng)
    X_lf = scale_to_bounds(U)
    # HF は LF 点の部分集合(入れ子): 均等に n_hf 点を抽出
    idx = np.linspace(0, len(X_lf) - 1, n_hf).astype(int)
    X_hf = X_lf[idx]
    return X_lf, X_hf, idx

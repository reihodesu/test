"""
多目的最適化: NSGA-II (資料 p.44「遺伝的アルゴリズム NSGA-II」)。

サロゲートモデル上で、|S11min| と log(QL) を同時最小化するパレート解を求める
(資料 p.44「多目的最適化とは目的変数がトレードオフにある時に両者の関係を求める」)。
f0 が仕様帯域から外れる設計は制約違反としてペナルティを与える。

外部依存(pymoo等)を避け、非優越ソート + 混雑度 + SBX交叉 + 多項式突然変異の
コンパクトな NSGA-II を自前実装する。
"""
from __future__ import annotations

import numpy as np


def _fast_nondominated_sort(F):
    n = len(F)
    S = [[] for _ in range(n)]
    ndom = np.zeros(n, int)
    fronts = [[]]
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(F[p], F[q]):
                S[p].append(q)
            elif _dominates(F[q], F[p]):
                ndom[p] += 1
        if ndom[p] == 0:
            fronts[0].append(p)
    i = 0
    while fronts[i]:
        nxt = []
        for p in fronts[i]:
            for q in S[p]:
                ndom[q] -= 1
                if ndom[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    return fronts[:-1]


def _dominates(a, b):
    return np.all(a <= b) and np.any(a < b)


def _crowding(F):
    n = len(F)
    if n == 0:
        return np.array([])
    d = np.zeros(n)
    for m in range(F.shape[1]):
        order = np.argsort(F[:, m])
        d[order[0]] = d[order[-1]] = np.inf
        fmin, fmax = F[order[0], m], F[order[-1], m]
        if fmax - fmin < 1e-12:
            continue
        for k in range(1, n - 1):
            d[order[k]] += (F[order[k + 1], m] - F[order[k - 1], m]) / (fmax - fmin)
    return d


def _sbx(p1, p2, rng, eta=15, pc=0.9):
    c1, c2 = p1.copy(), p2.copy()
    if rng.random() > pc:
        return c1, c2
    for i in range(len(p1)):
        if rng.random() <= 0.5 and abs(p1[i] - p2[i]) > 1e-12:
            u = rng.random()
            beta = (2 * u) ** (1 / (eta + 1)) if u <= 0.5 else (1 / (2 * (1 - u))) ** (1 / (eta + 1))
            c1[i] = 0.5 * ((1 + beta) * p1[i] + (1 - beta) * p2[i])
            c2[i] = 0.5 * ((1 - beta) * p1[i] + (1 + beta) * p2[i])
    return np.clip(c1, 0, 1), np.clip(c2, 0, 1)


def _poly_mut(x, rng, eta=20, pm=None):
    x = x.copy()
    if pm is None:
        pm = 1.0 / len(x)
    for i in range(len(x)):
        if rng.random() < pm:
            u = rng.random()
            if u < 0.5:
                delta = (2 * u) ** (1 / (eta + 1)) - 1
            else:
                delta = 1 - (2 * (1 - u)) ** (1 / (eta + 1))
            x[i] = np.clip(x[i] + delta, 0, 1)
    return x


def nsga2(eval_fn, dim, pop=80, gen=60, seed=0):
    """NSGA-II 本体。

    eval_fn(U) : (pop, dim) の [0,1] 正規化設計 -> (F, G)
                 F=(pop, n_obj) 目的(最小化), G=(pop,) 制約違反量(<=0 で満足)
    戻り値: 最終世代の U, F, G
    """
    rng = np.random.default_rng(seed)
    P = rng.random((pop, dim))
    F, G = eval_fn(P)

    def rank_key(U, F, G):
        # 制約付き: 実行可能解を優先し、その中で非優越ソート
        feas = G <= 0
        ranks = np.full(len(U), 1 << 30)
        cd = np.zeros(len(U))
        # 実行可能グループ
        for grp_mask, base in [(feas, 0)]:
            idx = np.where(grp_mask)[0]
            if len(idx):
                fronts = _fast_nondominated_sort(F[idx])
                for r, fr in enumerate(fronts):
                    sub = idx[fr]
                    ranks[sub] = base + r
                    cd[sub] = _crowding(F[sub])
        # 実行不可グループ: 制約違反量でランク付け(実行可能解より必ず後ろ)
        idx = np.where(~feas)[0]
        if len(idx):
            order = idx[np.argsort(G[idx])]
            ranks[order] = (1 << 20) + np.arange(len(order))
            cd[order] = 0.0
        return ranks, cd

    for _ in range(gen):
        ranks, cd = rank_key(P, F, G)
        # トーナメント選択で親を選ぶ
        def tour():
            a, b = rng.integers(0, len(P), 2)
            if ranks[a] < ranks[b] or (ranks[a] == ranks[b] and cd[a] > cd[b]):
                return P[a]
            return P[b]
        # 子生成
        Q = []
        while len(Q) < pop:
            c1, c2 = _sbx(tour(), tour(), rng)
            Q.append(_poly_mut(c1, rng)); Q.append(_poly_mut(c2, rng))
        Q = np.array(Q[:pop])
        FQ, GQ = eval_fn(Q)
        # 親子合併から次世代を選抜
        R = np.vstack([P, Q]); FR = np.vstack([F, FQ]); GR = np.concatenate([G, GQ])
        ranks, cd = rank_key(R, FR, GR)
        order = sorted(range(len(R)), key=lambda i: (ranks[i], -cd[i]))[:pop]
        P, F, G = R[order], FR[order], GR[order]

    ranks, cd = rank_key(P, F, G)
    feas = G <= 0
    if feas.any():
        pf = _fast_nondominated_sort(F[feas])[0]
        front_idx = np.where(feas)[0][pf]
    else:
        front_idx = np.array([int(np.argmin(G))])
    return P, F, G, front_idx

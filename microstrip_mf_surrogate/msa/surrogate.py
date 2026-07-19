"""
サロゲートモデル: ガウス過程回帰と2種のマルチフィデリティ統合。

資料 p.19, p.38-39 の3方式を実装:

  1. HF-only        : 高忠実度データのみのガウス過程 (少数点 -> 不確かさ大)
  2. Multi-fidelity : 差分補正型 (Additive Correction)
                      w_HF = w_LF_hat + δ(x)   (資料の残差補正型, ρ=1)
  3. Data Fusion    : co-kriging (AR1, Le Gratiet)
                      w_HF = ρ * w_LF_hat + δ(x)   (相関ρを学習)

いずれも出力は「予測値 + 予測の不確かさ(標準偏差)」を返す(資料 p.6 の
エラーバー付き予測)。SCVR(標準化CV誤差)で方式間を比較する(資料 p.39)。
"""
from __future__ import annotations

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel

from .geometry import BOUNDS, XKEYS


def _normalize(X):
    """設計変数を [0,1]^6 に正規化。"""
    X = np.atleast_2d(np.asarray(X, float))
    U = np.empty_like(X)
    for j, k in enumerate(XKEYS):
        lo, hi = BOUNDS[k]
        U[:, j] = (X[:, j] - lo) / (hi - lo)
    return U


def _make_gp(noise=1e-4, n_restarts=1):
    kernel = (ConstantKernel(1.0, (1e-3, 1e3))
              * Matern(length_scale=np.ones(len(XKEYS)),
                       length_scale_bounds=(1e-2, 1e2), nu=2.5)
              + WhiteKernel(noise, (1e-8, 1e0)))
    return GaussianProcessRegressor(kernel=kernel, normalize_y=True,
                                    n_restarts_optimizer=n_restarts, alpha=1e-8)


class GP:
    """単一忠実度ガウス過程 (予測値 + 標準偏差)。"""

    def __init__(self):
        self.gp = _make_gp()

    def fit(self, X, y):
        self.gp.fit(_normalize(X), np.asarray(y, float))
        return self

    def predict(self, X):
        mu, sd = self.gp.predict(_normalize(X), return_std=True)
        return mu, sd


class MultiFidelity:
    """差分補正型マルチフィデリティ (Additive Correction, ρ=1)。

    gp_lf を外部から与えると LF GP の再学習を省ける(LOO高速化)。
    """

    def __init__(self, gp_lf=None):
        self.gp_lf = gp_lf if gp_lf is not None else _make_gp()
        self._lf_prefit = gp_lf is not None
        self.gp_d = _make_gp()

    def fit(self, X_lf, y_lf, X_hf, y_hf):
        if not self._lf_prefit:
            self.gp_lf.fit(_normalize(X_lf), np.asarray(y_lf, float))
        mu_lf_at_hf = self.gp_lf.predict(_normalize(X_hf))
        resid = np.asarray(y_hf, float) - mu_lf_at_hf
        self.gp_d.fit(_normalize(X_hf), resid)
        return self

    def predict(self, X):
        U = _normalize(X)
        mu_lf, sd_lf = self.gp_lf.predict(U, return_std=True)
        mu_d, sd_d = self.gp_d.predict(U, return_std=True)
        mu = mu_lf + mu_d
        sd = np.sqrt(sd_lf ** 2 + sd_d ** 2)
        return mu, sd


class DataFusion:
    """データフュージョン: AR1 co-kriging (相関 ρ を学習)。"""

    def __init__(self, gp_lf=None):
        self.gp_lf = gp_lf if gp_lf is not None else _make_gp()
        self._lf_prefit = gp_lf is not None
        self.gp_d = _make_gp()
        self.rho = 1.0
        self.b = 0.0

    def fit(self, X_lf, y_lf, X_hf, y_hf):
        if not self._lf_prefit:
            self.gp_lf.fit(_normalize(X_lf), np.asarray(y_lf, float))
        mu_lf_at_hf = self.gp_lf.predict(_normalize(X_hf))
        y_hf = np.asarray(y_hf, float)
        # ρ と定数項を最小二乗で推定: y_hf ≈ ρ*mu_lf + b
        A = np.vstack([mu_lf_at_hf, np.ones_like(mu_lf_at_hf)]).T
        coef, *_ = np.linalg.lstsq(A, y_hf, rcond=None)
        self.rho, self.b = float(coef[0]), float(coef[1])
        resid = y_hf - (self.rho * mu_lf_at_hf + self.b)
        self.gp_d.fit(_normalize(X_hf), resid)
        return self

    def predict(self, X):
        U = _normalize(X)
        mu_lf, sd_lf = self.gp_lf.predict(U, return_std=True)
        mu_d, sd_d = self.gp_d.predict(U, return_std=True)
        mu = self.rho * mu_lf + self.b + mu_d
        sd = np.sqrt((self.rho * sd_lf) ** 2 + sd_d ** 2)
        return mu, sd


def _prefit_lf(X_lf, y_lf):
    """LF GP を一度だけ学習して返す(LOO で使い回す)。"""
    gp = _make_gp()
    gp.fit(_normalize(X_lf), np.asarray(y_lf, float))
    return gp


def _make_model(kind, gp_lf):
    if kind == "HF_only":
        return GP()
    if kind == "MultiFidelity":
        return MultiFidelity(gp_lf=gp_lf)
    if kind == "DataFusion":
        return DataFusion(gp_lf=gp_lf)
    raise ValueError(kind)


def scvr(kind, X_lf, y_lf, X_hf, y_hf):
    """Standardized CV Error (leave-one-out, HF点) を計算 (資料 p.39)。

    kind: "HF_only" | "MultiFidelity" | "DataFusion"。
    定義: 標準化CV誤差 = RMSE_LOO / std(y_HF)。
      1.0 = 「平均値で予測」と同等 (無情報)、0 に近いほど良い。
      資料 p.39 の値域(f0~0.09, s11min~0.79 等)と整合する正規化RMSE。
    LF GP は1度だけ学習して各foldで使い回す(高速化)。
    """
    X_hf = np.atleast_2d(X_hf)
    y_hf = np.asarray(y_hf, float)
    n = len(X_hf)
    gp_lf = _prefit_lf(X_lf, y_lf) if kind != "HF_only" else None
    err = np.empty(n)
    for i in range(n):
        mask = np.ones(n, bool); mask[i] = False
        m = _make_model(kind, gp_lf)
        if kind == "HF_only":
            m.fit(X_hf[mask], y_hf[mask])
        else:
            m.fit(X_lf, y_lf, X_hf[mask], y_hf[mask])
        mu, _ = m.predict(X_hf[i:i + 1])
        err[i] = y_hf[i] - float(mu[0])
    sd = np.std(y_hf)
    if sd < 1e-12:
        sd = 1.0
    return float(np.sqrt(np.mean(err ** 2)) / sd)


def scvr_poison(kind, X_lf, y_lf, X_hf, y_hf, clean_mask):
    """データ選別効果を公平に評価 (資料 p.40)。

    評価対象は常に「クリーン点(QL≤30)」に固定し、学習集合だけを変える:
      before : 全HF点で学習 (汚染された高QL点を含む)
      after  : クリーン点のみで学習
    いずれもクリーン点上の LOO 正規化RMSE を返す。高QL点が汚染要因なら
    before > after となり、選別で精度が上がることを示す。
    """
    X_hf = np.atleast_2d(X_hf)
    y_hf = np.asarray(y_hf, float)
    clean_idx = np.where(clean_mask)[0]
    gp_lf = _prefit_lf(X_lf, y_lf) if kind != "HF_only" else None
    eb, ea = [], []
    for i in clean_idx:
        # after: クリーン点のみ(自分を除く)で学習
        m_after = _make_model(kind, gp_lf)
        tr_after = clean_mask.copy(); tr_after[i] = False
        # before: 全点(自分を除く)で学習
        m_before = _make_model(kind, gp_lf)
        tr_before = np.ones(len(X_hf), bool); tr_before[i] = False
        if kind == "HF_only":
            m_after.fit(X_hf[tr_after], y_hf[tr_after])
            m_before.fit(X_hf[tr_before], y_hf[tr_before])
        else:
            m_after.fit(X_lf, y_lf, X_hf[tr_after], y_hf[tr_after])
            m_before.fit(X_lf, y_lf, X_hf[tr_before], y_hf[tr_before])
        ea.append(y_hf[i] - float(m_after.predict(X_hf[i:i+1])[0][0]))
        eb.append(y_hf[i] - float(m_before.predict(X_hf[i:i+1])[0][0]))
    sd = np.std(y_hf[clean_mask])
    sd = sd if sd > 1e-12 else 1.0
    return (float(np.sqrt(np.mean(np.square(eb))) / sd),
            float(np.sqrt(np.mean(np.square(ea))) / sd))


def loo_pred(kind, X_lf, y_lf, X_hf, y_hf):
    """LOO 予測値 (予測 vs 実測 散布図用)。"""
    X_hf = np.atleast_2d(X_hf)
    y_hf = np.asarray(y_hf, float)
    n = len(X_hf)
    gp_lf = _prefit_lf(X_lf, y_lf) if kind != "HF_only" else None
    mu = np.empty(n)
    for i in range(n):
        mask = np.ones(n, bool); mask[i] = False
        m = _make_model(kind, gp_lf)
        if kind == "HF_only":
            m.fit(X_hf[mask], y_hf[mask])
        else:
            m.fit(X_lf, y_lf, X_hf[mask], y_hf[mask])
        mu[i] = float(m.predict(X_hf[i:i + 1])[0][0])
    return mu

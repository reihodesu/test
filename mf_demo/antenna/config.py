"""antenna/config.py

成果物A（マルチフィデリティ・サロゲートのデモ）共通の設定値。

- 設計変数の範囲・公称点（HANDOVER A-2）
- 物理定数
- matplotlib の日本語フォント設定（図中の文言は日本語：HANDOVER 共通方針）

数値はすべて解析的な「もっともらしさ」を優先した合成値であり、実測較正では
ない。目的は原理を絵で伝えること（HANDOVER 想定質問への回答）。
"""
from __future__ import annotations

import numpy as np

# --- 物理定数 --------------------------------------------------------------
C_LIGHT = 2.99792458e8  # 光速 [m/s]
F_DESIGN_HZ = 2.45e9    # 設計中心周波数 2.45 GHz（ISM 帯）
LAM0 = C_LIGHT / F_DESIGN_HZ  # 自由空間波長 ≈ 0.12237 m

# --- 設計変数（6個）: HANDOVER A-2 -----------------------------------------
# 順序を固定して DOE / サロゲートで共通利用する。
VAR_NAMES = ["X1", "X2", "X3", "X4", "X5", "X6"]
VAR_LABELS = {
    "X1": "X1: パッチ幅/波長",
    "X2": "X2: 下部パッチ幅比",
    "X3": "X3: パッチ長/波長",
    "X4": "X4: 給電オフセット",
    "X5": "X5: 基板厚さ [m]",
    "X6": "X6: 基板比誘電率",
}
# (下限, 上限)
BOUNDS = {
    "X1": (0.15, 0.35),
    "X2": (0.50, 1.00),
    "X3": (0.15, 0.35),   # λ/4 共振近傍で 0.25
    "X4": (-0.10, 0.25),  # 0 = 中央給電
    "X5": (0.0015, 0.005),
    "X6": (1.5, 5.0),
}
BOUNDS_ARR = np.array([BOUNDS[n] for n in VAR_NAMES])  # shape (6, 2)
LOWER = BOUNDS_ARR[:, 0]
UPPER = BOUNDS_ARR[:, 1]
SPAN = UPPER - LOWER

# 公称点（各変数のほぼ中央。X4 は dip 近傍を避けた 0.05 に置く）
NOMINAL = np.array([0.25, 0.75, 0.25, 0.05, 0.00325, 3.25])

# --- 応答（3個）: HANDOVER A-3 ---------------------------------------------
RESP_NAMES = ["f0", "s11min", "log10QL"]
RESP_LABELS = {
    "f0": "f0: 共振周波数 [GHz]",
    "s11min": "s11min: リターンロス最小 |S11|",
    "log10QL": "log10(QL): Loaded Q の常用対数",
}
# 目標帯（図の帯表示・制約抽出に使う）
RESP_TARGET = {
    "f0": (2.44, 2.46),        # 目標帯
    "s11min": (None, 0.316),   # ≤ 0.316 (= -10 dB)
    "log10QL": (None, 1.477),  # ≤ 1.477 (= log10(30))
}

# 再現性: 乱数シードは全て固定（HANDOVER 共通方針）
SEED = 20260719


def clip_to_bounds(X: np.ndarray) -> np.ndarray:
    """設計変数を範囲内にクリップ。"""
    X = np.atleast_2d(np.asarray(X, dtype=float))
    return np.clip(X, LOWER, UPPER)


def setup_japanese_font() -> str:
    """matplotlib の日本語フォントを設定し、使用フォント名を返す。

    環境に応じて IPAGothic 等の CJK フォントを探索。見つからない場合は
    既定フォントのまま（文字化けの可能性あり）。
    """
    import matplotlib
    from matplotlib import font_manager

    candidates = [
        "IPAGothic", "IPAPGothic", "Noto Sans CJK JP",
        "TakaoGothic", "VL Gothic", "Yu Gothic", "MS Gothic",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((c for c in candidates if c in available), None)
    if chosen:
        matplotlib.rcParams["font.family"] = chosen
    matplotlib.rcParams["axes.unicode_minus"] = False  # 負号の文字化け防止
    return chosen or matplotlib.rcParams["font.family"]

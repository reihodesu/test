"""
msa - Microstrip Antenna Multi-Fidelity Surrogate demo package.

KESCO/SmartUQ セミナー資料「後半：マイクロストリップアンテナの設計事例」を
SPDMチームの理解促進のために模擬再現するサンプル実装。

構成:
    hammerstad  : マイクロストリップ線路の特性インピーダンス Z0 / 実効誘電率 eeff
    tline       : 伝送線路ネットワークの周波数応答を解く小型ACソルバ(LTSpice相当)
    geometry    : 無次元設計変数 X1..X6 -> 物理寸法への変換
    lowfidelity : 低忠実度(LF)モデル = LTSpice相当の回路モデル
    highfidelity: 高忠実度(HF)モデル = FEM相当(フリンジング/相互結合/有限分解能)
    metrics     : S11(f) -> f0, |S11min|, QL 抽出とエラーデータ除外
    doe         : スライスLHDによる実験計画
    surrogate   : ガウス過程 / マルチフィデリティ / データフュージョン
    optimize    : NSGA-II 多目的最適化
"""

from . import hammerstad, tline, geometry, lowfidelity, highfidelity, metrics, doe

__all__ = [
    "hammerstad",
    "tline",
    "geometry",
    "lowfidelity",
    "highfidelity",
    "metrics",
    "doe",
]

# 物理定数
C0 = 299_792_458.0  # 光速 [m/s]
Z0_FEED = 50.0      # 給電線の特性インピーダンス [ohm]
F_DESIGN = 2.45e9   # 設計中心周波数 [Hz]

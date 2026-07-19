"""
低忠実度(LF)モデル = 資料の LTSpice 回路モデル相当。

資料 p.33 の前処理の仮定をそのまま実装:
 - 電波の放射位置はアンテナ端部のみ
 - 放射抵抗は R = 90 * (W/λ0)^2 と近似
 - 伝搬速度は sqrt(eeff) で光速を割る
 - 線路インピーダンスは Hammerstad 近似式
 - 合流地点はキルヒホッフ(節点則)のみ、散乱行列は使わない
 - 幅変化による有効容量などは使わない  <- LF ではこれを無視するのが要点

寸法(Geometry) -> (td, Z0, R_rad) に変換して tline.Network を組み、
S11(f) を計算する。「速いが単純」なモデル。
"""
from __future__ import annotations

import numpy as np

from . import hammerstad
from .tline import TLine, Shunt, Network


# 放射(スロット)コンダクタンス G=(1/90)(W/λ0)^2 (Balanis の伝送線路モデル)。
# 放射端は抵抗 R=1/G としてグランドへ接続する(資料の R=90(W/λ0)^2 と同族の形)。
# RAD_CAL は共振の鋭さ(QL)と整合を資料動作点域(QL~10-30)に合わせる縮尺定数。
RAD_CAL = 1.0


def radiation_resistance(w: float, lam0: float) -> float:
    """放射端の等価抵抗 R = 90 / (W/λ0)^2 * RAD_CAL  [ohm]。

    スロット放射コンダクタンス G=(1/90)(W/λ0)^2 の逆数。幅が広いほど良く放射し
    (=Rが小さく)、狭いほど高抵抗になる。過大値は上限でクリップ。
    """
    ratio = max(w / lam0, 1e-3)
    r = RAD_CAL * 90.0 / (ratio ** 2)
    return float(min(r, 5.0e3))


def build_network(geo, c0: float) -> Network:
    """Geometry -> LTSpice相当の伝送線路ネットワーク。"""
    # 各枝の (td, Z0)
    td1, z1, _ = hammerstad.line_params(geo.W1, geo.H, geo.er, geo.Len1, c0)
    td2, z2, _ = hammerstad.line_params(geo.W2, geo.H, geo.er, geo.Len2, c0)
    td3, z3, _ = hammerstad.line_params(geo.W3, geo.H, geo.er, geo.Len3, c0)
    td4, z4, _ = hammerstad.line_params(geo.W4, geo.H, geo.er, geo.Len4, c0)

    # 放射抵抗 (端部の幅で決まる)
    r1 = radiation_resistance(geo.W1, geo.lam0)   # 近接端 (幅 W1)
    r2 = radiation_resistance(geo.W3, geo.lam0)   # 遠方端アーム
    r3 = radiation_resistance(geo.W2, geo.lam0)

    net = Network(
        lines=[
            TLine("N003", "N001", td1, z1),   # T1 -> R1
            TLine("N001", "N002", td2, z2),   # T2 -> R3
            TLine("N001", "N005", td3, z3),   # T3 -> R2
            TLine("N001", "Port1", td4, z4),  # T4 給電線
        ],
        shunts=[
            Shunt("N003", r=r1),
            Shunt("N005", r=r2),
            Shunt("N002", r=r3),
        ],
        port="Port1",
        zref=50.0,
    )
    return net


def s11(geo, freqs: np.ndarray, c0: float) -> np.ndarray:
    return build_network(geo, c0).s11(freqs)

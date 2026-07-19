"""
伝送線路ネットワークの周波数応答を解く小型 AC ソルバ。

資料 p.34 の LTSpice ネットリストを Python で等価に解く:

    T1 N003 0 N001 0 Td=td1 Z0=z1     (放射端1へ)
    T2 N001 0 N002 0 Td=td2 Z0=z2     (放射端3へ)
    T3 N001 0 N005 0 Td=td3 Z0=z3     (放射端2へ)
    T4 N001 0 Port1 0 Td=td4 Z0=z4    (50Ω給電線)
    R1 N003 0 R r_rad1                 (放射抵抗)
    R2 N005 0 R r_rad2
    R3 N002 0 R r_rad3
    V1 Port1 0 AC 1
    .ac lin n_freq freq_min freq_max
    .net V(Port1) V1 Rin=50

節点アドミタンス法(MNA)で各周波数の入力インピーダンス Zin を求め、
S11 = (Zin - Zref)/(Zin + Zref) を返す。

資料 p.33「線路の合流地点キルヒホッフの法則のみ考慮」「散乱行列は使わない」
=> ここでは節点電流則(KCL)でアドミタンス行列を組む素直な実装。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


@dataclass
class TLine:
    """理想伝送線路 (節点 a-b 間、ground 基準)。"""
    a: str
    b: str
    td: float      # 遅延時間 [s]
    z0: float      # 特性インピーダンス [ohm]


@dataclass
class Shunt:
    """節点-ground 間の並列素子 (抵抗 R もしくは容量 C)。"""
    node: str
    r: float = np.inf   # 抵抗 [ohm]
    c: float = 0.0      # 容量 [F] (HFモデルのフリンジング容量用)


@dataclass
class Network:
    lines: list = field(default_factory=list)
    shunts: list = field(default_factory=list)
    port: str = "Port1"
    zref: float = 50.0

    def _nodes(self):
        s = set()
        for ln in self.lines:
            s.add(ln.a); s.add(ln.b)
        for sh in self.shunts:
            s.add(sh.node)
        s.discard("0")  # ground
        return sorted(s)

    def s11(self, freqs: np.ndarray) -> np.ndarray:
        """周波数配列に対する S11 (複素) を返す。周波数方向にバッチ求解。"""
        freqs = np.asarray(freqs, float)
        nodes = self._nodes()
        idx = {n: i for i, n in enumerate(nodes)}
        N = len(nodes)
        p = idx[self.port]
        nf = len(freqs)
        w = 2.0 * np.pi * freqs                      # (nf,)
        Y = np.zeros((nf, N, N), dtype=complex)       # 周波数ごとの節点アドミタンス

        # 伝送線路のスタンプ (2ポート Y 行列; ground 共通)
        for ln in self.lines:
            theta = w * ln.td
            s = np.sin(theta)
            s = np.where(np.abs(s) < 1e-12, 1e-12, s)
            yaa = -1j * np.cos(theta) / (ln.z0 * s)   # -j cot(theta)/Z0
            yab = 1j / (ln.z0 * s)                     #  j/(Z0 sin theta)
            ia = idx.get(ln.a); ib = idx.get(ln.b)
            if ln.a != "0":
                Y[:, ia, ia] += yaa
            if ln.b != "0":
                Y[:, ib, ib] += yaa
            if ln.a != "0" and ln.b != "0":
                Y[:, ia, ib] += yab
                Y[:, ib, ia] += yab
        # 並列素子 (節点-ground)
        for sh in self.shunts:
            y = np.zeros(nf, dtype=complex)
            if np.isfinite(sh.r) and sh.r > 0:
                y += 1.0 / sh.r
            if sh.c > 0:
                y += 1j * w * sh.c
            j = idx[sh.node]
            Y[:, j, j] += y

        # ポートに 1A 注入 -> 節点電圧を解く -> Zin = V(port)
        I = np.zeros((nf, N), dtype=complex)
        I[:, p] = 1.0
        try:
            V = np.linalg.solve(Y, I[..., None])[..., 0]
            zin = V[:, p]
        except np.linalg.LinAlgError:
            zin = np.zeros(nf, dtype=complex)
        return (zin - self.zref) / (zin + self.zref)

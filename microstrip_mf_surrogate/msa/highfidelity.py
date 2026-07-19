"""
高忠実度(HF)モデル = 資料の COMSOL FEM 相当の「モック」。

本サンプルには実 FEM(COMSOL) が無いため、LF回路モデルに対して
「単純モデルが取りこぼす物理」を追加した高忠実度モックを作る。
資料 p.38-39 で述べられる LF/HF の差の特徴を再現する:

  * 「f0では LF(LTSpice) では現れなかった X1(=パッチ幅) による変化が現れる」
      -> フリンジングによる等価長延長 ΔL(W,H,er) を加え、f0 が幅に依存するようにする。
  * 「HFでは Log(QL) や s11min のような複雑な変化」「log(QL)中のdip」
      -> 2つの放射スロット間の相互結合(給電位置 X4 依存)を加え、
         QL に給電位置依存の dip を生じさせる。
  * FEM は周波数分解能 20MHz、後処理でスプライン補間 (資料 p.35, p.40)
      -> 粗い周波数格子 + 微小な離散化ノイズ。

これにより「LFは滑らかで単純」「HFは少数点だが豊かな物理」という
マルチフィデリティの前提が成立し、差分/相関学習の効果を実演できる。

注意: これは定量的に COMSOL を再現するものではなく、資料のストーリー(少数HFを
LFで増幅する)を体験するための教育用モック。定数は資料の動作点近傍に較正済み。
"""
from __future__ import annotations

import numpy as np

from . import hammerstad
from .tline import TLine, Shunt, Network


def _delta_L(w: float, h: float, er: float) -> float:
    """フリンジングによる等価長延長 ΔL (Hammerstad-Kirschning 型)。

    幅 W が広いほど、基板が厚いほど延長が大きい -> f0 が W(=X1) に依存する。
    """
    eeff = hammerstad.eeff_microstrip(w, h, er)
    u = w / h
    dl = 0.412 * h * (eeff + 0.300) * (u + 0.264) / ((eeff - 0.258) * (u + 0.813))
    return float(dl)


def build_network(geo, c0: float,
                  coupling: float = 0.35,
                  fringe_len_scale: float = 0.45,
                  fringe_cap_scale: float = 0.20) -> Network:
    """HF 相当ネットワーク: フリンジング長延長 + 端部フリンジ容量 + 相互結合。

    fringe_len_scale/fringe_cap_scale は「HFはLFより数%低い周波数へずれる」程度に
    抑える較正係数(実FEMとの定量一致ではなく、資料のMFストーリー再現のため)。
    """
    # フリンジングでパッチ実効長を延長 (両端 ΔL, 幅Wに依存 -> f0のX1依存を生む)
    dl1 = fringe_len_scale * _delta_L(geo.W1, geo.H, geo.er)
    dl2 = fringe_len_scale * _delta_L(geo.W2, geo.H, geo.er)
    Len1 = geo.Len1 + dl1
    Len2 = geo.Len2 + dl2
    Len3 = geo.Len3 + dl2

    td1, z1, ee1 = hammerstad.line_params(geo.W1, geo.H, geo.er, Len1, c0)
    td2, z2, ee2 = hammerstad.line_params(geo.W2, geo.H, geo.er, Len2, c0)
    td3, z3, ee3 = hammerstad.line_params(geo.W3, geo.H, geo.er, Len3, c0)
    td4, z4, _ = hammerstad.line_params(geo.W4, geo.H, geo.er, geo.Len4, c0)

    # 放射抵抗 + スロット間相互結合(給電位置=長さ非対称に依存)
    from .lowfidelity import radiation_resistance
    r1 = radiation_resistance(geo.W1, geo.lam0)
    r2 = radiation_resistance(geo.W3, geo.lam0)
    r3 = radiation_resistance(geo.W2, geo.lam0)

    # スロット間の電気的離間 (半波近傍で相互コンダクタンスが効く)
    #   給電オフセット(Len1 vs Len2 の差)に依存して QL に dip を作る
    sep = abs(Len2 - Len1) / geo.lam0
    mutual = coupling * np.cos(2.0 * np.pi * sep)   # -1..1
    r1 *= (1.0 + 0.5 * mutual)
    r2 *= (1.0 - 0.4 * mutual)
    r3 *= (1.0 - 0.4 * mutual)

    # 端部フリンジ容量 (LFでは無視していた「幅変化による有効容量」)
    def cap(w, ee):
        # C ~ ΔL * eeff / (c0 * Z0) を端部容量として近似
        z = hammerstad.z0_microstrip(w, geo.H, geo.er)
        return fringe_cap_scale * _delta_L(w, geo.H, geo.er) * np.sqrt(ee) / (c0 * z)

    c1 = cap(geo.W1, ee1)
    c2 = cap(geo.W3, ee3)
    c3 = cap(geo.W2, ee2)

    net = Network(
        lines=[
            TLine("N003", "N001", td1, z1),
            TLine("N001", "N002", td2, z2),
            TLine("N001", "N005", td3, z3),
            TLine("N001", "Port1", td4, z4),
        ],
        shunts=[
            Shunt("N003", r=r1, c=c1),
            Shunt("N005", r=r2, c=c2),
            Shunt("N002", r=r3, c=c3),
        ],
        port="Port1",
        zref=50.0,
    )
    return net


def s11(geo, freqs: np.ndarray, c0: float, rng: np.random.Generator | None = None,
        noise_db: float = 0.0) -> np.ndarray:
    """HF の S11。noise_db>0 で FEM離散化を模した微小ノイズを付与。"""
    out = build_network(geo, c0).s11(freqs)
    if noise_db > 0 and rng is not None:
        mag = np.abs(out)
        ph = np.angle(out)
        # 振幅にごく小さな相対ノイズ
        mag = np.clip(mag * (1.0 + noise_db * rng.standard_normal(mag.shape)), 0, 1.2)
        out = mag * np.exp(1j * ph)
    return out

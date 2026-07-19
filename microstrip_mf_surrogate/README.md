# マイクロストリップアンテナ設計 — マルチフィデリティ・サロゲート サンプル

KESCO/SmartUQ セミナー資料「**後半：マイクロストリップアンテナの設計事例**」
（`KESCO_..._20260625_V3.pdf` p.26–49）を、**SPDMチームの理解促進**を目的に
Python で模擬再現する実行可能サンプルです。

> **位置づけ**：本サンプルは COMSOL / LTSpice / SmartUQ の実行環境を必要としません。
> 資料に登場する **LTSpice（低忠実度）→ COMSOL FEM（高忠実度）→ マルチフィデリティ・
> サロゲート → 多目的最適化** という *ワークフローと考え方* を、自己完結の物理モデルと
> ガウス過程で追体験できるようにしたものです。
> **定量的には資料と一致しません**（資料でも「定量的にズレていても構わない」との指示）。
> 目的は「なぜマルチフィデリティが効くのか」「サロゲートの価値は速い予測ではなく
> 速い理解」という論点を、動かして確かめられるようにすることです。

---

## 1. 何を再現しているか（資料との対応）

| 資料 | 本サンプルでの再現 |
|---|---|
| p.28 フェーズA：仕様定義 (f0=2.45±0.01GHz, \|S11min\|≤0.316, QL≤30) | `msa/metrics.py` の `SPEC`、`scripts/run_demo.py` フェーズA |
| p.31 設計方針：オフセット給電1/2波長共振、給電位置で整合調整 | `msa/geometry.py`（X1..X6 → 物理寸法） |
| p.32 実験計画：6変数・スライスLHD | `msa/doe.py` |
| p.33 LTSpice前処理：放射抵抗 R∝(W/λ0)²、Hammerstad式、伝搬速度√εeff | `msa/hammerstad.py`, `msa/lowfidelity.py` |
| p.34 LTSpiceネットリスト（伝送線路4本＋放射抵抗3個） | `msa/tline.py`（小型ACソルバ） |
| p.35 後処理：スプライン補間、f0/\|S11min\|/QL 抽出、エラー除外 | `msa/metrics.py` |
| p.36 COMSOL FEM（PML＝無限領域） | `msa/highfidelity.py`（FEM相当モック） |
| p.38–39 サロゲート3方式比較（HFのみ / データフュージョン / マルチフィデリティ）と SCVR | `msa/surrogate.py` |
| p.40–41 QL>30 データ選別で S11min 精度改善 | `surrogate.scvr_poison`, `pipeline.eval_hf` |
| p.44 多目的最適化 NSGA-II（\|S11min\| vs log(QL) パレート） | `msa/optimize.py` |
| p.45–46 FEM精密計算 → f0 仕様外 → X3 チューニング | `run_demo.py` `tuning()` |
| p.49 まとめ：少数HFを増幅、不確かさで判断 | 出力レポート末尾 |

---

## 2. 物理モデルの中身

### 低忠実度（LF）= LTSpice 相当（`lowfidelity.py`）
資料 p.33 の仮定をそのまま実装した **伝送線路ネットワークの回路モデル**：

- 放射はアンテナ端部のみ。放射端はスロットコンダクタンス
  `G=(1/90)(W/λ0)²` の逆数 `R=1/G` としてグランドへ接続。
- 線路は Hammerstad 近似式で特性インピーダンス `Z0`・実効誘電率 `εeff` を計算し、
  伝搬速度 `v=c/√εeff` から遅延時間 `td` に変換。
- 合流点はキルヒホッフ則（節点アドミタンス法）のみ。散乱行列や幅変化の
  有効容量は使わない。

`tline.py` は資料 p.34 の LTSpice ネットリスト（`T1..T4`, `R1..R3`, `.ac`）を
**周波数掃引で解く小型ACソルバ**です（各周波数で節点アドミタンス行列を組んで
入力インピーダンス `Zin` を解き、`S11=(Zin-50)/(Zin+50)`）。

### 高忠実度（HF）= COMSOL FEM 相当のモック（`highfidelity.py`）
実 FEM が無いため、LF回路に **単純モデルが取りこぼす物理** を加えた
「高忠実度モック」を用意しています：

- **フリンジングによる等価長延長 ΔL**（Hammerstad-Kirschning 型）
  → f0 が幅 W(=X1) に依存（資料 p.38「LFに現れなかった X1 変化がHFで現れる」）。
- **放射スロット間の相互結合**（給電位置依存）
  → log(QL) に給電位置依存の構造（資料の「dip / BM」）。
- **端部フリンジ容量**（LFで無視した「幅変化による有効容量」）。
- **20MHz の粗い周波数格子 + 後処理スプライン補間 + 微小離散化ノイズ**
  （資料 p.35, p.40）。鋭い（高QL）共振では格子が真の谷を外し \|S11min\| が
  浅く見える系統誤差を再現（資料 p.40「スプライン補間では対応不能」）。

この結果、「**LF＝滑らかで単純**」「**HF＝少数点だが豊かな物理**」という
マルチフィデリティの前提が成立し、差分/相関学習の効果を体験できます。

### 較正について（正直な注記）
本トイモデルは自由空間波長で無次元化しているため、共振点や整合が資料の
動作点域（f0~2.45GHz, QL~10–30）に入るよう、以下の**縮尺のみ**の較正定数を
置いています（物理の形は変えていません）：
`geometry.LEN_CAL`（長さ）, `lowfidelity.RAD_CAL`（放射抵抗）,
`highfidelity` のフリンジング係数。

---

## 3. サロゲート3方式（`surrogate.py`）

いずれもガウス過程回帰。出力は **予測値 ＋ 予測の不確かさ（±σ）**。

1. **HF-only**：高忠実度データのみ。少数点のため不確かさ大。
2. **Multi-fidelity（差分補正型 / Additive Correction）**
   `w_HF = w_LF_hat + δ(x)`（LF予測に残差 δ を足す。資料 p.19, p.22）。
3. **Data Fusion（co-kriging, AR1）**
   `w_HF = ρ·w_LF_hat + δ(x)`（相関 ρ を最小二乗で学習。資料 p.19, p.21）。

**標準化CV誤差（SCVR）** = `RMSE_LOO / std(y_HF)`（1.0＝平均値予測と同等、
0に近いほど良い）で方式を比較します（資料 p.39 の値域と整合する正規化RMSE）。

---

## 4. 実行方法

```bash
pip install -r requirements.txt
python scripts/run_demo.py
```

- 標準出力とレポート `outputs/results.md` にワークフロー全体の結果、
  `outputs/results.json` に機械可読の数値、`figures/*.png` に図が出力されます。
- 実行は数分（DOE評価＋GPのLOO交差検証）。乱数シード固定で再現します。

### 個別モジュールを触る
```python
from msa import geometry, lowfidelity, highfidelity, metrics, C0, F_DESIGN
import numpy as np
X = [0.31, 0.5, 0.205, 0.27, 0.003, 3.0]           # X1..X6
geo = geometry.build_geometry(X, F_DESIGN, C0)
f = np.linspace(2e9, 3e9, 501)
m = metrics.extract_metrics(f, lowfidelity.s11(geo, f, C0))
print(m.f0/1e9, m.s11min, m.QL)                     # f0[GHz], |S11min|, QL
```

---

## 5. 生成される図

| ファイル | 内容 |
|---|---|
| `lf_hf_curves.png` | 同一設計での LF と HF の \|S11\| 応答（HFはフリンジングで低域へずれる） |
| `feed_sweep.png` | 給電位置 X4 に対する整合(\|S11min\|)と Q（トレードオフ、資料 p.31/p.48） |
| `scvr_all.png` | 3方式の SCVR 棒グラフ（MF/DFが HF-only を下回る＝改善） |
| `loo_scatter.png` | Leave-One-Out 予測 vs 実測（QL選別 前/後） |
| `mf_surface.png` | MFサロゲートの予測±2σ（給電位置に対する f0/\|S11min\|/log(QL)） |
| `pareto.png` | NSGA-II による \|S11min\|–log(QL) パレートフロント（資料 p.44） |
| `final_s11.png` | 最終設計の \|S11\|（X3チューニング前後、資料 p.46） |

---

## 6. 典型的な結論（実行例）

- **マルチフィデリティ／データフュージョンは HF-only より SCVR を大きく下げる**
  （例：f0 で 0.83→0.35）。＝少数の高忠実度データを低忠実度で「増幅」できる。
- **給電位置 X4 が整合(\|S11min\|)と Q を支配**し、最適点付近に整合の谷がある。
- **QL>30 の汚染点を除くと \|S11min\| の予測精度が上がる**（資料 p.40）。
- **多目的最適化→FEM検証→X3チューニング** で、少ない学習データから
  仕様内（f0∈[2.44,2.46], \|S11min\|≤0.316, QL≤30）の設計に到達できる。

> サロゲートの価値は「速い予測」ではなく「**速い理解**」。予測に不確かさを添えることで、
> *どこを信じ、次にどこを測るか* が見える——という資料 p.49 のメッセージを、
> 手元で動かして確認するためのサンプルです。

---

## 7. ディレクトリ構成

```
microstrip_mf_surrogate/
├─ README.md
├─ requirements.txt
├─ msa/                    # ライブラリ本体
│  ├─ hammerstad.py        # Z0 / εeff / 50Ω幅合成
│  ├─ tline.py             # 伝送線路ネットワークの小型ACソルバ（LTSpice相当）
│  ├─ geometry.py          # X1..X6 → 物理寸法
│  ├─ lowfidelity.py       # LFモデル（LTSpice相当）
│  ├─ highfidelity.py      # HFモデル（FEM相当モック）
│  ├─ metrics.py           # f0/|S11min|/QL 抽出・エラー除外・仕様判定
│  ├─ doe.py               # スライスLHD
│  ├─ surrogate.py         # GP / Multi-fidelity / Data Fusion / SCVR
│  ├─ optimize.py          # NSGA-II
│  └─ pipeline.py          # 設計変数→評価指標の共通窓口
├─ scripts/
│  └─ run_demo.py          # ワークフロー一気通貫（図・レポート生成）
├─ figures/                # 生成される図
└─ outputs/                # results.md, results.json
```

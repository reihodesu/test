# explorer — DC_v5 保存劣化モデルの Sobol 感度解析 ＋ 設計探索アーキテクチャ

`microstrip_sobol_analysis`（マイクロストリップ用 Sobol パッケージ）を、DC_v5 の
**保存劣化 実式**へ転用したもの。`evaluate()` を DC_v5 の `calc_dc_outputs()` に
差し替え、README 転用節が要求する 3 点（時間依存・独立性・分布モード）を実装した。

## 構成

| ファイル | 役割 |
|---|---|
| `vendor_dcv5/` | DC_v5 実式の最小取り込み（`dc_model.py` = `calculators/DC_index/aging/dc_model.py` を無改変、`core/config.py`・`core/exceptions.py`）。**劣化式そのものは実物** |
| `cell_design.py` | ② 独立上流変数 → 派生量（eps/K/L/Typ）。DOE は独立変数のみに張る（B-4②） |
| `degradation.py` | 劣化ラッパ。`calc_dc_outputs` を叩き、劣化速度を T_use の Arrhenius に、応答＝容量維持率 `tmax(t)/tmax(0)` |
| `config.py` | 独立上流変数の仕様（design/variation 分布モード, 物理妥当域）B-4① |
| `sensitivity.py` | Sobol 解析（時間依存 B-4③・マスキング B-4④） |
| `plots.py` | 感度図（主効果/交互作用/ネットワーク/時間推移/領域条件付き/収束） |
| `screening.py` | ① 感度スクリーニング＋制約評価（OK/NG） |
| `viz_explorer.py` | ①擬似並行座標（感度自動反映）・③制約つきコンター・アーキテクチャ図 |
| `run_sensitivity.py` | 感度解析一括実行 → `output/explorer/sobol_*.png` |
| `run_explorer.py` | ①②③ 設計探索アーキテクチャ一括実行 → `output/explorer/explore_*.png` |

## 実行

```bash
pip install numpy scipy scikit-learn matplotlib pandas SALib
cd <repo>
PYTHONIOENCODING=utf-8 python -m mf_demo.explorer.run_sensitivity 256   # 感度解析6図
PYTHONIOENCODING=utf-8 python -m mf_demo.explorer.run_explorer 600      # ①②③ 5図
```

## 対象モデル（保存劣化 = DC_v5 実式 / 社内テクニカルレポート準拠 v2）

```
独立上流変数（報告書 NCR2170JB Step2 の探索6因子 ＋ 使用温度, 7個）
  セル抵抗R0 / 正極塗布量 / 正極利用率 / 活物質密度 / 電解液拡散係数 / 正極曲路率 / 使用温度
    │  cell_design.py（評価関数内部で派生量を計算 = B-4②）
    ▼
派生量: 塗布量K / 空隙率eps / 合剤厚みL / 面積容量 / セル容量Typ / a0
    │  dc_model.calc_dc_outputs()（DC_v5 実式, b'=b_ocv/2=2.0V）
    ▼   R(t)=R0+r(T)·t（線形, §4実証） / a(t)=a0+k(T)·√t（√t, §3復帰率）
主応答（＝設計成立条件, 報告書§2 / NCR2170JB Step2）:
  放電後電圧 y_end >= 2.5V（抵抗劣化モード指標）
  限界Li塩濃度 Cli <= 1.4M（電解液Li+濃度拡散劣化モード指標）
```

- 劣化速度係数 k,r は使用温度 T の Arrhenius（10℃2倍則 Ea≈60kJ/mol, §1/§6）
- 2劣化モード（抵抗劣化⇄拡散劣化）を無次元指標 Cli/C_Li_design で判定（§2 図）
- 応答で支配因子が異なる: 放電後電圧←抵抗/塗布量/温度、限界Li塩濃度←曲路率/塗布量/拡散係数
  （報告書 S28「限界Li塩濃度: 塗布量>曲路率>拡散係数」と整合）
- 保存が進むと限界Li塩濃度が設計budget(1.4M)を超え、抵抗劣化→拡散劣化モードへ遷移（支配因子の変遷）


## 設計判断（重要）

- **分布モードで支配因子が入れ替わる**（B-4①）: design（一様）では塗布量が支配、
  variation（3σ正規）では使用温度が支配。どちらのモードで出した指標かを図に明記。
- **独立性**（B-4②）: 派生量（eps/K/L…）は入力に撒かず評価関数内部で計算。
  派生量そのものの寄与を見たい場合は Shapley effects 等が必要（本スコープ外）。
- **時間依存**（B-4③）: 感度指標の時間推移を出力。初期は塗布量/比容量、長期は
  温度加速項へ支配が移る。
- **物理妥当域マスキング**（B-4④）: 判別式負（放電不能）/ 維持率∉(0,1] / 温度外挿を
  無効サンプルとして除外率で記録・警告。

## 転用元との対応

`microstrip_sobol_analysis` の比較軸「LF vs HF」を「design vs variation（分布モード）」に
置換。ネットワーク図・領域条件付き感度・収束確認はそのまま踏襲。

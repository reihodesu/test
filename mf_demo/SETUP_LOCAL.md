# ローカル環境セットアップ手順（Windows / `C:\Calc_V3\test`）

保存劣化 Sobol 感度解析＋設計探索アーキテクチャ一式を、ローカル PC で動かすための手順です。
本パッケージは合成データ／理論式で完結しており、実データは不要です。

---

## 0. 前提ソフトウェア

| ソフト | 用途 | 確認コマンド |
|---|---|---|
| **Python 3.10 以上** | 感度解析・作図の本体 | `python --version` |
| **Node.js 18 以上** | Word 報告書の生成（docx-js） | `node --version` |
| 日本語フォント **IPAGothic** または **Noto Sans CJK JP** | 図中の日本語表示 | 下記 §4 |

Node.js は Word 報告書（`.docx`）を再生成する場合のみ必要です。図と解析だけなら Python のみで動きます。

---

## 1. 配置

本 zip を展開し、中身の `mf_demo` フォルダが以下になるように置きます。

```
C:\Calc_V3\test\
└─ mf_demo\
   ├─ explorer\        ← 本命（保存劣化 感度解析＋設計探索）
   ├─ antenna\         ← 先行デモ（独立、任意）
   ├─ output\          ← 図・報告書の出力先
   ├─ requirements.txt
   └─ SETUP_LOCAL.md   ← 本ファイル
```

すべてのパスはスクリプト位置からの相対で解決するため、`C:\Calc_V3\test` 以外へ置いても動きます。
Python は `mf_demo` の **親フォルダ**（＝ `C:\Calc_V3\test`）を作業ディレクトリにして実行してください
（`python -m mf_demo.explorer.xxx` のパッケージ実行のため）。

---

## 2. Python 環境の構築

PowerShell またはコマンドプロンプトで:

```bat
cd C:\Calc_V3\test
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r mf_demo\requirements.txt
```

主要依存: `numpy scipy scikit-learn matplotlib pandas SALib plotly dash`

---

## 3. 実行（図の生成）

作業ディレクトリは常に `C:\Calc_V3\test`（＝ `mf_demo` の親）です。
Windows で日本語出力の文字化けを防ぐため `PYTHONIOENCODING=utf-8` を推奨します。

```bat
cd C:\Calc_V3\test
set PYTHONIOENCODING=utf-8

REM 基本の感度図5枚（sobol_*.png）+ sobol_result.json
python -m mf_demo.explorer.run_sensitivity 4096 2048

REM 設計探索アーキテクチャ ①②③（explore_*.png）
python -m mf_demo.explorer.run_explorer 600

REM 改訂第3版で追加した図（D群・E-6・F-1）
python -m mf_demo.explorer.run_figures_v3
```

出力はすべて `mf_demo\output\explorer\` に保存されます（全13図）。

> 動作確認だけなら軽い引数で: `python -m mf_demo.explorer.run_sensitivity 256`
> （N=256 なら数十秒。F-1 と主感度は N を上げるほど信頼区間が縮む代わりに時間がかかります。
> 4096 での主感度は約6分、`run_figures_v3` は F-1 の LHS を含め数分です。）

---

## 4. 日本語フォント（図の文字化け対策）

matplotlib が `IPAGothic` → `Noto Sans CJK JP` の順で日本語フォントを探します。
どちらも無い場合、図の日本語が「□」になります。以下のいずれかを導入してください。

- **IPAフォント**: <https://moji.or.jp/ipafont/> から IPAexゴシック等をインストール。
- **Noto Sans CJK JP**: Google Noto Fonts を導入。
- 導入後にフォントキャッシュを消すと確実です:
  ```bat
  del /q "%USERPROFILE%\.matplotlib\fontlist-*.json"
  ```

（`explorer/plots.py` / `viz_explorer.py` の冒頭でフォント優先順位を設定しています。
別フォントを使う場合はそこを編集してください。）

---

## 5. Word 報告書（改訂第3版）の再生成 — 任意

図を生成したあと、`.docx` を作り直す場合のみ Node.js を使います。

```bat
cd C:\Calc_V3\test\mf_demo\explorer
npm install          REM 初回のみ（docx を取得）
node build_report.js
```

出力: `mf_demo\output\報告書_保存劣化_感度解析.docx`

`build_report.js` は図の PNG から寸法を直接読むため、外部の寸法ファイルは不要です。
図（`mf_demo\output\explorer\*.png`）が先に生成されている必要があります。

---

## 6. トラブルシューティング

| 症状 | 対処 |
|---|---|
| `ModuleNotFoundError: mf_demo` | 作業ディレクトリが `mf_demo` の親（`C:\Calc_V3\test`）か確認。`python -m mf_demo....` で実行。 |
| 図の日本語が □ になる | §4 のフォント導入＋キャッシュ削除。 |
| `SALib` が無い | `pip install -r mf_demo\requirements.txt` を再実行。 |
| コンソールの日本語が文字化け | `set PYTHONIOENCODING=utf-8`（PowerShell は `$env:PYTHONIOENCODING="utf-8"`）。 |
| `node: command not found` | Node.js を導入。報告書を作らないなら不要。 |
| `build_report.js` で画像が見つからない | 先に §3 で図を生成。`mf_demo\output\explorer\` に PNG があるか確認。 |

---

## 7. モジュール構成（参考）

| ファイル | 役割 |
|---|---|
| `explorer/vendor_dcv5/dc_model.py` | **DC_v5 実式（無改変・変更禁止）**。線形抵抗劣化・√t容量劣化・定W放電の閉形式。 |
| `explorer/cell_design.py` | 独立上流変数 → 派生量（空隙率・厚み・面積容量・a0）。 |
| `explorer/degradation.py` | 実式ラッパ（b'=2.0V, Arrhenius, 3応答=電圧/Li塩/維持可否, 2モード）。 |
| `explorer/config.py` | 変数定義・設計/ばらつき分布・時間グリッド・制約閾値。 |
| `explorer/sensitivity.py` | Sobol 感度・時間推移・モード割合・領域条件付き・F-1 頑健性。`MIN_SAMPLES=200` ガード。 |
| `explorer/plots.py` | 感度図（主感度・時間推移・モード遷移/積み上げ・ネットワーク・収束・条件付き・F-1）。 |
| `explorer/viz_explorer.py` | 擬似並行座標・制約つきコンター・コンター条件比較・アーキテクチャ図。 |
| `explorer/screening.py` | 感度スクリーニング（能動軸自動抽出）・設計母集団生成。 |
| `explorer/run_sensitivity.py` | 感度図5枚の一括実行。 |
| `explorer/run_explorer.py` | 設計探索 ①②③ の一括実行。 |
| `explorer/run_figures_v3.py` | 改訂第3版の追加図（D群・E-6・F-1）の一括実行。 |
| `explorer/build_report.js` | Word 報告書（改訂第3版）の生成（docx-js）。 |

再現性: 乱数シードは全モジュールで固定。図中文言は日本語。
本プロトタイプは原理可視化を優先した合成モデルであり、精度較正済みの設計ツールではありません
（劣化式本体は DC_v5 実物、`cell_design.py` の上流→派生写像のみ最小スラブモデル）。

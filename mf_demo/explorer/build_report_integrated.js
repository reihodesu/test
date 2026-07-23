// 保存劣化 感度解析 詳細報告書 改訂第3版 (docx-js)
const fs = require('fs');
const path = require('path');
const D = require('docx');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, TableOfContents,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, AlignmentType,
  ImageRun, PageBreak, PageOrientation, LevelFormat, Header, Footer, PageNumber,
} = D;

// パスはスクリプト位置（mf_demo/explorer/）を基準に解決する（OS 非依存）。
const OUT_DIR = path.resolve(__dirname, '..', 'output');
const FIG = path.join(OUT_DIR, 'explorer');
// PNG の IHDR チャンク（先頭16-24バイト）から幅・高さを直接読む → 外部 figdims.json 不要。
function pngSize(file) {
  const b = fs.readFileSync(path.join(FIG, file));
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}
const dims = new Proxy({}, { get: (_, name) => pngSize(name) });
const JP = 'IPAGothic';
const NAVY = '1F3864', ACC = 'B4472C', GREY = '595959', GREEN = '2E7D32', GOLD = 'B8860B';

// ---- helpers ----
function h(text, level) { return new Paragraph({ heading: level, spacing: { before: 220, after: 110 }, children: [new TextRun({ text, font: JP })] }); }
function p(runs, opts = {}) {
  const arr = Array.isArray(runs) ? runs : [runs];
  return new Paragraph({ spacing: { after: 90, line: 276 }, alignment: opts.align, ...opts.pp,
    children: arr.map(r => typeof r === 'string' ? new TextRun({ text: r, font: JP, size: opts.size || 21, color: opts.color, bold: opts.bold, italics: opts.italics }) : r) });
}
function bullet(text, opts = {}) {
  return new Paragraph({ bullet: { level: opts.level || 0 }, spacing: { after: 60, line: 270 },
    children: [new TextRun({ text, font: JP, size: 21, bold: opts.bold, color: opts.color })] });
}
function fig(file, widthPx, caption) {
  const [w, hh] = dims[file]; const width = widthPx; const height = Math.round(widthPx * hh / w);
  const img = new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 40 },
    children: [new ImageRun({ type: 'png', data: fs.readFileSync(path.join(FIG, file)), transformation: { width, height } })] });
  const cap = new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
    children: [new TextRun({ text: caption, font: JP, size: 18, italics: true, color: GREY })] });
  return [img, cap];
}
function cell(text, opts = {}) {
  return new TableCell({ width: { size: opts.w, type: WidthType.DXA },
    shading: opts.shade ? { type: ShadingType.CLEAR, fill: opts.shade, color: 'auto' } : undefined,
    margins: { top: 40, bottom: 40, left: 90, right: 90 },
    children: [new Paragraph({ alignment: opts.align, children: (Array.isArray(text) ? text : [text]).map(t => new TextRun({ text: t, font: JP, size: opts.size || 19, bold: opts.bold, color: opts.color })) })] });
}
function table(colW, rows) {
  const total = colW.reduce((a, b) => a + b, 0);
  return new Table({ columnWidths: colW, width: { size: total, type: WidthType.DXA },
    borders: ['top', 'bottom', 'left', 'right', 'insideHorizontal', 'insideVertical'].reduce((o, k) => (o[k] = { style: BorderStyle.SINGLE, size: 4, color: 'AAAAAA' }, o), {}),
    rows: rows.map((r, i) => new TableRow({ tableHeader: i === 0,
      children: r.map((c, j) => cell(c.t, { w: colW[j], shade: i === 0 ? NAVY : (c.shade || (i % 2 ? 'F2F5FA' : 'FFFFFF')), color: i === 0 ? 'FFFFFF' : c.color, bold: i === 0 || c.bold, align: c.align, size: c.size })) })) });
}
const H = (t, w, align) => ({ t, w, align: align || AlignmentType.CENTER });

const children = [];

// ===== 表紙 =====
children.push(
  new Paragraph({ spacing: { before: 1400, after: 120 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'DC向けセル 保存劣化モデルの', font: JP, size: 40, bold: true, color: NAVY })] }),
  new Paragraph({ spacing: { after: 500 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: '感度解析と設計探索アーキテクチャ', font: JP, size: 40, bold: true, color: NAVY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
    children: [new TextRun({ text: '― 理論式ベース Sobol 感度解析（統合版: 改訂第3版 ＋ F-1残課題の消し込み検証）―', font: JP, size: 24, color: ACC })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 900, after: 60 },
    children: [new TextRun({ text: 'プロトタイプ実装報告書', font: JP, size: 26, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: '対象: DC_v5 保存劣化理論式（社内テクニカルレポート T0073-2025-00305 / NCR2170JB Step2 準拠）', font: JP, size: 19, color: GREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '作成日: 2026-07-23 ／ 統合版（改訂第3版に §8 検証結果を統合）', font: JP, size: 19, color: GREY })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ===== 目次 =====
children.push(h('目次', HeadingLevel.HEADING_1));
children.push(new TableOfContents('目次', { hyperlink: true, headingStyleRange: '1-2' }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ===== 概要 (E-1) =====
children.push(h('概要（エグゼクティブサマリー）', HeadingLevel.HEADING_1));
children.push(p('データセンター（DC）向け高出力円筒セルでは、保存後の出力劣化が設計成立の鍵となる。本報告書は、社内で構築済みの保存劣化理論式（DC_v5, 定W放電モデル）を直接モンテカルロで叩く Sobol 感度解析のプロトタイプを実装し、設計探索3点セット（コンター図・並行座標・感度ネットワーク図）と統合した設計探索アーキテクチャを提示する。'));
children.push(p([ new TextRun({ text: '本検討の核心（感度解析でしか出ない結論）: ', font: JP, size: 21, bold: true, color: ACC }),
  new TextRun({ text: '限界Li塩濃度の支配因子は、拡散劣化モードが頻発する領域（塗布量10〜13・曲路率1.7〜2.0）では、全域で首位の材料物性=曲路率から、制御可能な設計因子=活物質密度へ入れ替わる（§5.4）。この入れ替わりは代入方針（median／penalty）と代入非依存の順位相関（Spearman |ρ|）の3手法すべてで再現し、代入方針に頑健であることを確認した（§5.4／図6）。全域感度では見えず、領域を絞って初めて現れる非自明な結果であり、「材料で決まる（打ち手がない）」という誤解を退けて設計上の打ち手を示す。', font: JP, size: 21 }) ]));
children.push(p([ new TextRun({ text: 'その他の結果: ', font: JP, size: 21, bold: true, color: NAVY }),
  new TextRun({ text: '①応答（放電後電圧／限界Li塩濃度／300W維持可否）ごとに支配因子が明確に分離する（§5.1）。②保存が進むと支配モードが抵抗劣化から拡散劣化へ遷移する。ただしこれは劣化項が r(T)·t と k(T)·√t である以上の理論式の代数的帰結であり、感度解析でなくとも導ける。よって「感度」ではなく', font: JP, size: 21 }),
  new TextRun({ text: '不確かさ伝播（UP）の成果', font: JP, size: 21, bold: true }),
  new TextRun({ text: 'として遷移時期と母集団比率を定量化したものと位置づける（§5.2）。③限界Li塩濃度の感度は代入方針で ST 上位が入れ替わる（§4.5(3)）— これ自体が本検討で判明した数値的注意点であり、成立可否は二値応答で別途分解した。④入力分布モード（design／variation）で支配因子が反転する（§5.5）。', font: JP, size: 21 }) ]));
children.push(p([ new TextRun({ text: '添付テクニカルレポートとの整合（部分整合）: ', font: JP, size: 21, bold: true, color: NAVY }),
  new TextRun({ text: '理論式の構造（線形抵抗劣化・√t容量劣化・Arrhenius 10℃2倍則・限界Li塩濃度）と設計成立範囲（放電後電圧≥2.5V かつ 限界Li塩濃度≤1.4M）は再現した。限界Li塩濃度の感度順位（レポートS28: 塗布量>曲路率>拡散係数）は、入力範囲・代入方針・領域で順位が動くため「部分整合」と位置づける（§3・§4.5(3)・§5.4）。', font: JP, size: 21 }) ]));

// ===== §1 背景 =====
children.push(h('1. 背景と目的', HeadingLevel.HEADING_1));
children.push(p('生成AI・データセンターの普及に伴い、高出力円筒リチウムイオン電池（2170で200〜300W／〜120s級）の需要が急増している。100W級以上の高出力では保存後の出力劣化が顕著になり、予測との乖離・劣化要因の推定が課題となっている。社内では定W放電領域のOCV線形性と電解液Li+濃度拡散限界に基づく保存劣化-定W放電の理論モデルが構築済みである。'));
children.push(p('チームの設計探索（Ansys optiSLang）における主力可視化は、(1) 2軸コンター図（制約線つき OK/NG 把握）と (2) 並行座標プロット（多次元フィルタリング）である。本検討の目的は、これに 第3の柱として感度解析の可視化 を加え、さらに保存劣化理論式を（サロゲート MOP/CoP を経由せず）直接叩いて感度を算出するプロトタイプを構築し、チームへ「動く絵」として提示することにある。'));

// ===== §2 対象モデル =====
children.push(h('2. 対象モデル：DC_v5 保存劣化理論式', HeadingLevel.HEADING_1));
children.push(p('中核は DC_v5 の実式 calc_dc_outputs()（calculators/DC_index/aging/dc_model.py）を無改変で用いる。定W放電の閉形式で放電後電圧と限界Li塩濃度を算出する。'));
children.push(h('2.1 劣化の理論式', HeadingLevel.HEADING_2));
children.push(bullet('抵抗劣化（線形）: R(t) = R0 + r(T)·t  … 保存中の抵抗上昇は√より線形（レポート§4で実証）', {}));
children.push(bullet('容量劣化（√t）: a(t) = a0 + k(T)·√t  … 0.05C保存復帰率が√t・Arrheniusにのる（§3）', {}));
children.push(bullet('放電後電圧: y_end = b\' + √(b\'² − z·R − z·a·t/3600)  （z=放電電力, b\'=b_ocv/2）', {}));
children.push(bullet('限界Li塩濃度: Cli = C_rate·Qareal /(Jlim·1000),  Jlim = 2zF·Dely·ε^γ / L （拡散限界指標）', {}));
children.push(bullet('劣化速度係数 k, r は使用温度 T の Arrhenius（10℃2倍則, Ea≈60 kJ/mol）で温度加速', {}));
children.push(h('2.2 独立上流変数（DOEを張る対象）', HeadingLevel.HEADING_2));
children.push(p('Sobol分解の前提（入力独立）を満たすため、DOEは真に独立な上流変数のみに張り、派生量（塗布量K・空隙率ε・厚みL・面積容量・セル容量Typ・a0）は評価関数の内部（cell_design.py）で計算する。変数群は報告書 NCR2170JB Step2 の探索6因子＋使用温度に整合させた。'));
children.push(table([1700, 1500, 1400, 4000], [
  [H('変数'), H('分類'), H('設計範囲'), H('意味・役割', 4000, AlignmentType.LEFT)],
  [{t:'セル抵抗 R0'},{t:'設計因子'},{t:'3〜8 mΩ'},{t:'初期抵抗。放電後電圧を強く支配', w:4000, align:AlignmentType.LEFT}],
  [{t:'正極塗布量'},{t:'設計因子'},{t:'6〜13 mg/cm²'},{t:'K・厚みL・容量に波及。両応答に効く', w:4000, align:AlignmentType.LEFT}],
  [{t:'正極利用率'},{t:'材料物性'},{t:'0.190〜0.215 Ah/g'},{t:'活物質比容量。容量・a0に波及', w:4000, align:AlignmentType.LEFT}],
  [{t:'活物質密度'},{t:'設計因子'},{t:'3.2〜3.7 g/cm³'},{t:'空隙率ε・厚みLに波及（拡散に効く）', w:4000, align:AlignmentType.LEFT}],
  [{t:'電解液拡散係数'},{t:'材料物性'},{t:'3.2〜4.8e-10 m²/s'},{t:'拡散限界 Jlim を規定', w:4000, align:AlignmentType.LEFT}],
  [{t:'正極曲路率 γ'},{t:'材料物性'},{t:'1.4〜2.0'},{t:'実効拡散 D_eff=Dely·ε^γ を規定', w:4000, align:AlignmentType.LEFT}],
  [{t:'使用温度'},{t:'使用条件'},{t:'25〜50 ℃'},{t:'Arrhenius で劣化速度を加速', w:4000, align:AlignmentType.LEFT}],
]));
children.push(p([new TextRun({text:'注（B-4②）: ', font:JP, size:19, bold:true}), new TextRun({text:'派生量そのものの寄与を見る場合は Shapley effects 等が必要であり本スコープ外。派生量を独立にサンプリングすると物理的にありえない組合せを踏み、Sobol分解の解釈が破綻するため避けている。', font:JP, size:19, color:GREY})]));

// ===== §3 レビュー =====
children.push(h('3. 理論モデルのレビュー（添付レポートとの整合性）', HeadingLevel.HEADING_1));
children.push(p('添付の社内テクニカルレポート（保存後出力劣化-理論とDC向け18機種／DC設計適用／NCR2170JB Step2）に照らし、実装モデルの妥当性を確認した。主要な整合点を下表に示す。'));
children.push(table([3400, 3600, 2200], [
  [H('レポートの記述', 3400, AlignmentType.LEFT), H('実装での対応', 3600, AlignmentType.LEFT), H('判定', 2200)],
  [{t:'保存中の抵抗上昇は√より線形（+1mΩ/年想定）', w:3400, align:AlignmentType.LEFT},{t:'R(t)=R0+r·t（線形）を採用', w:3600, align:AlignmentType.LEFT},{t:'一致', color:GREEN, bold:true}],
  [{t:'容量復帰率は√t・Arrheniusプロット（10℃2倍則）', w:3400, align:AlignmentType.LEFT},{t:'a(t)=a0+k·√t、kをArrhenius(Ea≈60kJ/mol)', w:3600, align:AlignmentType.LEFT},{t:'一致', color:GREEN, bold:true}],
  [{t:'定W放電の放電後電圧一般式', w:3400, align:AlignmentType.LEFT},{t:'y_end=b\'+√(b\'²−zR−zat/3600)', w:3600, align:AlignmentType.LEFT},{t:'一致', color:GREEN, bold:true}],
  [{t:'限界Li塩濃度（無次元C-rate→拡散限界）', w:3400, align:AlignmentType.LEFT},{t:'Cli=C_rate·Qareal/(Jlim·1000)', w:3600, align:AlignmentType.LEFT},{t:'一致', color:GREEN, bold:true}],
  [{t:'抵抗上昇で限界Li塩濃度が上昇（S18/S35）', w:3400, align:AlignmentType.LEFT},{t:'R(t)↑→C_rate↑→Cli(t)↑ を再現', w:3600, align:AlignmentType.LEFT},{t:'一致', color:GREEN, bold:true}],
  [{t:'限界Li塩濃度の影響順位: 塗布量>曲路率>拡散係数（S28）', w:3400, align:AlignmentType.LEFT},{t:'全域ST(design,median): 曲路率0.53/塗布量0.32/密度0.25。順位は範囲・代入・領域で変動', w:3600, align:AlignmentType.LEFT},{t:'部分整合（§3.2）', color:GOLD, bold:true}],
  [{t:'設計成立: 放電後電圧≥2.5V かつ 限界Li塩濃度≤1.4M（Step2）', w:3400, align:AlignmentType.LEFT},{t:'同一制約でOK/NG・コンター定義', w:3600, align:AlignmentType.LEFT},{t:'一致', color:GREEN, bold:true}],
  [{t:'300Wは非常に厳しい（容量・発熱）', w:3400, align:AlignmentType.LEFT},{t:'低塗布量・高温で300W維持不可を無効化', w:3600, align:AlignmentType.LEFT},{t:'一致', color:GREEN, bold:true}],
]));
children.push(h('3.1 レビューで反映した改善', HeadingLevel.HEADING_2));
children.push(bullet('放電開始電圧を物理値 b\'=b_ocv/2=2.0V に修正 → 放電後電圧が物理域2.5〜4Vに（レポートの放電後電圧域と一致）'));
children.push(bullet('主応答を「放電後電圧」「限界Li塩濃度」に再定義（＝レポートの設計成立条件そのもの）'));
children.push(bullet('独立変数をレポート6設計因子＋使用温度に整合。制約つきコンターを セル抵抗×塗布量 に'));
children.push(bullet('2劣化モード（抵抗劣化⇄拡散劣化）を無次元指標 Cli/C_Li_design で判定・可視化'));
children.push(h('3.2 感度順位の「部分整合」判定の根拠（C-2補）', HeadingLevel.HEADING_2));
children.push(p([new TextRun({text:'レポートS28の順位（塗布量>曲路率>拡散係数）と本実装の全域感度が完全一致しない理由を、成立する説明のみに整理する。主説明は代入方針依存性である。', font:JP, size:21})]));
children.push(bullet('主説明＝代入方針依存性（§4.5(3)）: 限界Li塩濃度の ST 上位は median と penalty で入れ替わる（median: 曲路率>塗布量>密度／penalty: 塗布量>抵抗>温度）。penalty は無効化の原因（塗布量・温度）を最悪値で埋めるため塗布量の寄与が跳ね上がり、レポートの「塗布量首位」に近づく。すなわち順位は無効サンプルの扱い方に従属する。', {}));
children.push(bullet('補助説明＝範囲依存性（§5.5 の E-3 で検証）: 曲路率の設計範囲 1.4〜2.0（幅0.60）はばらつき3σ（約0.58）と同程度で過大ではないが、より狭い現実的範囲（1.5〜1.7）に絞ると曲路率の順位が下がり、密度0.36/塗布量0.35/拡散係数0.25 となってレポートS28に近づく。', {}));
children.push(p([new TextRun({text:'不採用とした説明: ', font:JP, size:19, bold:true, color:ACC}), new TextRun({text:'第2版までにあった「variation なら拡散係数が3位に上がる」という説明は、実際の variation 感度（曲路率0.38/温度0.28/密度0.27）で拡散係数が3位に来ないため成立せず、削除した。', font:JP, size:19, color:GREY})]));

// ===== §4 方法 =====
children.push(h('4. 感度解析の方法', HeadingLevel.HEADING_1));
children.push(p('SALib の Saltelli サンプリング＋Sobol解析により、一次感度 S1 と総合効果 ST を算出する。理論式は評価が安価なため、サロゲート（MOP/CoP）を経由せず直接モンテカルロで叩く。これにより代理モデルの近似誤差が指標に混入せず、「サロゲート誤差か物理か」の切り分け問題も消える。'));
children.push(p([new TextRun({text:'実装した4要件: ', font:JP, size:21, bold:true, color:NAVY})]));
children.push(bullet('① 入力分布モード切替: design（設定上下限の一様分布／設計探索用） と variation（実工程3σの正規分布／ばらつきリスク評価用）。どちらのモードで出した指標かを図に明記。'));
children.push(bullet('② 独立性: 独立な上流変数にのみDOEを張り、セル設計計算は評価関数の内部に含める。'));
children.push(bullet('③ 時間依存性: 評価時点を複数指定し、感度指標の時間推移を出力（支配因子の変遷）。'));
children.push(bullet('④ 物理妥当域マスキング: 300W維持不可（判別式負）・温度外挿・非物理値を無効サンプルとして検出し、除外率を記録・警告（基準5年で約28%、8年で最大約39%）。処理方針は §4.5 に明記。'));

// ===== §4.5 数値信頼性の確認 (P1) =====
children.push(h('4.5 数値信頼性の確認', HeadingLevel.HEADING_2));
children.push(p('指標を読者が信用してよいか自分で判断できるよう、収束・除外率・代入方針・分母定義をまとめる。本解析の主感度・ネットワーク・収束は N=4096（Saltelli 65,536点／モード。2次指標 S2 を含む）、時間推移は N=2048（30,720点／時点）、モード割合は N=1024（9,216点／時点）で算出した。DC_v5 実式の1点あたり評価時間は約0.66 ms（実測）である。'));
children.push(p([new TextRun({text:'注（E-5, N の使い分け）: ', font:JP, size:19, bold:true}), new TextRun({text:'N は解析目的で変える。2次指標 S2 を要する図（主感度・ネットワーク・収束）は Saltelli 行列が (2d+2)N と大きくなるため精度確保に N=4096 を用い、S2 不要で多時点を回す図（時間推移・モード割合）は N を下げて計算量を抑えた。各図キャプションに N と実評価点数を併記し、本文と一致させている。', font:JP, size:19, color:GREY})]));
children.push(p([new TextRun({text:'(1) 収束と信頼区間: ', font:JP, size:20, bold:true, color:NAVY}), new TextRun({text:'全ての棒グラフに 95%信頼区間を誤差棒で表示した。評価点数を増やすと信頼区間が縮小し順位が確定する（例：限界Li塩濃度の曲路率 ST は 1,152点で 0.48±0.16 → 36,864点で 0.50±0.03）。交互作用ネットワーク図では、2次指標 S2 の 95%信頼区間が 0 を跨ぐ（非有意な）エッジを破線・淡色に落とし、ノイズを太い線として誤読させないようにした。', font:JP, size:20})]));
children.push(...fig('sobol_convergence.png', 560, '図0. Sobol指標の収束（限界Li塩濃度, design, 5年）。横軸=実際に評価した点数（対数）、縦軸=ST、誤差棒=95%CI。N≈2,000（約3万点）以上で順位が確定する。'));
children.push(p([new TextRun({text:'(2) 無効サンプルの処理: ', font:JP, size:20, bold:true, color:NAVY}), new TextRun({text:'無効サンプルの扱いを明示的な引数 invalid_policy（median=中央値代入／penalty=worst-case代入／report_only）で選択できるようにした。既定は median。ただし欠測はランダムではなく、300W維持不可になるのは低塗布量・高温の個体であり、まさに感度を測りたい因子と強く相関する。したがって代入は指標を系統的に歪め得る。', font:JP, size:20})]));
children.push(p([new TextRun({text:'(3) 代入方針のロバスト性【本検討で判明した数値的注意点】: ', font:JP, size:20, bold:true, color:ACC}), new TextRun({text:'限界Li塩濃度の全域 ST 上位を median と penalty で比較すると順位が入れ替わった（median: 曲路率>塗布量>密度／penalty: 塗布量>抵抗>温度。top3 非安定）。penalty は「無効化の原因（塗布量・温度）」を最悪値で埋めるため、Cli の大きさを決める因子（曲路率）と成立可否を決める因子を混同する。よって全域の限界Li塩濃度感度は「成立する設計に条件づけた指標」と解釈し、成立可否そのものは次の二値応答で別途分解するのが正しい。なお §5.4 の核心（領域条件付きの曲路率→密度の入れ替わり）は、この不安定性の影響下にありながらも3手法で再現することを F-1 検証で確認した（§5.4）。', font:JP, size:20})]));
children.push(p([new TextRun({text:'(4) 二値応答「300W維持可否」の追加: ', font:JP, size:20, bold:true, color:NAVY}), new TextRun({text:'300W維持の成否（0/1）を新しい応答として追加した。これは全域で定義されるため代入が不要で、欠測バイアスの影響を受けない。「どの因子が電力維持の成否を支配するか」に直接答え、有効率の時系列（84%→61%）の因子分解にあたる。結果は塗布量・セル抵抗・使用温度が支配（§5.1 参照）。', font:JP, size:20})]));
children.push(p([new TextRun({text:'(5) 母集団比率の分母: ', font:JP, size:20, bold:true, color:NAVY}), new TextRun({text:'拡散劣化モード割合を「全サンプル基準」と「有効サンプル基準」の2分母で併記した（図3・図3補）。8年時点で 42%（全基準）に対し 68%（有効基準）と乖離する。脱落するのは高塗布量＝拡散モードに落ちやすい個体なので、有効基準は生存者バイアスで過大評価となる。この乖離自体が報告すべき結果である（§5.2 の E-4 参照）。', font:JP, size:20})]));

// ===== §5 結果 =====
children.push(h('5. 結果', HeadingLevel.HEADING_1));
children.push(h('5.1 応答ごとに支配因子が異なる', HeadingLevel.HEADING_2));
children.push(p('放電後電圧（抵抗劣化モードの指標）、限界Li塩濃度（拡散劣化モードの指標）、および300W維持可否（二値＝電力維持の成否）の3応答で、支配因子が明確に分離する。放電後電圧と維持可否は 塗布量・セル抵抗・使用温度 が支配し、限界Li塩濃度は 曲路率・塗布量・活物質密度 が支配する。すべて N=4096（65,536点）、誤差棒は95%信頼区間。'));
children.push(...fig('sobol_main.png', 640, '図1. Sobol感度（3応答×2分布モード, design, 5年, N=4096＝65,536点, 誤差棒=95%CI）。上=放電後電圧、中=限界Li塩濃度、下=300W維持可否（二値・代入不要）。左=design、右=variation。各パネルに分布モード・評価時点・N・代入方針・有効率を明記。'));
children.push(table([2500, 3450, 3250], [
  [H('応答（モード）', 2500, AlignmentType.LEFT), H('design での ST 上位', 3450, AlignmentType.LEFT), H('variation での ST 上位', 3250, AlignmentType.LEFT)],
  [{t:'放電後電圧（抵抗劣化）', w:2500, align:AlignmentType.LEFT},{t:'塗布量0.93 / セル抵抗0.54 / 温度0.39', w:3450, align:AlignmentType.LEFT},{t:'温度0.75 / 塗布量0.57 / セル抵抗0.47', w:3250, align:AlignmentType.LEFT}],
  [{t:'限界Li塩濃度（拡散劣化）', w:2500, align:AlignmentType.LEFT},{t:'曲路率0.53 / 塗布量0.32 / 密度0.25', w:3450, align:AlignmentType.LEFT},{t:'曲路率0.38 / 温度0.28 / 密度0.27', w:3250, align:AlignmentType.LEFT}],
  [{t:'300W維持可否（二値, 代入不要）', w:2500, align:AlignmentType.LEFT},{t:'塗布量0.81 / セル抵抗0.46 / 温度0.30', w:3450, align:AlignmentType.LEFT},{t:'温度0.79 / 塗布量0.39 / セル抵抗0.31', w:3250, align:AlignmentType.LEFT}],
]));
children.push(p([new TextRun({text:'分布モードで順位が変わる: ', font:JP, size:19, bold:true}), new TextRun({text:'variation（ばらつき）では使用温度の寄与が跳ね上がり、放電後電圧・維持可否とも温度が首位になる。設計探索（design）で「温度は自分で振らないから効かない」と見えても、ばらつきリスク評価では温度が主役になる。Sobol指標は与えた入力分布に完全従属するため、どちらのモードの指標かを常に明記する必要がある（詳細は §5.5）。', font:JP, size:19, color:GREY})]));

children.push(h('5.2 保存劣化過程での支配モードの変遷（不確かさ伝播の成果）', HeadingLevel.HEADING_2));
children.push(p('感度指標の時間推移を見ると、放電後電圧では使用温度・セル抵抗の寄与が保存とともに拡大する（温度加速項の顕在化）。一方、限界Li塩濃度では曲路率・塗布量が一貫して支配する。'));
children.push(...fig('sobol_time_evolution.png', 640, '図2. 感度指標の時間推移（design, N=2048＝30,720点/時点, 帯=95%CI）。左=放電後電圧、中=限界Li塩濃度、右=300W維持可否。横軸=保存年、縦軸=ST。'));
children.push(p([new TextRun({text:'位置づけ（レビューの姿勢に基づく峻別）: ', font:JP, size:21, bold:true, color:NAVY}), new TextRun({text:'この時間推移は厳密には感度解析というより理論式の構造上ほぼ必然の挙動である。劣化項が r(T)·t と k(T)·√t なので t=0 では温度の寄与は定義上ゼロで、増えるしかない。したがって以下のモード遷移は「感度でしか出ない結論」ではなく', font:JP, size:21}), new TextRun({text:'不確かさ伝播（UP）の成果', font:JP, size:21, bold:true}), new TextRun({text:'として、理論式の帰結を定量的に確認し遷移時期と母集団比率を定量化したものと位置づける。真に非自明な発見は §5.4（領域条件付き感度）にある。', font:JP, size:21})]));
children.push(p('公称設計では、保存が進むと限界Li塩濃度が設計budget（1.4M）を超え、同時に放電後電圧が2.5Vを割る。すなわち抵抗劣化モードから電解液Li+濃度拡散劣化モードへ、t≈5.8年で遷移する。母集団で見ると、拡散劣化モードの個体割合と成立率の推移は次のとおり。'));
children.push(...fig('sobol_mode_stacked.png', 470, '図3. 母集団の劣化モード内訳（design, N=1024＝9,216点/時点, 合計100%積み上げ面グラフ）。抵抗劣化／拡散劣化／300W維持不可 の3区分。無効個体（維持不可）が保存とともに拡大し、成立域が侵食される。'));
children.push(...fig('sobol_mode_transition.png', 620, '図3補. 支配モードの変遷（従＝折れ線）。左=公称設計の軌跡（放電後電圧・限界Li塩濃度が5〜6年で閾値を越えモード遷移）。右=拡散モード割合を全サンプル基準と有効サンプル基準の2分母で併記＋成立率・有効率。design, N=1024＝9,216点/時点。'));
children.push(table([2100, 1400, 1400, 1400, 1400], [
  [H('保存年'), H('0.25'), H('1'), H('3'), H('8')],
  [{t:'拡散モード割合（全サンプル基準）', align:AlignmentType.LEFT, w:2100},{t:'44%'},{t:'46%'},{t:'47%'},{t:'42%'}],
  [{t:'拡散モード割合（有効基準）', align:AlignmentType.LEFT, w:2100, color:GOLD},{t:'53%'},{t:'55%'},{t:'60%'},{t:'68%'}],
  [{t:'設計成立率（全サンプル基準）', align:AlignmentType.LEFT, w:2100},{t:'39%'},{t:'36%'},{t:'29%'},{t:'16%'}],
  [{t:'有効率=300W維持可（全基準）', align:AlignmentType.LEFT, w:2100},{t:'84%'},{t:'84%'},{t:'79%'},{t:'61%'}],
]));
children.push(p([new TextRun({text:'分母で書き分ける（E-4）: ', font:JP, size:19, bold:true, color:ACC}), new TextRun({text:'拡散モード割合は分母で挙動が逆になる。有効サンプル基準では 53→55→57→60→64→68% と単調増加するが、全サンプル基準では 44→45→46→47→47→46→42% と 2〜3年の47%を頂点に減少する。全基準で減るのは、保存が進むと無効個体（300W維持不可）が増え（有効率84%→61%）、その希釈により「有効かつ拡散モード」の全体に占める割合が下がるためである。脱落するのは高塗布量＝拡散モードに落ちやすい個体なので、有効基準は生存者バイアスで過大となる。§4.5(5) 参照。', font:JP, size:19, color:GREY})]));
children.push(p([new TextRun({text:'設計上の示唆: ', font:JP, size:19, bold:true}), new TextRun({text:'初期に抵抗劣化モードで成立していても、保存で限界Li塩濃度が上昇し拡散劣化モードへ落ちる。したがって「劣化後も限界Li塩濃度を下回る」初期Li塩濃度設計が必要条件であり、そのうえで抵抗上昇を抑えることが高出力寿命の延伸に直結する（レポートの改善方向性と整合）。', font:JP, size:19, color:GREY})]));

children.push(h('5.3 交互作用の可視化（第3の柱の本体）', HeadingLevel.HEADING_2));
children.push(p('並行座標は交互作用の表現が構造的に苦手（軸の並び順に依存し、3次以上は事実上見えない）。そこを埋めるのが交互作用ネットワーク図である。ノード径＝ST（総合効果）、エッジ太さ＝2次のSobol指標 S2（2変数の組合せ効果）を表す。'));
children.push(...fig('sobol_network.png', 600, '図4. 交互作用ネットワーク（限界Li塩濃度, design, 5年, N=4096＝65,536点）。ノード径＝ST、線＝2次Sobol指標 S2。S2の95%CIが0を跨ぐ非有意なエッジは破線・淡色に落とし、ノイズを太線として誤読させない。'));

children.push(h('5.4 領域条件付き感度と代入方針への頑健性（本検討の真の発見）', HeadingLevel.HEADING_2));
children.push(p('全体感度では「効き方が単調か、特定領域だけで変化するか」は答えられない。並行座標で領域を絞って感度を取り直すと初めて見える。全域→中間→拡散モード頻発域 と段階的に絞ると、限界Li塩濃度の支配因子は 曲路率（材料物性・制御しにくい）から 活物質密度（設計因子・制御できる）へ連続的に入れ替わる。部分集合が小さすぎると指標が不安定になるため、最小サンプル数のガード（有効N<200で警告）を設けている。'));
children.push(...fig('sobol_conditional.png', 620, '図5. 段階的3領域の領域条件付き感度（限界Li塩濃度, design, 5年, 各領域 N=2048＝30,720点）。全域→中間→拡散モード頻発域 の順に絞ると、材料因子=曲路率から制御可能な設計因子=活物質密度へ首位が連続的に入れ替わる。棒色＝因子分類（設計因子／材料物性／使用条件）。各領域ラベルにサンプル数・有効率・代入率を明記。'));
children.push(p([new TextRun({text:'この結論は感度解析でしか出ない: ', font:JP, size:20, bold:true, color:ACC}), new TextRun({text:'モード遷移（§5.2）が定W放電の代数的帰結であるのに対し、領域条件付きで支配因子が 材料物性（制御しにくい）→設計因子（制御できる）へ入れ替わるのは非自明で、「打ち手がある」という設計上の意味を持つ。報告書の価値はここにある。', font:JP, size:20})]));
children.push(h('5.4.1 頑健性検証 F-1（代入方針への頑健性）', HeadingLevel.HEADING_2));
children.push(p([new TextRun({text:'核心の懸念と検証: ', font:JP, size:20, bold:true, color:NAVY}), new TextRun({text:'この入れ替わりも限界Li塩濃度の感度であり、§4.5(3) で判明した「代入方針で ST 上位が入れ替わる」不安定性の影響下にある。そこで、拡散モード頻発域の有効率・代入率を実測し、invalid_policy を median と penalty の両方に振り、さらに代入非依存の参照として有効サンプルのみの Spearman |ρ|（順位相関ベース簡易感度。Saltelli 構造を使わないため厳密な分散分解ではなく単調性の指標）を併用して、「曲路率→活物質密度」の入れ替わりが3手法で再現するかを検証した。', font:JP, size:20})]));
children.push(table([2050, 1150, 1150, 1750, 1750, 1750], [
  [H('領域（塗布量／曲路率）', 2050, AlignmentType.LEFT), H('有効率', 1150), H('代入率', 1150), H('median ST 首位', 1750), H('penalty ST 首位', 1750), H('Spearman|ρ| 首位', 1750)],
  [{t:'全域', w:2050, align:AlignmentType.LEFT},{t:'72%'},{t:'28%'},{t:'曲路率 0.53'},{t:'塗布量 0.71'},{t:'曲路率 0.70'}],
  [{t:'中間（8〜13／1.6〜2.0）', w:2050, align:AlignmentType.LEFT},{t:'89%'},{t:'11%'},{t:'密度 0.36', color:GREEN, bold:true},{t:'抵抗 0.57'},{t:'密度 0.57', color:GREEN, bold:true}],
  [{t:'拡散頻発域（10〜13／1.7〜2.0）', w:2050, align:AlignmentType.LEFT},{t:'98%', color:GREEN, bold:true},{t:'2%', color:GREEN, bold:true},{t:'密度 0.45', color:GREEN, bold:true},{t:'密度 0.31', color:GREEN, bold:true},{t:'密度 0.66', color:GREEN, bold:true}],
]));
children.push(...fig('sobol_f1_robustness.png', 640, '図6. F-1 代入方針ロバスト性検証（限界Li塩濃度, 5年, 各領域 Saltelli 18,432点＋有効LHS 約4,300〜5,900点）。左=median代入 Sobol ST、中=penalty代入 Sobol ST、右=Spearman|ρ|（代入非依存）。いずれも拡散頻発域で活物質密度が首位（緑）。手法名と限界を図中に明記。'));
children.push(p([new TextRun({text:'判定＝代入方針に頑健（格上げ）: ', font:JP, size:20, bold:true, color:GREEN}), new TextRun({text:'拡散モード頻発域では median・penalty・Spearman の3手法すべてで活物質密度が首位となり、「曲路率→活物質密度」の入れ替わりが再現した。さらに核心が乗る拡散頻発域の代入率はわずか2%（全域28%・中間11%より格段に小さい）であり、核心は代入の影響を最も受けにくい領域にある。むしろ全域の方が代入の影響を強く受ける。以上より、§4.5(3) の「限界Li塩濃度の感度は代入方針依存」という懸念は §5.4 の核心には及ばず、明示的に解消されたと判断する。§5.4 を「代入方針に頑健な発見」に格上げする。', font:JP, size:20})]));

children.push(h('5.5 分布モードによる支配因子の反転（B-2）', HeadingLevel.HEADING_2));
children.push(p('§5.1 で触れたとおり、Sobol指標は与えた入力分布に完全従属する。design（設計上下限の一様分布）と variation（実工程3σの正規分布）で支配因子が反転する。これは §5.4 の領域による反転とは別種の反転であり、「設計マージンを何に対して取るか」に直結する運用判断である。'));
children.push(table([2650, 3300, 3300], [
  [H('応答', 2650, AlignmentType.LEFT), H('design 首位（設計探索）', 3300, AlignmentType.LEFT), H('variation 首位（ばらつきリスク）', 3300, AlignmentType.LEFT)],
  [{t:'放電後電圧', w:2650, align:AlignmentType.LEFT},{t:'塗布量 0.93', w:3300, align:AlignmentType.LEFT},{t:'使用温度 0.75', w:3300, align:AlignmentType.LEFT, color:ACC, bold:true}],
  [{t:'300W維持可否（二値）', w:2650, align:AlignmentType.LEFT},{t:'塗布量 0.81', w:3300, align:AlignmentType.LEFT},{t:'使用温度 0.79', w:3300, align:AlignmentType.LEFT, color:ACC, bold:true}],
]));
children.push(p([new TextRun({text:'運用上の意味: ', font:JP, size:20, bold:true, color:NAVY}), new TextRun({text:'設計探索（design）では自分で振る設計因子＝塗布量が首位に見えるが、量産ばらつき（variation）では自分では振らない使用温度が首位に反転する。「温度は設計変数でないから効かない」と設計探索の絵だけで判断すると、実運用での温度ばらつきに対するマージン不足を見落とす。Sobol 指標は入力分布に従属するため、どのモードの指標かを図・本文で常に明記すること。設計マージンは design で効く因子（塗布量）に対してだけでなく、variation で効く因子（温度）に対しても取る必要がある。', font:JP, size:20})]));

// ===== §6 アーキテクチャ =====
children.push(h('6. 設計探索アーキテクチャ（①②③の統合）', HeadingLevel.HEADING_1));
children.push(p('感度スクリーニング（①）で効く変数を自動抽出して並行座標へ反映し、交互作用ネットワーク（②）で並行座標が苦手な多変数関係を補完し、感度上位2軸で制約つきコンター（③）を描いて局所地形のOK/NGを把握する。成立域が狭い／支配モードが変わる場合は範囲を絞って感度を再計算する（領域条件付き・時点別）フィードバックループを持つ。'));
children.push(...fig('explore_architecture.png', 640, '図7. 設計探索アーキテクチャ全体像。感度スクリーニング→並行座標＋交互作用ネットワーク→制約つきコンター。'));
children.push(h('6.1 感度スクリーニング → 擬似並行座標（自動反映）', HeadingLevel.HEADING_2));
children.push(p('Sobol の ST 上位を能動軸として自動選択し、並行座標の軸順・強調に反映する（★能動軸を左に集約・強調、非能動軸は淡色）。個体は放電後電圧でカラーリングし、制約成立個体を強調する。これにより「どの軸に注目すべきか」を感度解析が決め、並行座標に橋渡しする。'));
children.push(...fig('explore_parallel.png', 630, '図8. 擬似並行座標プロット（Python実装）。感度スクリーニングを軸選択へ自動反映。★＝能動軸（ST上位）。'));
children.push(h('6.2 制約つき2軸コンター（局所地形 OK/NG）', HeadingLevel.HEADING_2));
children.push(p([new TextRun({text:'軸選択の根拠（D-2）: ', font:JP, size:21, bold:true}), new TextRun({text:'放電後電圧（y_end）基準の感度上位2軸である セル抵抗×正極塗布量 で主断面を描く（図9）。加えて、限界Li塩濃度（Cli）基準の感度上位2軸である 塗布量×活物質密度 の断面を追加し（図10）、拡散劣化モード側の地形を補完する。いずれも両制約線（放電後電圧≥2.5V, 限界Li塩濃度≤1.4M）を重ねる。', font:JP, size:21})]));
children.push(...fig('explore_contour.png', 430, '図9. 制約つき2軸コンター（y_end基準の上位2軸＝セル抵抗×正極塗布量, 5年後）。赤=放電後電圧下限、白破線=限界Li塩濃度上限、灰網掛=NG。固定値: 正極利用率0.205 Ah/g・活物質密度3.5 g/cm³・電解液拡散係数4.0e-10 m²/s・正極曲路率1.6・使用温度38℃（キャプション下部にも注記）。'));
children.push(...fig('explore_contour_cli.png', 430, '図10. 追加断面（Cli基準の上位2軸＝正極塗布量×活物質密度, 5年後）。同一の両制約線を重ねる。塗布量が高く密度が低い（＝空隙が多く実効拡散が長い）ほど限界Li塩濃度を超えNGになる。固定値: セル抵抗5.3mΩ・正極利用率0.205 Ah/g・電解液拡散係数4.0e-10 m²/s・正極曲路率1.6・使用温度38℃。'));
children.push(p('これらは報告書 NCR2170JB Step2 の設計探索（塗布量82±3 g/m²・セル抵抗≤5.3mΩで成立）と同形式・同傾向である。'));
children.push(h('6.3 コンター条件比較（曲路率 低/中/高, D-3）', HeadingLevel.HEADING_2));
children.push(p('図9・図10は固定値を1点に定めた断面である。固定した材料物性が地形をどれだけ動かすかを示すため、正極曲路率を 低(1.4)／中(1.7)／高(2.0) と振った3枚を横並びで比較する。曲路率が上がるほど実効拡散が短くなり限界Li塩濃度側の制約が厳しくなって、成立域（白地）が縮小し、2.0では断面全域がNGになる。これは D-1 の「固定値をどう選ぶかで地形が変わる」問題への実質的な回答でもある。'));
children.push(...fig('explore_contour_gamma3.png', 660, '図11. コンター条件比較（セル抵抗×塗布量, 5年後, 正極曲路率 低1.4／中1.7／高2.0）。曲路率上昇とともに成立域（白地）が縮小し、2.0では全域NG（灰網掛）。他の固定値は図9と同一。'));

// ===== §7 結論 (E-2) =====
children.push(h('7. 考察・結論・今後', HeadingLevel.HEADING_1));
children.push(p([new TextRun({text:'確定した核心（§5.4）: ', font:JP, size:21, bold:true, color:ACC}), new TextRun({text:'限界Li塩濃度の支配因子は、拡散劣化モードが頻発する領域で 材料物性=曲路率 から 制御可能な設計因子=活物質密度 へ入れ替わる。この入れ替わりは median／penalty／Spearman|ρ| の3手法で再現し、核心が乗る領域の代入率はわずか2%であることから、代入方針に頑健であると確定した（§4.5(3) の懸念を明示的に解消）。全域感度では見えず領域を絞って初めて現れる、感度解析でしか出ない結論であり、「材料で決まる＝打ち手がない」という誤解を退けて設計上の打ち手（密度）を示す。', font:JP, size:21})]));
children.push(bullet('DC_v5 の保存劣化理論式を直接モンテカルロで叩く Sobol 感度解析を実装し、社内テクニカルレポートと部分整合することを確認した（理論構造・設計成立範囲は一致、感度順位は範囲・代入・領域依存）。', {}));
children.push(bullet('応答ごとに支配因子が分離する（放電後電圧←塗布量/抵抗/温度、限界Li塩濃度←曲路率/塗布量/密度、二値維持可否←塗布量/抵抗/温度）ことを、95%信頼区間つきで定量化した。', {}));
children.push(bullet('限界Li塩濃度の全域感度は代入方針で ST 上位が入れ替わる（本検討で判明した数値的注意点, §4.5(3)）。成立可否は代入不要の二値応答で別途分解し、欠測バイアスを回避した。', {}));
children.push(bullet('分布モード（design／variation）で支配因子が反転する（放電後電圧・維持可否とも design=塗布量→variation=温度, §5.5）。設計マージンを何に対して取るかの運用判断に直結する。', {}));
children.push(p([new TextRun({text:'不確かさ伝播（UP）の成果として格下げした項目: ', font:JP, size:21, bold:true, color:NAVY}), new TextRun({text:'保存に伴う抵抗劣化→拡散劣化のモード遷移と温度寄与の時間拡大は、劣化項が r(T)·t と k(T)·√t である以上の理論式の代数的帰結であり、モンテカルロを回さずとも導ける。よって「感度の発見」ではなく、遷移時期（公称≈5.8年）と母集団比率（分母併記）を定量化した UP の成果と位置づける。', font:JP, size:21})]));
children.push(p([new TextRun({text:'今後の発展: ', font:JP, size:21, bold:true, color:NAVY})]));
children.push(bullet('F-1 の残課題は本統合版 §8 で消し込んだ: 領域境界近傍の連続性は完全成立（段差なく滑らかに首位交代, s≈0.58 で交差）、8年再現性は代入非依存の2手法（median/Spearman）で成立（penalty のみ温度へ発散＝代入率上昇による §4.5(3) の既知効果）。'));
children.push(bullet('セル設計計算を DC_v5 CellDesign（run_calc）実体へ接続（現状は物理無矛盾な最小スラブモデル）。'));
children.push(bullet('Li塩消費モデル（保存によるLiPF6消費で初期Li塩濃度が低下）を組み込み、拡散劣化モードへの到達時刻を予測。'));
children.push(bullet('Plotly/Dash によるインタラクティブ版（ブラッシング連動）。現状は擬似＝静的Python図。'));

// ===== 付録A =====
// ===== §8 統合版で追加した検証 (F-1 残課題の消し込み) =====
children.push(h('8. F-1 残課題の消し込み検証（統合版で追加）', HeadingLevel.HEADING_1));
children.push(p('改訂第3版 §7 で「今後の検証対象」として残した F-1 の2つの残課題を実測で消し込み、本統合版に統合する。いずれも §5.4 の核心（拡散モード頻発域で 限界Li塩濃度の支配因子が 曲路率→活物質密度 へ入れ替わる）を対象とし、乱数シードは固定して再現性を確保した。'));
children.push(h('8.1 検証B：領域境界近傍での連続性', HeadingLevel.HEADING_2));
children.push(p('§5.4 の入れ替わりが領域の切り方に依存する「崖（不連続）」ではなく、連続的な現象であることを確認する。全域から拡散モード頻発域へ向けて、塗布量の下限を 6→10 mg/cm²、曲路率の下限を 1.4→1.7 へ同時に連続的に絞り込み（絞り込み度 s=0→1）、各段階で 限界Li塩濃度 の ST（median, N=4096）を算出した。'));
children.push(...fig('sobol_f1_continuation.png', 660, '図12. F-1 残課題の消し込み。左＝検証B（領域境界の連続性, design, 5年, N=4096＝各段階65,536点）: 曲路率STが単調に低下・活物質密度STが単調に上昇し、s≈0.58 で滑らかに首位交代（崖ではない）。右＝検証A（8年再現性）: 拡散頻発域の首位因子STを5年（淡）と8年（濃）で比較。median/Spearman は8年でも活物質密度が首位、penalty のみ使用温度へ発散。'));
children.push(table([1900, 1500, 1500, 1500, 1900], [
  [H('絞り込み度 s', 1900), H('塗布量下限', 1500), H('曲路率下限', 1500), H('曲路率 ST', 1500), H('活物質密度 ST', 1900)],
  [{t:'0.00（全域）', w:1900, align:AlignmentType.LEFT},{t:'6.0'},{t:'1.40'},{t:'0.50', color:GREEN, bold:true},{t:'0.24'}],
  [{t:'0.33', w:1900, align:AlignmentType.LEFT},{t:'7.3'},{t:'1.50'},{t:'0.41', color:GREEN, bold:true},{t:'0.30'}],
  [{t:'0.50', w:1900, align:AlignmentType.LEFT},{t:'8.0'},{t:'1.55'},{t:'0.38', color:GREEN, bold:true},{t:'0.33'}],
  [{t:'0.67', w:1900, align:AlignmentType.LEFT},{t:'8.7'},{t:'1.60'},{t:'0.32'},{t:'0.37', color:'4C78A8', bold:true}],
  [{t:'1.00（頻発域）', w:1900, align:AlignmentType.LEFT},{t:'10.0'},{t:'1.70'},{t:'0.22'},{t:'0.46', color:'4C78A8', bold:true}],
]));
children.push(p([new TextRun({text:'判定＝完全成立: ', font:JP, size:20, bold:true, color:GREEN}), new TextRun({text:'曲路率STは 0.50→0.22 へ単調低下、活物質密度STは 0.24→0.46 へ単調上昇し、s≈0.58 付近で段差なく首位が交代した。有効率も 72%→98% へ単調に上がる。したがって §5.4 の入れ替わりは特定の領域境界の取り方に依存する不連続な人工物ではなく、拡散モードへ近づくほど連続的に密度支配へ移行する頑健な現象である。', font:JP, size:20})]));
children.push(h('8.2 検証A：他時点（8年）での再現性', HeadingLevel.HEADING_2));
children.push(p('§5.4 は基準5年での結果である。より劣化が進む8年時点でも同じ入れ替わりが再現するかを、5年と同じ3手法（median代入 / penalty代入 / 代入非依存の Spearman |ρ|）で拡散モード頻発域について算出した。'));
children.push(table([2400, 2000, 2100, 2100], [
  [H('手法', 2400, AlignmentType.LEFT), H('5年 頻発域 首位', 2000), H('8年 頻発域 首位', 2100), H('8年 判定', 2100)],
  [{t:'Sobol ST（median 代入）', w:2400, align:AlignmentType.LEFT},{t:'活物質密度 0.45'},{t:'活物質密度 0.43', color:GREEN, bold:true},{t:'再現', color:GREEN, bold:true}],
  [{t:'Sobol ST（penalty 代入）', w:2400, align:AlignmentType.LEFT},{t:'活物質密度 0.31'},{t:'使用温度 0.53', color:ACC, bold:true},{t:'発散', color:ACC, bold:true}],
  [{t:'Spearman|ρ|（代入非依存）', w:2400, align:AlignmentType.LEFT},{t:'活物質密度 0.66'},{t:'活物質密度 0.63', color:GREEN, bold:true},{t:'再現', color:GREEN, bold:true}],
]));
children.push(p([new TextRun({text:'判定＝代入非依存の2手法で成立（部分成立）: ', font:JP, size:20, bold:true, color:NAVY}), new TextRun({text:'8年でも median（中央値代入）と Spearman（代入非依存）は活物質密度を首位に維持し、核心は保たれる。一方 penalty（worst-case 代入）は8年で使用温度へ発散した。これは頑健性の破れではなく想定内である—8年は300W維持不可の個体が急増（頻発域の有効率も5年98%→8年91%）し、penalty は §4.5(3) で述べたとおり「無効化の原因（高温）」を最悪値で埋めるため、劣化が進むほど温度を強く拾う。すなわち penalty の発散は §4.5(3) の既知の性質の再確認であり、代入の影響を受けない指標（median 中央値・Spearman）では8年でも密度支配が確定している。', font:JP, size:20})]));
children.push(h('8.3 統合後の結論', HeadingLevel.HEADING_2));
children.push(p([new TextRun({text:'§5.4 の核心「拡散モード頻発域で 曲路率→活物質密度 へ支配因子が入れ替わる」は、(i) 代入方針3手法（§5.4.1）、(ii) 領域境界の連続性（§8.1, 完全成立）、(iii) 他時点8年（§8.2, 代入非依存の2手法で成立）の三面から検証され、代入非依存の指標では一貫して確定した。penalty 代入が全域および8年で温度・塗布量を拾うのは、成立可否の駆動因子と Cli の大きさの駆動因子を混同する §4.5(3) の性質であり、成立可否は二値応答で別途分解済みである。したがって設計上の打ち手（活物質密度による限界Li塩濃度マージン確保）は、保存後半（8年）まで有効と結論づけられる。', font:JP, size:21})]));

children.push(h('付録A. 実装・再現手順', HeadingLevel.HEADING_1));
children.push(p('乱数シードは全て固定し再現性を担保。図中の文言は日本語。主要モジュールは以下（mf_demo/explorer/）。'));
children.push(bullet('vendor_dcv5/dc_model.py … DC_v5 実式を無改変で取り込み（劣化式は実物）'));
children.push(bullet('cell_design.py … 独立上流変数→派生量（B-4②）'));
children.push(bullet('degradation.py … 実式ラッパ（b\'=2.0, Arrhenius, 3応答=電圧/Li塩/維持可否, 2モード）'));
children.push(bullet('config.py / sensitivity.py … 分布モード・時間依存・マスキング・領域条件付き・F-1頑健性'));
children.push(bullet('plots.py / screening.py / viz_explorer.py … 感度図・スクリーニング・並行座標/コンター/アーキテクチャ'));
children.push(p([new TextRun({text:'実行: ', font:JP, size:20, bold:true}), new TextRun({text:'python -m mf_demo.explorer.run_sensitivity 4096 2048（感度図）／ python -m mf_demo.explorer.run_explorer 600（①②③ 探索図）／ python -m mf_demo.explorer.run_figures_v3（D群・E-6・F-1）／ python -m mf_demo.explorer.run_f1_continuation（§8 の8年再現性・境界連続性, 図12）。', font:JP, size:19, color:GREY})]));
children.push(p([new TextRun({text:'免責: ', font:JP, size:19, bold:true, color:ACC}), new TextRun({text:'本プロトタイプは原理を絵で伝えることを優先した合成モデルであり、精度較正済みの設計ツールではない。数値は DC_v5 row82 近傍のオーダーに合わせてある。', font:JP, size:19, color:GREY})]));

// ===== 付録B 完了チェックリスト =====
children.push(h('付録B. 改訂第3版 改善項目 完了チェックリスト', HeadingLevel.HEADING_1));
children.push(p('改善依頼書（第III部）の残14件への対応状況。第2版で解決済みの数値信頼性（N・信頼区間・収束・代入方針・二値応答・分母併記）は維持している。'));
children.push(table([900, 4400, 700, 4000], [
  [H('ID', 900), H('内容', 4400, AlignmentType.LEFT), H('完了', 700), H('備考', 4000, AlignmentType.LEFT)],
  [{t:'F-1', w:900},{t:'§5.4 のロバスト性検証（median/penalty/代入非依存手法）', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'判定=頑健。3手法とも拡散頻発域で密度首位。頻発域の代入率2%で§4.5(3)懸念を解消し格上げ（§5.4.1/図6）', w:4000, align:AlignmentType.LEFT}],
  [{t:'E-1', w:900},{t:'エグゼクティブサマリー書き換え', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'核心=§5.4/F-1、モード遷移=UP成果、部分整合、§4.5(3)発見を明記', w:4000, align:AlignmentType.LEFT}],
  [{t:'E-2', w:900},{t:'§7 結論の書き換え', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'§5.4確定を明記。代入依存性・二値分解を含め、モード遷移をUPへ格下げ。F-1残課題を今後へ', w:4000, align:AlignmentType.LEFT}],
  [{t:'E-4', w:900},{t:'拡散モード割合の記述修正（分母で書き分け）', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'全基準44→47→42%（希釈で減少）、有効基準53→68%（増加）を機構まで記述（§5.2）', w:4000, align:AlignmentType.LEFT}],
  [{t:'B-2', w:900},{t:'§5.5 新設＋参照切れ修正', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'§5.5「分布モードによる支配因子の反転」新設。§5.1末尾の参照を§5.5へ修正', w:4000, align:AlignmentType.LEFT}],
  [{t:'E-5', w:900},{t:'N 表記の統一（全図キャプション）', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'N=4096/2048/1024 の使い分け理由を§4.5に明記。全図に N＋実評価点数を併記', w:4000, align:AlignmentType.LEFT}],
  [{t:'D-1', w:900},{t:'図9 の固定値明記', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'固定5変数（利用率0.205/密度3.5/拡散4.0e-10/曲路率1.6/温度38℃）をキャプション明記', w:4000, align:AlignmentType.LEFT}],
  [{t:'D-2', w:900},{t:'軸選択根拠＋塗布量×密度 断面の追加', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'「y_end基準で軸選択」を明記。Cli主体の塗布量×密度断面（図10）を新規追加、両制約線重ね', w:4000, align:AlignmentType.LEFT}],
  [{t:'D-3', w:900},{t:'コンター条件比較（曲路率 低/中/高）', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'曲路率1.4/1.7/2.0 の3枚横並び（図11）。2.0で全域NG。§6.3', w:4000, align:AlignmentType.LEFT}],
  [{t:'D-4-1', w:900},{t:'図5 の因子分類による色分け', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'設計因子／材料物性／使用条件 で棒を色分け（図5）', w:4000, align:AlignmentType.LEFT}],
  [{t:'D-4-2', w:900},{t:'図5 の段階的3領域化', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'全域→中間→拡散頻発域 の3領域で連続的な首位入れ替わりを表示（図5）', w:4000, align:AlignmentType.LEFT}],
  [{t:'D-4-3', w:900},{t:'図5 に各領域のサンプル数・有効率・代入率を明記', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'各領域ラベルに N・有効率・代入率を併記（F-1と直結, 表§5.4.1と一致）', w:4000, align:AlignmentType.LEFT}],
  [{t:'E-6', w:900},{t:'図3右を3分割積み上げ面グラフへ', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'抵抗劣化／拡散劣化／300W維持不可 の合計100%積み上げを主（図3）、折れ線を従（図3補）', w:4000, align:AlignmentType.LEFT}],
  [{t:'E-3', w:900},{t:'曲路率範囲の妥当性検討＋C-2補', w:4400, align:AlignmentType.LEFT},{t:'✓', color:GREEN, bold:true},{t:'範囲0.60はばらつき3σ(0.58)相当で過大でない。狭域(1.5-1.7)では曲路率順位低下。C-2補で不成立説明を削除（§3.2）', w:4000, align:AlignmentType.LEFT}],
  [{t:'F-1補', w:900, shade:'FCE4D6'},{t:'§5.4 残課題の消し込み（統合版で追加）', w:4400, align:AlignmentType.LEFT, shade:'FCE4D6'},{t:'✓', color:GREEN, bold:true, shade:'FCE4D6'},{t:'§8: 境界連続性=完全成立（s≈0.58で滑らか交代, 図12左）／8年再現性=median・Spearman で成立、penaltyは温度へ発散（§4.5(3)効果, 図12右）', w:4000, align:AlignmentType.LEFT, shade:'FCE4D6'}],
]));
children.push(p([new TextRun({text:'注（統合版）: ', font:JP, size:18, bold:true, color:ACC}), new TextRun({text:'本統合版は改訂第3版（14項目 完了）に、§7 で「今後」としていた F-1 残課題の検証（§8）を統合したもの。数値信頼性・14項目の結論は改訂第3版から不変。', font:JP, size:18, color:GREY})]));

// ===== ドキュメント =====
const doc = new Document({
  styles: { default: { document: { run: { font: JP, size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 30, bold: true, color: NAVY, font: JP }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 24, bold: true, color: ACC, font: JP }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
    ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1200, bottom: 1200, left: 1200, right: 1200 } } },
    footers: { default: new Footer({ children: [ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ children: ['DC向けセル 保存劣化 感度解析報告書（統合版） ／ ', PageNumber.CURRENT], font: JP, size: 16, color: GREY }) ] }) ] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(OUT_DIR, '報告書_保存劣化_感度解析_統合版.docx');
  fs.writeFileSync(out, buf);
  console.log('WROTE', out, buf.length, 'bytes');
});

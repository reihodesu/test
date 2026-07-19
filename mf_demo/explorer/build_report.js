// 保存劣化 感度解析 詳細報告書 (docx-js)
const fs = require('fs');
const path = require('path');
const D = require('docx');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, TableOfContents,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, AlignmentType,
  ImageRun, PageBreak, PageOrientation, LevelFormat, Header, Footer, PageNumber,
} = D;

const FIG = '/home/user/test/mf_demo/output/explorer';
const dims = JSON.parse(fs.readFileSync('/tmp/claude-0/-home-user-test/66f60544-0d32-51d6-b6fc-f2239fe73a6e/scratchpad/figdims.json'));
const JP = 'IPAGothic';
const NAVY = '1F3864', ACC = 'B4472C', GREY = '595959';

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
    children: [new TextRun({ text: '― 理論式ベース Sobol 感度解析による支配因子・支配モードの変遷可視化 ―', font: JP, size: 24, color: ACC })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 900, after: 60 },
    children: [new TextRun({ text: 'プロトタイプ実装報告書', font: JP, size: 26, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: '対象: DC_v5 保存劣化理論式（社内テクニカルレポート T0073-2025-00305 / NCR2170JB Step2 準拠）', font: JP, size: 19, color: GREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '作成日: 2026-07-19', font: JP, size: 19, color: GREY })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ===== 目次 =====
children.push(h('目次', HeadingLevel.HEADING_1));
children.push(new TableOfContents('目次', { hyperlink: true, headingStyleRange: '1-2' }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ===== 概要 =====
children.push(h('概要（エグゼクティブサマリー）', HeadingLevel.HEADING_1));
children.push(p('データセンター（DC）向け高出力円筒セルでは、保存後の出力劣化が設計成立の鍵となる。本報告書は、社内で構築済みの保存劣化理論式（DC_v5, 定W放電モデル）を直接モンテカルロで叩く Sobol 感度解析のプロトタイプを実装し、設計探索3点セット（コンター図・並行座標・感度ネットワーク図）と統合した設計探索アーキテクチャを提示する。'));
children.push(p([ new TextRun({ text: '主要な結果: ', font: JP, size: 21, bold: true, color: NAVY }),
  new TextRun({ text: '①応答（放電後電圧／限界Li塩濃度）ごとに支配因子が明確に分離する。②保存が進むと支配モードが抵抗劣化モードから電解液Li+濃度拡散劣化モードへ遷移する（本検討の核心）。③感度スクリーニングを並行座標へ自動反映し、制約つき2軸コンター（セル抵抗×塗布量）と組み合わせる設計探索アーキテクチャを構築した。', font: JP, size: 21 }) ]));
children.push(p([ new TextRun({ text: '添付テクニカルレポートとの整合: ', font: JP, size: 21, bold: true, color: NAVY }),
  new TextRun({ text: '理論式の構造（線形抵抗劣化・√t容量劣化・Arrhenius 10℃2倍則・限界Li塩濃度）、限界Li塩濃度の感度順位（塗布量／曲路率が主）、および NCR2170JB Step2 の設計成立範囲（放電後電圧≥2.5V かつ 限界Li塩濃度≤1.4M）を再現した。', font: JP, size: 21 }) ]));

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
  [{t:'保存中の抵抗上昇は√より線形（+1mΩ/年想定）', w:3400, align:AlignmentType.LEFT},{t:'R(t)=R0+r·t（線形）を採用', w:3600, align:AlignmentType.LEFT},{t:'一致', color:'2E7D32', bold:true}],
  [{t:'容量復帰率は√t・Arrheniusプロット（10℃2倍則）', w:3400, align:AlignmentType.LEFT},{t:'a(t)=a0+k·√t、kをArrhenius(Ea≈60kJ/mol)', w:3600, align:AlignmentType.LEFT},{t:'一致', color:'2E7D32', bold:true}],
  [{t:'定W放電の放電後電圧一般式', w:3400, align:AlignmentType.LEFT},{t:'y_end=b\'+√(b\'²−zR−zat/3600)', w:3600, align:AlignmentType.LEFT},{t:'一致', color:'2E7D32', bold:true}],
  [{t:'限界Li塩濃度（無次元C-rate→拡散限界）', w:3400, align:AlignmentType.LEFT},{t:'Cli=C_rate·Qareal/(Jlim·1000)', w:3600, align:AlignmentType.LEFT},{t:'一致', color:'2E7D32', bold:true}],
  [{t:'抵抗上昇で限界Li塩濃度が上昇（S18/S35）', w:3400, align:AlignmentType.LEFT},{t:'R(t)↑→C_rate↑→Cli(t)↑ を再現', w:3600, align:AlignmentType.LEFT},{t:'一致', color:'2E7D32', bold:true}],
  [{t:'限界Li塩濃度の影響順位: 塗布量>曲路率>拡散係数（S28）', w:3400, align:AlignmentType.LEFT},{t:'Cli感度ST: 曲路率0.56/塗布量0.33/密度0.26', w:3600, align:AlignmentType.LEFT},{t:'整合（順位再現）', color:'2E7D32', bold:true}],
  [{t:'設計成立: 放電後電圧≥2.5V かつ 限界Li塩濃度≤1.4M（Step2）', w:3400, align:AlignmentType.LEFT},{t:'同一制約でOK/NG・コンター定義', w:3600, align:AlignmentType.LEFT},{t:'一致', color:'2E7D32', bold:true}],
  [{t:'300Wは非常に厳しい（容量・発熱）', w:3400, align:AlignmentType.LEFT},{t:'高温・高塗布量で300W維持不可を無効化', w:3600, align:AlignmentType.LEFT},{t:'一致', color:'2E7D32', bold:true}],
]));
children.push(h('3.1 レビューで反映した改善', HeadingLevel.HEADING_2));
children.push(bullet('放電開始電圧を物理値 b\'=b_ocv/2=2.0V に修正 → 放電後電圧が物理域2.5〜4Vに（レポートの放電後電圧域と一致）'));
children.push(bullet('主応答を「放電後電圧」「限界Li塩濃度」に再定義（＝レポートの設計成立条件そのもの）'));
children.push(bullet('独立変数をレポート6設計因子＋使用温度に整合。制約つきコンターを セル抵抗×塗布量 に'));
children.push(bullet('2劣化モード（抵抗劣化⇄拡散劣化）を無次元指標 Cli/C_Li_design で判定・可視化'));

// ===== §4 方法 =====
children.push(h('4. 感度解析の方法', HeadingLevel.HEADING_1));
children.push(p('SALib の Saltelli サンプリング＋Sobol解析により、一次感度 S1 と総合効果 ST を算出する。理論式は評価が安価なため、サロゲート（MOP/CoP）を経由せず直接モンテカルロで叩く。これにより代理モデルの近似誤差が指標に混入せず、「サロゲート誤差か物理か」の切り分け問題も消える。'));
children.push(p([new TextRun({text:'実装した4要件: ', font:JP, size:21, bold:true, color:NAVY})]));
children.push(bullet('① 入力分布モード切替: design（設定上下限の一様分布／設計探索用） と variation（実工程3σの正規分布／ばらつきリスク評価用）。どちらのモードで出した指標かを図に明記。'));
children.push(bullet('② 独立性: 独立な上流変数にのみDOEを張り、セル設計計算は評価関数の内部に含める。'));
children.push(bullet('③ 時間依存性: 評価時点を複数指定し、感度指標の時間推移を出力（支配因子の変遷）。'));
children.push(bullet('④ 物理妥当域マスキング: 300W維持不可（判別式負）・温度外挿・非物理値を無効サンプルとして検出し、除外率を記録・警告（本解析では基準5年時点で約24〜28%）。'));

// ===== §5 結果 =====
children.push(h('5. 結果', HeadingLevel.HEADING_1));
children.push(h('5.1 応答ごとに支配因子が異なる', HeadingLevel.HEADING_2));
children.push(p('放電後電圧（抵抗劣化モードの指標）と限界Li塩濃度（拡散劣化モードの指標）では、支配因子が明確に分離する。放電後電圧は 塗布量・セル抵抗・使用温度 が支配し、限界Li塩濃度は 曲路率・塗布量・活物質密度・拡散係数 が支配する。'));
children.push(...fig('sobol_main.png', 630, '図1. Sobol感度（2応答×2分布モード）。上=放電後電圧、下=限界Li塩濃度。左=design、右=variation。応答で支配因子が分離し、分布モードでも順位が変わる。'));
children.push(table([2600, 3400, 3200], [
  [H('応答（モード）', 2600, AlignmentType.LEFT), H('design での ST 上位', 3400, AlignmentType.LEFT), H('variation での ST 上位', 3200, AlignmentType.LEFT)],
  [{t:'放電後電圧（抵抗劣化）', w:2600, align:AlignmentType.LEFT},{t:'塗布量0.96 / セル抵抗0.55 / 温度0.40', w:3400, align:AlignmentType.LEFT},{t:'温度0.71 / 塗布量0.50 / セル抵抗0.37', w:3200, align:AlignmentType.LEFT}],
  [{t:'限界Li塩濃度（拡散劣化）', w:2600, align:AlignmentType.LEFT},{t:'曲路率0.56 / 塗布量0.33 / 密度0.26', w:3400, align:AlignmentType.LEFT},{t:'曲路率0.40 / 密度0.27 / 拡散係数0.24', w:3200, align:AlignmentType.LEFT}],
]));
children.push(p([new TextRun({text:'B-4①の含意: ', font:JP, size:19, bold:true}), new TextRun({text:'variation（ばらつき）では使用温度の寄与が跳ね上がる。設計探索（design）で「温度は自分で振らないから効かない」と見えても、ばらつきリスク評価では温度が主役になり得る。Sobol指標は与えた入力分布に完全従属するため、どちらのモードの指標かを常に明記する必要がある。', font:JP, size:19, color:GREY})]));

children.push(h('5.2 保存劣化過程での支配因子・支配モードの変遷【核心】', HeadingLevel.HEADING_2));
children.push(p('感度指標の時間推移を見ると、放電後電圧では使用温度・セル抵抗の寄与が保存とともに拡大する（温度加速項の顕在化）。一方、限界Li塩濃度では曲路率・塗布量が一貫して支配する。'));
children.push(...fig('sobol_time_evolution.png', 630, '図2. 感度指標の時間推移（design）。左=放電後電圧、右=限界Li塩濃度。横軸=保存年、縦軸=ST。'));
children.push(p('さらに重要なのは、支配「モード」自体が保存とともに遷移することである。公称設計では、保存が進むと限界Li塩濃度が設計budget（1.4M）を超え、同時に放電後電圧が2.5Vを割る。すなわち抵抗劣化モードから電解液Li+濃度拡散劣化モードへ、5年近傍で遷移する。母集団で見ると、拡散劣化モードの個体割合は保存とともに増加し（53%→69%）、設計成立率は低下する（39%→16%）。'));
children.push(...fig('sobol_mode_transition.png', 630, '図3. 支配因子・支配モードの変遷（本検討の核心）。左=公称設計の軌跡（放電後電圧・限界Li塩濃度が5年近傍で閾値を越えモード遷移）。右=母集団の拡散モード割合・成立率・有効率の時間推移。'));
children.push(table([1900, 1500, 1500, 1500, 1500], [
  [H('保存年'), H('0.25'), H('1'), H('3'), H('5〜8')],
  [{t:'拡散劣化モード割合', align:AlignmentType.LEFT, w:1900},{t:'53%'},{t:'55%'},{t:'59%'},{t:'63→69%'}],
  [{t:'設計成立率', align:AlignmentType.LEFT, w:1900},{t:'39%'},{t:'36%'},{t:'29%'},{t:'24→16%'}],
  [{t:'有効率(300W維持可)', align:AlignmentType.LEFT, w:1900},{t:'84%'},{t:'84%'},{t:'79%'},{t:'73→61%'}],
]));
children.push(p([new TextRun({text:'設計上の示唆: ', font:JP, size:19, bold:true}), new TextRun({text:'初期に抵抗劣化モードで成立していても、保存で限界Li塩濃度が上昇し拡散劣化モードへ落ちる。したがって「劣化後も限界Li塩濃度を下回る」初期Li塩濃度設計が必要条件であり、そのうえで抵抗上昇を抑えることが高出力寿命の延伸に直結する（レポートの改善方向性と整合）。', font:JP, size:19, color:GREY})]));

children.push(h('5.3 交互作用の可視化（第3の柱の本体）', HeadingLevel.HEADING_2));
children.push(p('並行座標は交互作用の表現が構造的に苦手（軸の並び順に依存し、3次以上は事実上見えない）。そこを埋めるのが交互作用ネットワーク図である。ノード径＝ST（総合効果）、エッジ太さ＝2次のSobol指標 S2（2変数の組合せ効果）を表す。'));
children.push(...fig('sobol_network.png', 600, '図4. 交互作用ネットワーク（design）。左=放電後電圧、右=限界Li塩濃度。ノード色＝因子分類、径＝ST、線＝S2。'));

children.push(h('5.4 領域条件付き感度（並行座標ブラッシング相当）', HeadingLevel.HEADING_2));
children.push(p('全体感度では「効き方が単調か、特定領域だけで変化するか」は答えられない。並行座標で領域を絞って感度を取り直すと初めて見える。拡散劣化モードが出やすい領域（塗布量10〜13・曲路率1.7〜2.0）に絞ると、限界Li塩濃度の支配因子は曲路率から活物質密度へ入れ替わる。部分集合が小さすぎると指標が不安定になるため、最小サンプル数のガード（N<200で警告）を設けている。'));
children.push(...fig('sobol_conditional.png', 600, '図5. 領域条件付き感度（限界Li塩濃度, design）。全域 vs ブラッシング領域で寄与度の順位が変わる。'));

// ===== §6 アーキテクチャ =====
children.push(h('6. 設計探索アーキテクチャ（①②③の統合）', HeadingLevel.HEADING_1));
children.push(p('感度スクリーニング（①）で効く変数を自動抽出して並行座標へ反映し、交互作用ネットワーク（②）で並行座標が苦手な多変数関係を補完し、感度上位2軸で制約つきコンター（③）を描いて局所地形のOK/NGを把握する。成立域が狭い／支配モードが変わる場合は範囲を絞って感度を再計算する（領域条件付き・時点別）フィードバックループを持つ。'));
children.push(...fig('explore_architecture.png', 640, '図6. 設計探索アーキテクチャ全体像。感度スクリーニング→並行座標＋交互作用ネットワーク→制約つきコンター。'));
children.push(h('6.1 感度スクリーニング → 擬似並行座標（自動反映）', HeadingLevel.HEADING_2));
children.push(p('Sobol の ST 上位を能動軸として自動選択し、並行座標の軸順・強調に反映する（★能動軸を左に集約・強調、非能動軸は淡色）。個体は放電後電圧でカラーリングし、制約成立個体を強調する。これにより「どの軸に注目すべきか」を感度解析が決め、並行座標に橋渡しする。'));
children.push(...fig('explore_parallel.png', 630, '図7. 擬似並行座標プロット（Python実装）。感度スクリーニングを軸選択へ自動反映。★＝能動軸（ST上位）。'));
children.push(h('6.2 制約つき2軸コンター（局所地形 OK/NG）', HeadingLevel.HEADING_2));
children.push(p('感度上位2軸である セル抵抗×正極塗布量 で局所地形を描く。塗布量上限は限界Li塩濃度1.4Mのラインで、塗布量下限は放電後電圧2.5Vのラインで決まり、セル抵抗が高いほど成立する塗布量帯が狭い。これは報告書 NCR2170JB Step2 の設計探索（塗布量82±3 g/m²・セル抵抗≤5.3mΩで成立）と同形式・同傾向である。'));
children.push(...fig('explore_contour.png', 470, '図8. 制約つき2軸コンター（セル抵抗×正極塗布量, 5年後）。赤=放電後電圧下限、白破線=限界Li塩濃度上限、網掛=NG。'));

// ===== §7 結論 =====
children.push(h('7. 考察・結論・今後', HeadingLevel.HEADING_1));
children.push(bullet('DC_v5 の保存劣化理論式を直接モンテカルロで叩く Sobol 感度解析を実装し、社内テクニカルレポートと整合することを確認した（理論構造・感度順位・設計成立範囲）。', {bold:false}));
children.push(bullet('応答ごとに支配因子が分離し（放電後電圧←抵抗/塗布量/温度、限界Li塩濃度←曲路率/塗布量/拡散）、保存とともに支配モードが抵抗劣化→拡散劣化へ遷移することを定量化・可視化した。', {}));
children.push(bullet('感度スクリーニングの並行座標への自動反映、交互作用ネットワーク、制約つきコンターを統合した設計探索アーキテクチャを提示した。', {}));
children.push(p([new TextRun({text:'今後の発展: ', font:JP, size:21, bold:true, color:NAVY})]));
children.push(bullet('セル設計計算を DC_v5 CellDesign（run_calc）実体へ接続（現状は物理無矛盾な最小スラブモデル）。'));
children.push(bullet('Li塩消費モデル（保存によるLiPF6消費で初期Li塩濃度が低下）を組み込み、拡散劣化モードへの到達時刻を予測。'));
children.push(bullet('Plotly/Dash によるインタラクティブ版（ブラッシング連動）。現状は擬似＝静的Python図。'));
children.push(bullet('応答経路のバッジ表示（MOP経由 CAE由来応答 と 理論式直接 の混在を明示）。'));

// ===== 付録 =====
children.push(h('付録A. 実装・再現手順', HeadingLevel.HEADING_1));
children.push(p('乱数シードは全て固定し再現性を担保。図中の文言は日本語。主要モジュールは以下（mf_demo/explorer/）。'));
children.push(bullet('vendor_dcv5/dc_model.py … DC_v5 実式を無改変で取り込み（劣化式は実物）'));
children.push(bullet('cell_design.py … 独立上流変数→派生量（B-4②）'));
children.push(bullet('degradation.py … 実式ラッパ（b\'=2.0, Arrhenius, 2応答, 2モード）'));
children.push(bullet('config.py / sensitivity.py … 分布モード・時間依存・マスキング'));
children.push(bullet('plots.py / screening.py / viz_explorer.py … 感度図・スクリーニング・並行座標/コンター/アーキテクチャ'));
children.push(p([new TextRun({text:'実行: ', font:JP, size:20, bold:true}), new TextRun({text:'python -m mf_demo.explorer.run_sensitivity 256  （感度6図）／  python -m mf_demo.explorer.run_explorer 600  （①②③ 5図）', font:JP, size:19, color:GREY})]));
children.push(p([new TextRun({text:'免責: ', font:JP, size:19, bold:true, color:ACC}), new TextRun({text:'本プロトタイプは原理を絵で伝えることを優先した合成モデルであり、精度較正済みの設計ツールではない。数値は DC_v5 row82 近傍のオーダーに合わせてある。', font:JP, size:19, color:GREY})]));

// ===== ドキュメント =====
const doc = new Document({
  styles: { default: { document: { run: { font: JP, size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 30, bold: true, color: NAVY, font: JP }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 24, bold: true, color: ACC, font: JP }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
    ] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1200, bottom: 1200, left: 1200, right: 1200 } } },
    footers: { default: new Footer({ children: [ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ children: ['DC向けセル 保存劣化 感度解析報告書 ／ ', PageNumber.CURRENT], font: JP, size: 16, color: GREY }) ] }) ] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = '/home/user/test/mf_demo/output/報告書_保存劣化_感度解析.docx';
  fs.writeFileSync(out, buf);
  console.log('WROTE', out, buf.length, 'bytes');
});

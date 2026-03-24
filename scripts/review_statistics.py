#!/usr/bin/env python3
"""
統計記述の自動校正スクリプト

チェック項目:
  - p値の誤用
  - サンプルサイズの明記
  - 効果量の報告
  - 95%CIの記載
  - n<10データの使用
"""

import re
from pathlib import Path
from datetime import datetime

class StatisticalReviewer:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.good_practices = []
    
    def check_p_value_usage(self, text):
        """p値の誤用チェック"""
        print("🔍 p値の使用をチェック中...")
        
        # p>0.05で「有意」と書いていないか
        pattern_bad = r'p\s*[>≥]\s*0\.05.*?有意'
        matches = re.finditer(pattern_bad, text, re.IGNORECASE)
        
        for match in matches:
            self.issues.append(
                f"❌ p値誤用: p>0.05で「有意」と記述 → \"{match.group()}\""
            )
        
        # p値の適切な報告があるか
        pattern_good = r'p\s*[<≤]\s*0\.(001|01|05)'
        matches = list(re.finditer(pattern_good, text, re.IGNORECASE))
        
        if matches:
            self.good_practices.append(
                f"✅ p値の適切な報告: {len(matches)}箇所で確認"
            )
        
        # p値のみで効果量なし
        if 'p <' in text or 'p<' in text:
            if 'Cohen' not in text and 'd =' not in text:
                self.warnings.append(
                    "⚠️ p値報告はあるが効果量（Cohen's d）の報告がない"
                )
    
    def check_sample_size(self, text):
        """サンプルサイズの明記チェック"""
        print("🔍 サンプルサイズの明記をチェック中...")
        
        # n=XX の記載
        pattern_n = r'n\s*=\s*\d+'
        matches = list(re.finditer(pattern_n, text, re.IGNORECASE))
        
        if matches:
            self.good_practices.append(
                f"✅ サンプルサイズの明記: {len(matches)}箇所で確認"
            )
        else:
            self.warnings.append(
                "⚠️ サンプルサイズ（n=XX）の明記がない"
            )
        
        # 小サンプル（n<10）の警告
        small_n = re.findall(r'n\s*=\s*([0-9])\b', text, re.IGNORECASE)
        for n in small_n:
            if int(n) < 10:
                self.warnings.append(
                    f"⚠️ 小サンプル（n={n}）での統計検定 → 検出力不足の可能性"
                )
    
    def check_effect_size(self, text):
        """効果量の報告チェック"""
        print("🔍 効果量の報告をチェック中...")
        
        # Cohen's d, η², r など
        effect_patterns = [
            r"Cohen'?s?\s+d",
            r'η²',
            r'r\s*=\s*0\.\d+',
            r'効果量'
        ]
        
        found_effect = False
        for pattern in effect_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found_effect = True
                break
        
        if found_effect:
            self.good_practices.append(
                "✅ 効果量の報告あり"
            )
        else:
            self.issues.append(
                "❌ 効果量の報告がない → 統計的有意性のみでは不十分"
            )
    
    def check_confidence_interval(self, text):
        """信頼区間の記載チェック"""
        print("🔍 信頼区間の記載をチェック中...")
        
        # 95% CI, [XX, YY]など
        ci_patterns = [
            r'95%\s*CI',
            r'信頼区間',
            r'\[\s*\d+\.?\d*\s*,\s*\d+\.?\d*\s*\]'
        ]
        
        found_ci = False
        for pattern in ci_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found_ci = True
                break
        
        if found_ci:
            self.good_practices.append(
                "✅ 信頼区間の報告あり"
            )
        else:
            self.warnings.append(
                "⚠️ 信頼区間の報告がない → 推定の精度が不明"
            )
    
    def check_descriptive_stats(self, text):
        """記述統計のチェック"""
        print("🔍 記述統計の報告をチェック中...")
        
        # 平均±SD の形式
        pattern_mean_sd = r'\d+\.?\d*\s*±\s*\d+\.?\d*'
        matches = list(re.finditer(pattern_mean_sd, text))
        
        if matches:
            self.good_practices.append(
                f"✅ 記述統計（平均±SD）: {len(matches)}箇所で報告"
            )
        
        # 中央値の報告
        if '中央値' in text or 'median' in text.lower():
            self.good_practices.append(
                "✅ 中央値の報告あり → 分布の歪みを考慮"
            )
    
    def review_sections_files(self):
        """sections/フォルダ内のファイルをレビュー"""
        print("\n" + "=" * 60)
        print("📄 sections/ フォルダのファイルをレビュー")
        print("=" * 60)
        
        sections_dir = Path('sections')
        if not sections_dir.exists():
            self.warnings.append("⚠️ sections/ フォルダが見つかりません")
            return
        
        files = list(sections_dir.glob('*.md')) + list(sections_dir.glob('*.tex'))
        
        if not files:
            self.warnings.append("⚠️ レビュー対象ファイルがありません")
            return
        
        print(f"\n✅ {len(files)}個のファイルを発見:")
        for f in files:
            print(f"   - {f.name}")
        
        all_text = []
        for file_path in files:
            try:
                text = file_path.read_text(encoding='utf-8')
                all_text.append(text)
                print(f"\n📖 {file_path.name} をチェック中...")
                
                self.check_p_value_usage(text)
                self.check_sample_size(text)
                self.check_effect_size(text)
                self.check_confidence_interval(text)
                self.check_descriptive_stats(text)
            
            except Exception as e:
                self.warnings.append(f"⚠️ {file_path.name} 読み込みエラー: {str(e)}")
        
        return '\n\n'.join(all_text)
    
    def generate_report(self):
        """レポート生成"""
        print("\n" + "=" * 60)
        print("📄 統計記述レビューレポート生成")
        print("=" * 60)
        
        report_lines = [
            "# 統計記述の自動校正レポート",
            "",
            f"**生成日時**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}",
            "",
            "---",
            "",
            "## 1. チェック項目",
            "",
            "- ✅ p値の誤用",
            "- ✅ サンプルサイズの明記",
            "- ✅ 効果量の報告",
            "- ✅ 95%信頼区間の記載",
            "- ✅ n<10データの使用",
            "- ✅ 記述統計の適切性",
            "",
            "---",
            "",
            "## 2. 検出された問題",
            ""
        ]
        
        if self.issues:
            for issue in self.issues:
                report_lines.append(f"{issue}")
                report_lines.append("")
        else:
            report_lines.append("✅ 重大な問題は検出されませんでした")
            report_lines.append("")
        
        report_lines.extend([
            "---",
            "",
            "## 3. 警告",
            ""
        ])
        
        if self.warnings:
            for warning in self.warnings:
                report_lines.append(f"{warning}")
                report_lines.append("")
        else:
            report_lines.append("✅ 警告はありません")
            report_lines.append("")
        
        report_lines.extend([
            "---",
            "",
            "## 4. 良い実践例",
            ""
        ])
        
        if self.good_practices:
            for practice in self.good_practices:
                report_lines.append(f"{practice}")
                report_lines.append("")
        else:
            report_lines.append("⚠️ 統計報告の改善が必要です")
            report_lines.append("")
        
        report_lines.extend([
            "---",
            "",
            "## 5. 推奨される統計報告フォーマット",
            "",
            "### APA形式に準拠した報告",
            "",
            "```",
            "【t検定の報告例】",
            "TA*とAHA*の間には統計的に有意な差が認められた",
            "(t(190) = 6.502, p < 0.001, Cohen's d = 0.938)。",
            "",
            "【記述統計の報告例】",
            "TA*の平均計算時間は15.46±23.28秒（平均±SD、n=96）であり、",
            "95%信頼区間は[10.75秒, 20.18秒]であった。",
            "",
            "【効果量の解釈例】",
            "Cohen's d = 0.938は大きな効果（d > 0.8）を示しており、",
            "実務的にも重要な差であることが示唆された。",
            "```",
            "",
            "### 避けるべき表現",
            "",
            "```",
            "❌ 「有意差があった（p=0.06）」",
            "   → p > 0.05は有意ではない",
            "",
            "❌ 「差があった」",
            "   → 統計的検定と効果量を明記",
            "",
            "❌ 「ほぼ有意（p=0.06）」",
            "   → 有意水準は事前に設定すべき",
            "```",
            "",
            "---",
            "",
            "## 6. チェックリスト",
            "",
            "### 論文提出前の確認事項",
            "",
            "- [ ] すべてのt検定にp値、自由度、効果量を記載",
            "- [ ] すべての記述統計にサンプルサイズを明記",
            "- [ ] 平均値には標準偏差または標準誤差を併記",
            "- [ ] 主要な統計量に95%信頼区間を記載",
            "- [ ] 効果量の解釈（小/中/大）を明記",
            "- [ ] 有意水準（α=0.05）を明記",
            "- [ ] 統計ソフトウェア/パッケージを明記（scipy.stats等）",
            "",
            "---",
            "",
            "## 7. 参考資料",
            "",
            "### APA Publication Manual (第7版)",
            "- t検定: t(df) = value, p < threshold",
            "- 効果量: Cohen's d = value (interpretation)",
            "- 記述統計: M = mean, SD = std, 95% CI [low, high]",
            "",
            "### 推奨文献",
            "- Cumming, G. (2014). The New Statistics: Why and How.",
            "- Field, A. (2013). Discovering Statistics Using IBM SPSS Statistics.",
            ""
        ])
        
        # ファイル保存
        output_path = Path('STATISTICAL_REVIEW_REPORT.md')
        output_path.write_text('\n'.join(report_lines), encoding='utf-8')
        
        print(f"\n✅ レポート生成完了: {output_path}")
    
    def run_review(self):
        """完全レビュー実行"""
        print("=" * 60)
        print("🔍 統計記述の自動校正開始")
        print("=" * 60)
        
        # ファイルレビュー
        self.review_sections_files()
        
        # レポート生成
        self.generate_report()
        
        # サマリー
        print("\n" + "=" * 60)
        print("📋 レビュー完了サマリー")
        print("=" * 60)
        print(f"\n重大な問題: {len(self.issues)}")
        print(f"警告: {len(self.warnings)}")
        print(f"良い実践例: {len(self.good_practices)}")
        print(f"\n詳細: STATISTICAL_REVIEW_REPORT.md を参照してください")

if __name__ == '__main__':
    reviewer = StatisticalReviewer()
    reviewer.run_review()

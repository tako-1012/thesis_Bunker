#!/usr/bin/env python3
"""
demo_recording_guide.py
Unity可視化デモ動画撮影ガイド
"""

import os
import subprocess
import time
from pathlib import Path

class DemoRecordingGuide:
    """デモ動画撮影ガイド"""
    
    def __init__(self):
        self.unity_project_path = Path.home() / "thesis_work/unity/PathPlanningVisualization"
        self.output_path = Path.home() / "thesis_work/demo_videos"
        self.output_path.mkdir(exist_ok=True)
        
    def print_setup_instructions(self):
        """セットアップ手順を表示"""
        print("🎬 Unity可視化デモ動画撮影ガイド")
        print("=" * 60)
        print()
        
        print("📋 事前準備:")
        print("1. Unity Hubでプロジェクトを開く")
        print("2. Recorderパッケージをインストール")
        print("3. シーンを設定")
        print("4. マテリアルを作成")
        print()
        
        print("🎥 撮影手順:")
        print("1. Window → General → Recorder → Recorder Window")
        print("2. 設定:")
        print("   - 解像度: 1920x1080")
        print("   - フレームレート: 60fps")
        print("   - フォーマット: MP4")
        print("   - 出力先: ~/thesis_work/demo_videos/")
        print()
        
        print("📝 撮影シナリオ:")
        self.print_recording_scenario()
        
    def print_recording_scenario(self):
        """撮影シナリオを表示"""
        scenarios = [
            ("オープニング", 10, "タイトル表示・プロジェクト概要"),
            ("地形タイプ紹介", 30, "7種類の地形を順に表示"),
            ("経路計画デモ", 60, "複数シナリオでの経路表示"),
            ("ロボット移動", 30, "ロボットの移動アニメーション"),
            ("インタラクティブ操作", 30, "カメラ操作・UI操作"),
            ("統計結果表示", 30, "100%成功率・グラフ表示")
        ]
        
        total_time = 0
        for i, (title, duration, description) in enumerate(scenarios, 1):
            print(f"{i}. {title} ({duration}秒)")
            print(f"   {description}")
            total_time += duration
        
        print(f"\n合計時間: {total_time}秒 ({total_time//60}分{total_time%60}秒)")
        print()
        
    def print_unity_setup_commands(self):
        """Unity設定コマンドを表示"""
        print("🔧 Unity設定コマンド:")
        print()
        
        print("# プロジェクトを開く")
        print(f"cd {self.unity_project_path}")
        print("unity-editor .")
        print()
        
        print("# Recorderパッケージインストール")
        print("Window → Package Manager → Recorder → Install")
        print()
        
        print("# シーン設定")
        print("1. MainVisualizationシーンを開く")
        print("2. SimulationManagerオブジェクトを作成")
        print("3. 各スクリプトをアタッチ")
        print("4. UI Canvasを作成")
        print()
        
    def print_material_setup(self):
        """マテリアル設定を表示"""
        print("🎨 マテリアル設定:")
        print()
        
        materials = [
            ("TerrainMaterial", "地形用", "緑色、半透明"),
            ("PathMaterial", "経路用", "青色、発光"),
            ("ObstacleMaterial", "障害物用", "灰色、半透明"),
            ("RobotMaterial", "ロボット用", "黄色、金属質")
        ]
        
        for name, purpose, description in materials:
            print(f"- {name}: {purpose} ({description})")
        
        print()
        print("作成手順:")
        print("1. Assets → Create → Material")
        print("2. 名前を設定")
        print("3. 色とプロパティを調整")
        print("4. スクリプトで参照")
        print()
        
    def print_recording_tips(self):
        """撮影のコツを表示"""
        print("💡 撮影のコツ:")
        print()
        
        tips = [
            "カメラの動きを滑らかに",
            "UI操作はゆっくりと",
            "各シーンで十分な時間を取る",
            "音声ナレーションを追加（オプション）",
            "複数回撮影してベストを選択",
            "編集で不要な部分をカット"
        ]
        
        for i, tip in enumerate(tips, 1):
            print(f"{i}. {tip}")
        
        print()
        
    def print_post_production(self):
        """ポストプロダクション手順を表示"""
        print("✂️ ポストプロダクション:")
        print()
        
        print("推奨ソフトウェア:")
        print("- DaVinci Resolve (無料)")
        print("- OpenShot (無料)")
        print("- Adobe Premiere Pro (有料)")
        print()
        
        print("編集手順:")
        print("1. 不要な部分をカット")
        print("2. トランジションを追加")
        print("3. タイトル・字幕を追加")
        print("4. 音声を調整")
        print("5. 最終出力（MP4, 1080p）")
        print()
        
    def generate_recording_script(self):
        """撮影台本を生成"""
        script_path = self.output_path / "recording_script.md"
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write("# Unity可視化デモ動画撮影台本\n\n")
            f.write("## 全体構成 (3分)\n\n")
            
            scenarios = [
                ("オープニング", 10, "タイトル表示・プロジェクト概要"),
                ("地形タイプ紹介", 30, "7種類の地形を順に表示"),
                ("経路計画デモ", 60, "複数シナリオでの経路表示"),
                ("ロボット移動", 30, "ロボットの移動アニメーション"),
                ("インタラクティブ操作", 30, "カメラ操作・UI操作"),
                ("統計結果表示", 30, "100%成功率・グラフ表示")
            ]
            
            for i, (title, duration, description) in enumerate(scenarios, 1):
                f.write(f"### {i}. {title} ({duration}秒)\n")
                f.write(f"{description}\n\n")
                f.write("**撮影ポイント:**\n")
                f.write("- カメラアングル: 俯瞰視点\n")
                f.write("- 操作: 滑らかな動き\n")
                f.write("- フォーカス: 主要要素\n\n")
        
        print(f"📝 撮影台本を生成: {script_path}")
        
    def run(self):
        """メイン実行"""
        self.print_setup_instructions()
        self.print_unity_setup_commands()
        self.print_material_setup()
        self.print_recording_tips()
        self.print_post_production()
        self.generate_recording_script()
        
        print("🎉 デモ動画撮影準備完了！")
        print(f"📁 出力先: {self.output_path}")

def main():
    guide = DemoRecordingGuide()
    guide.run()

if __name__ == "__main__":
    main()



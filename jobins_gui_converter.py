#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jobins CSV変換ツール（GUI版）
tkinterを使用したユーザーフレンドリーなインターフェース
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import csv
import yaml
import os
import threading
from datetime import datetime
import re
import logging
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JobinsGUIConverter:
    def __init__(self, root):
        self.root = root
        self.root.title('Jobins CSV変換ツール')
        self.root.geometry('800x600')
        self.root.resizable(True, True)
        
        # 変数初期化
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()
        self.config_file_path = tk.StringVar(value='jobins_yaml_mapping.yaml')
        
        # 変換クラス初期化
        self.converter = None
        
        # UI構築
        self.create_widgets()
        
        # 設定ファイルの初期チェック
        self.check_config_file()
    
    def create_widgets(self):
        """GUI要素を作成"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # グリッド設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # タイトル
        title_label = ttk.Label(main_frame, text="Jobins CSV変換ツール", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 入力ファイル選択
        ttk.Label(main_frame, text="求人マスタCSVファイル:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.input_file_path, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 5))
        ttk.Button(main_frame, text="選択", command=self.select_input_file).grid(row=1, column=2, padx=(5, 0))
        
        # 出力先選択
        ttk.Label(main_frame, text="出力先フォルダ:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_file_path, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 5))
        ttk.Button(main_frame, text="選択", command=self.select_output_folder).grid(row=2, column=2, padx=(5, 0))
        
        # 設定ファイル
        ttk.Label(main_frame, text="設定ファイル:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.config_file_path, width=50).grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 5))
        ttk.Button(main_frame, text="選択", command=self.select_config_file).grid(row=3, column=2, padx=(5, 0))
        
        # 実行ボタン
        self.convert_button = ttk.Button(main_frame, text="変換実行", command=self.start_conversion)
        self.convert_button.grid(row=4, column=0, columnspan=3, pady=20)
        
        # 進捗バー
        self.progress_var = tk.StringVar(value="準備完了")
        ttk.Label(main_frame, text="進捗:").grid(row=5, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.progress_var).grid(row=5, column=1, sticky=tk.W, padx=(10, 0))
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='determinate')
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 20))
        
        # 詳細進捗表示
        self.detail_progress_var = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.detail_progress_var, font=('Arial', 8)).grid(row=7, column=0, columnspan=3, sticky=tk.W)
        
        # ログ表示エリア
        ttk.Label(main_frame, text="ログ:").grid(row=8, column=0, sticky=(tk.W, tk.N))
        
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=15, width=80)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # グリッド重み設定
        main_frame.rowconfigure(9, weight=1)
    
    def log_message(self, message):
        """ログメッセージを表示"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def check_config_file(self):
        """設定ファイルの存在確認"""
        if os.path.exists(self.config_file_path.get()):
            self.log_message(f"設定ファイルを確認しました: {self.config_file_path.get()}")
        else:
            self.log_message("⚠️ 設定ファイルが見つかりません。選択してください。")
    
    def select_input_file(self):
        """入力ファイル選択ダイアログ"""
        filename = filedialog.askopenfilename(
            title="求人マスタCSVファイルを選択",
            filetypes=[("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")]
        )
        if filename:
            self.input_file_path.set(filename)
            self.log_message(f"入力ファイルを選択: {os.path.basename(filename)}")
    
    def select_output_folder(self):
        """出力先フォルダ選択ダイアログ"""
        folder = filedialog.askdirectory(title="出力先フォルダを選択")
        if folder:
            self.output_file_path.set(folder)
            self.log_message(f"出力先フォルダを選択: {folder}")
    
    def select_config_file(self):
        """設定ファイル選択ダイアログ"""
        filename = filedialog.askopenfilename(
            title="YAML設定ファイルを選択",
            filetypes=[("YAMLファイル", "*.yaml"), ("YAMLファイル", "*.yml"), ("すべてのファイル", "*.*")]
        )
        if filename:
            self.config_file_path.set(filename)
            self.log_message(f"設定ファイルを選択: {os.path.basename(filename)}")
    
    def validate_inputs(self):
        """入力値の検証"""
        if not self.input_file_path.get():
            messagebox.showerror("エラー", "求人マスタCSVファイルを選択してください。")
            return False
        
        if not os.path.exists(self.input_file_path.get()):
            messagebox.showerror("エラー", "選択された入力ファイルが存在しません。")
            return False
        
        if not self.config_file_path.get():
            messagebox.showerror("エラー", "設定ファイルを選択してください。")
            return False
        
        if not os.path.exists(self.config_file_path.get()):
            messagebox.showerror("エラー", "選択された設定ファイルが存在しません。")
            return False
        
        return True
    
    def start_conversion(self):
        """変換処理を開始（別スレッドで実行）"""
        if not self.validate_inputs():
            return
        
        # UI無効化
        self.convert_button.config(state='disabled')
        self.progress_bar['value'] = 0
        self.progress_var.set("変換準備中...")
        self.detail_progress_var.set("")
        
        # 別スレッドで変換実行
        thread = threading.Thread(target=self.run_conversion)
        thread.daemon = True
        thread.start()
    
    def run_conversion(self):
        """実際の変換処理"""
        try:
            self.log_message("=" * 50)
            self.log_message("変換処理を開始します")
            
            # 変換器初期化
            self.converter = SimpleJobinsConverter(self.config_file_path.get())
            self.log_message("設定ファイルを読み込みました")
            
            # 出力ファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            input_filename = os.path.basename(self.input_file_path.get())
            output_filename = f"JOBINS掲載用_{timestamp}.csv"
            
            if self.output_file_path.get():
                output_path = os.path.join(self.output_file_path.get(), output_filename)
            else:
                output_path = output_filename
            
            self.log_message(f"入力ファイル: {input_filename}")
            self.log_message(f"出力ファイル: {output_filename}")
            
            # 変換実行
            success = self.converter.convert_csv_with_callback(
                self.input_file_path.get(), 
                output_path,
                self.log_message,
                progress_callback=self.update_progress
            )
            
            if success:
                self.log_message("✅ 変換が正常に完了しました！")
                self.log_message(f"出力ファイル: {os.path.abspath(output_path)}")
                
                # 完了メッセージ
                self.root.after(0, lambda: messagebox.showinfo(
                    "完了", 
                    f"変換が完了しました！\n\n出力ファイル:\n{os.path.abspath(output_path)}"
                ))
            else:
                self.log_message("❌ 変換中にエラーが発生しました")
                self.root.after(0, lambda: messagebox.showerror("エラー", "変換中にエラーが発生しました。"))
        
        except Exception as e:
            error_msg = f"予期しないエラーが発生しました: {str(e)}"
            self.log_message(f"❌ {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("エラー", error_msg))
        
        finally:
            # UI復元
            self.root.after(0, self.reset_ui)
    
    def update_progress(self, current, total, message=""):
        """進捗状況を更新"""
        if total > 0:
            progress_percentage = (current / total) * 100
            self.progress_bar['value'] = progress_percentage
            self.progress_var.set(f"進行中: {current}/{total} ({progress_percentage:.1f}%)")
            if message:
                self.detail_progress_var.set(message)
        self.root.update_idletasks()
    
    def reset_ui(self):
        """UI状態をリセット"""
        self.progress_bar['value'] = 0
        self.progress_var.set("準備完了")
        self.detail_progress_var.set("")
        self.convert_button.config(state='normal')

class SimpleJobinsConverter:
    """CSV変換クラス（simple_converterから移植）"""
    
    def _load_job_categories(self):
        """職種分類テーブルをExcelファイルから読み込み"""
        try:
            # Excelファイルから職種分類テーブルを読み込み
            df = pd.read_excel('職種分類.xlsx')
            
            # A列（大分類）、B列（中分類）、C列（Notion職種(紐づけ)）を取得
            job_categories = []
            for index, row in df.iterrows():
                major_category = str(row.iloc[0]).strip() if len(row) > 0 and pd.notna(row.iloc[0]) else ""
                minor_category = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                notion_link = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""
                
                # 大分類と中分類が存在し、空文字でない場合のみ追加
                if major_category and minor_category and major_category != "nan" and minor_category != "nan":
                    job_categories.append((major_category, minor_category, notion_link if notion_link != "nan" else ""))
            
            logger.info(f"職種分類テーブルを読み込み完了: {len(job_categories)}件")
            return job_categories
            
        except Exception as e:
            logger.warning(f"Excelファイル読み込みエラー、フォールバックデータを使用: {e}")
            # フォールバック: ハードコーディングされたデータを使用（Notion紐づけ用は空文字）
            fallback_data = self._get_fallback_job_categories()
            logger.info(f"フォールバックデータ使用: {len(fallback_data)}件")
            return fallback_data
    
    def _get_fallback_job_categories(self):
        """フォールバック用のハードコーディングされた職種分類テーブル"""
        return [
            ("営業", "企画営業【法人営業・個人営業】", ""),
        ("営業", "代理店営業【代理店渉外・パートナーセールス・アライアンス】", ""),
        ("営業", "内勤営業、カウンターセールス", ""),
        ("営業", "ルートセールス、外商", ""),
        ("営業", "海外営業", ""),
        ("営業", "メディカル営業【MR・MS・DMR・医療機器営業】", ""),
        ("営業", "技術・システム・IT営業", ""),
        ("営業", "その他営業関連職", ""),
        ("営業", "コールセンター運営・管理・SV", ""),
        ("営業", "カスタマーサポート、ヘルプデスク", ""),
        ("営業", "オペレーター、アポインター", ""),
        ("営業", "キャリアカウンセラー、キャリアコンサルタント、人材派遣コーディネーター", ""),
        ("営業", "人材系営業", ""),
        ("事務・管理", "一般事務、庶務", ""),
        ("事務・管理", "営業事務、営業アシスタント", ""),
        ("事務・管理", "受付", ""),
        ("事務・管理", "秘書", ""),
        ("事務・管理", "その他事務関連職", ""),
        ("事務・管理", "財務、会計、税務", ""),
        ("事務・管理", "経理", ""),
        ("事務・管理", "内部統制、内部監査", ""),
        ("事務・管理", "総務", ""),
        ("事務・管理", "人事、給与、労務、採用", ""),
        ("事務・管理", "法務、コンプライアンス", ""),
        ("事務・管理", "知財、特許", ""),
        ("事務・管理", "広報、IR", ""),
        ("事務・管理", "情報セキュリティ", ""),
        ("事務・管理", "物流企画、物流管理、在庫管理、商品管理", ""),
        ("事務・管理", "資材調達、購買", ""),
        ("事務・管理", "貿易事務、国際業務", ""),
        ("事務・管理", "通関士", ""),
        ("企画・マーケティング・経営・管理職", "商品企画、商品開発", ""),
        ("企画・マーケティング・経営・管理職", "販促企画、営業企画", ""),
        ("企画・マーケティング・経営・管理職", "市場調査、市場分析、マーケティングリサーチ", ""),
        ("企画・マーケティング・経営・管理職", "広告、宣伝", ""),
        ("企画・マーケティング・経営・管理職", "Webマーケティング、デジタルマーケティング", ""),
        ("企画・マーケティング・経営・管理職", "経営企画", ""),
        ("企画・マーケティング・経営・管理職", "事業企画、事業統括", ""),
        ("企画・マーケティング・経営・管理職", "新規事業企画、事業プロデュース", ""),
        ("企画・マーケティング・経営・管理職", "海外事業企画", ""),
        ("企画・マーケティング・経営・管理職", "CEO、COO、CFO、CIO、CTO、経営幹部、幹部候補", ""),
        ("企画・マーケティング・経営・管理職", "管理職【営業マネージャー・企画系】", ""),
        ("企画・マーケティング・経営・管理職", "管理職【管理部門系】", ""),
        ("企画・マーケティング・経営・管理職", "管理職【その他】", ""),
        ("企画・マーケティング・経営・管理職", "マーチャンダイザー、VMD、バイヤー、買取査定", ""),
        ("企画・マーケティング・経営・管理職", "店舗開発、FC開発", ""),
        ("企画・マーケティング・経営・管理職", "FCオーナー、代理店研修生", ""),
        ("サービス・販売・外食", "スーパーバイザー、店舗指導、エリアマネージャー", ""),
        ("サービス・販売・外食", "教育・研修トレーナー【サービス・販売・外食系】", ""),
        ("サービス・販売・外食", "店長、店長候補、店長補佐", ""),
        ("サービス・販売・外食", "販売スタッフ、販売アドバイザー、売場担当", ""),
        ("サービス・販売・外食", "美容部員、化粧品販売員", ""),
        ("サービス・販売・外食", "ホールスタッフ、フロアスタッフ", ""),
        ("サービス・販売・外食", "調理師、調理補助、シェフ、パティシエ", ""),
        ("サービス・販売・外食", "その他小売・流通・外食・アミューズメント関連職", ""),
        ("サービス・販売・外食", "美容師、理容師", ""),
        ("サービス・販売・外食", "エステティシャン", ""),
        ("サービス・販売・外食", "アロマセラピスト、ネイリスト", ""),
        ("サービス・販売・外食", "トリマー", ""),
        ("サービス・販売・外食", "その他美容・エステ・リラクゼーション関連職", ""),
        ("サービス・販売・外食", "旅行手配、添乗員、ツアーコンダクター", ""),
        ("サービス・販売・外食", "カウンタースタッフ、予約手配、オペレーター", ""),
        ("サービス・販売・外食", "ホテル、旅館、宿泊施設サービス", ""),
        ("サービス・販売・外食", "ホテル支配人", ""),
        ("サービス・販売・外食", "客室乗務員【CA】、グランドスタッフ、グランドハンドリング、パイロット、航空管制官", ""),
        ("サービス・販売・外食", "ウェディングプランナー、ブライダルコーディネーター、ドレスコーディネーター", ""),
        ("サービス・販売・外食", "葬祭ディレクター・プランナー", ""),
        ("サービス・販売・外食", "その他旅行・ホテル・航空・ブライダル・葬祭関連職", ""),
        ("Web・インターネット・ゲーム", "Webプロデューサー、Webディレクター、Webマスター、Web企画、Webプランナー", ""),
        ("Web・インターネット・ゲーム", "Web編集、コンテンツ企画", ""),
        ("Web・インターネット・ゲーム", "Webデザイナー、フロントエンドエンジニア、コーダー、フラッシャー", ""),
        ("Web・インターネット・ゲーム", "情報アーキテクト、UI/UXデザイナー", ""),
        ("Web・インターネット・ゲーム", "システムディレクター、テクニカルディレクター", ""),
        ("Web・インターネット・ゲーム", "アクセス解析、統計解析、データ分析、データアナリスト", ""),
        ("Web・インターネット・ゲーム", "SEOコンサルタント、SEMコンサルタント", ""),
        ("Web・インターネット・ゲーム", "ホームページ管理、Web担当者", ""),
        ("Web・インターネット・ゲーム", "ECサイト運営", ""),
        ("Web・インターネット・ゲーム", "その他Web担当者、インターネット関連", ""),
        ("Web・インターネット・ゲーム", "ゲームプロデューサー、ディレクター", ""),
        ("Web・インターネット・ゲーム", "ゲームデザイナー、ゲームプランナー、ゲーム企画、シナリオライター", ""),
        ("Web・インターネット・ゲーム", "ゲームプログラマ、ゲームエンジニア", ""),
        ("Web・インターネット・ゲーム", "CGデザイナー、グラフィックデザイナー、イラストレーター", ""),
        ("Web・インターネット・ゲーム", "サウンドクリエイター、サウンドプログラマ", ""),
        ("Web・インターネット・ゲーム", "その他ゲーム・マルチメディア関連職", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "クリエイティブディレクター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "アートディレクター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "アカウントエグゼクティブ【AE】、アカウントプランナー【AP】", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "メディアプランナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "プロモーションプロデューサー・ディレクター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "コピーライター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "グラフィックデザイナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "制作進行管理", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "フォトグラファー、カメラマン", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "イラストレーター【広告・グラフィック関連】", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "DTPオペレーター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "その他広告・グラフィック関連職", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "編集、エディター、デスク、校正", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "記者、ライター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "テクニカルライター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "その他出版・印刷関連職", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "プロデューサー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "ディレクター、プランナー、監督、演出", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "脚本家、放送作家、シナリオライター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "映像制作、編集、技術、音響、照明、カメラ", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "アニメーター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "AP【アシスタントプロデューサー】、AD【アシスタントディレクター】、進行", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "アナウンサー、俳優、モデル、コンパニオン", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "声優、ナレーター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "芸能マネージャー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "その他映像・音響・イベント・芸能・テレビ・放送関連職", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "ファッションデザイナー、服飾雑貨デザイナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "テキスタイルデザイナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "アクセサリーデザイナー、ジュエリーデザイナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "パタンナー、縫製", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "ソーイングスタッフ、ファッションリフォーマー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "スタイリスト、ヘアメイク、メイクアップアーティスト", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "インテリアコーディネーター、インテリアプランナー、インテリアデザイナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "店舗・空間デザイナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "工業デザイナー、プロダクトデザイナー", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "カラーコーディネーター", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "生産管理・品質管理【ファッション・インテリア・空間デザイン・プロダクトデザイン関連】", ""),
        ("クリエイティブ【メディア・アパレルデザイン】", "その他ファッション・インテリア・空間・プロダクトデザイン関連職", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "経営コンサルタント、戦略コンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "財務コンサルタント、会計コンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "組織コンサルタント、人事コンサルタント、業務プロセスコンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "生産コンサルタント、物流コンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "営業コンサルタント、マーケティングコンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "ISOコンサルタント、ISO審査員", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "公開業務【IPO】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "研究調査員、リサーチャー", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "環境調査、環境分析", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "その他コンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "公認会計士、税理士", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "弁護士、弁理士、特許技術者", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "司法書士、行政書士", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "社会保険労務士、中小企業診断士", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "技術コンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "士業補助者", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "その他専門コンサルタント", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "ディーラー、トレーダー、ファンドマネージャー、運用業務", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "アクチュアリー、クオンツ、金融商品開発", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "投資銀行業務【インベストバンキング】、M&A業務、ストラテジックファイナンス", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "アナリスト、エコノミスト、リサーチ", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "金融法人営業", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "FP【ファイナンシャルプランナー】、金融個人営業", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "金融代理店営業、パートナーセールス", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "事務・管理【銀行系】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "事務・管理【生損保系】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "事務・管理【信託系】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "事務・管理【証券系】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "事務・管理【カード・信販・ノンバンク系】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "事務・管理【商品取引系】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "金融システム企画", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "リスク・与信・債権管理", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "アンダーライター、生損保系専門職【査定・損害調査等】", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "その他金融専門職", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "用地仕入、不動産仕入", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "不動産営業", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "不動産鑑定、デューデリジェンス", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "不動産管理、マンション管理、ビル管理", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "プロパティマネージャー", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "ファシリティマネージャー", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "アセットマネージャー", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "不動産事業企画、不動産開発", ""),
        ("専門職【コンサルタント・士業・金融・不動産】", "その他不動産専門職", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "システムアナリスト", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "システムコンサルタント", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "システムアーキテクト、ITアーキテクト", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "パッケージ導入コンサルタント【ERP・SCM・CRM等】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "パッケージ導入コンサルタント【OS・メール・グループウェア等】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "セキュリティコンサルタント、セキュリティエンジニア", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "プリセールス、セールスエンジニア", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "Web・オープン系 プロジェクトマネージャー【PM】、リーダー【PL】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "Web・オープン系 SE【アプリケーション設計】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "Web・オープン系 SE【データベース設計】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "Web・オープン系 プログラマ【PG】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "Web・オープン系 SE【モバイル・スマートフォン】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "汎用機系 プロジェクトマネージャー【PM】、リーダー【PL】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "汎用機系 SE【アプリケーション設計】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "汎用機系 SE【データベース設計】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "汎用機系 プログラマ【PG】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "制御系 プロジェクトマネージャー【PM】、リーダー【PL】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "制御系 SE【ソフトウェア設計】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "制御系 プログラマ【PG】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "組み込み系 プロジェクトマネージャー【PM】、リーダー【PL】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "組み込み系 SE【ソフトウェア設計】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "組み込み系 プログラマ【PG】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "パッケージソフト・ミドルウェア プロダクトマネージャー、リーダー【PL】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "パッケージソフト・ミドルウェア 開発エンジニア", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "パッケージソフト・ミドルウェア QAエンジニア", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "パッケージソフト・ミドルウェア ローカライズ", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "ネットワーク設計・ネットワーク構築", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "サーバ設計・サーバ構築", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "通信インフラ計画・通信インフラ策定", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "通信インフラ設計・通信インフラ構築【有線系】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "通信インフラ設計・通信インフラ構築【無線系】", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "通信インフラ設置・通信インフラテスト", ""),
        ("ITエンジニア【システム開発・SE・インフラ】", "サーバ運用・保守", ""),
    ]
    
    def __init__(self, yaml_config_path):
        self.yaml_config_path = yaml_config_path
        self.config = self._load_yaml_config()
        
        # 職種分類テーブルを動的に読み込み
        self.JOB_CATEGORIES = self._load_job_categories()
        self.field_mapping = self.config['mapping_spec']['field_mapping']
        self.processing_rules = self.config['processing_rules']
        
        # OpenAI API設定
        load_dotenv()
        api_key = os.getenv('GPTAPI')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
        else:
            self.openai_client = None
        
        # キャッシュ機能
        self.job_classification_cache = {}
        
    def _load_yaml_config(self):
        """YAMLマッピング設定を読み込み"""
        with open(self.yaml_config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    
    def _should_include_row(self, row, headers):
        """行がフィルタ条件を満たすかチェック"""
        # 含める条件
        if 'include_if' in self.processing_rules['filter']:
            for field, value in self.processing_rules['filter']['include_if'].items():
                if field in headers:
                    field_index = headers.index(field)
                    if field_index < len(row) and str(row[field_index]) != str(value):
                        return False
        
        # 除外条件
        if 'exclude_if' in self.processing_rules['filter']:
            for field, condition in self.processing_rules['filter']['exclude_if'].items():
                if field in headers:
                    field_index = headers.index(field)
                    if field_index < len(row):
                        field_value = row[field_index].strip()
                        if condition == '"" or null':
                            if field_value == '' or field_value == '""' or field_value.lower() == 'null':
                                return False
        
        return True
    
    def _get_source_value(self, row, headers, source_field):
        """ソースフィールドから値を取得"""
        if source_field == 'null' or source_field is None:
            return ""
        
        if source_field in headers:
            field_index = headers.index(source_field)
            if field_index < len(row):
                return row[field_index].strip()
        
        return ""
    
    def _transform_field(self, source_value, transform_rule, row=None, headers=None):
        """フィールド変換ルールを適用"""
        if transform_rule == "そのまま":
            return source_value
        
        elif transform_rule.startswith("固定："):
            fixed_value = transform_rule.replace("固定：", "").strip()
            if fixed_value.startswith('"') and fixed_value.endswith('"'):
                fixed_value = fixed_value[1:-1]
            # 「空白」という文字列は実際の空白に変換
            if fixed_value == "空白":
                fixed_value = ""
            return fixed_value
        
        elif "GPT" in transform_rule:
            # 職種分類（中分類）の場合はOpenAI APIを使用
            if "職種分類" in transform_rule:
                return self._classify_job_category_with_gpt(source_value, transform_rule, row, headers)
            else:
                return self._simple_classification(source_value, transform_rule, row, headers)
        
        elif "採用人数" in transform_rule:
            return self._extract_hiring_count(source_value)
        
        elif "年齢" in transform_rule and "記載がない場合" in transform_rule:
            if source_value and source_value.strip():
                return source_value
            elif "35" in transform_rule:
                return "35"
            elif "25" in transform_rule:
                return "25"
        
        elif "都道府県正規化" in transform_rule:
            return self._normalize_prefecture(source_value)
        
        return source_value
    
    def _classify_job_category_with_gpt(self, source_value, transform_rule, row, headers):
        """OpenAI APIを使用して職種分類を判定（キャッシュ機能付き）"""
        if not source_value or not source_value.strip():
            return ""
        
        # キャッシュから検索
        cache_key = source_value.strip()
        if cache_key in self.job_classification_cache:
            return self.job_classification_cache[cache_key]
        
        if not self.openai_client:
            # API未設定の場合はキーワードベースフォールバック
            result = self._keyword_based_classification(source_value)
            self.job_classification_cache[cache_key] = result
            return result
        
        try:
            # 事前フィルタリング: 技術系の場合は営業系を完全除外
            pre_filtered_result = self._pre_filter_technical_jobs(source_value)
            if pre_filtered_result:
                self.job_classification_cache[cache_key] = pre_filtered_result
                return pre_filtered_result
            
            # AH列の値を取得して動的フィルタリング
            ah_value = source_row.get("AH列の値", "") if hasattr(source_row, 'get') else ""
            if not ah_value and hasattr(source_row, 'iloc') and len(source_row) > 33:  # AH列は34番目（0ベース）
                ah_value = str(source_row.iloc[33]).strip() if pd.notna(source_row.iloc[33]) else ""
            
            # AH列の値に基づいて選択肢をフィルタリング
            if ah_value:
                filtered_categories = [
                    category for category in self.JOB_CATEGORIES 
                    if category[2] == ah_value  # C列（Notion職種(紐づけ)）と一致
                ]
                if filtered_categories:
                    job_options = [category[1] for category in filtered_categories]
                    logger.info(f"AH列の値 '{ah_value}' に基づいて {len(job_options)} の選択肢にフィルタリング")
                else:
                    # 一致する選択肢がない場合は全選択肢を使用
                    job_options = [category[1] for category in self.JOB_CATEGORIES]
                    logger.warning(f"AH列の値 '{ah_value}' に一致する選択肢なし、全選択肢を使用")
            else:
                # AH列の値がない場合は全選択肢を使用
                job_options = [category[1] for category in self.JOB_CATEGORIES]
                logger.info("AH列の値なし、全選択肢を使用")
            
            job_options_text = "\n".join([f"{i+1}. {option}" for i, option in enumerate(job_options)])
            
            # プロンプト作成
            prompt = f"""以下の求人タイトルに最も適した職種分類を、下記の選択肢から1つだけ選んでください。

【最優先判定ルール（営業系絶対除外）】
・「エンジニア」「開発」「プログラマー」「SE」「PG」+ プログラミング言語（Java/PHP/Python/JavaScript等）が含まれる場合
  → 営業系職種は絶対に選択禁止、必ずITエンジニア系を選択
・「デザイナー」「UI」「UX」「デザイン」が含まれる場合
  → 営業系職種は絶対に選択禁止、必ずクリエイティブ系またはWeb系を選択

【通常の判定ルール】
・「マーケティング」「企画」が含まれる場合は企画・マーケティング系を選択
・「採用」「人事」「HR」が含まれる場合は事務・管理系の人事関連を選択
・「営業」「セールス」は技術系キーワードが一切ない場合のみ営業系を選択

【求人タイトル】
{source_value}

【職種分類の選択肢】
{job_options_text}

回答は「番号: 職種名」の形式で、最も適切な1つだけを選択してください。
例: 1: 企画営業【法人営業・個人営業】"""

            # OpenAI API呼び出し
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは職種分類の専門家です。業務内容を分析して最適な職種分類を選択してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            # レスポンス解析
            answer = response.choices[0].message.content.strip()
            
            # 回答から職種名を抽出
            result = "その他営業関連職"  # デフォルト
            for line in answer.split('\n'):
                if ':' in line:
                    try:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            job_name = parts[1].strip()
                            # フィルタリングされた選択肢内に存在するかチェック
                            if job_name in job_options:
                                result = job_name
                                break
                    except:
                        continue
                    if result != "その他営業関連職":
                        break
            
            # キャッシュに保存
            self.job_classification_cache[cache_key] = result
            return result
            
        except Exception as e:
            # API呼び出し失敗時のキーワードベースフォールバック
            print(f"OpenAI API呼び出しエラー: {e}")
            result = self._keyword_based_classification(source_value)
            self.job_classification_cache[cache_key] = result
            return result
    
    def _get_job_major_category(self, job_minor_category):
        """職種中分類から職種大分類を取得"""
        for major, minor, _ in self.JOB_CATEGORIES:
            if minor == job_minor_category:
                return major
        return ""
    
    def _normalize_prefecture(self, value):
        """都道府県を一つに正規化（東京都優先）"""
        if not value or not value.strip():
            return ""
        
        # カンマ区切りで分割
        parts = [part.strip() for part in value.split(',')]
        
        # 東京都が含まれているかチェック
        for part in parts:
            if '東京都' in part:
                return '東京都'
        
        # 東京都がない場合は最初の都道府県を返す
        if parts:
            return parts[0]
        
        return value.strip()
    
    def _sort_field_mapping_by_priority(self):
        """フィールドマッピングを処理優先度でソート"""
        # 職種分類（中分類）を最優先、職種（大分類）を次に処理
        priority_order = {
            "職種分類（中分類）": 1,
            "職種（大分類）": 2
        }
        
        def get_priority(mapping):
            target_column = mapping['target_column']
            return priority_order.get(target_column, 999)  # その他は最後
        
        return sorted(self.field_mapping, key=get_priority)
    
    def _simple_classification(self, source_value, transform_rule, row, headers):
        """簡単な分類ロジック"""
        if not source_value:
            return ""
        
        source_str = source_value.lower()
        
        # 休日分類
        if "土日休み" in transform_rule or "シフト制" in transform_rule:
            if any(keyword in source_str for keyword in ["土日", "週休2日", "完全週休"]):
                return "土日休み"
            elif any(keyword in source_str for keyword in ["シフト", "交代", "24時間"]):
                return "シフト制"
            else:
                return "その他"
        
        # 転勤可能性
        elif "転勤" in transform_rule and ("あり" in transform_rule or "なし" in transform_rule):
            if any(keyword in source_str for keyword in ["転勤", "異動", "転勤あり"]):
                return "あり"
            else:
                return "なし"
        
        # 試用期間
        elif "試用期間" in transform_rule and ("あり" in transform_rule or "なし" in transform_rule):
            if any(keyword in source_str for keyword in ["試用期間", "試用", "研修期間"]):
                return "あり"
            else:
                return "なし"
        
        # 賞与
        elif "賞与" in transform_rule and ("あり" in transform_rule or "なし" in transform_rule):
            if any(keyword in source_str for keyword in ["賞与", "ボーナス", "年２回", "年2回"]):
                return "あり"
            else:
                return "なし"
        
        return ""
    
    def _extract_hiring_count(self, source_value):
        """採用人数を抽出"""
        if not source_value:
            return "若干名"
        
        # 数字+名/人のパターンを検索
        number_pattern = r'(\d+)(?:名|人)'
        match = re.search(number_pattern, source_value)
        
        if match:
            return f"{match.group(1)}名"
        elif any(keyword in source_value for keyword in ["若干", "数名"]):
            return "若干名"
        else:
            return "若干名"
    
    def convert_csv_with_callback(self, input_csv_path, output_csv_path, log_callback, progress_callback=None):
        """CSVファイルを変換（コールバック付き）"""
        log_callback(f"CSVファイル読み込み開始: {os.path.basename(input_csv_path)}")
        
        # フィールドマッピングを処理順序で並び替え（職種分類（中分類）を先に処理）
        sorted_field_mapping = self._sort_field_mapping_by_priority()
        
        # 出力カラムの準備（元の順序を維持）
        output_columns = [mapping['target_column'] for mapping in self.field_mapping]
        
        input_count = 0
        output_count = 0
        total_rows = 0
        
        try:
            # 総行数をカウント
            with open(input_csv_path, 'r', encoding='utf-8-sig') as temp_file:
                total_rows = sum(1 for line in temp_file) - 1  # ヘッダーを除く
            log_callback(f"総行数: {total_rows} 行")
            
            if progress_callback:
                progress_callback(0, total_rows, "CSV読み込み開始")
            
            with open(input_csv_path, 'r', encoding='utf-8-sig') as infile, \
                 open(output_csv_path, 'w', encoding='utf-8-sig', newline='') as outfile:
                
                reader = csv.reader(infile)
                writer = csv.writer(outfile)
                
                # ヘッダー行処理
                input_headers = next(reader)
                input_count += 1
                log_callback(f"ヘッダー読み込み完了: {len(input_headers)} 列")
                
                # 出力ヘッダー書き込み
                writer.writerow(output_columns)
                
                # データ行処理
                for row in reader:
                    input_count += 1
                    
                    # 進捗表示
                    if progress_callback:
                        stage_message = "フィルタリング中"
                        if input_count % 100 == 0:  # 100行ごとに更新
                            progress_callback(input_count, total_rows, stage_message)
                    
                    # フィルタリングチェック
                    if not self._should_include_row(row, input_headers):
                        continue
                    
                    # 進捗表示更新
                    if progress_callback:
                        cache_info = f"(キャッシュ: {len(self.job_classification_cache)}件)"
                        progress_callback(input_count, total_rows, f"データ変換中 {cache_info}")
                    
                    # 出力行作成
                    output_row = []
                    job_minor_category = ""
                    
                    for mapping in sorted_field_mapping:  # 優先度順で処理
                        source_field = mapping['source_field']
                        target_column = mapping['target_column']
                        transform_rule = mapping['transform']
                        
                        # ソース値取得
                        source_value = self._get_source_value(row, input_headers, source_field)
                        
                        # 職種分類判定の場合は特別表示
                        if target_column == "職種分類（中分類）" and "GPT" in transform_rule:
                            if progress_callback:
                                progress_callback(input_count, total_rows, f"AI職種判定中 (行:{output_count+1})")
                        
                        # 変換適用
                        transformed_value = self._transform_field(
                            source_value, transform_rule, row, input_headers
                        )
                        
                        # 職種分類（中分類）の場合は値を保存
                        if target_column == "職種分類（中分類）":
                            job_minor_category = transformed_value
                        
                        # 職種（大分類）の場合は職種分類（中分類）から取得
                        elif target_column == "職種（大分類）":
                            transformed_value = self._get_job_major_category(job_minor_category)
                    
                    # 元の順序で出力行を構築
                    final_output_row = []
                    for original_mapping in self.field_mapping:
                        target_column = original_mapping['target_column']
                        
                        # 対応する値を見つけて追加
                        found_value = ""
                        for processed_mapping in sorted_field_mapping:
                            if processed_mapping['target_column'] == target_column:
                                # 処理済みの値を使用（簡略化のため、再処理）
                                source_field = processed_mapping['source_field']
                                transform_rule = processed_mapping['transform']
                                source_value = self._get_source_value(row, input_headers, source_field)
                                
                                if target_column == "職種分類（中分類）":
                                    found_value = job_minor_category
                                elif target_column == "職種（大分類）":
                                    found_value = self._get_job_major_category(job_minor_category)
                                else:
                                    found_value = self._transform_field(
                                        source_value, transform_rule, row, input_headers
                                    )
                                break
                        
                        final_output_row.append(found_value)
                    
                    # 出力行書き込み
                    writer.writerow(final_output_row)
                    output_count += 1
        
        except Exception as e:
            log_callback(f"変換処理でエラーが発生: {e}")
            return False
        
        # 最終進捗更新
        if progress_callback:
            progress_callback(total_rows, total_rows, "変換完了")
        
        log_callback(f"入力行数: {input_count}")
        log_callback(f"出力行数: {output_count}")
        log_callback(f"フィルタリング: {input_count - output_count} 行除外")
        log_callback(f"キャッシュヒット数: {len(self.job_classification_cache)} 件")
        
        return True
    
    def _pre_filter_technical_jobs(self, source_value):
        """技術系職種の事前フィルタリング（営業系誤分類防止）"""
        if not source_value:
            return None
        
        content = source_value.lower()
        
        # 技術系の強力なシグナル
        engineer_keywords = ["エンジニア", "開発", "プログラマー", "se", "pg"]
        tech_languages = ["java", "php", "python", "javascript", "react", "vue", "angular", "go", "ruby", "c++", "c#", "swift", "kotlin"]
        tech_tools = ["docker", "kubernetes", "aws", "azure", "gcp", "git", "github"]
        
        has_engineer = any(keyword in content for keyword in engineer_keywords)
        has_language = any(keyword in content for keyword in tech_languages)
        has_tools = any(keyword in content for keyword in tech_tools)
        
        # エンジニア + プログラミング言語 = 絶対的技術職
        if has_engineer and (has_language or has_tools):
            if any(keyword in content for keyword in ["バックエンド", "backend", "サーバー", "api"]):
                return "Web・オープン系 SE【アプリケーション設計】"
            elif any(keyword in content for keyword in ["フロントエンド", "frontend", "react", "vue"]):
                return "Webデザイナー、フロントエンドエンジニア、コーダー、フラッシャー"
            elif any(keyword in content for keyword in ["インフラ", "サーバー", "ネットワーク", "aws", "azure"]):
                return "サーバ設計・サーバ構築"
            else:
                return "Web・オープン系 プログラマ【PG】"
        
        # デザイナー系の事前フィルタリング
        designer_keywords = ["デザイナー", "ui", "ux"]
        if any(keyword in content for keyword in designer_keywords):
            if any(keyword in content for keyword in ["ui", "ux"]):
                return "情報アーキテクト、UI/UXデザイナー"
            elif "web" in content:
                return "Webデザイナー、フロントエンドエンジニア、コーダー、フラッシャー"
            else:
                return "グラフィックデザイナー"
        
        return None  # 事前フィルタリング該当なし
    
    def _keyword_based_classification(self, source_value):
        """キーワードベースでの職種分類（GPT API未設定時のフォールバック）"""
        if not source_value:
            return "その他営業関連職"
        
        content = source_value.lower()
        
        # エンジニア系（強力な優先判定）
        engineer_keywords = ["エンジニア", "開発", "プログラマー", "se", "pg"]
        engineer_strong_keywords = engineer_keywords
        tech_languages = ["java", "php", "python", "javascript", "react", "vue", "angular", "go", "ruby", "c++", "c#"]
        tech_keywords = [
            "プログラム", "コーディング", "プログラミング", "バックエンド", "フロントエンド",
            "サーバー", "インフラ", "ネットワーク", "データベース", "mysql", "sql", "api"
        ]
        
        # 技術系キーワード + プログラミング言語の組み合わせで絶対的にエンジニア判定
        has_engineer_keyword = any(keyword in content for keyword in engineer_strong_keywords)
        has_tech_language = any(keyword in content for keyword in tech_languages)
        has_tech_keyword = any(keyword in content for keyword in tech_keywords)
        
        if has_engineer_keyword and (has_tech_language or has_tech_keyword):
            if any(keyword in content for keyword in ["バックエンド", "サーバー", "api", "java", "php", "python"]):
                return "Web・オープン系 SE【アプリケーション設計】"
            elif any(keyword in content for keyword in ["フロントエンド", "react", "vue", "angular", "javascript"]):
                return "Webデザイナー、フロントエンドエンジニア、コーダー、フラッシャー"
            elif any(keyword in content for keyword in ["インフラ", "サーバー", "ネットワーク"]):
                return "サーバ設計・サーバ構築"
            else:
                return "Web・オープン系 プログラマ【PG】"
        
        # デザイナー系
        designer_keywords = [
            "デザイナー", "デザイン", "ui", "ux", "グラフィック", "webデザイン",
            "figma", "photoshop", "illustrator", "アートディレクター"
        ]
        if any(keyword in content for keyword in designer_keywords):
            if any(keyword in content for keyword in ["ui", "ux", "webデザイン"]):
                return "情報アーキテクト、UI/UXデザイナー"
            elif any(keyword in content for keyword in ["web"]):
                return "Webデザイナー、フロントエンドエンジニア、コーダー、フラッシャー"
            else:
                return "グラフィックデザイナー"
        
        # マーケティング系
        marketing_keywords = [
            "マーケティング", "企画", "広告", "宣伝", "プロモーション", "商品企画",
            "事業企画", "経営企画", "webマーケティング", "デジタルマーケティング"
        ]
        if any(keyword in content for keyword in marketing_keywords):
            if "経営" in content:
                return "経営企画"
            elif any(keyword in content for keyword in ["web", "デジタル"]):
                return "Webマーケティング、デジタルマーケティング"
            elif "商品" in content:
                return "商品企画、商品開発"
            else:
                return "販促企画、営業企画"
        
        # 人事・採用系
        hr_keywords = [
            "人事", "採用", "hr", "リクルート", "キャリアアドバイザー", "キャリアコンサルタント"
        ]
        if any(keyword in content for keyword in hr_keywords):
            if any(keyword in content for keyword in ["キャリア", "アドバイザー", "コンサルタント"]):
                return "キャリアカウンセラー、キャリアコンサルタント、人材派遣コーディネーター"
            else:
                return "人事、給与、労務、採用"
        
        # ディレクター系（エンジニアやデザイナーが誤分類されやすい）
        director_keywords = ["ディレクター", "プロデューサー", "pm", "プロジェクトマネージャー"]
        if any(keyword in content for keyword in director_keywords):
            if any(keyword in content for keyword in engineer_keywords):
                return "Web・オープン系 プロジェクトマネージャー【PM】、リーダー【PL】"
            elif any(keyword in content for keyword in ["web"]):
                return "Webプロデューサー、Webディレクター、Webマスター、Web企画、Webプランナー"
            else:
                return "管理職【その他】"
        
        # 営業系（技術系キーワードがない場合のみ）
        sales_keywords = ["営業", "セールス", "法人営業", "個人営業"]
        all_tech_keywords = engineer_strong_keywords + tech_languages + tech_keywords + designer_keywords
        
        has_sales = any(keyword in content for keyword in sales_keywords)
        has_any_tech = any(keyword in content for keyword in all_tech_keywords)
        
        # 営業キーワードがあっても技術系キーワードがある場合は営業系を選択しない
        if has_sales and not has_any_tech:
            return "企画営業【法人営業・個人営業】"
        
        # デフォルト
        return "その他営業関連職"

def main():
    root = tk.Tk()
    app = JobinsGUIConverter(root)
    root.mainloop()

if __name__ == "__main__":
    main()
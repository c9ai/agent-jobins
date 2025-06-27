#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
求人マスタCSVをJobins用CSVへ変換するスクリプト
YAMLマッピング設定に基づいてフィールド変換を実行
"""

import pandas as pd
import yaml
import argparse
import logging
from pathlib import Path
from datetime import datetime
import re
import os
from dotenv import load_dotenv
from openai import OpenAI

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JobinsCSVConverter:
    def __init__(self, yaml_config_path):
        """
        初期化
        
        Args:
            yaml_config_path (str): YAMLマッピングファイルのパス
        """
        self.yaml_config_path = yaml_config_path
        self.config = self._load_yaml_config()
        self.field_mapping = self.config['mapping_spec']['field_mapping']
        self.processing_rules = self.config['processing_rules']
        
        # OpenAI API設定
        load_dotenv()
        api_key = os.getenv('GPTAPI')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
            logger.info("OpenAI API設定完了")
        else:
            self.openai_client = None
            logger.warning("OpenAI APIキーが設定されていません")
        
        # キャッシュ機能
        self.job_classification_cache = {}
        
        # 職種分類テーブル
        self.JOB_CATEGORIES = self._load_job_categories()
        
    def _load_yaml_config(self):
        """YAMLマッピング設定を読み込み"""
        try:
            with open(self.yaml_config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error(f"YAML設定ファイルの読み込みに失敗: {e}")
            raise
    
    def _apply_filter(self, df):
        """フィルタリング条件を適用"""
        filtered_df = df.copy()
        
        # 含める条件
        if 'include_if' in self.processing_rules['filter']:
            for field, value in self.processing_rules['filter']['include_if'].items():
                if field in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df[field] == value]
                    logger.info(f"フィルタ適用: {field} == {value}, 残り件数: {len(filtered_df)}")
        
        # 除外条件
        if 'exclude_if' in self.processing_rules['filter']:
            for field, condition in self.processing_rules['filter']['exclude_if'].items():
                if field in filtered_df.columns:
                    if condition == '"" or null':
                        # 空文字またはnullを除外
                        filtered_df = filtered_df[
                            (filtered_df[field].notna()) & 
                            (filtered_df[field] != '') & 
                            (filtered_df[field] != '""')
                        ]
                        logger.info(f"フィルタ適用: {field} != '' or null, 残り件数: {len(filtered_df)}")
        
        return filtered_df
    
    def _transform_field(self, source_value, transform_rule, source_row=None):
        """
        フィールド変換ルールを適用
        
        Args:
            source_value: ソース値
            transform_rule (str): 変換ルール
            source_row (Series): ソース行データ（GPT分類等で使用）
            
        Returns:
            変換後の値
        """
        if transform_rule == "そのまま":
            return source_value if pd.notna(source_value) else ""
        
        elif transform_rule.startswith("固定："):
            # 固定値
            fixed_value = transform_rule.replace("固定：", "").strip()
            if fixed_value.startswith('"') and fixed_value.endswith('"'):
                fixed_value = fixed_value[1:-1]
            return fixed_value
        
        elif "GPT" in transform_rule:
            # 職種分類（中分類）の場合はOpenAI APIを使用
            if "職種分類" in transform_rule:
                return self._classify_job_category_with_gpt(source_value, transform_rule, source_row)
            else:
                return self._simple_classification(source_value, transform_rule, source_row)
        
        elif "分類元のテーブル" in transform_rule:
            # 職種（大分類）は職種分類（中分類）から取得
            if "職種(大分類)" in transform_rule or "職種（大分類）" in transform_rule:
                # 同じ行の職種分類（中分類）から大分類を取得
                if hasattr(self, '_current_job_minor_category'):
                    return self._get_job_major_category(self._current_job_minor_category)
            return ""
        
        elif "採用人数" in transform_rule:
            # 採用人数抽出
            return self._extract_hiring_count(source_value)
        
        elif "年齢" in transform_rule and "記載がない場合" in transform_rule:
            # 年齢制限処理
            if pd.notna(source_value) and str(source_value).strip():
                return str(source_value)
            elif "35" in transform_rule:
                return "35"
            elif "25" in transform_rule:
                return "25"
        
        else:
            # その他の変換ルール（暫定的にそのまま返す）
            return source_value if pd.notna(source_value) else ""
    
    def _simple_classification(self, source_value, transform_rule, source_row):
        """簡単な分類ロジック（GPTの代替）"""
        if pd.isna(source_value):
            return ""
        
        source_str = str(source_value).lower()
        
        # 休日分類
        if "土日休み" in transform_rule:
            if any(keyword in source_str for keyword in ["土日", "週休2日", "完全週休"]):
                return "土日休み"
            elif any(keyword in source_str for keyword in ["シフト", "交代", "24時間"]):
                return "シフト制"
            else:
                return "その他"
        
        # 転勤可能性
        elif "転勤" in transform_rule:
            if any(keyword in source_str for keyword in ["転勤", "異動", "転勤あり"]):
                return "あり"
            else:
                return "なし"
        
        # 試用期間
        elif "試用期間" in transform_rule:
            if any(keyword in source_str for keyword in ["試用期間", "試用", "研修期間"]):
                return "あり"
            else:
                return "なし"
        
        # 賞与
        elif "賞与" in transform_rule:
            if any(keyword in source_str for keyword in ["賞与", "ボーナス", "年２回", "年2回"]):
                return "あり"
            else:
                return "なし"
        
        return ""
    
    def _extract_hiring_count(self, source_value):
        """採用人数を抽出"""
        if pd.isna(source_value):
            return "若干名"
        
        source_str = str(source_value)
        
        # 数字+名/人のパターンを検索
        number_pattern = r'(\d+)(?:名|人)'
        match = re.search(number_pattern, source_str)
        
        if match:
            return f"{match.group(1)}名"
        elif any(keyword in source_str for keyword in ["若干", "数名"]):
            return "若干名"
        else:
            return "若干名"
    
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
    
    def _classify_job_category_with_gpt(self, source_value, transform_rule, source_row):
        """OpenAI APIを使用して職種分類を判定（キャッシュ機能付き）"""
        if not source_value or not source_value.strip():
            return ""
        
        # キャッシュから検索
        cache_key = source_value.strip()
        if cache_key in self.job_classification_cache:
            logger.debug(f"キャッシュヒット: {cache_key}")
            return self.job_classification_cache[cache_key]
        
        if not self.openai_client:
            # API未設定の場合はフォールバック
            result = "その他営業関連職"
            self.job_classification_cache[cache_key] = result
            logger.warning("OpenAI API未設定、フォールバック値を使用")
            return result
        
        try:
            # AH列（職種）の値を取得して動的フィルタリング
            ah_value = ""
            if source_row is not None:
                ah_value = source_row.get("職種", "") if hasattr(source_row, 'get') else ""
                if not ah_value and hasattr(source_row, 'iloc'):
                    # フォールバック: 職種列が見つからない場合
                    ah_value = ""
            
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
            prompt = f"""以下の業務内容に最も適した職種分類を、下記の選択肢から1つだけ選んでください。

【業務内容】
{source_value}

【職種分類の選択肢】
{job_options_text}

回答は「番号: 職種名」の形式で、最も適切な1つだけを選択してください。
例: 1: 企画営業【法人営業・個人営業】"""

            # OpenAI API呼び出し
            logger.info(f"OpenAI API呼び出し中...")
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
            logger.debug(f"GPT回答: {answer}")
            
            # 回答から職種名を抽出（フィルタリングされた選択肢内で検証）
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
            logger.info(f"職種分類完了: {result}")
            return result
            
        except Exception as e:
            # API呼び出し失敗時のフォールバック
            import traceback
            logger.error(f"OpenAI API呼び出しエラー: {e}")
            logger.error(f"スタックトレース: {traceback.format_exc()}")
            result = "その他営業関連職"
            self.job_classification_cache[cache_key] = result
            return result
    
    def _get_job_major_category(self, job_minor_category):
        """職種中分類から職種大分類を取得"""
        for major, minor, _ in self.JOB_CATEGORIES:
            if minor == job_minor_category:
                return major
        return ""
    
    def convert_csv(self, input_csv_path, output_csv_path=None):
        """
        CSVファイルを変換
        
        Args:
            input_csv_path (str): 入力CSVファイルパス
            output_csv_path (str): 出力CSVファイルパス
            
        Returns:
            pandas.DataFrame: 変換後のデータフレーム
        """
        logger.info(f"CSVファイル読み込み開始: {input_csv_path}")
        
        # CSVファイル読み込み
        try:
            df = pd.read_csv(input_csv_path, encoding='utf-8-sig')
            logger.info(f"読み込み完了: {len(df)} 行")
        except Exception as e:
            logger.error(f"CSVファイル読み込みエラー: {e}")
            raise
        
        # フィルタリング適用
        filtered_df = self._apply_filter(df)
        logger.info(f"フィルタリング後: {len(filtered_df)} 行")
        
        # 出力データフレーム初期化
        output_df = pd.DataFrame()
        
        # フィールドマッピングを適用（職種分類を先に処理）
        job_minor_categories = {}  # 行ごとの職種分類（中分類）を保存
        
        # 1. 職種分類（中分類）を先に処理
        for mapping in self.field_mapping:
            target_column = mapping['target_column']
            if target_column == "職種分類（中分類）":
                source_field = mapping['source_field']
                transform_rule = mapping['transform']
                
                logger.info("職種分類（中分類）の処理開始")
                
                if source_field in filtered_df.columns:
                    # 各行に対して職種分類を実行
                    for idx, row in filtered_df.iterrows():
                        source_value = row[source_field] if pd.notna(row[source_field]) else ""
                        job_minor = self._transform_field(source_value, transform_rule, row)
                        job_minor_categories[idx] = job_minor
                    
                    output_df[target_column] = [job_minor_categories.get(idx, "") for idx in filtered_df.index]
                    logger.info(f"職種分類（中分類）完了: {len(self.job_classification_cache)} 件キャッシュ")
                else:
                    logger.warning(f"ソースフィールドが見つかりません: {source_field}")
                    output_df[target_column] = ""
                break
        
        # 2. その他のフィールドを処理
        for mapping in self.field_mapping:
            source_field = mapping['source_field']
            target_column = mapping['target_column']
            transform_rule = mapping['transform']
            
            # 職種分類（中分類）は既に処理済みなのでスキップ
            if target_column == "職種分類（中分類）":
                continue
            
            logger.debug(f"変換中: {source_field} -> {target_column}")
            
            if target_column == "職種（大分類）":
                # 職種（大分類）は職種分類（中分類）から取得
                output_df[target_column] = [
                    self._get_job_major_category(job_minor_categories.get(idx, ""))
                    for idx in filtered_df.index
                ]
                logger.info("職種（大分類）完了")
                
            elif source_field == 'null' or source_field is None:
                # ソースフィールドがnullの場合は固定値または空値
                if transform_rule.startswith("固定："):
                    output_df[target_column] = transform_rule.replace("固定：", "").strip().replace('"', '')
                else:
                    output_df[target_column] = ""
            else:
                # ソースフィールドが存在する場合
                if source_field in filtered_df.columns:
                    # 各行に対して変換ルールを適用
                    output_df[target_column] = filtered_df.apply(
                        lambda row: self._transform_field(
                            row[source_field], transform_rule, row
                        ), 
                        axis=1
                    )
                else:
                    logger.warning(f"ソースフィールドが見つかりません: {source_field}")
                    output_df[target_column] = ""
        
        # 出力ファイル保存
        if output_csv_path:
            try:
                output_df.to_csv(output_csv_path, encoding='utf-8-sig', index=False)
                logger.info(f"変換完了: {output_csv_path}")
            except Exception as e:
                logger.error(f"出力ファイル保存エラー: {e}")
                raise
        
        return output_df

def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='求人マスタCSVをJobins用CSVへ変換')
    parser.add_argument('input_csv', help='入力CSVファイルパス')
    parser.add_argument('-c', '--config', default='jobins_yaml_mapping.yaml', 
                       help='YAMLマッピング設定ファイル (default: jobins_yaml_mapping.yaml)')
    parser.add_argument('-o', '--output', help='出力CSVファイルパス')
    parser.add_argument('-v', '--verbose', action='store_true', help='詳細ログ出力')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 出力ファイル名生成
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_path = Path(args.input_csv)
        args.output = input_path.parent / f"JOBINS掲載用_{timestamp}.csv"
    
    try:
        # 変換器初期化
        converter = JobinsCSVConverter(args.config)
        
        # CSV変換実行
        result_df = converter.convert_csv(args.input_csv, args.output)
        
        print(f"変換完了!")
        print(f"入力: {args.input_csv}")
        print(f"出力: {args.output}")
        print(f"変換件数: {len(result_df)} 行")
        
    except Exception as e:
        logger.error(f"変換処理でエラーが発生しました: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
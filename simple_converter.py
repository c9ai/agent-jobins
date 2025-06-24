#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡易版CSV変換スクリプト（pandasなしバージョン）
求人マスタCSVをJobins用CSVへ変換
"""

import csv
import yaml
import argparse
import sys
import os
from datetime import datetime
import re

class SimpleJobinsConverter:
    def __init__(self, yaml_config_path):
        self.yaml_config_path = yaml_config_path
        self.config = self._load_yaml_config()
        self.field_mapping = self.config['mapping_spec']['field_mapping']
        self.processing_rules = self.config['processing_rules']
        
    def _load_yaml_config(self):
        """YAMLマッピング設定を読み込み"""
        try:
            with open(self.yaml_config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"YAML設定ファイルの読み込みに失敗: {e}")
            sys.exit(1)
    
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
        
        return source_value
    
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
    
    def convert_csv(self, input_csv_path, output_csv_path=None):
        """CSVファイルを変換"""
        print(f"CSVファイル読み込み開始: {input_csv_path}")
        
        # 出力ファイル名生成
        if not output_csv_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_csv_path = f"JOBINS掲載用_{timestamp}.csv"
        
        # 出力カラムの準備
        output_columns = [mapping['target_column'] for mapping in self.field_mapping]
        
        input_count = 0
        output_count = 0
        
        try:
            with open(input_csv_path, 'r', encoding='utf-8-sig') as infile, \
                 open(output_csv_path, 'w', encoding='utf-8-sig', newline='') as outfile:
                
                reader = csv.reader(infile)
                writer = csv.writer(outfile)
                
                # ヘッダー行処理
                input_headers = next(reader)
                input_count += 1
                
                # 出力ヘッダー書き込み
                writer.writerow(output_columns)
                
                # データ行処理
                for row in reader:
                    input_count += 1
                    
                    # フィルタリングチェック
                    if not self._should_include_row(row, input_headers):
                        continue
                    
                    # 出力行作成
                    output_row = []
                    for mapping in self.field_mapping:
                        source_field = mapping['source_field']
                        transform_rule = mapping['transform']
                        
                        # ソース値取得
                        source_value = self._get_source_value(row, input_headers, source_field)
                        
                        # 変換適用
                        transformed_value = self._transform_field(
                            source_value, transform_rule, row, input_headers
                        )
                        
                        output_row.append(transformed_value)
                    
                    # 出力行書き込み
                    writer.writerow(output_row)
                    output_count += 1
        
        except Exception as e:
            print(f"変換処理でエラーが発生: {e}")
            return False
        
        print(f"変換完了!")
        print(f"入力: {input_csv_path} ({input_count} 行)")
        print(f"出力: {output_csv_path} ({output_count} 行)")
        print(f"出力ファイルパス: {os.path.abspath(output_csv_path)}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description='求人マスタCSVをJobins用CSVへ変換（簡易版）')
    parser.add_argument('input_csv', help='入力CSVファイルパス')
    parser.add_argument('-c', '--config', default='jobins_yaml_mapping.yaml', 
                       help='YAMLマッピング設定ファイル')
    parser.add_argument('-o', '--output', help='出力CSVファイルパス')
    
    args = parser.parse_args()
    
    # 入力ファイル存在チェック
    if not os.path.exists(args.input_csv):
        print(f"入力ファイルが見つかりません: {args.input_csv}")
        return 1
    
    # 設定ファイル存在チェック
    if not os.path.exists(args.config):
        print(f"設定ファイルが見つかりません: {args.config}")
        return 1
    
    try:
        converter = SimpleJobinsConverter(args.config)
        success = converter.convert_csv(args.input_csv, args.output)
        return 0 if success else 1
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
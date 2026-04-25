# BRCA1/TP53 ゲノム解析ツール

NCBIの公開データを使ってGC含量とORFを解析・可視化するPythonスクリプトです。

## 使い方

```bash
py brca1_analysis.py
```

## 出力されるファイル

- `gc_window_comparison.png` - ウィンドウサイズ別GC含量分布
- `orf_distribution.png` - ORF長さ分布

## 使用ライブラリ

- BioPython
- matplotlib
- pandas
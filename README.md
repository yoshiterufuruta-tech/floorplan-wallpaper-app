# Floorplan Wallpaper API

図面画像から以下を自動で計算する API:

- 壁線抽出 → 壁周長
- 開口部検出（窓・ドア）
- 寸法OCR
- 開口部と寸法の紐付け
- 壁紙面積（㎡）

## 起動方法（ローカル）

```bash
pip install -r requirements.txt
uvicorn main:app --reload

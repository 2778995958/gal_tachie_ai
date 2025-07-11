import os
import csv
from PIL import Image
import sys
from typing import Dict, List, NamedTuple

# --- 1. 資料結構與 CSV 載入函式 (保持不變) ---
class Rect(NamedTuple): left: int; top: int; right: int; bottom: int
class LayerData(NamedTuple): source_file: str; name: str; rect: Rect

def load_layer_database(csv_path: str) -> Dict[str, LayerData]:
    db = {}
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    db[row['layer_name']] = LayerData(row['source_lsf'], row['layer_name'], Rect(int(row['rect_left']), int(row['rect_top']), int(row['rect_right']), int(row['rect_bottom'])))
                except (KeyError, ValueError): continue
    except FileNotFoundError:
        print(f"致命錯誤：找不到圖層數據庫 '{csv_path}'。")
        return None
    print(f"✅ 成功載入 {len(db)} 筆圖層數據。")
    return db

# --- 2. 兩階段解析器 (已加入 dupdress 邏輯) ---
def parse_config_with_rules(config_path: str) -> Dict:
    base_assets = {"outfits": {}, "faces": {}}
    rules = []
    
    print(f"📖 正在解析資產定義檔 (階段一): {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if not parts: continue
            part_type = parts[0]
            if part_type in ["dress", "face"] and len(parts) >= 3:
                group_id, layer_name = parts[1], parts[2]
                asset_list = base_assets["outfits"] if part_type == "dress" else base_assets["faces"]
                if group_id not in asset_list: asset_list[group_id] = []
                asset_list[group_id].append(layer_name)
            elif part_type in ["dupface", "dupdress"] and len(parts) >= 3:
                rules.append({'type': part_type, 'parts': parts[1:]})

    print(f"⚙️ 正在應用 {len(rules)} 條生成規則 (階段二)...")
    final_assets = {"outfits": base_assets["outfits"].copy(), "faces": base_assets["faces"].copy()}
    
    for rule in rules:
        rule_type, rule_parts = rule['type'], rule['parts']
        
        if rule_type == 'dupface' and len(rule_parts) >= 2:
            suffix, layer_to_add = rule_parts[0], rule_parts[1]
            new_faces = {}
            for face_id, face_layers in base_assets["faces"].items():
                new_id = f"{face_id}{suffix}"
                new_layers = face_layers + [layer_to_add]
                new_faces[new_id] = new_layers
            final_assets["faces"].update(new_faces)
            print(f"  - 應用 'dupface' 規則，衍生出 {len(new_faces)} 個新表情。")

        elif rule_type == 'dupdress' and len(rule_parts) >= 2:
            suffix, layer_to_add = rule_parts[0], rule_parts[1]
            new_outfits = {}
            # 規則只對基礎衣服生效，避免重複衍生
            for outfit_id, outfit_layers in base_assets["outfits"].items():
                new_id = f"{outfit_id}{suffix}"
                new_layers = outfit_layers + [layer_to_add]
                new_outfits[new_id] = new_layers
            final_assets["outfits"].update(new_outfits)
            print(f"  - 應用 'dupdress' 規則，衍生出 {len(new_outfits)} 套新衣服。")

    print(f"✅ 成功生成最終資產！共 {len(final_assets['outfits'])} 套衣服, {len(final_assets['faces'])} 個表情。")
    return final_assets

# --- 3. 核心合成函式 (保持不變) ---
def compose_image(recipe: List[str], db: Dict[str, LayerData], img_folder: str) -> Image.Image:
    # ... (此函式與上個版本完全相同，此處省略以保持簡潔) ...
    layers_data = [db[name] for name in recipe if name in db]
    if not layers_data: return None
    min_left, min_top = min(l.rect.left for l in layers_data), min(l.rect.top for l in layers_data)
    max_right, max_bottom = max(l.rect.right for l in layers_data), max(l.rect.bottom for l in layers_data)
    canvas = Image.new('RGBA', (max_right - min_left, max_bottom - min_top), (0, 0, 0, 0))
    for layer_data in layers_data:
        try:
            layer_img = Image.open(os.path.join(img_folder, f"{layer_data.name}.png")).convert("RGBA")
            temp_canvas = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            paste_pos = (layer_data.rect.left - min_left, layer_data.rect.top - min_top)
            temp_canvas.paste(layer_img, paste_pos)
            canvas = Image.alpha_composite(canvas, temp_canvas)
        except FileNotFoundError: continue
    return canvas

# --- 4. 主程式 (已修正檔名邏輯) ---
def main():
    CSV_DB_FILE = 'lsf_universal_export.csv'
    IMAGES_DIR = 'images'
    CONFIG_FILE = 'master_config.txt'
    OUTPUT_DIR = 'output2'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    layer_db = load_layer_database(CSV_DB_FILE)
    if not layer_db: return

    assets = parse_config_with_rules(CONFIG_FILE)
    if not assets: return

    print("\n🏭 終極版工廠啟動...")

    for outfit_id, outfit_layers in assets["outfits"].items():
        if not outfit_layers: continue
            
        representative_layer_name = outfit_layers[0]
        if representative_layer_name not in layer_db:
            print(f"  - 警告: outfit '{outfit_id}' 的代表圖層 '{representative_layer_name}' 不在CSV中，跳過。")
            continue
            
        source_lsf_filename = layer_db[representative_layer_name].source_file
        lsf_base_name = os.path.splitext(source_lsf_filename)[0]
            
        for face_id, face_layers in assets["faces"].items():
            final_recipe = outfit_layers + face_layers
            
            # 使用 LSF 基礎檔名 + 衣服ID + 表情ID 的格式
            output_filename = f"{lsf_base_name}_{outfit_id}_{face_id}.png"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            
            print(f"  - 正在合成: {output_filename}")
            
            final_image = compose_image(final_recipe, layer_db, IMAGES_DIR)
            
            if final_image:
                final_image.save(output_path)
                print(f"    ✅ 已儲存。")
            else:
                print(f"    ❌ 合成失敗。")

    print("\n✨ 所有組合已生成完畢！")

if __name__ == "__main__":
    main()
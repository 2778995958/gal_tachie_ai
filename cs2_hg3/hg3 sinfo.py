import os
import csv
from PIL import Image
from typing import Dict, List, NamedTuple
from collections import defaultdict
from itertools import combinations

# --- 1. 輔助函式與資料結構 ---
class LayerData(NamedTuple):
    file_name: str; canvas_width: int; canvas_height: int; offset_x: int; offset_y: int

def load_layer_database(txt_path: str) -> Dict[str, LayerData]:
    db = {};
    try:
        with open(txt_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                try:
                    base_name = os.path.splitext(row['FileName'])[0]
                    db[base_name.lower()] = LayerData(file_name=row['FileName'], canvas_width=int(row['CanvasWidth']), canvas_height=int(row['CanvasHeight']), offset_x=int(row['OffsetX']), offset_y=int(row['OffsetY']))
                except (KeyError, ValueError): continue
    except FileNotFoundError:
        print(f"致命錯誤：找不到圖層數據庫 '{txt_path}'。"); return None
    print(f"✅ 成功載入 {len(db)} 筆圖層數據。"); return db

def load_png_fragment(base_name, png_dir, db, cache):
    lookup_key = base_name.lower()
    if lookup_key in cache: return cache[lookup_key]
    layer_data = db.get(lookup_key)
    if not layer_data: print(f"    - 警告: 數據庫中找不到圖層 '{base_name}'"); return None
    png_path = os.path.join(png_dir, os.path.splitext(layer_data.file_name)[0] + ".png")
    if os.path.exists(png_path):
        try:
            img = Image.open(png_path).convert('RGBA'); cache[lookup_key] = img; return img
        except Exception as e: print(f"  [Error] Failed to load image {png_path}: {e}")
    else:
        print(f"  [Warning] Image file not found: {png_path}")
    cache[lookup_key] = None; return None

def compose_image(recipe: List[str], db: Dict[str, LayerData], img_folder: str, canvas_size: tuple, cache: dict) -> Image.Image:
    canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
    for layer_name in recipe:
        fragment = load_png_fragment(layer_name, img_folder, db, cache)
        if fragment:
            offset = (db[layer_name.lower()].offset_x, db[layer_name.lower()].offset_y)
            box = (offset[0], offset[1], offset[0] + fragment.width, offset[1] + fragment.height)
            base_crop = canvas.crop(box); composite_crop = Image.alpha_composite(base_crop, fragment); canvas.paste(composite_crop, box)
    return canvas

# --- 2. 針對單一角色組的處理函式 ---
# 【V38 NameError 修正】: 函式定義中加入了 db 參數
def process_character_group(prefix: str, instructions: List[Dict], db: Dict, img_dir: str, output_dir: str):
    print(f"\n--- 正在處理角色組: {prefix} ---")
    
    canvas_size = None
    for instruction in instructions:
        layer_name = instruction.get('layer')
        if layer_name and layer_name.lower() in db:
            canvas_size = (db[layer_name.lower()].canvas_width, db[layer_name.lower()].canvas_height)
            print(f"🎨 檢測到畫布尺寸: {canvas_size[0]}x{canvas_size[1]} (基於圖層 '{layer_name}')"); break
    if canvas_size is None: print(f"  [錯誤] 無法確定角色組 '{prefix}' 的畫布尺寸，跳過。"); return

    base_outfits = defaultdict(list); outfit_options = []
    base_faces = defaultdict(list); face_options = []
    for item in instructions:
        class_type, group_id, layer_name = item['class'], item['id'], item['layer']
        if class_type == 'dress': base_outfits[group_id].append(item)
        elif class_type == 'face': base_faces[group_id].append(item)
        elif class_type == 'dupdress': outfit_options.append(item)
        elif class_type == 'dupface': face_options.append(item)

    final_outfits = {}
    if not base_outfits: final_outfits[''] = []
    else:
        for gid, items in base_outfits.items(): final_outfits[gid] = items
        for i in range(1, len(outfit_options) + 1):
            for combo in combinations(outfit_options, i):
                for base_id, base_items in base_outfits.items():
                    new_id = base_id + "".join(sorted(opt['id'] for opt in combo))
                    final_outfits[new_id] = base_items + list(combo)

    final_faces = {}
    if not base_faces: final_faces[''] = []
    else:
        for gid, items in base_faces.items(): final_faces[gid] = items
        for i in range(1, len(face_options) + 1):
            for combo in combinations(face_options, i):
                for base_id, base_items in base_faces.items():
                    new_id = base_id + "".join(sorted(opt['id'] for opt in combo))
                    final_faces[new_id] = base_items + list(combo)
    
    image_cache = {}
    print(f"  🔄 正在組合 {len(final_outfits)} 套衣服與 {len(final_faces)} 個表情...")
    for outfit_id, outfit_items in final_outfits.items():
        for face_id, face_items in final_faces.items():
            
            all_items_for_recipe = outfit_items + face_items

            # 【V38 排序規則修正】: 根據檔名後綴的長度進行排序
            def get_suffix_length(item):
                layer_name = item['layer']
                if '_' in layer_name:
                    return len(layer_name.rsplit('_', 1)[-1])
                return len(layer_name) # 如果沒有底線，就用整個名稱長度

            all_items_for_recipe.sort(key=get_suffix_length)
            
            final_ordered_layers = [item['layer'] for item in all_items_for_recipe]
            
            if not final_ordered_layers: continue

            output_filename = f"{prefix}_{outfit_id}_{face_id}.png"
            output_path = os.path.join(output_dir, output_filename)

            print(f"    - 正在合成: {output_filename}")
            final_image = compose_image(final_ordered_layers, db, img_dir, canvas_size, image_cache)
            if final_image:
                final_image.save(output_path)
                print(f"      ✅ 已儲存。")

# --- 3. 主程式 ---
def main():
    DB_FILE = 'hg3_coordinates.txt'; IMAGES_DIR = 'images'; RECIPE_FILE = 'recipes.txt'; OUTPUT_DIR = 'output_final'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    layer_db = load_layer_database(DB_FILE)
    if not layer_db: return

    all_instructions = []
    try:
        with open(RECIPE_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            for i, row in enumerate(reader):
                if not row or not row[0] or row[0].strip().startswith('#') or len(row) < 3: continue
                class_type, group_id, layer_name = [col.strip() for col in row[:3]]
                layer_name_no_ext = os.path.splitext(layer_name)[0]
                all_instructions.append({'class': class_type, 'id': group_id, 'layer': layer_name_no_ext, 'order': i})
        print(f"📖 成功解析 {len(all_instructions)} 條圖層指令。")
    except FileNotFoundError:
        print(f"致命錯誤：找不到配方檔 '{RECIPE_FILE}'。"); return
    
    if not all_instructions: print("錯誤: 配方檔為空。"); return

    char_ingredients = defaultdict(list)
    for instruction in all_instructions:
        layer_name = instruction.get('layer')
        if layer_name:
            if '_' in layer_name: prefix = layer_name.rsplit('_', 1)[0]
            else: prefix = layer_name
            char_ingredients[prefix].append(instruction)
    print(f"ℹ️ 檢測到 {len(char_ingredients)} 個角色組: {list(char_ingredients.keys())}")

    print("\n🏭 合成工廠啟動...")
    for prefix, instructions in char_ingredients.items():
        # 將 db 傳遞進去
        process_character_group(prefix, instructions, layer_db, IMAGES_DIR, OUTPUT_DIR)
        
    print("\n✨ 所有任務已處理完畢！")

if __name__ == "__main__":
    main()

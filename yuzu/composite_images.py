import json
from PIL import Image
import os
import shutil
import re
import glob

# --- 設定區 ---
OUTPUT_DIR = "universal_final_output"
# --- 設定結束 ---

class UniversalFinalEngine:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.scenes = {}
        os.makedirs(self.output_dir, exist_ok=True)
        self._load_all_scenes()

    def _load_all_scenes(self):
        print("--- 正在掃描並載入所有場景資源 ---")
        all_json_files = glob.glob('ev*.json')
        scene_files = [f for f in all_json_files if '.resx.' not in f]
        for json_path in scene_files:
            scene_name = json_path.replace('.json', '')
            print(f"  - 發現並載入: {scene_name}")
            with open(json_path, 'r', encoding='utf-8') as f:
                self.scenes[scene_name] = json.load(f)
        print("--- 所有場景載入完畢 ---\n")

    def _get_image_path(self, scene_name, image_id: int):
        path = os.path.join(scene_name, f"{image_id}.png")
        return path if os.path.exists(path) else None

    def phase1_generate_images(self):
        print("--- Phase 1: 正在生成所有基礎圖片 (採用多底圖邏輯) ---")
        for scene_name, scene_data in self.scenes.items():
            print(f"\n--- 開始處理場景: {scene_name} ---")
            
            file_prefix = re.sub(r'[a-zA-Z]$', '', scene_name)
            
            # 建立一個從 layer_id 到 layer_info 的快速查找字典
            layer_map = {layer['layer_id']: layer for layer in scene_data['layers']}

            # 第一輪：先處理所有沒有 diff_id 的底圖層
            base_layers = [l for l in scene_data['layers'] if 'diff_id' not in l]
            for layer_info in base_layers:
                output_name = file_prefix + layer_info['name'].lower()
                output_path = os.path.join(self.output_dir, f"{output_name}.png")
                img_path = self._get_image_path(scene_name, layer_info['layer_id'])
                if img_path:
                    # 使用 Pillow 開啟再儲存，以解決 CRC 不同的問題
                    Image.open(img_path).convert("RGBA").save(output_path)
                    print(f"- 已生成底圖: {output_name}.png")

            # 第二輪：處理所有有 diff_id 的前景圖層
            foreground_layers = [l for l in scene_data['layers'] if 'diff_id' in l]
            for layer_info in foreground_layers:
                output_name = file_prefix + layer_info['name'].lower()
                output_path = os.path.join(self.output_dir, f"{output_name}.png")
                
                # 找到它對應的底圖層
                base_layer_info = layer_map.get(layer_info['diff_id'])
                if not base_layer_info:
                    print(f"  -> 警告: 找不到 diff_id {layer_info['diff_id']} 對應的底圖層，跳過 {output_name}")
                    continue
                
                base_output_name = file_prefix + base_layer_info['name'].lower()
                base_image_path = os.path.join(self.output_dir, f"{base_output_name}.png")
                
                fg_image_path = self._get_image_path(scene_name, layer_info['layer_id'])

                if os.path.exists(base_image_path) and fg_image_path:
                    base_image = Image.open(base_image_path).convert("RGBA")
                    fg_image = Image.open(fg_image_path).convert("RGBA")
                    
                    final_canvas = base_image.copy()
                    final_canvas.paste(fg_image, (layer_info['left'], layer_info['top']), fg_image)
                    final_canvas.save(output_path)
                    print(f"- 已生成前景圖: {output_name}.png (底圖: {base_output_name}.png)")

        print("--- Phase 1 完成 ---\n")

    def phase2_process_composites(self, thumb_name):
        # ... (Phase 2 邏輯不變) ...
        print(f"--- Phase 2: 正在為 '{thumb_name}' 進行疊加 ---")
        composite_map = {}
        # ... (代碼省略以保持簡潔，與上一版相同) ...
        if not os.path.exists('cg.txt'): return composite_map
        with open('cg.txt', 'r', encoding='utf-8') as f:
            cg_content = f.read()
        match = re.search(f"^{re.escape(thumb_name)},(.*)", cg_content, re.MULTILINE)
        if not match: return composite_map
        composite_tasks = re.findall(r'([\w_]+)\|*\*([\w_]+)', match.group(1))
        for base_name, patch_name in composite_tasks:
            base_image_path = os.path.join(self.output_dir, f"{base_name}.png")
            patch_image_path = os.path.join(self.output_dir, f"{patch_name}.png")
            if not os.path.exists(base_image_path) or not os.path.exists(patch_image_path): continue
            base_image = Image.open(base_image_path).convert("RGBA")
            patch_image = Image.open(patch_image_path).convert("RGBA")
            base_image.paste(patch_image, (0, 0), patch_image)
            base_image.save(patch_image_path)
            composite_map[patch_name] = base_name
        print(f"--- '{thumb_name}' 疊加任務完成 ---\n")
        return composite_map

    def phase3_rename_files(self, thumb_name):
        # ... (Phase 3 邏輯不變) ...
        print(f"--- Phase 3: 正在為 '{thumb_name}' 的結果重命名 ---")
        # ... (代碼省略以保持簡潔，與上一版相同) ...
        if not os.path.exists('cg.txt'): return
        with open('cg.txt', 'r', encoding='utf-8') as f:
            cg_content = f.read()
        match = re.search(f"^{re.escape(thumb_name)},(.*)", cg_content, re.MULTILINE)
        if not match: return
        all_names_in_order = match.group(1).split(',')
        counter = 1
        for name in all_names_in_order:
            order_index = f"{counter:02d}"
            if '|*' in name:
                base_name, patch_name = name.split('|*')
                old_path = os.path.join(self.output_dir, f"{patch_name}.png")
                match_patch = re.match(r'(ev\d+)_([a-z]{2})', patch_name)
                match_base = re.match(r'ev\d+([a-z]{2})', base_name)
                if match_patch and match_base:
                    prefix, patch_code, base_code = match_patch.group(1), match_patch.group(2), match_base.group(1)
                    new_name = f"{prefix}_{order_index}_{base_code}{patch_code}.png"
                    new_path = os.path.join(self.output_dir, new_name)
                    if os.path.exists(old_path) and old_path != new_path: os.rename(old_path, new_path)
            else:
                old_path = os.path.join(self.output_dir, f"{name}.png")
                match_simple = re.match(r'(ev\d+)([a-z]{2})', name)
                if match_simple:
                    prefix, code = match_simple.groups()
                    new_name = f"{prefix}_{order_index}_{code}.png"
                    new_path = os.path.join(self.output_dir, new_name)
                    if os.path.exists(old_path) and old_path != new_path: os.rename(old_path, new_path)
            counter += 1
        print(f"--- '{thumb_name}' 重命名完成 ---\n")


if __name__ == "__main__":
    engine = UniversalFinalEngine(OUTPUT_DIR)
    engine.phase1_generate_images()
    
    # 自動尋找並處理所有 thum_evXXX 任務
    if os.path.exists('cg.txt'):
        with open('cg.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        thumb_names = re.findall(r'^(thum_ev\d+)', content, re.MULTILINE)
        for thumb in thumb_names:
            engine.phase2_process_composites(thumb)
            engine.phase3_rename_files(thumb)
    
    print("所有生產任務已執行完畢！")
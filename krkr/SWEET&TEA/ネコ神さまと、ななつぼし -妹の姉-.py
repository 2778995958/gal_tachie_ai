# 【Purpure立繪合成系統 Ver. 41.0 - 服裝多層堆疊版】
# 修正重點：
# 1. 支援 "同一服裝名 = 同一套圖" 的邏輯。
#    例如:
#    dress 制服 ... 制服
#    dress 制服 ... メガネ
#    程式會將這兩行合併，合成時同時畫出 "制服" 和 "メガネ"。
# 2. 保持先前的所有功能 (ID檔名、自動裁切、貓耳自動搜尋)。

import os
import glob
from PIL import Image
from datetime import datetime

# ==============================================================================
# --- 設定區 ---
# ==============================================================================
MIMI_VARIANTS = [0, 1, 2]        # 差分變數 (mimi)
GENERATE_SIMPLE_MODE = True      # 是否生成無 mimi 版
OUTPUT_ROOT = "output"           # 輸出資料夾
# ==============================================================================

class LayerSystem:
    def __init__(self, txt_path, img_folder_name):
        self.layers = {}
        self.path_map = {}      
        self.suffix_map = {}    
        self.txt_path = txt_path
        self.img_folder = img_folder_name
        self.img_prefix = f"{img_folder_name}_"

    def normalize_key(self, text):
        """統一移除空白與 tab，轉小寫"""
        return text.replace(" ", "").replace("\t", "").strip()

    def load_layers(self):
        print(f"[INFO] 正在解析圖層檔: {self.txt_path}")
        try:
            with open(self.txt_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            raw_data = {}
            for line in lines:
                parts = line.strip().split('\t')
                if len(parts) < 10: continue
                try:
                    layer_id = parts[9].strip()
                    parent_id = parts[10].strip() if len(parts) > 10 and parts[10] else None
                    name = parts[1].strip()
                    
                    info = {
                        "name": name,
                        "id": layer_id,
                        "parent_id": parent_id,
                        "type": parts[0].strip(),
                        "left": int(parts[2]) if parts[2] else 0,
                        "top": int(parts[3]) if parts[3] else 0,
                        "width": int(parts[4]) if parts[4] else 0,
                        "height": int(parts[5]) if parts[5] else 0,
                        "filename": f"{self.img_prefix}{layer_id}.png"
                    }
                    raw_data[layer_id] = info
                except:
                    continue
            
            self.layers = raw_data
            
            count = 0
            for lid, info in raw_data.items():
                if info['type'] == '0': 
                    full_path = info["name"]
                    curr = info
                    while curr["parent_id"] and curr["parent_id"] in raw_data:
                        parent = raw_data[curr["parent_id"]]
                        full_path = parent["name"] + "/" + full_path
                        curr = parent
                    
                    # 1. 絕對路徑
                    clean_full = self.normalize_key(full_path)
                    self.path_map[clean_full] = info
                    
                    # 2. 後綴路徑 (模糊搜尋用)
                    parts = full_path.split('/')
                    if len(parts) >= 2:
                        suffix_2 = "/".join(parts[-2:])
                        self.suffix_map[self.normalize_key(suffix_2)] = info
                    if len(parts) >= 3:
                        suffix_3 = "/".join(parts[-3:])
                        self.suffix_map[self.normalize_key(suffix_3)] = info
                    
                    # 3. 純檔名
                    self.suffix_map[self.normalize_key(info["name"])] = info
                    
                    count += 1

            print(f"[INFO] 圖層解析完成，索引了 {count} 張圖片。")
            return True
        except Exception as e:
            print(f"[錯誤] 解析圖層檔失敗: {e}")
            return False

    def get_layer_by_path(self, path):
        target = self.normalize_key(path)
        if target in self.path_map: return self.path_map[target]
        
        parts = path.split('/')
        if len(parts) >= 2:
            suffix = "/".join(parts[-2:])
            clean_suffix = self.normalize_key(suffix)
            if clean_suffix in self.suffix_map: return self.suffix_map[clean_suffix]
            
        if len(parts) > 0:
            name_only = self.normalize_key(parts[-1])
            if name_only in self.suffix_map: return self.suffix_map[name_only]
            
        return None

class RuleSystem:
    def __init__(self, sinfo_path):
        self.sinfo_path = sinfo_path
        # 修改：不再是用 list 存單個 dress，而是用 OrderList + Dict 來分組
        self.dress_order = []      # 記錄服裝名稱出現的順序 (例如 ["制服", "制服メガネなし"])
        self.dress_layers = {}     # 記錄服裝對應的圖層列表 (例如 "制服" -> ["制服", "メガネ"])
        self.aliases = {}
        self.fgnames = {} 

    def load_rules(self):
        if not os.path.exists(self.sinfo_path): return False
        try:
            with open(self.sinfo_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    parts = line.split('\t')
                    cmd = parts[0]

                    if cmd == 'dress':
                        if len(parts) >= 5:
                            d_name = parts[1].strip()
                            d_layer = parts[4].strip()
                            
                            # --- 關鍵修改：服裝分組邏輯 ---
                            if d_name not in self.dress_layers:
                                self.dress_layers[d_name] = []
                                self.dress_order.append(d_name) # 記錄順序
                            
                            # 將該行定義的 layer 加入該服裝的清單中
                            self.dress_layers[d_name].append(d_layer)
                    
                    elif cmd == 'fgname':
                        logic_name = parts[1].strip()
                        real_path = parts[2].strip()
                        condition = parts[3].strip() if len(parts) > 3 else None
                        
                        if logic_name not in self.fgnames: self.fgnames[logic_name] = []
                        self.fgnames[logic_name].append({"path": real_path, "condition": condition})

                    elif cmd == 'fgalias':
                        self.aliases[parts[1].strip()] = [p.strip() for p in parts[2:]]
            return True
        except Exception as e:
            print(f"[錯誤] {e}")
            return False

def check_condition(condition_str, mimi_val):
    if mimi_val is None: return False
    if not condition_str: return True
    if "mimi" in condition_str:
        return f"mimi=={mimi_val}" in condition_str.replace(" ", "")
    return True

def process_character(txt_file, sinfo_file, log_file):
    char_name = os.path.splitext(os.path.basename(txt_file))[0]
    img_folder = char_name
    
    log_file.write(f"\n===== 開始處理: {char_name} =====\n")
    
    layer_sys = LayerSystem(txt_file, img_folder)
    if not layer_sys.load_layers(): return

    rule_sys = RuleSystem(sinfo_file)
    if not rule_sys.load_rules(): return

    char_out_dir = os.path.join(OUTPUT_ROOT, char_name)
    if not os.path.exists(char_out_dir): os.makedirs(char_out_dir)

    loop_variants = [None] if GENERATE_SIMPLE_MODE else []
    loop_variants.extend(MIMI_VARIANTS)

    generated_files = set()

    # --- 依照服裝順序處理 ---
    for dress_name in rule_sys.dress_order:
        
        # 1. 取得該服裝的所有基礎圖層 (支援多層)
        target_layers = rule_sys.dress_layers[dress_name]
        base_layer_infos = []
        
        missing_base = False
        for path in target_layers:
            l_info = layer_sys.get_layer_by_path(path)
            if l_info:
                base_layer_infos.append(l_info)
            else:
                print(f"[警告] 找不到服裝 '{dress_name}' 的構成圖層: {path}")
                missing_base = True
        
        if missing_base and not base_layer_infos:
            print(f"[跳過] 服裝 {dress_name} 完全無法讀取")
            continue
        
        print(f"--- 處理中: {dress_name} (由 {len(base_layer_infos)} 個圖層組成) ---")

        for mimi_val in loop_variants:
            is_simple_mode = (mimi_val is None)
            
            # 2. 搜尋自動綁定部件 (e.g. 貓耳)
            auto_parts = []
            if not is_simple_mode:
                suffix = f"@{dress_name}"
                for logic_name, variants in rule_sys.fgnames.items():
                    if logic_name.endswith(suffix):
                        for v in variants:
                            if check_condition(v['condition'], mimi_val):
                                target_path = v['path']
                                p_info = layer_sys.get_layer_by_path(target_path)
                                if p_info:
                                    auto_parts.append(p_info)
            
            # 3. 處理每個表情
            for alias_name, components in rule_sys.aliases.items():
                draw_queue = []
                
                # 順序 A: 衣服列表 (最底層，可能包含多個圖層，如 本體+眼鏡)
                draw_queue.extend(base_layer_infos)
                
                # 順序 B: 自動配件 (貓耳)
                draw_queue.extend(auto_parts)

                # 順序 C: 表情部件
                for comp_key in components:
                    if comp_key in ["パーツ_無し", "ダミー"]: continue
                    
                    candidates = rule_sys.fgnames.get(comp_key, [])
                    target_path = None
                    for cand in candidates:
                         if is_simple_mode:
                             target_path = cand['path']
                             break
                         else:
                             if check_condition(cand['condition'], mimi_val):
                                target_path = cand['path']
                                break
                    
                    if not target_path and comp_key in layer_sys.path_map:
                        target_path = comp_key
                    if not target_path: 
                         target_path = comp_key

                    if target_path:
                        l_info = layer_sys.get_layer_by_path(target_path)
                        if l_info: draw_queue.append(l_info)

                if not draw_queue: continue

                # --- 檔名生成 ---
                used_ids = [str(p['id']) for p in draw_queue]
                
                # 去重但保留順序 (確保衣服ID在最前)
                ordered_unique_ids = []
                seen = set()
                for uid in used_ids:
                    if uid not in seen:
                        ordered_unique_ids.append(uid)
                        seen.add(uid)
                
                id_string = "_".join(ordered_unique_ids)
                out_filename = f"{char_name}_{id_string}.png"
                
                if out_filename in generated_files:
                    continue 

                # --- 合成 ---
                try:
                    valid_parts = [p for p in draw_queue if p['width'] > 0 and p['height'] > 0]
                    if not valid_parts: continue

                    min_x = min(p['left'] for p in valid_parts)
                    min_y = min(p['top'] for p in valid_parts)
                    max_x = max(p['left'] + p['width'] for p in valid_parts)
                    max_y = max(p['top'] + p['height'] for p in valid_parts)
                    
                    canvas_w = max_x - min_x
                    canvas_h = max_y - min_y
                    
                    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

                    for part in draw_queue:
                        p_path = os.path.join(img_folder, part['filename'])
                        if os.path.exists(p_path):
                            part_img = Image.open(p_path).convert("RGBA")
                            buffer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                            buffer.paste(part_img, (part['left'] - min_x, part['top'] - min_y))
                            canvas = Image.alpha_composite(canvas, buffer)

                    out_fullpath = os.path.join(char_out_dir, out_filename)
                    canvas.save(out_fullpath)
                    generated_files.add(out_filename)
                    print(f"  已生成: {out_filename}")

                except Exception as e:
                    print(f"  [Error] {e}")

if __name__ == '__main__':
    LOG_FILENAME = "generation_log.txt"
    print(f"程式啟動 (Ver 41.0 - Multi-layer Dress)... Log: {LOG_FILENAME}")
    
    with open(LOG_FILENAME, 'w', encoding='utf-8') as log:
        log.write(f"--- {datetime.now()} ---\n")
        txt_files = [f for f in glob.glob('*.txt') if 'sinfo' not in f and 'log' not in f]
        for txt in txt_files:
            sinfo = txt.replace(".txt", ".sinfo.txt")
            if os.path.exists(sinfo):
                process_character(txt, sinfo, log)
    print("\n完成。")

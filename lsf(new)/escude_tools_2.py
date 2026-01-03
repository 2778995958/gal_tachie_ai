import argparse
import sqlite3
import os
import glob
import struct
import re
import csv
from PIL import Image, ImageChops
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import functools

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
# EscudeTools v8.0 (Final) - by Gemini
# 功能:
#   -d:         [解包] .bin -> .db (SQLite)
#   -a:         [通用合成] 強制合成所有 .lsf 檔案的全部圖層 (無視資料庫)
#   -ev:        [合成] 根據 .db 合成事件CG (Event)
#   -s:         [合成] 根據 .db 合成角色立繪 (Stand)
#   -b:         [用於-s] 指定臉紅模式 (可多選，用逗號分隔)
#   -export_lsf:[匯出] .lsf -> .csv (用於分析)
#   -j:         [優化] 指定 CPU 核心數
# ===========================================================================
# 相依性: pip install Pillow numpy
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

# ===========================================================================
# 資料結構定義
# ===========================================================================
@dataclass
class LsfFileHeader:
    revision: int = 0; bg: int = 0; id: int = 0; layer_count: int = 0; width: int = 0; height: int = 0; bx: int = 0; by: int = 0
@dataclass
class Rect:
    left: int = 0; top: int = 0; right: int = 0; bottom: int = 0
@dataclass
class LsfLayerInfo:
    name: str = ""; text: str = ""; rect: Rect = field(default_factory=Rect); cx: int = 0; cy: int = 0; index: int = 0; state: int = 0; mode: int = 0; opacity: int = 0; fill: int = 0; value: int = 0; skip: bool = False
@dataclass
class LsfImageData:
    file_path: str = ""; width: int = 0; height: int = 0
@dataclass
class LsfData:
    filepath: str; lsf_name: str; header: LsfFileHeader = field(default_factory=LsfFileHeader); layers_info: List[LsfLayerInfo] = field(default_factory=list); images: List[LsfImageData] = field(default_factory=list)
@dataclass
class StTable:
    name: str; file: str; option: List[str]; face: int; order: int
@dataclass
class Face:
    face_options: List[str] = field(default_factory=list)
@dataclass
class EvTable:
    name: str; file: str; option: List[str]; order: int

# ===========================================================================
# 核心邏輯實作
# ===========================================================================

def decode_str(b: bytes) -> str:
    return b.decode('cp932', errors='ignore').strip('\x00')

class LsfManager:
    def __init__(self): self._lsf_lookup = {}
    def load_lsf(self, path: str):
        if not os.path.isfile(path): return
        lsf_name = os.path.splitext(os.path.basename(path))[0].lower()
        lsf_dir = os.path.dirname(path)
        with open(path, 'rb') as f:
            header_bytes = f.read(28)
            if len(header_bytes) < 28: return
            sig, rev, bg, id, l_count, w, h, bx, by = struct.unpack('<IHHHHiiii', header_bytes)
            if sig != 0x46534C: return
            header = LsfFileHeader(rev, bg, id, l_count, w, h, bx, by)
            lsf_data = LsfData(filepath=path, lsf_name=lsf_name, header=header)
            for _ in range(header.layer_count):
                layer_bytes = f.read(164)
                if len(layer_bytes) < 164: continue
                name_b, text_b, r_l, r_t, r_r, r_b, cx, cy, idx, state, mode, op, fill, val = struct.unpack('<64s64siiiiiiBBBBII', layer_bytes)
                layer_info = LsfLayerInfo(name=decode_str(name_b), text=decode_str(text_b), rect=Rect(r_l, r_t, r_r, r_b), cx=cx, cy=cy, index=idx, state=state, mode=mode, opacity=op, fill=fill, value=val)
                if name_b.startswith(b'\x00ul\x00'): layer_info.skip = True
                lsf_data.layers_info.append(layer_info)
                img = LsfImageData()
                if not layer_info.skip: img.file_path = os.path.join(lsf_dir, layer_info.name + ".png")
                lsf_data.images.append(img)
        self._lsf_lookup[lsf_name] = lsf_data
    def find_lsf_data_by_name(self, name: str) -> LsfData: return self._lsf_lookup.get(name.lower())

class TableManager:
    @staticmethod
    def parse_options(lsf_data: LsfData, option_str: str) -> list:
        match = re.search(r'p(\d+):(\d+)', option_str)
        if not match: return []
        target_index, target_state = int(match.group(1)), int(match.group(2))
        found_layers = []
        for i, layer_info in enumerate(lsf_data.layers_info):
            if (layer_info.index == 0 and layer_info.state == 0 and layer_info.index == target_index and (layer_info.state + 1) == target_state) or \
               (layer_info.index == target_index and layer_info.state == target_state):
                found_layers.append(i)
        return found_layers
    @staticmethod
    def order_layer(layer_indices: list, layer_filenames: list) -> list:
        if not layer_indices or len(layer_indices) != len(layer_filenames): return layer_indices
        def get_sort_key(filename):
            parts = filename.split('_')
            return int(parts[-1]) if len(parts) >= 3 and parts[-1].isdigit() else 0
        zipped = sorted(zip(layer_indices, layer_filenames), key=lambda x: get_sort_key(x[1]))
        return [item[0] for item in zipped]

class ImageManager:
    @staticmethod
    def composite(base_img: Image.Image, lsf_data: LsfData, layer_index: int) -> Image.Image:
        layer_info = lsf_data.layers_info[layer_index]
        image_info = lsf_data.images[layer_index]
        
        if not image_info.file_path or not os.path.exists(image_info.file_path): 
            return base_img
            
        with Image.open(image_info.file_path) as part_img:
            part_img = part_img.convert("RGBA")
            if base_img.mode != 'RGBA':
                base_img = base_img.convert('RGBA')

            dx, dy = layer_info.rect.left, layer_info.rect.top
            
            # 準備一張跟底圖一樣大的暫存畫布
            # 1. 如果是正片疊底 (Mode 3)，底色要是白色 (因為白色 x 任何色 = 原色)
            # 2. 如果是相加 (Mode 10) 或其他，底色用透明
            bg_color = (255, 255, 255, 0) if layer_info.mode == 3 else (0, 0, 0, 0)
            layer_canvas = Image.new('RGBA', base_img.size, bg_color)
            
            # 將素材貼到暫存畫布的正確位置
            layer_canvas.paste(part_img, (dx, dy), part_img)

            # ==========================================
            # 根據模式選擇正確的混合演算法
            # ==========================================
            
            if layer_info.mode == 3:  # Multiply (正片疊底 / 乗算)
                # 原理：白色變透明，深色疊加變暗
                # 注意：這裡我們使用 ImageChops.multiply
                # 為了避免透明度出錯，我們先把兩張圖都轉成 RGB 進行疊加運算，最後再把 Alpha 補回來
                # (因為通常 Mode 3 是用來畫陰影，範圍不會超過底圖的角色)
                
                # 1. 建立混合用的圖層，背景全白 (255)
                multiply_layer = Image.new('RGBA', base_img.size, (255, 255, 255, 255))
                multiply_layer.paste(part_img, (dx, dy), part_img)
                
                # 2. 使用 Pillow 內建的 multiply
                # 這會讓白色背景消失，只留下深色的帽子/陰影
                result = ImageChops.multiply(base_img, multiply_layer)
                
                # 3. 修正 Alpha 通道 (通常保留底圖的 Alpha)
                # 這能確保陰影不會畫到角色外面去，也不會產生奇怪的方塊
                r, g, b, _ = result.split()
                a = base_img.split()[3] # 取回底圖的 Alpha
                return Image.merge('RGBA', (r, g, b, a))

            elif layer_info.mode == 10: # Add (相加 / 線性加亮)
                # 原理：黑色變透明，亮色疊加更亮
                add_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
                add_layer.paste(part_img, (dx, dy), part_img)
                return ImageChops.add(base_img, add_layer)
                
            else: # Normal (一般模式)
                # 使用 alpha_composite 確保半透明邊緣平滑 (無黑邊)
                # 建立全透明圖層
                normal_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
                normal_layer.paste(part_img, (dx, dy), part_img)
                return Image.alpha_composite(base_img, normal_layer)

def read_string_from_pool(text_pool: bytes, offset: int, encoding='cp932') -> str:
    if offset >= len(text_pool): return f"<Invalid Offset: {offset}>"
    end_index = text_pool.find(b'\x00', offset)
    if end_index == -1: end_index = len(text_pool)
    string_bytes = text_pool[offset:end_index]
    try: return string_bytes.decode(encoding)
    except Exception: return string_bytes.decode('utf-8', errors='ignore')

def process_sheet_for_db(schema_block: bytes, data_block: bytes, text_pool: bytes) -> Dict[str, Any]:
    sheet_info = {"name": "", "columns": [], "records": []}
    try:
        sheet_name_offset = struct.unpack_from('<I', schema_block, 0)[0]
        sheet_info["name"] = read_string_from_pool(text_pool, sheet_name_offset)
        column_count = struct.unpack_from('<I', schema_block, 4)[0]
        record_byte_size = 0
        current_offset = 8
        for _ in range(column_count):
            col_type, col_size, col_name_offset = struct.unpack_from('<HHI', schema_block, current_offset)
            col_name_raw = read_string_from_pool(text_pool, col_name_offset)
            col_name_final = f"{col_name_raw}_{col_type}{col_size}"
            sheet_info["columns"].append({"name": col_name_final, "type": col_type, "size": col_size})
            record_byte_size += col_size
            current_offset += 8
    except Exception as e:
        print(f"    [!!!] Error parsing schema block: {e}"); return None
    try:
        if record_byte_size == 0: return sheet_info
        record_count = len(data_block) // record_byte_size
        current_offset = 0
        for _ in range(record_count):
            record_dict = {}
            for column in sheet_info["columns"]:
                field_bytes = data_block[current_offset : current_offset + column["size"]]
                if column["type"] == 4:
                    str_offset = struct.unpack('<I', field_bytes)[0]
                    record_dict[column["name"]] = read_string_from_pool(text_pool, str_offset)
                else:
                    if column["size"] == 1: record_dict[column["name"]] = struct.unpack('<B', field_bytes)[0]
                    elif column["size"] == 2: record_dict[column["name"]] = struct.unpack('<h', field_bytes)[0]
                    elif column["size"] == 4:
                        if "色" in column["name"]: record_dict[column["name"]] = struct.unpack('<I', field_bytes)[0]
                        else: record_dict[column["name"]] = struct.unpack('<i', field_bytes)[0]
                    else: record_dict[column["name"]] = field_bytes
                current_offset += column["size"]
            sheet_info["records"].append(record_dict)
    except Exception as e:
        print(f"    [!!!] Error parsing data block: {e}")
    return sheet_info

# ===========================================================================
# 4. 功能函式
# ===========================================================================

def process_and_save(lsf_data: LsfData, layer_indices: list, output_path: str):
    header = lsf_data.header; canvas = Image.new('RGBA', (header.width, header.height), (0, 0, 0, 0))
    for index in layer_indices: canvas = ImageManager.composite(canvas, lsf_data, index)
    canvas.save(output_path, 'PNG'); return os.path.basename(output_path)

def process_st_record(st: StTable, lsf_manager: LsfManager, face_groups: dict, output_dir: str, blush_modes: Optional[List[int]]):
    print(f"--- 開始處理 ID: {st.name} (檔案: {st.file}) ---")
    lsf_data = lsf_manager.find_lsf_data_by_name(st.file); 
    if not lsf_data: return f"[警告] {st.name}: 找不到 LSF 檔案 {st.file}.lsf"
    face_data = face_groups.get(st.face, Face()); 
    if not face_data.face_options: return f"[資訊] {st.name}: 無額外表情選項"
    generated_files = []
    for n, face_opt in enumerate(face_data.face_options):
        base_options = st.option + [face_opt]; no_blush_options = [opt for opt in base_options if not opt.startswith('p2:')]; blush2_options = no_blush_options + ['p2:2']
        all_variations = {0: {"suffix": "_b0", "options": no_blush_options}, 1: {"suffix": "_b1", "options": base_options}, 2: {"suffix": "_b2", "options": blush2_options}}
        variations_to_process = {}
        if blush_modes is not None:
            for mode in blush_modes:
                if mode in all_variations: variations_to_process[mode] = all_variations[mode]
        else:
            variations_to_process = {0: all_variations[0], 2: all_variations[2],}
            if any(opt.startswith('p2:1') for opt in base_options): variations_to_process[1] = all_variations[1]
        for _, var_data in variations_to_process.items():
            suffix, current_options = var_data["suffix"], var_data["options"]
            all_layers, all_filenames = [], []
            for opt in current_options:
                if not opt: continue
                indices = TableManager.parse_options(lsf_data, opt); all_layers.extend(indices)
                for i in indices: all_filenames.append(lsf_data.layers_info[i].name)
            if not all_layers: continue
            ordered_list = TableManager.order_layer(all_layers, all_filenames)
            match = re.search(r'([a-zA-Z]+\d+)$', st.name); id_suffix = f"_{match.group(1)}" if match else ""
            new_base_name = f"st_{st.file}{id_suffix}"
            output_path = os.path.join(output_dir, f"{new_base_name}_{n}{suffix}.png")
            process_and_save(lsf_data, ordered_list, output_path); generated_files.append(os.path.basename(output_path))
    return f"[成功] {st.name}: 已生成 {len(generated_files)} 個檔案"

def compose_st_images(image_dir: str, db_path: str, blush_modes: Optional[List[int]] = None, jobs: Optional[int] = None):
    title = "開始合成角色立繪 (ST) 圖片"; 
    if blush_modes is not None: title += f" (指定模式: {blush_modes})"
    else: title += " (自動生成多種臉紅變化)"
    print(f"\n--- {title} ---")
    if not os.path.isdir(image_dir) or not os.path.isfile(db_path): print(f"[錯誤] 請檢查提供的路徑是否有效。"); return
    print("[*] 正在載入所有 LSF 檔案..."); lm = LsfManager(); [lm.load_lsf(p) for p in glob.glob(os.path.join(image_dir, '**', '*.lsf'), recursive=True)]
    print("[*] 正在讀取資料庫..."); conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    all_tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    st_table_name = next((name for name in all_tables if name.startswith("立ち")), None)
    face_table_name = next((name for name in all_tables if name.startswith("表情")), None)
    if not st_table_name or not face_table_name: print(f"[錯誤] 找不到 '立ち' 或 '表情' 資料表。"); conn.close(); return
    st_records = [StTable(name=r['ID_44'], file=r['ファイル_44'], option=(r['オプション_44'] or "").split(' '), face=r['表情_14'], order=r['CG鑑賞_14']) for r in cursor.execute(f"SELECT * FROM [{st_table_name}]")]
    face_groups = {}
    face_table_info = cursor.execute(f"PRAGMA table_info([{face_table_name}])").fetchall(); face_table_columns = [info['name'] for info in face_table_info]
    face_records = cursor.execute(f"SELECT * FROM [{face_table_name}]").fetchall()
    for r in face_records:
        option_value = r['オプション_44']
        if not option_value: continue
        for i, col_name in enumerate(face_table_columns[2:], 2):
            face_id = i - 2
            if r[col_name] == 1:
                if face_id not in face_groups: face_groups[face_id] = Face()
                face_groups[face_id].face_options.append(option_value)
    conn.close()
    output_dir = os.path.join(os.path.dirname(image_dir) or ".", "Output_ST_Py"); os.makedirs(output_dir, exist_ok=True)
    print(f"[*] 資料庫讀取完畢，共 {len(st_records)} 筆立繪記錄，{len(face_groups)} 個表情組。"); print(f"[*] 輸出目錄: {output_dir}"); print("[*] 開始派發合成任務到 CPU 核心...")
    tasks_to_run = [rec for rec in st_records if rec.order != 0]
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        task_func = functools.partial(process_st_record, lsf_manager=lm, face_groups=face_groups, output_dir=output_dir, blush_modes=blush_modes)
        results = list(executor.map(task_func, tasks_to_run))
    print("[*] 所有任務已完成。結果摘要：")
    for res in results: print(f"  - {res}")
    print("\n--- ST 圖片處理完成 ---")

def convert_bin_to_db(bin_dir: str):
    print("\n--- 開始轉換 .bin 到 .db ---")
    if not os.path.isdir(bin_dir): print(f"[錯誤] 目錄不存在，請檢查您的路徑: {bin_dir}"); return
    output_dir = os.path.join(os.path.dirname(bin_dir) or ".", "unpacked_output"); os.makedirs(output_dir, exist_ok=True)
    bin_files = glob.glob(os.path.join(bin_dir, '*.bin'))
    if not bin_files: print(f"[資訊] 在 '{bin_dir}' 中找不到任何 .bin 檔案。"); return
    for filepath in bin_files:
        print(f"[*] 正在處理檔案: {filepath}")
        output_db_path = os.path.join(output_dir, os.path.basename(filepath).replace('.bin', '.db'))
        if os.path.exists(output_db_path): os.remove(output_db_path)
        conn = sqlite3.connect(output_db_path); cursor = conn.cursor()
        with open(filepath, 'rb') as f:
            if f.read(4) != b'mdb\x00': print("[!] 檔案簽名無效。"); continue
            sheet_index = 0
            while True:
                size_bytes = f.read(4)
                if not size_bytes or size_bytes == b'\x00\x00\x00\x00': print("  [-] 已到達檔案結尾標記。"); break
                try:
                    schema_size = struct.unpack('<I', size_bytes)[0]; schema_block = f.read(schema_size)
                    data_size = struct.unpack('<I', f.read(4))[0]; data_block = f.read(data_size)
                    text_size = struct.unpack('<I', f.read(4))[0]; text_pool = f.read(text_size)
                    sheet_data = process_sheet_for_db(schema_block, data_block, text_pool)
                    if sheet_data and sheet_data['columns']:
                        table_name = f"{sheet_data['name']}_{sheet_index:02d}"
                        print(f"    - 正在寫入資料表: [{table_name}]")
                        cols_defs = [f"[{col['name']}] {'TEXT' if col['type'] == 4 else 'INTEGER'}" for col in sheet_data['columns']]
                        cursor.execute(f"CREATE TABLE IF NOT EXISTS [{table_name}] ({', '.join(cols_defs)})")
                        if sheet_data['records']:
                            col_names = [f"[{col['name']}]" for col in sheet_data['columns']]
                            placeholders = ', '.join(['?'] * len(col_names))
                            insert_sql = f"INSERT INTO [{table_name}] ({', '.join(col_names)}) VALUES ({placeholders})"
                            data_to_insert = [tuple(rec[col['name']] for col in sheet_data['columns']) for rec in sheet_data['records']]
                            cursor.executemany(insert_sql, data_to_insert)
                    sheet_index += 1
                except Exception as e:
                    print(f"  [!!!] 處理過程中發生意外錯誤: {e}"); break
        conn.commit(); conn.close()
        print(f"[+] 成功轉換並儲存到 '{output_db_path}'\n")
    print("--- .bin 轉換完成 ---")

def export_lsf_to_csv(image_dir: str):
    print("\n--- 開始匯出 LSF 圖層資訊到 CSV ---")
    if not os.path.isdir(image_dir): print(f"[錯誤] LSF 檔案目錄不存在: {image_dir}"); return
    lm = LsfManager()
    lsf_files = glob.glob(os.path.join(image_dir, '**', '*.lsf'), recursive=True)
    if not lsf_files: print(f"[資訊] 在 '{image_dir}' 中找不到任何 .lsf 檔案。"); return
    output_dir = os.path.join(os.path.dirname(image_dir) or ".", "LSF_Export_Py"); os.makedirs(output_dir, exist_ok=True)
    print(f"[*] CSV 檔案將儲存到: {output_dir}")
    for lsf_path in lsf_files:
        lm.load_lsf(lsf_path)
        lsf_data = lm.find_lsf_data_by_name(os.path.splitext(os.path.basename(lsf_path))[0])
        if not lsf_data: print(f"  [警告] 無法載入 LSF 檔案: {lsf_path}"); continue
        csv_filename = f"{lsf_data.lsf_name}.csv"; csv_filepath = os.path.join(output_dir, csv_filename)
        header = ['Layer_Index', 'PNG_Filename', 'X_Offset', 'Y_Offset', 'Width', 'Height', 'Blend_Mode', 'Opacity', 'Game_Logic_Index', 'Game_Logic_State']
        with open(csv_filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f); writer.writerow(header)
            for i, layer in enumerate(lsf_data.layers_info):
                writer.writerow([i, layer.name, layer.rect.left, layer.rect.top, layer.rect.right - layer.rect.left, layer.rect.bottom - layer.rect.top, layer.mode, layer.opacity, layer.index, layer.state])
        print(f"  [成功] 已匯出 {len(lsf_data.layers_info)} 個圖層到: {csv_filename}")
    print("\n--- LSF 匯出完成 ---")
    
def compose_ev_images(image_dir: str, db_path: str, jobs: Optional[int]):
    print("\n--- 開始合成事件 (EV) 圖片 (多進程加速) ---")
    if not os.path.isdir(image_dir) or not os.path.isfile(db_path): print(f"[錯誤] 請檢查提供的路徑是否有效。"); return
    print("[*] 正在載入所有 LSF 檔案..."); lm = LsfManager(); [lm.load_lsf(p) for p in glob.glob(os.path.join(image_dir, '**', '*.lsf'), recursive=True)]
    print("[*] 正在讀取資料庫..."); conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    event_table_name = next((row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'イベント%';")), None)
    if not event_table_name: print("[錯誤] 在資料庫中找不到 'イベント' 資料表。"); conn.close(); return
    event_records = [EvTable(name=r['ID_44'], file=r['ファイル_44'], option=(r['オプション_44'] or "").split(' '), order=r['CG鑑賞_14']) for r in cursor.execute(f"SELECT * FROM [{event_table_name}]")]
    conn.close()
    output_dir = os.path.join(os.path.dirname(image_dir) or ".", "Output_EV_Py"); os.makedirs(output_dir, exist_ok=True)
    print(f"[*] 資料庫讀取完畢，共 {len(event_records)} 筆事件記錄。"); print(f"[*] 輸出目錄: {output_dir}"); print("[*] 開始派發合成任務到 CPU 核心...")
    tasks = []
    for evt in event_records:
        if evt.order == 0: continue
        lsf_data = lm.find_lsf_data_by_name(evt.file)
        if not lsf_data: print(f"  [警告] 找不到 LSF 檔案: {evt.file}.lsf，跳過。"); continue
        
        base_name = evt.name; cg_order = evt.order
        match = re.search(r'[@#]', base_name)
        new_name = f"{base_name[:match.start()]}_{cg_order}{base_name[match.start():]}" if match else f"{base_name}_{cg_order}"
        output_path = os.path.join(output_dir, f"{new_name}.png")

        pending_list, pending_list_fn = [], []
        for opt in evt.option:
            if not opt: continue
            layer_indices = TableManager.parse_options(lsf_data, opt); pending_list.extend(layer_indices)
            for i in layer_indices: pending_list_fn.append(lsf_data.layers_info[i].name)
        ordered_list = TableManager.order_layer(pending_list, pending_list_fn)
        if not ordered_list or ordered_list[0] != 0: ordered_list.insert(0, 0)
        tasks.append({'lsf_data': lsf_data, 'layers': ordered_list, 'out_path': output_path})
        
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(process_and_save, t['lsf_data'], t['layers'], t['out_path']): t['out_path'] for t in tasks}
        for future in as_completed(futures):
            try: print(f"  [+] 已完成: {future.result()}")
            except Exception as exc: print(f'  [!] 任務 {futures[future]} 產生錯誤: {exc}')
    print("\n--- EV 圖片處理完成 ---")

def compose_all_lsf(image_dir: str, jobs: Optional[int]):
    print("\n--- 開始通用 LSF 合成 (合成所有圖層) ---")
    if not os.path.isdir(image_dir): print(f"[錯誤] 圖片目錄不存在: {image_dir}"); return
    print("[*] 正在載入所有 LSF 檔案..."); lm = LsfManager(); lsf_files_paths = glob.glob(os.path.join(image_dir, '**', '*.lsf'), recursive=True); [lm.load_lsf(lsf_path) for lsf_path in lsf_files_paths]
    output_dir = os.path.join(os.path.dirname(image_dir) or ".", "Output_All_Py"); os.makedirs(output_dir, exist_ok=True)
    print(f"[*] 輸出目錄: {output_dir}"); print(f"[*] 找到 {len(lm._lsf_lookup)} 個 .lsf 檔案，開始派發任務...")
    tasks = []
    for lsf_name, lsf_data in lm._lsf_lookup.items():
        all_layer_indices = list(range(lsf_data.header.layer_count)); all_layer_filenames = [layer.name for layer in lsf_data.layers_info]
        ordered_list = TableManager.order_layer(all_layer_indices, all_layer_filenames)
        output_path = os.path.join(output_dir, f"{lsf_name}.png")
        tasks.append({'lsf_data': lsf_data, 'layers': ordered_list, 'out_path': output_path})
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(process_and_save, t['lsf_data'], t['layers'], t['out_path']): t['out_path'] for t in tasks}
        for future in as_completed(futures):
            try: print(f"  [+] 已完成: {future.result()}")
            except Exception as exc: print(f'  [!] 任務 {futures[future]} 產生錯誤: {exc}')
    print("\n--- 通用 LSF 合成完成 ---")

# ===========================================================================
# 5. 命令列介面設定
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="一個用於處理 Escude 遊戲引擎資源的 Python 整合工具。", formatter_class=argparse.RawTextHelpFormatter)
    
    parser.add_argument("-d", nargs=1, metavar='<bin_dir>', help="[解包] 將指定目錄下的所有 .bin 檔案轉換為 .db 資料庫。\n         範例: -d \"C:\\path\\to\\your\\bin_files\"")
    parser.add_argument("-a", nargs=1, metavar='<LsfPath>', help="[通用合成] 強制合成指定目錄下所有LSF檔案(組合全部圖層)。")
    parser.add_argument("-ev", nargs=2, metavar=('<EvPath>', '<db_path>'), help="[合成] 合成事件 (EV) 圖片 (檔名會包含CG鑑賞ID)。")
    parser.add_argument("-s", nargs=2, metavar=('<StPath>', '<db_path>'), help="[合成] 合成角色立繪 (ST) 圖片 (檔名已優化，可搭配-b)。")
    
    parser.add_argument("-b", type=str, metavar='<modes>', 
                        help="[用於 -s] 指定臉紅模式 (可多選，用逗號分隔):\n"
                             "  0 = 無臉紅 (移除 p2)\n"
                             "  1 = 原始定義 (通常為 p2:1)\n"
                             "  2 = 臉紅B (使用 p2:2)\n"
                             "  範例: -b 0,2 (只生成無臉紅和臉紅B)")

    parser.add_argument("-export_lsf", nargs=1, metavar='<LsfPath>', help="[匯出] 匯出 LSF 圖層資訊到 CSV。")
    parser.add_argument("-j", "--jobs", type=int, metavar='<num>', help="[優化] 指定使用的 CPU 核心數量 (預設: 全部可用核心)。")
    
    args = parser.parse_args()
    
    if args.d:
        convert_bin_to_db(bin_dir=args.d[0])
    elif args.a:
        compose_all_lsf(image_dir=args.a[0], jobs=args.jobs)
    elif args.ev:
        compose_ev_images(image_dir=args.ev[0], db_path=args.ev[1], jobs=args.jobs)
    elif args.s:
        blush_mode_list = None
        if args.b:
            try:
                blush_mode_list = [int(x.strip()) for x in args.b.split(',')]
                if not all(mode in [0, 1, 2] for mode in blush_mode_list): raise ValueError("模式只能是 0, 1, 或 2。")
            except ValueError as e:
                print(f"[錯誤] -b 參數格式錯誤: {e}\n請使用逗號分隔的數字 (例如: -b 0,2)"); return
        compose_st_images(image_dir=args.s[0], db_path=args.s[1], blush_modes=blush_mode_list, jobs=args.jobs)
    elif args.export_lsf:
        export_lsf_to_csv(image_dir=args.export_lsf[0])
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

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
from concurrent.futures import ProcessPoolExecutor, as_completed # <--- 匯入多進程處理模組
import functools # <--- 用於輔助傳遞參數

# ===========================================================================
# 1. 資料結構定義 (與之前相同)
# ===========================================================================
# ... (為了簡潔，此處省略與上一版完全相同的 dataclass 定義) ...
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
# 2. 核心邏輯實作 (與之前相同)
# ===========================================================================
# ... (為了簡潔，此處省略 LsfManager, TableManager, ImageManager 等與上一版完全相同的 class) ...
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
        layer_info = lsf_data.layers_info[layer_index]; image_info = lsf_data.images[layer_index]
        if not image_info.file_path or not os.path.exists(image_info.file_path): return base_img
        with Image.open(image_info.file_path) as part_img:
            part_img = part_img.convert("RGBA"); base_np = np.array(base_img, dtype=np.float64) / 255.0; part_np = np.array(part_img, dtype=np.float64) / 255.0
            fg_layer = np.zeros_like(base_np); dx, dy = layer_info.rect.left, layer_info.rect.top; part_h, part_w = part_np.shape[:2]; base_h, base_w = base_np.shape[:2]
            x1, y1 = max(dx, 0), max(dy, 0); x2, y2 = min(dx + part_w, base_w), min(dy + part_h, base_h)
            part_x1, part_y1 = x1 - dx, y1 - dy; part_x2, part_y2 = x2 - dx, y2 - dy
            if x1 < x2 and y1 < y2: fg_layer[y1:y2, x1:x2] = part_np[part_y1:part_y2, part_x1:part_x2]
            bg_rgb, bg_a = base_np[:,:,:3], base_np[:,:,3:4]; fg_rgb, fg_a = fg_layer[:,:,:3], fg_layer[:,:,3:4]
            mode = layer_info.mode; out_a = fg_a + bg_a * (1.0 - fg_a); mask = out_a > 1e-6
            if mode == 3: out_rgb_blend = fg_rgb * bg_rgb
            elif mode == 10: out_rgb_blend = fg_rgb + bg_rgb
            else: out_rgb_blend = fg_rgb
            numerator = out_rgb_blend * fg_a + bg_rgb * bg_a * (1.0 - fg_a); out_rgb = np.zeros_like(bg_rgb)
            np.divide(numerator, out_a, where=mask, out=out_rgb)
            final_np_float = np.concatenate([out_rgb, out_a], axis=2); final_np_float = np.clip(final_np_float, 0.0, 1.0) 
            final_np_uint8 = (final_np_float * 255).round().astype(np.uint8)
            return Image.fromarray(final_np_uint8, 'RGBA')

# ===========================================================================
# 3. 任務函式 (給多進程使用)
# ===========================================================================

def process_and_save(lsf_data: LsfData, layer_indices: list, output_path: str):
    """
    單一圖片的合成與儲存任務 (無變化)。
    """
    header = lsf_data.header
    canvas = Image.new('RGBA', (header.width, header.height), (0, 0, 0, 0))
    for index in layer_indices:
        canvas = ImageManager.composite(canvas, lsf_data, index)
    canvas.save(output_path, 'PNG')
    # 在子進程中，我們回傳檔名以供主進程顯示
    return os.path.basename(output_path)

def process_st_record(st: StTable, lsf_manager: LsfManager, face_groups: dict, output_dir: str, blush_mode: Optional[int]):
    """
    處理單一 ST 記錄的完整任務，包含生成多種變化版本。
    """
    print(f"--- 開始處理 ST: {st.name} ---")
    lsf_data = lsf_manager.find_lsf_data_by_name(st.file)
    if not lsf_data: return f"[警告] {st.name}: 找不到 LSF 檔案 {st.file}.lsf"
    
    face_data = face_groups.get(st.face, Face())
    if not face_data.face_options: return f"[資訊] {st.name}: 無額外表情選項"

    generated_files = []
    for n, face_opt in enumerate(face_data.face_options):
        base_options = st.option + [face_opt]
        no_blush_options = [opt for opt in base_options if not opt.startswith('p2:')]
        blush2_options = no_blush_options + ['p2:2']
        all_variations = {
            0: {"suffix": "_b0", "options": no_blush_options},
            1: {"suffix": "_b1", "options": base_options},
            2: {"suffix": "_b2", "options": blush2_options}
        }
        variations_to_process = {}
        if blush_mode is not None:
            if blush_mode in all_variations: variations_to_process = {blush_mode: all_variations[blush_mode]}
        else:
            variations_to_process = {0: all_variations[0], 2: all_variations[2],}
            if any(opt.startswith('p2:1') for opt in base_options): variations_to_process[1] = all_variations[1]

        for _, var_data in variations_to_process.items():
            suffix, current_options = var_data["suffix"], var_data["options"]
            all_layers, all_filenames = [], []
            for opt in current_options:
                if not opt: continue
                indices = TableManager.parse_options(lsf_data, opt)
                all_layers.extend(indices)
                for i in indices: all_filenames.append(lsf_data.layers_info[i].name)
            if not all_layers: continue
            ordered_list = TableManager.order_layer(all_layers, all_filenames)
            output_path = os.path.join(output_dir, f"{st.name}_{n}{suffix}.png")
            
            # 實際執行合成
            process_and_save(lsf_data, ordered_list, output_path)
            generated_files.append(os.path.basename(output_path))
            
    return f"[成功] {st.name}: 已生成 {len(generated_files)} 個檔案"

# ===========================================================================
# 4. 主功能函式 (重構成使用多進程)
# ===========================================================================

def compose_st_images(image_dir: str, db_path: str, blush_mode: Optional[int] = None):
    # ... (前面的載入邏輯與上一版相同) ...
    title = "開始合成角色立繪 (ST) 圖片"
    if blush_mode is not None: title += f" (指定模式: {blush_mode})"
    else: title += " (自動生成多種臉紅變化)"
    print(f"\n--- {title} ---")
    if not os.path.isdir(image_dir) or not os.path.isfile(db_path): print(f"[錯誤] 請檢查提供的路徑是否有效。"); return
    
    print("[*] 正在載入所有 LSF 檔案...")
    lm = LsfManager(); [lm.load_lsf(p) for p in glob.glob(os.path.join(image_dir, '**', '*.lsf'), recursive=True)]
    
    print("[*] 正在讀取資料庫...")
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
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
    print(f"[*] 資料庫讀取完畢，共 {len(st_records)} 筆立繪記錄，{len(face_groups)} 個表情組。")
    
    output_dir = os.path.join(os.path.dirname(image_dir) or ".", "Output_ST_Py"); os.makedirs(output_dir, exist_ok=True)
    print(f"[*] 輸出目錄: {output_dir}")
    print("[*] 開始派發合成任務到 CPU 核心...")

    # <<<< 這裡是新的多進程處理核心 >>>>
    tasks_to_run = [rec for rec in st_records if rec.order != 0]
    with ProcessPoolExecutor() as executor:
        # 使用 functools.partial 來「預填」那些在所有任務中都相同的參數
        task_func = functools.partial(process_st_record, 
                                      lsf_manager=lm, 
                                      face_groups=face_groups, 
                                      output_dir=output_dir,
                                      blush_mode=blush_mode)
        
        # 將所有任務提交到進程池，並在完成時獲取結果
        results = list(executor.map(task_func, tasks_to_run))

    print("[*] 所有任務已完成。結果摘要：")
    for res in results:
        print(f"  - {res}")
        
    print("\n--- ST 圖片處理完成 ---")

# ... (其餘所有函式，包括 compose_ev_images, convert_bin_to_db, export_lsf_to_csv 都維持原樣) ...
def convert_bin_to_db(bin_dir: str):
    print("\n--- 開始轉換 .bin 到 .db ---")
    if not os.path.isdir(bin_dir): print(f"[錯誤] 目錄不存在: {bin_dir}"); return
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
def compose_ev_images(image_dir: str, db_path: str):
    print("\n--- 開始合成事件 (EV) 圖片 (多進程加速) ---")
    if not os.path.isdir(image_dir) or not os.path.isfile(db_path): print(f"[錯誤] 請檢查提供的路徑是否有效。"); return
    print("[*] 正在載入所有 LSF 檔案...")
    lm = LsfManager(); [lm.load_lsf(p) for p in glob.glob(os.path.join(image_dir, '**', '*.lsf'), recursive=True)]
    print("[*] 正在讀取資料庫...")
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    event_table_name = next((row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'イベント%';")), None)
    if not event_table_name: print("[錯誤] 在資料庫中找不到 'イベント' 資料表。"); conn.close(); return
    event_records = [EvTable(name=r['ID_44'], file=r['ファイル_44'], option=(r['オプション_44'] or "").split(' '), order=r['CG鑑賞_14']) for r in cursor.execute(f"SELECT * FROM [{event_table_name}]")]
    conn.close()
    output_dir = os.path.join(os.path.dirname(image_dir) or ".", "Output_EV_Py"); os.makedirs(output_dir, exist_ok=True)
    print(f"[*] 資料庫讀取完畢，共 {len(event_records)} 筆事件記錄。")
    print(f"[*] 輸出目錄: {output_dir}")
    print("[*] 開始派發合成任務到 CPU 核心...")
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
            layer_indices = TableManager.parse_options(lsf_data, opt)
            pending_list.extend(layer_indices)
            for i in layer_indices: pending_list_fn.append(lsf_data.layers_info[i].name)
        ordered_list = TableManager.order_layer(pending_list, pending_list_fn)
        if not ordered_list or ordered_list[0] != 0: ordered_list.insert(0, 0)
        tasks.append({'lsf_data': lsf_data, 'layers': ordered_list, 'out_path': output_path})
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_and_save, t['lsf_data'], t['layers'], t['out_path']) for t in tasks]
        for future in as_completed(futures):
            try:
                result = future.result()
                print(f"  [+] 已完成: {result}")
            except Exception as exc:
                print(f'  [!] 一個任務產生錯誤: {exc}')
    print("\n--- EV 圖片處理完成 ---")

# ===========================================================================
# 5. 命令列介面設定
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="一個用於處理 Escude 遊戲引擎資源的 Python 整合工具。", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-d", nargs=1, metavar='<bin_dir>', help="[解包] 將指定目錄下的所有 .bin 檔案轉換為 .db 資料庫。")
    parser.add_argument("-c", nargs=2, metavar=('<EvPath>', '<db_path>'), help="[合成] 合成事件 (EV) 圖片 (檔名會包含CG鑑賞ID)。")
    parser.add_argument("-s", nargs=2, metavar=('<StPath>', '<db_path>'), help="[合成] 合成角色立繪 (ST) 圖片 (可搭配-b選項)。")
    parser.add_argument("-b", type=int, choices=[0, 1, 2], metavar='<mode>', help="[用於 -s] 指定臉紅模式:\n  0=無臉紅, 1=原始定義, 2=臉紅B")
    parser.add_argument("-export_lsf", nargs=1, metavar='<LsfPath>', help="[匯出] 匯出 LSF 圖層資訊到 CSV。")
    args = parser.parse_args()
    if args.d:
        convert_bin_to_db(bin_dir=args.d[0])
    elif args.c:
        compose_ev_images(image_dir=args.c[0], db_path=args.c[1])
    elif args.s:
        compose_st_images(image_dir=args.s[0], db_path=args.s[1], blush_mode=args.b)
    elif args.export_lsf:
        export_lsf_to_csv(image_dir=args.export_lsf[0])
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
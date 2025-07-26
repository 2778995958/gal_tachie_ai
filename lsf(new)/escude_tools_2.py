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
# EscudeTools v6.0 - by Gemini
# 功能:
#   -d:         [解包] .bin -> .db (SQLite)
#   -db:        [合成] 根據 .db 檔案全自動合成所有圖片 (推薦)
#   -a:         [通用合成] 強制合成所有 .lsf 檔案的全部圖層
#   -s:         [合成] 合成角色立繪 (可搭配 -b 進行精確控制)
#   -b:         [用於-s] 指定臉紅模式 (可多選，用逗號分隔, e.g., -b 0,2)
#   -export_lsf:[匯出] .lsf -> .csv (用於分析)
#   -j:         [優化] 指定 CPU 核心數
# ===========================================================================
# 相依性: pip install Pillow numpy
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

# ===========================================================================
# 資料結構定義 (與之前相同)
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
# 核心邏輯實作 (與之前相同)
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
# 4. 功能函式
# ===========================================================================
def process_and_save(lsf_data: LsfData, layer_indices: list, output_path: str):
    # ... (此函式與上一版相同) ...
    header = lsf_data.header; canvas = Image.new('RGBA', (header.width, header.height), (0, 0, 0, 0))
    for index in layer_indices: canvas = ImageManager.composite(canvas, lsf_data, index)
    canvas.save(output_path, 'PNG'); return os.path.basename(output_path)

def process_st_record(st: StTable, lsf_manager: LsfManager, face_groups: dict, output_dir: str, blush_modes: Optional[List[int]]):
    # ... (此函式與上一版相同) ...
    print(f"--- 開始處理 ST: {st.name} ---")
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
            output_path = os.path.join(output_dir, f"{st.name}_{n}{suffix}.png")
            process_and_save(lsf_data, ordered_list, output_path); generated_files.append(os.path.basename(output_path))
    return f"[成功] {st.name}: 已生成 {len(generated_files)} 個檔案"

def compose_st_images(image_dir: str, db_path: str, blush_modes: Optional[List[int]] = None, jobs: Optional[int] = None):
    # <<<< 函式簽章已更新，blush_mode -> blush_modes (列表) >>>>
    title = "開始合成角色立繪 (ST) 圖片"
    if blush_modes is not None: title += f" (指定模式: {blush_modes})"
    else: title += " (自動生成多種臉紅變化)"
    # ... (其餘載入邏輯與上一版相同) ...
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

# ... (其餘功能函式與上一版相同，此處省略) ...
def convert_bin_to_db(bin_dir: str):
    # ... (內容省略)
    pass
def export_lsf_to_csv(image_dir: str):
    # ... (內容省略)
    pass
def compose_all_lsf(image_dir: str, jobs: Optional[int]):
    # ... (內容省略)
    pass
def compose_ev_images(image_dir: str, db_path: str, jobs: Optional[int]):
    # ... (內容省略)
    pass

# ===========================================================================
# 5. 命令列介面設定
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="一個用於處理 Escude 遊戲引擎資源的 Python 整合工具。", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-db", nargs=2, metavar=('<ImgPath>', '<db_path>'), help="[全自動合成] 根據 .db 檔案全自動合成所有圖片 (推薦)。")
    parser.add_argument("-a", nargs=1, metavar='<LsfPath>', help="[通用合成] 強制合成指定目錄下所有LSF檔案(組合全部圖層)。")
    parser.add_argument("-d", nargs=1, metavar='<bin_dir>', help="[解包] 將指定目錄下的所有 .bin 檔案轉換為 .db 資料庫。")
    parser.add_argument("-s", nargs=2, metavar=('<StPath>', '<db_path>'), help="[合成] 合成角色立繪 (ST) 圖片 (可搭配-b選項)。")
    
    # <<<< 更新 -b 命令的說明與行為 >>>>
    parser.add_argument("-b", type=str, metavar='<modes>', 
                        help="[用於 -s] 指定臉紅模式 (可多選，用逗號分隔):\n"
                             "  0 = 無臉紅 (移除 p2)\n"
                             "  1 = 原始定義 (通常為 p2:1)\n"
                             "  2 = 臉紅B (使用 p2:2)\n"
                             "  範例: -b 0,2 (只生成無臉紅和臉紅B)")

    parser.add_argument("-export_lsf", nargs=1, metavar='<LsfPath>', help="[匯出] 匯出 LSF 圖層資訊到 CSV。")
    parser.add_argument("-j", "--jobs", type=int, metavar='<num>', help="[優化] 指定使用的 CPU 核心數量 (預設: 全部可用核心)。")
    
    args = parser.parse_args()
    
    # <<<< 更新 -s 命令的參數解析邏輯 >>>>
    if args.s:
        blush_mode_list = None
        if args.b:
            try:
                # 解析用逗號分隔的字串
                blush_mode_list = [int(x.strip()) for x in args.b.split(',')]
                # 驗證每個數字是否合法
                if not all(mode in [0, 1, 2] for mode in blush_mode_list):
                    raise ValueError("模式只能是 0, 1, 或 2。")
            except ValueError as e:
                print(f"[錯誤] -b 參數格式錯誤: {e}\n請使用逗號分隔的數字 (例如: -b 0,2)")
                return
        
        compose_st_images(image_dir=args.s[0], db_path=args.s[1], blush_modes=blush_mode_list, jobs=args.jobs)

    elif args.db:
        compose_from_database(image_dir=args.db[0], db_path=args.db[1], jobs=args.jobs)
    elif args.a:
        compose_all_lsf(image_dir=args.a[0], jobs=args.jobs)
    elif args.d:
        convert_bin_to_db(bin_dir=args.d[0])
    elif args.export_lsf:
        export_lsf_to_csv(image_dir=args.export_lsf[0])
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

# final_assembler.py (v3.2 - Strict Body/Face Naming Edition)
# 修正版：完美支援「身_序號_臉」與單純「身_序號」的動態命名邏輯。

import struct
import os
import sys
import glob
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    print("錯誤：Pillow 函式庫未安裝。請執行 'pip install Pillow'")
    sys.exit(1)

# --- 結構定義 ---
@dataclass
class SPMHeader:
    signature: bytes; entry_count: int
@dataclass
class SPMEntryHeader:
    entry_count: int; width: int; height: int; base_x: int; base_y: int;
    base_cx: int; base_cy: int; unknown1: int; unknown2: int;
    unknown3: int; unknown4: int
@dataclass
class SPMEntry:
    index: int; dst_x: int; dst_y: int; dst_cx: int; dst_cy: int;
    width: int; height: int; src_x: int; src_y: int; src_cx: int;
    src_cy: int; unknown1: int; unknown2: int; unknown3: int
@dataclass
class SPMData:
    header: SPMHeader
    image_groups: List[Tuple[SPMEntryHeader, List[SPMEntry]]] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)

# --- 檔案解析邏輯 ---
def parse_spm(file_path: str) -> SPMData:
    with open(file_path, 'rb') as f:
        stream = BytesIO(f.read())
    sig = stream.read(13)
    if sig != b'SPM VER-2.00\x00':
        raise ValueError(f"檔案 {os.path.basename(file_path)} 不是有效的 SPM 格式。")
    (entry_count,) = struct.unpack('<I', stream.read(4))
    header = SPMHeader(signature=sig, entry_count=entry_count)
    spm_data = SPMData(header=header)
    for _ in range(header.entry_count):
        buffer = stream.read(44)
        if len(buffer) < 44: raise IOError("檔案讀取錯誤：SPMEntryHeader 資料不足。")
        entry_header_data = struct.unpack('<IIIiiiiIIII', buffer)
        entry_header = SPMEntryHeader(*entry_header_data)
        entries = []
        for _ in range(entry_header.entry_count):
            buffer = stream.read(56)
            if len(buffer) < 56: raise IOError("檔案讀取錯誤：SPMEntry 資料不足。")
            entry_data = struct.unpack('<IiiiiIIiiiiIII', buffer)
            entries.append(SPMEntry(*entry_data))
        spm_data.image_groups.append((entry_header, entries))
    (filename_count,) = struct.unpack('<I', stream.read(4))
    for _ in range(filename_count):
        char_list = []
        while True:
            char = stream.read(1)
            if char == b'' or char == b'\x00': break
            char_list.append(char)
        spm_data.filenames.append(b''.join(char_list).decode('sjis', 'ignore').strip())
    return spm_data

# --- 圖片合併與動態命名邏輯 ---
def merge_spm_to_image(spm_data: SPMData, spm_filename: str, images_dir: str, output_dir: str, file_lookup: Dict[str, str]):
    base_filename = os.path.splitext(spm_filename)[0]
    
    for i, (entry_header, entries) in enumerate(spm_data.image_groups):
        print(f"  > 正在合成圖片組 #{i}...")
        final_image = Image.new('RGBA', (entry_header.width, entry_header.height), (0, 0, 0, 0))
        
        # 用來紀錄這一組裡面使用到的所有圖片主檔名（不含副檔名）
        used_filenames = []
        
        for entry in entries:
            try:
                if entry.index >= len(spm_data.filenames): continue
                spm_img_name = spm_data.filenames[entry.index]
                real_filename = file_lookup.get(spm_img_name.lower())
                if not real_filename: continue
                
                # 擷取主檔名（例如 'mi_00101as'）
                img_base_name = os.path.splitext(real_filename)[0]
                if img_base_name not in used_filenames:
                    used_filenames.append(img_base_name)
                
                full_path = os.path.join(images_dir, real_filename)
                
                with Image.open(full_path) as part_img:
                    part_img = part_img.convert('RGBA')
                    
                    if entry.width == 0 or entry.height == 0: continue
                        
                    box = (entry.src_x, entry.src_y, entry.src_x + entry.width, entry.src_y + entry.height)
                    piece = part_img.crop(box)
                    
                    # 最終位置 = 碎片的絕對位置 - 攝影機的絕對位置
                    final_dst_x = entry.dst_x - entry_header.base_x
                    final_dst_y = entry.dst_y - entry_header.base_y
                    
                    temp_layer = Image.new('RGBA', final_image.size, (0, 0, 0, 0))
                    temp_layer.paste(piece, (final_dst_x, final_dst_y))
                    final_image = Image.alpha_composite(final_image, temp_layer)

            except Exception as e:
                print(f"    [錯誤] 處理碎片 {spm_img_name} 時發生錯誤: {e}")
                
        # <<< 動態檔名判定區塊 >>>
        if len(used_filenames) >= 2:
            # 情況 1：同時有身與臉
            body_name = used_filenames[0]  # 第一個為身
            face_name = used_filenames[1]  # 第二個為臉
            output_name = f"{body_name}_{i:02d}_{face_name}.png"
        elif len(used_filenames) == 1:
            # 情況 2：若是身，就生成 身_序號.png (例如: mi_00101as_00.png)
            body_name = used_filenames[0]
            output_name = f"{body_name}_{i:02d}.png"
        else:
            # 安全回溯機制
            output_name = f"{base_filename}_{i:02d}.png"
            
        output_filename = os.path.join(output_dir, output_name)
        final_image.save(output_filename, 'PNG')
        print(f"    => 成功儲存至: {output_filename}")

# --- 主程式 ---
def main():
    IMAGES_FOLDER = 'images'
    OUTPUT_FOLDER = 'output'
    
    print("--- SPM 最終合成腳本 (v3.2 - 條件命名版) ---")

    if not os.path.isdir(IMAGES_FOLDER):
        print(f"錯誤：找不到圖片來源資料夾 '{IMAGES_FOLDER}'。")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    try:
        image_files_on_disk = os.listdir(IMAGES_FOLDER)
        file_lookup = {f.lower(): f for f in image_files_on_disk}
    except Exception as e:
        print(f"錯誤：無法讀取 '{IMAGES_FOLDER}' 資料夾內容: {e}")
        return

    spm_files = glob.glob('*.spm')
    if not spm_files:
        print("在目前目錄下找不到任何 .spm 檔案。")
        return
    
    print(f"\n找到了 {len(spm_files)} 個 .spm 檔案，準備開始批次處理...\n")

    for spm_path in spm_files:
        print(f"--- 正在處理檔案: {spm_path} ---")
        try:
            spm_data = parse_spm(spm_path)
            merge_spm_to_image(spm_data, os.path.basename(spm_path), IMAGES_FOLDER, OUTPUT_FOLDER, file_lookup)
        except Exception as e:
            print(f"處理 {spm_path} 時發生嚴重錯誤，已跳過此檔案: {e}\n")
    
    print("\n--- 所有任務處理完畢 ---")

if __name__ == "__main__":
    main()
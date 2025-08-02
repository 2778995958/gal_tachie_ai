# -*- coding: utf-8 -*-
import argparse
import os
import glob
import struct
import csv
from dataclasses import dataclass, field
from typing import List

# ===========================================================================
# 1. 資料結構定義 (Data Structures)
# 這些是解析 LSF 檔案所需的結構，我們從原腳本中保留下來。
# ===========================================================================
@dataclass
class LsfFileHeader:
    """LSF 檔案的檔頭資訊"""
    revision: int = 0
    bg: int = 0
    id: int = 0
    layer_count: int = 0
    width: int = 0
    height: int = 0
    bx: int = 0
    by: int = 0

@dataclass
class Rect:
    """定義一個矩形區域"""
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

@dataclass
class LsfLayerInfo:
    """LSF 檔案中單一圖層的詳細資訊"""
    name: str = ""
    text: str = ""
    rect: Rect = field(default_factory=Rect)
    cx: int = 0
    cy: int = 0
    index: int = 0
    state: int = 0
    mode: int = 0
    opacity: int = 0
    fill: int = 0
    value: int = 0
    skip: bool = False

@dataclass
class LsfImageData:
    """LSF 圖層對應的圖片資訊 (在此腳本中主要用於結構完整性)"""
    file_path: str = ""
    width: int = 0
    height: int = 0

@dataclass
class LsfData:
    """代表一個完整的 LSF 檔案的資料集合"""
    filepath: str
    lsf_name: str
    header: LsfFileHeader = field(default_factory=LsfFileHeader)
    layers_info: List[LsfLayerInfo] = field(default_factory=list)
    images: List[LsfImageData] = field(default_factory=list)

# ===========================================================================
# 2. 核心邏輯實作 (Core Logic)
# 這裡是解析 LSF 檔案的核心類別和函式。
# ===========================================================================

def decode_str(b: bytes) -> str:
    """
    將 CP932 (Shift-JIS) 編碼的位元組解碼成字串。
    """
    return b.decode('cp932', errors='ignore').strip('\x00')

class LsfManager:
    """
    管理 LSF 檔案的讀取和解析。
    """
    def __init__(self):
        self._lsf_lookup = {}

    def load_lsf(self, path: str) -> 'LsfData':
        """
        從指定路徑讀取並解析一個 .lsf 檔案。
        """
        if not os.path.isfile(path):
            return None
        
        lsf_name = os.path.splitext(os.path.basename(path))[0].lower()
        lsf_dir = os.path.dirname(path)

        try:
            with open(path, 'rb') as f:
                header_bytes = f.read(28)
                if len(header_bytes) < 28:
                    return None
                
                sig, rev, bg, id, l_count, w, h, bx, by = struct.unpack('<IHHHHiiii', header_bytes)
                if sig != 0x46534C:  # 'LSF' in little-endian
                    return None
                
                header = LsfFileHeader(rev, bg, id, l_count, w, h, bx, by)
                lsf_data = LsfData(filepath=path, lsf_name=lsf_name, header=header)

                for _ in range(header.layer_count):
                    layer_bytes = f.read(164)
                    if len(layer_bytes) < 164:
                        continue
                    
                    name_b, text_b, r_l, r_t, r_r, r_b, cx, cy, idx, state, mode, op, fill, val = struct.unpack('<64s64siiiiiiBBBBII', layer_bytes)
                    
                    layer_info = LsfLayerInfo(
                        name=decode_str(name_b),
                        text=decode_str(text_b),
                        rect=Rect(r_l, r_t, r_r, r_b),
                        cx=cx, cy=cy, index=idx, state=state,
                        mode=mode, opacity=op, fill=fill, value=val
                    )
                    
                    if name_b.startswith(b'\x00ul\x00'):
                        layer_info.skip = True
                    
                    lsf_data.layers_info.append(layer_info)
                    
                    # 即使我們不處理圖片，也保持結構一致
                    img = LsfImageData()
                    if not layer_info.skip:
                        img.file_path = os.path.join(lsf_dir, layer_info.name + ".png")
                    lsf_data.images.append(img)

            self._lsf_lookup[lsf_name] = lsf_data
            return lsf_data
        except Exception as e:
            print(f"[錯誤] 讀取檔案 {path} 時發生問題: {e}")
            return None

# ===========================================================================
# 3. 主要功能函式 (Main Function)
# ===========================================================================

def export_lsf_to_csv_combined(image_dir: str):
    """
    掃描指定目錄下的所有 LSF 檔案，並將其圖層資訊匯出到一個合併的 CSV 檔案中。
    """
    print("\n--- 開始匯出 LSF 圖層資訊到單一 CSV ---")
    if not os.path.isdir(image_dir):
        print(f"[錯誤] LSF 檔案目錄不存在: {image_dir}")
        return

    lm = LsfManager()
    
    # 遞迴搜尋所有 .lsf 檔案
    lsf_files = glob.glob(os.path.join(image_dir, '**', '*.lsf'), recursive=True)
    if not lsf_files:
        print(f"[資訊] 在 '{image_dir}' 中找不到任何 .lsf 檔案。")
        return

    # 建立輸出目錄和檔案路徑
    output_dir = os.path.join(os.path.dirname(image_dir) or ".", "LSF_Export_Py")
    os.makedirs(output_dir, exist_ok=True)
    csv_filepath = os.path.join(output_dir, "lsf_export_all.csv")
    print(f"[*] 將所有資訊匯出到單一檔案: {csv_filepath}")

    # 定義 CSV 檔頭，新增一欄來標示來源檔案
    header = [
        'Source_LSF_File', 'Layer_Index', 'PNG_Filename', 'X_Offset', 'Y_Offset', 
        'Width', 'Height', 'Blend_Mode', 'Opacity', 'Game_Logic_Index', 'Game_Logic_State'
    ]

    # 開啟 CSV 檔案並寫入所有資料
    try:
        with open(csv_filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(header) # 先寫入檔頭

            total_layers_exported = 0
            # 遍歷所有找到的 LSF 檔案
            for lsf_path in lsf_files:
                lsf_data = lm.load_lsf(lsf_path)
                if not lsf_data:
                    print(f"  [警告] 無法載入或解析 LSF 檔案: {os.path.basename(lsf_path)}")
                    continue

                # 遍歷該檔案中的每一個圖層
                for i, layer in enumerate(lsf_data.layers_info):
                    row_data = [
                        lsf_data.lsf_name,  # 來源 LSF 檔案名
                        i,                  # 圖層在檔案內的索引
                        layer.name,         # 圖層對應的 PNG 檔名
                        layer.rect.left,
                        layer.rect.top,
                        layer.rect.right - layer.rect.left, # 計算寬度
                        layer.rect.bottom - layer.rect.top, # 計算高度
                        layer.mode,
                        layer.opacity,
                        layer.index,
                        layer.state
                    ]
                    writer.writerow(row_data)
                
                print(f"  [處理完成] 已從 {os.path.basename(lsf_path)} 匯出 {len(lsf_data.layers_info)} 個圖層。")
                total_layers_exported += len(lsf_data.layers_info)
        
        print(f"\n[成功] 匯出完成！總共從 {len(lsf_files)} 個 LSF 檔案匯出了 {total_layers_exported} 個圖層記錄。")

    except IOError as e:
        print(f"[嚴重錯誤] 無法寫入檔案 {csv_filepath}。請檢查權限或磁碟空間。錯誤訊息: {e}")

    print("--- LSF 匯出任務結束 ---")


# ===========================================================================
# 4. 命令列介面設定 (Command-Line Interface)
# ===========================================================================
def main():
    """
    設定並解析命令列參數。
    """
    parser = argparse.ArgumentParser(
        description="一個將 LSF 檔案圖層資訊匯出到單一 CSV 檔案的工具。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "lsf_dir", 
        metavar='<LsfPath>', 
        help="包含 .lsf 檔案的來源目錄路徑。\n腳本會遞迴搜尋此目錄下的所有 .lsf 檔案。"
    )
    
    args = parser.parse_args()
    
    export_lsf_to_csv_combined(image_dir=args.lsf_dir)


if __name__ == '__main__':
    main()
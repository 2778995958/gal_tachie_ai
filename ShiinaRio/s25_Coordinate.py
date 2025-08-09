import sys
import os
import struct
import csv
import glob

class S25CoordinateExtractor:
    """
    一個專門從 S25 檔案中提取畫格座標和尺寸資訊的類別。
    它會讀取檔案標頭和每個畫格的元數據，但會跳過耗時的圖片像素解碼。
    """
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = open(filepath, 'rb')
        # 提取檔案的基本名稱，例如 "file.s25" -> "file"
        self.base_name = os.path.splitext(os.path.basename(filepath))[0]

    def __del__(self):
        """確保在物件被銷毀時關閉檔案。"""
        if hasattr(self, 'file') and self.file:
            self.file.close()

    def extract_metadata(self):
        """
        主函式，用於從 S25 檔案中提取所有畫格的元數據 (座標、尺寸等)。
        """
        print(f"--- 開始處理檔案: {os.path.basename(self.filepath)} ---")
        
        # 1. 驗證檔案簽名
        sig = self.file.read(4)
        if sig != b'S25\0':
            print("  錯誤: 檔案簽名不符，跳過此檔案。")
            return []

        try:
            # 2. 讀取畫格總數和每個畫格的偏移位置
            frame_count, = struct.unpack('<i', self.file.read(4))
            
            # 進行一個合理的檢查，避免讀取到異常大的畫格數量
            if not (0 <= frame_count < 10000):
                print(f"  警告: 偵測到異常的畫格數量 ({frame_count})，跳過此檔案。")
                return []
                
            frame_offsets = list(struct.unpack(f'<{frame_count}I', self.file.read(4 * frame_count)))
            print(f"  找到 {len(frame_offsets)} 個畫格偏移位置。")

        except struct.error:
            print("  錯誤: 讀取檔案標頭失敗，檔案可能已損壞。")
            return []

        all_frames_metadata = []
        # 3. 遍歷所有畫格偏移，提取元數據
        for i, offset in enumerate(frame_offsets):
            if offset == 0:  # 偏移為 0 通常表示一個空的或無效的畫格
                continue
            
            try:
                metadata = self._extract_frame_header(i, offset)
                all_frames_metadata.append(metadata)
            except Exception as e:
                print(f"    錯誤: 提取畫格 {i} 的元數據失敗: {e}")
        
        print(f"--- 完成檔案: {os.path.basename(self.filepath)} ---")
        return all_frames_metadata

    def _extract_frame_header(self, frame_index, frame_offset):
        """
        跳轉到指定的畫格位置，只讀取前 20 個位元組的標頭資訊。
        這個標頭包含了我們需要的所有座標和尺寸數據。
        """
        self.file.seek(frame_offset)
        
        # S25 畫格標頭結構:
        # - Width (4 bytes, unsigned int)
        # - Height (4 bytes, unsigned int)
        # - OffsetX (4 bytes, signed int)
        # - OffsetY (4 bytes, signed int)
        # - Flags (4 bytes, unsigned int)
        width, height, offset_x, offset_y, _ = struct.unpack('<IIiiI', self.file.read(20))
        
        # 產生一個與 CSV 欄位對應的字典
        metadata = {
            'frame_index': f"{self.base_name}_{frame_index}",
            'width': width,
            'height': height,
            'offset_x': offset_x,
            'offset_y': offset_y
        }
        return metadata

def write_master_csv(csv_path, metadata_list):
    """將收集到的所有元數據寫入一個 CSV 檔案。"""
    if not metadata_list:
        print("沒有找到任何可寫入 CSV 的資訊。")
        return
        
    print(f"\n正在寫入主座標檔: {csv_path}")
    fieldnames = ['frame_index', 'width', 'height', 'offset_x', 'offset_y']
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metadata_list)
        print("CSV 檔案寫入完成。")
    except IOError as e:
        print(f"錯誤：無法寫入 CSV 檔案 '{csv_path}': {e}")


def batch_process_all(s25_input_dir, csv_output_path):
    """
    批次處理指定資料夾中所有的 S25 檔案。
    """
    print("=== 進入批次處理模式 ===")
    
    # 搜尋所有 .S25 和 .s25 檔案
    s25_files = glob.glob(os.path.join(s25_input_dir, '*.S25'))
    s25_files.extend(glob.glob(os.path.join(s25_input_dir, '*.s25')))
    
    if not s25_files:
        print(f"在 '{s25_input_dir}' 資料夾中沒有找到任何 .S25 檔案。")
        return
        
    master_metadata_list = []
    # 使用 set 去除重複的檔案路徑，然後排序以確保處理順序一致
    for s25_file_path in sorted(list(set(s25_files))):
        extractor = S25CoordinateExtractor(s25_file_path)
        file_metadata = extractor.extract_metadata()
        if file_metadata:
            master_metadata_list.extend(file_metadata)
            
    write_master_csv(csv_output_path, master_metadata_list)

def main():
    """程式主進入點。"""
    try:
        # 將資料夾設定在腳本所在的目錄下
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # 如果在互動式環境中執行，__file__ 可能不存在
        script_dir = os.getcwd()

    s25_input_dir = os.path.join(script_dir, 's25')
    csv_output_path = os.path.join(script_dir, 'coordinates.csv')
    
    # 檢查輸入資料夾是否存在
    if not os.path.isdir(s25_input_dir):
        print(f"錯誤: 輸入資料夾 '{s25_input_dir}' 不存在！")
        print("請在腳本所在目錄下建立一個名為 's25' 的資料夾，並將 S25 檔案放入其中。")
        sys.exit(1)
    
    batch_process_all(s25_input_dir, csv_output_path)
    
    print("\n所有處理已完成！")

if __name__ == "__main__":
    main()
import os
import pathlib
import struct

def get_kaguya_xy(root_folder):
    """
    主函數，掃描指定資料夾，解析 .alp 和 .anm 檔案並產生座標文字檔。
    """
    print("\nScanning for .alp and .anm files...")
    all_files = pathlib.Path(root_folder).rglob("*")
    target_files = [f for f in all_files if f.is_file() and f.suffix.lower() in ['.alp', '.anm']]

    if not target_files:
        print("No .alp or .anm files found in the specified path.")
        return

    xylist_human = []
    xylist_auto = []

    print("-" * 20)
    for file_path in target_files:
        print(f"Processing {file_path.name}...")
        try:
            if file_path.suffix.lower() == '.alp':
                human, auto = process_alp_file(file_path, root_folder)
            elif file_path.suffix.lower() == '.anm':
                human, auto = process_anm_file(file_path, root_folder)
            else:
                continue
            
            xylist_human.extend(human)
            xylist_auto.extend(auto)

        except Exception as e:
            print(f"  ERROR processing {file_path.name}: {e}")
    print("-" * 20)

    try:
        output_filename = "Kaguya_XY_Offset_FINAL.txt"
        auto_output_filename = "Kaguya_XY_Offset_FINAL(Auto).txt"

        with open(output_filename, "w", encoding="utf-8") as txt:
            txt.write("\n".join(xylist_human) + "\n")

        with open(auto_output_filename, "w", encoding="utf-8") as txt:
            txt.write("\n".join(xylist_auto) + "\n")

        print(f"\n✅✅✅ Success! The definitive coordinate files have been generated:")
        print(f"   - {output_filename}")
        print(f"   - {auto_output_filename}")

    except Exception as e:
        print(f"\nError writing output files: {e}")

def process_alp_file(file_path, root_path):
    """處理單一 .alp 檔案"""
    with open(file_path, "rb") as f:
        f.seek(4)
        pos_x = int.from_bytes(f.read(2), byteorder="little", signed=True)
        f.seek(8)
        pos_y = int.from_bytes(f.read(2), byteorder="little", signed=True)

    relative_path = os.path.relpath(file_path, root_path)
    posix_path = pathlib.Path(relative_path).as_posix()
    human = f"{posix_path} : {pos_x}, {pos_y}"
    auto = f"{file_path.stem},{pos_x},{pos_y}"
    return [human], [auto]

def process_anm_file(file_path, root_path):
    """
    處理 ANM 檔案，包含針對特殊檔案類型的判斷邏輯。
    """
    human_list = []
    auto_list = []

    with open(file_path, "rb") as f:
        signature = f.read(4)
        if signature not in [b'AN00', b'AN10', b'AN20', b'AN21', b'PL00', b'PL10']:
            return [], []

        # 步驟 1: 跳過複雜的標頭 (Header)
        if signature in [b'AN20', b'AN21']:
            table_count = struct.unpack('<H', f.read(2))[0]
            f.seek(2, 1)

            for _ in range(table_count):
                command = f.read(1)[0]
                if command == 1: f.seek(8, 1)
                else: f.seek(4, 1)
            
            count2 = struct.unpack('<H', f.read(2))[0]
            if count2 == 1: f.seek(8, 1)

            if signature == b'AN21':
                if f.read(7) != b'[PIC]10':
                    return [], []

        # 步驟 2: 讀取全局資訊
        if signature in [b'AN00', b'AN10']:
            f.seek(20)
            table_count = struct.unpack('<h', f.read(2))[0]
            f.seek(table_count * 4 + 2, 1)
        
        frame_count = struct.unpack('<h', f.read(2))[0]
        if frame_count <= 0: return [], []

        global_l, global_t, global_w, global_h = struct.unpack('<iiii', f.read(16))
        
        # 【關鍵】檢查是否為特殊處理的檔案類型
        is_special_file = '乳' in file_path.name or '胸' in file_path.name

        # 步驟 3: 循環讀取每一影格的資訊
        for i in range(frame_count):
            rect_size = 20 if signature != b'AN00' else 16
            anm_rect_bytes = f.read(rect_size)
            if len(anm_rect_bytes) < rect_size: break

            if rect_size == 20:
                frame_l, frame_t, frame_w, frame_h, frame_bpp = struct.unpack('<iiiii', anm_rect_bytes)
            else:
                frame_l, frame_t, frame_w, frame_h = struct.unpack('<iiii', anm_rect_bytes)
                frame_bpp = 4

            # 【關鍵】根據檔案類型使用不同的座標公式
            if is_special_file and signature in [b'AN21', b'PL10']:
                # 特殊檔案：直接使用全局座標
                final_x = global_l
                final_y = global_t
            else:
                # 一般檔案：使用全局座標 + 影格座標
                final_x = global_l + frame_l
                final_y = global_t + frame_t

            relative_path = os.path.relpath(file_path, root_path)
            posix_path = pathlib.Path(relative_path).as_posix()
            human_list.append(f"{posix_path}#{i:02d} : {final_x}, {final_y}")
            auto_list.append(f"{file_path.stem}#{i:02d},{final_x},{final_y}")

            pixel_data_size = frame_w * frame_h * frame_bpp
            f.seek(pixel_data_size, 1)
            
            if signature in [b'AN21', b'PL10']:
                break

    return human_list, auto_list


if __name__ == "__main__":
    while True:
        target_folder = input('Write your target folder path : ').replace("'", "").replace('"', "")
        if os.path.isdir(target_folder):
            get_kaguya_xy(target_folder)
            break
        else:
            print("Path not exist or is not a directory. Please try again.")

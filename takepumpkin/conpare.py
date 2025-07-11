import os
import shutil
import hashlib

def calculate_crc(file_path):
    """計算檔案的 CRC32 值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def compare_and_move(folder1, folder2):
    same_folder1 = os.path.join(folder1, 'same')
    same_folder2 = os.path.join(folder2, 'same')
    
    os.makedirs(same_folder1, exist_ok=True)
    os.makedirs(same_folder2, exist_ok=True)

    log = []

    for file in os.listdir(folder1):
        file_path1 = os.path.join(folder1, file)
        if os.path.isfile(file_path1):
            crc1 = calculate_crc(file_path1)
            
            file_path2 = os.path.join(folder2, file)
            if os.path.isfile(file_path2):
                crc2 = calculate_crc(file_path2)
                
                if crc1 == crc2:
                    # 移動檔案
                    shutil.move(file_path1, same_folder1)
                    shutil.move(file_path2, same_folder2)
                    log.append(f"Moved: {file} (CRC: {crc1})")

    # 寫入日誌
    with open('log.txt', 'w') as log_file:
        for entry in log:
            log_file.write(entry + '\n')

# 使用範例
folder1 = '5HOMESTAY a la mode n'
folder2 = '5HOMESTAY a la mode o'
compare_and_move(folder1, folder2)
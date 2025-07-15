import os
import struct
import csv

def extract_and_write_to_txt(filepath, txt_writer):
    """
    Opens an HG3 file, reads the 'stdinfo' blocks, and writes the data to the provided writer.
    """
    print(f"Processing: {os.path.basename(filepath)}...")
    
    try:
        with open(filepath, 'rb') as f:
            sig = f.read(4)
            if sig != b'HG-3':
                print(f" -> Skipped: {os.path.basename(filepath)} is not a valid HG-3 file.")
                return

            f.seek(20)
            stdinfo_count = 0
            
            while True:
                tag_data = f.read(16)
                if not tag_data:
                    break

                tag_sig_bytes, offset_next, length = struct.unpack('<8sII', tag_data)

                if tag_sig_bytes.startswith(b'stdinfo'):
                    stdinfo_count += 1
                    info_data = f.read(40)
                    if len(info_data) < 40:
                        continue

                    (
                        width, height, depth, 
                        offset_x, offset_y, 
                        total_width, total_height,
                        unknown1, unknown2, unknown3
                    ) = struct.unpack('<IIIIIIIIII', info_data)

                    row = [
                        os.path.basename(filepath),
                        stdinfo_count,
                        width, height, offset_x, offset_y,
                        total_width, total_height, depth,
                        unknown1, unknown2, unknown3
                    ]
                    
                    txt_writer.writerow(row)
                
                else:
                    if length > 0 and length < 10000000:
                         f.seek(length, 1)

    except Exception as e:
        print(f" -> An error occurred while processing {os.path.basename(filepath)}: {e}")

if __name__ == '__main__':
    IMAGES_DIR = 'hg3'
    # 【變更點】: 輸出檔名改為 'hg3_coordinates.txt'
    OUTPUT_TXT = 'hg3_coordinates.txt'

    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
        print(f"Created directory '{IMAGES_DIR}'. Please place your .hg3 files inside it.")
        exit()

    hg3_files = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith('.hg3')]

    if not hg3_files:
        print(f"No .hg3 files found in the '{IMAGES_DIR}' directory.")
        exit()

    print(f"Found {len(hg3_files)} .hg3 files. Processing will start now.")
    print(f"Output will be saved to '{OUTPUT_TXT}'")

    try:
        # 使用我們推薦的 'utf-8-sig' (UTF-8 with BOM) 編碼
        with open(OUTPUT_TXT, 'w', newline='', encoding='utf-8-sig') as txtfile:
            # 維持使用 Tab ('\t') 作為分隔符
            writer = csv.writer(txtfile, delimiter='\t')

            headers = [
                'FileName', 'StdinfoIndex', 'FragmentWidth', 'FragmentHeight', 
                'OffsetX', 'OffsetY', 'CanvasWidth', 'CanvasHeight', 'ColorDepth',
                'Unknown1', 'Unknown2', 'Unknown3'
            ]
            writer.writerow(headers)

            for filename in hg3_files:
                filepath = os.path.join(IMAGES_DIR, filename)
                extract_and_write_to_txt(filepath, writer)
        
        print(f"\nProcessing complete! All coordinate data has been saved to '{OUTPUT_TXT}'.")
        print("File format: UTF-8 with BOM, Tab-separated.")

    except IOError as e:
        print(f"\nError: Could not write to file '{OUTPUT_TXT}'. Please check permissions or if the file is in use. Message: {e}")
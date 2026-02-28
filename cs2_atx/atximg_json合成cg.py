import os
import json
import numpy as np
from PIL import Image

def composite(base_np, part_img, pos):
    part_np = np.array(part_img, dtype=np.uint8)
    ph, pw = part_np.shape[:2]
    bh, bw = base_np.shape[:2]
    x, y = pos
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + pw, bw), min(y + ph, bh)
    if x1 >= x2 or y1 >= y2:
        return base_np
    px1, py1 = x1 - x, y1 - y
    px2, py2 = x2 - x, y2 - y
    base_r = base_np[y1:y2, x1:x2]
    part_r = part_np[py1:py2, px1:px2]
    a = part_r[:, :, 3:4] / 255.0
    base_np[y1:y2, x1:x2, :3] = (part_r[:, :, :3] * a + base_r[:, :, :3] * (1 - a)).astype(np.uint8)
    base_np[y1:y2, x1:x2, 3] = (part_r[:, :, 3] + base_r[:, :, 3] * (1 - a[:, :, 0])).astype(np.uint8)
    return base_np

def parse_cglist(path):
    """解析 cglist.lst，回傳 [(entry_line, name, values), ...]"""
    entries = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('@') or line.startswith('['):
                continue
            parts = line.split(',')
            name = parts[0]
            values = parts[1:]
            entries.append((line, name, values))
    return entries

def load_folder_data(folder_path):
    """載入資料夾的 info.json 和 offset.json，回傳 (group_map, offset_map, base_key)
    group_map: {group_num: {item: filename}}
    """
    info_path = os.path.join(folder_path, "info.json")
    offset_path = os.path.join(folder_path, "offset.json")
    if not os.path.isfile(info_path) or not os.path.isfile(offset_path):
        return None, None, None

    with open(info_path, 'r', encoding='utf-8-sig') as f:
        info_data = json.load(f)
    with open(offset_path, 'r', encoding='utf-8-sig') as f:
        offset_data = json.load(f)

    offset_map = {item['Key']: tuple(item['Value']) for item in offset_data}

    # 找底圖 (offset 0,0)
    base_key = None
    for k, v in offset_map.items():
        if v == (0, 0):
            base_key = k
            break

    # 建立 group_map: {group_num_str: {item_str: filename}}
    group_map = {}
    for item in info_data:
        key = item['Key']  # e.g. "1_5@0"
        val = item['Value']  # e.g. "ev02l_05"
        if '@' in key and '_' in key.split('@')[0]:
            prefix = key.split('@')[0]  # "1_5"
            g, i = prefix.split('_', 1)  # group="1", item="5"
            group_map.setdefault(int(g), {})[i] = val

    return group_map, offset_map, base_key

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cglist_path = os.path.join(script_dir, "cglist.lst")
    out_dir = os.path.join(script_dir, "out")
    os.makedirs(out_dir, exist_ok=True)

    entries = parse_cglist(cglist_path)
    # 快取已載入的資料夾
    cache = {}

    for entry_line, name, values in entries:
        if not values:
            continue
        folder_idx = values[0]
        group_values = values[1:]  # 各 group 的選擇

        # 資料夾名: name去掉最後一字 + 'l' + folder_idx
        folder_name = name[:-1] + 'l' + folder_idx
        folder_path = os.path.join(script_dir, folder_name)

        if not os.path.isdir(folder_path):
            print(f"跳過 {entry_line}：資料夾 {folder_name} 不存在")
            continue

        if folder_path not in cache:
            cache[folder_path] = load_folder_data(folder_path)
        group_map, offset_map, base_key = cache[folder_path]

        if base_key is None:
            print(f"跳過 {entry_line}：找不到底圖")
            continue

        base_path = os.path.join(folder_path, base_key + ".png")
        if not os.path.isfile(base_path):
            print(f"跳過 {entry_line}：底圖 {base_key}.png 不存在")
            continue

        # 收集要疊加的圖層
        overlays = []
        for gi, item_val in enumerate(group_values, start=1):
            if not item_val:  # 空值跳過
                continue
            group = group_map.get(gi)
            if not group:
                print(f"  警告 {entry_line}：group {gi} 不存在")
                continue
            filename = group.get(item_val)
            if not filename:
                print(f"  警告 {entry_line}：group {gi} item {item_val} 不存在")
                continue
            pos = offset_map.get(filename)
            if pos is None:
                print(f"  警告 {entry_line}：{filename} 無 offset")
                continue
            img_path = os.path.join(folder_path, filename + ".png")
            if not os.path.isfile(img_path):
                print(f"  警告 {entry_line}：{filename}.png 不存在")
                continue
            overlays.append((img_path, pos))

        # 合成
        base_img = Image.open(base_path).convert("RGBA")
        canvas = np.array(base_img)
        for img_path, pos in overlays:
            with Image.open(img_path) as part:
                canvas = composite(canvas, part.convert("RGBA"), pos)

        # 輸出檔名: 用逗號替換成底線
        out_name = entry_line.replace(',', '_') + ".png"
        Image.fromarray(canvas).save(os.path.join(out_dir, out_name))
        print(f"輸出: {out_name}")

    print("完成！")

if __name__ == '__main__':
    main()

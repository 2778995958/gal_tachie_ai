import os
import json
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def process(subdir, out_dir):
    offset_path = os.path.join(subdir, "offset.json")
    if not os.path.isfile(offset_path):
        return
    with open(offset_path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    entries = {item['Key']: tuple(item['Value']) for item in data}

    base_key = None
    for k, v in entries.items():
        if v == (0, 0):
            base_key = k
            break
    if base_key is None:
        print(f"跳過 {subdir}：找不到 (0,0) 底圖")
        return

    base_path = os.path.join(subdir, base_key + ".png")
    if not os.path.isfile(base_path):
        print(f"跳過 {subdir}：底圖 {base_key}.png 不存在")
        return

    base_img = Image.open(base_path).convert("RGBA")
    print(f"處理 {subdir}，底圖: {base_key}.png")

    os.makedirs(out_dir, exist_ok=True)
    base_np = np.array(base_img)
    folder_name = os.path.basename(subdir)

    def do_one(key, pos):
        img_path = os.path.join(subdir, key + ".png")
        if not os.path.isfile(img_path):
            print(f"  警告：{key}.png 不存在，跳過")
            return
        canvas = base_np.copy()
        with Image.open(img_path) as part:
            canvas = composite(canvas, part.convert("RGBA"), pos)
        suffix = key.rsplit('_', 1)[-1] if '_' in key else key
        Image.fromarray(canvas).save(os.path.join(out_dir, f"{folder_name}_{suffix}.png"))
        print(f"  輸出: {folder_name}_{suffix}.png")

    tasks = {k: v for k, v in entries.items() if k != base_key}
    with ThreadPoolExecutor() as pool:
        list(pool.map(lambda kv: do_one(*kv), tasks.items()))

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "out")
    for item in os.listdir(script_dir):
        subdir = os.path.join(script_dir, item)
        if os.path.isdir(subdir) and item != "out":
            process(subdir, out_dir)
    print("完成！")

if __name__ == '__main__':
    main()

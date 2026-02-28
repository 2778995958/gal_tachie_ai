"""
batch_composite.py
放置: CatSystem\
功能: 讀 bustup_dict.json，自動搜尋所有含 offset.json 的資料夾，批量合成立繪
輸出: output/{資料夾名}/{資料夾名}_{g1}_{g2}[_{g3}...].png
"""
import os, sys, re, json, numpy as np
from PIL import Image
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

# ─── Alpha 合成 ───
def composite(base_np, part_img, pos):
    part_np = np.array(part_img.convert("RGBA"), dtype=np.uint8)
    ph, pw = part_np.shape[:2]
    bh, bw = base_np.shape[:2]
    x, y = pos
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + pw, bw), min(y + ph, bh)
    if x1 >= x2 or y1 >= y2:
        return base_np
    px1, py1 = x1 - x, y1 - y
    br = base_np[y1:y2, x1:x2]
    pr = part_np[py1:py1+(y2-y1), px1:px1+(x2-x1)]
    a = pr[:, :, 3:4] / 255.0
    base_np[y1:y2, x1:x2, :3] = (pr[:, :, :3] * a + br[:, :, :3] * (1 - a)).astype(np.uint8)
    base_np[y1:y2, x1:x2, 3]  = (pr[:, :, 3]  + br[:, :, 3] * (1 - a[:, :, 0])).astype(np.uint8)
    return base_np


# ─── 載入 info.json + offset.json ───
def load_folder(folder_path):
    """回傳 (group_map, offset_map, base_key)"""
    with open(os.path.join(folder_path, 'info.json'), 'r', encoding='utf-8-sig') as f:
        info = json.load(f)
    with open(os.path.join(folder_path, 'offset.json'), 'r', encoding='utf-8-sig') as f:
        offsets = json.load(f)

    offset_map = {it['Key']: tuple(it['Value']) for it in offsets}

    base_key = None
    group_map = {}  # {group_int: {item_str: filename}}
    for it in info:
        prefix = it['Key'].split('@')[0]
        val = it['Value']
        if '_' in prefix:
            g_str, i_str = prefix.split('_', 1)
            try:
                group_map.setdefault(int(g_str), {})[i_str] = val
            except ValueError:
                base_key = val
        else:
            base_key = val

    return group_map, offset_map, base_key


# ─── 計算統一畫布 ───
def calc_canvas(folder_path, group_map, offset_map, base_key):
    all_fns = [base_key]
    for items in group_map.values():
        all_fns.extend(items.values())

    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for fn in all_fns:
        pos = offset_map.get(fn)
        if pos is None:
            continue
        p = os.path.join(folder_path, fn + '.png')
        if not os.path.isfile(p):
            continue
        with Image.open(p) as img:
            w, h = img.size
        min_x, min_y = min(min_x, pos[0]), min(min_y, pos[1])
        max_x, max_y = max(max_x, pos[0] + w), max(max_y, pos[1] + h)

    if min_x == float('inf'):
        return None, None
    return (max_x - min_x, max_y - min_y), (-min_x, -min_y)


# ─── 主程式 ───
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dict_path = os.path.join(script_dir, 'bustup_dict.json')
    out_root = os.path.join(script_dir, 'output')

    if not os.path.isfile(dict_path):
        print('Error: bustup_dict.json not found. Run gen_bustup_dict.py first.')
        return

    # 1) 載入字典，解析為 {角色名: set of group tuples}
    with open(dict_path, 'r', encoding='utf-8') as f:
        raw_specs = json.load(f)

    char_combos = {}
    for spec in raw_specs:
        parts = spec.split(',')
        if len(parts) < 4:
            continue
        char_name = parts[0]          # ca11
        groups = parts[2:]            # [g1, g2, ...]
        while groups and groups[-1] == '':
            groups.pop()
        if groups:
            char_combos.setdefault(char_name, set()).add(tuple(groups))

    print(f'Dict: {len(char_combos)} characters, '
          f'{sum(len(v) for v in char_combos.values())} unique combos')

    # 2) 搜尋所有含 offset.json + info.json 的資料夾
    folder_index = {}
    for root, dirs, files in os.walk(script_dir):
        # 跳過 output 目錄
        if 'output' in dirs:
            dirs.remove('output')
        if 'offset.json' in files and 'info.json' in files:
            folder_index[os.path.basename(root)] = root

    print(f'Found {len(folder_index)} folders with offset.json')

    # 3) 匹配與合成
    os.makedirs(out_root, exist_ok=True)
    total = 0
    done = 0
    skipped = 0

    for folder_name, folder_path in sorted(folder_index.items()):
        # 從資料夾名提取角色名: ca11l -> ca11, cd21l -> cd21
        m = re.match(r'^(c[a-d]\d\d)', folder_name)
        if not m:
            continue
        char_name = m.group(1)
        if char_name not in char_combos:
            continue

        combos = char_combos[char_name]
        total += len(combos)

        # 載入
        try:
            group_map, offset_map, base_key = load_folder(folder_path)
        except Exception as e:
            print(f'[SKIP] {folder_name}: {e}')
            skipped += len(combos)
            done += len(combos)
            continue

        if base_key is None:
            skipped += len(combos)
            done += len(combos)
            continue

        canvas_size, origin = calc_canvas(folder_path, group_map, offset_map, base_key)
        if canvas_size is None:
            skipped += len(combos)
            done += len(combos)
            continue

        # 底圖
        base_path = os.path.join(folder_path, base_key + '.png')
        if not os.path.isfile(base_path):
            skipped += len(combos)
            done += len(combos)
            continue

        base_canvas = np.zeros((canvas_size[1], canvas_size[0], 4), dtype=np.uint8)
        with Image.open(base_path) as img:
            bp = offset_map.get(base_key, (0, 0))
            base_canvas = composite(base_canvas, img,
                                    (bp[0] + origin[0], bp[1] + origin[1]))

        # 輸出目錄
        char_out = os.path.join(out_root, folder_name)
        os.makedirs(char_out, exist_ok=True)

        # 按 G1 分組，共用 body_base
        g1_groups = defaultdict(list)
        for combo in combos:
            g1_groups[combo[0]].append(combo)

        img_cache = {}

        for g1_val, g1_combos in g1_groups.items():
            # body_base = base + G1
            body_base = base_canvas.copy()
            g1_items = group_map.get(1, {})
            g1_fn = g1_items.get(g1_val)
            if g1_fn:
                g1_pos = offset_map.get(g1_fn)
                g1_path = os.path.join(folder_path, g1_fn + '.png')
                if g1_pos and os.path.isfile(g1_path):
                    if g1_path not in img_cache:
                        img_cache[g1_path] = Image.open(g1_path).convert("RGBA")
                    body_base = composite(body_base, img_cache[g1_path],
                                          (g1_pos[0] + origin[0],
                                           g1_pos[1] + origin[1]))

            for combo in g1_combos:
                done += 1
                combo_str = '_'.join(c if c else '0' for c in combo)
                out_name = f'{folder_name}_{combo_str}.png'
                out_path = os.path.join(char_out, out_name)

                if os.path.exists(out_path):
                    continue

                canvas = body_base.copy()
                ox, oy = origin

                # G2, G3, G4 ...
                for gi, item_code in enumerate(combo[1:], start=2):
                    if not item_code:
                        continue
                    group = group_map.get(gi)
                    if not group:
                        continue
                    fn = group.get(item_code)
                    if not fn:
                        continue
                    pos = offset_map.get(fn)
                    if pos is None:
                        continue
                    img_path = os.path.join(folder_path, fn + '.png')
                    if not os.path.isfile(img_path):
                        continue
                    if img_path not in img_cache:
                        img_cache[img_path] = Image.open(img_path).convert("RGBA")
                    canvas = composite(canvas, img_cache[img_path],
                                       (pos[0] + ox, pos[1] + oy))

                Image.fromarray(canvas).save(out_path)
                print(f'[{done}/{total}] {out_name}')

        # 釋放快取
        for img in img_cache.values():
            img.close()

    print(f'\nDone! {done - skipped}/{total} composited, {skipped} skipped.')

if __name__ == '__main__':
    main()

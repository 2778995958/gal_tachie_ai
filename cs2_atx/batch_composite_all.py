"""
batch_composite.py
放置: CatSystem\
功能: 自動搜尋所有含 offset.json 的資料夾，從 info.json 枚舉所有組合，多線程批量合成立繪
輸出: output/{資料夾名}/{資料夾名}_{g1}_{g2}[_{g3}...].png
用法: python batch_composite.py [threads]
      threads 預設 = CPU 核心數
"""
import os, sys, re, json, threading, numpy as np
from PIL import Image
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product as _product

sys.stdout.reconfigure(encoding='utf-8')

# ─── 進度計數器 (線程安全) ───
_lock = threading.Lock()
_done = 0
_total = 0

def _tick(name):
    global _done
    with _lock:
        _done += 1
        n = _done
    print(f'[{n}/{_total}] {name}')


# ─── 單張合成任務 (提交給線程池) ───
def composite_task(body_base, overlays, out_path):
    """
    body_base: numpy array (會 copy)
    overlays:  [(layer_np, (x, y)), ...]
    """
    canvas = body_base.copy()
    for layer_np, pos in overlays:
        ph, pw = layer_np.shape[:2]
        bh, bw = canvas.shape[:2]
        x, y = pos
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + pw, bw), min(y + ph, bh)
        if x1 >= x2 or y1 >= y2:
            continue
        px1, py1 = x1 - x, y1 - y
        br = canvas[y1:y2, x1:x2]
        pr = layer_np[py1:py1+(y2-y1), px1:px1+(x2-x1)]
        a = pr[:, :, 3:4] / 255.0
        canvas[y1:y2, x1:x2, :3] = (pr[:, :, :3] * a + br[:, :, :3] * (1 - a)).astype(np.uint8)
        canvas[y1:y2, x1:x2, 3]  = (pr[:, :, 3]  + br[:, :, 3] * (1 - a[:, :, 0])).astype(np.uint8)
    Image.fromarray(canvas).save(out_path)
    _tick(os.path.basename(out_path))


# ─── 內部合成 (用於預備 body_base，主線程中) ───
def _composite_onto(base_np, layer_np, pos):
    ph, pw = layer_np.shape[:2]
    bh, bw = base_np.shape[:2]
    x, y = pos
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + pw, bw), min(y + ph, bh)
    if x1 >= x2 or y1 >= y2:
        return
    px1, py1 = x1 - x, y1 - y
    br = base_np[y1:y2, x1:x2]
    pr = layer_np[py1:py1+(y2-y1), px1:px1+(x2-x1)]
    a = pr[:, :, 3:4] / 255.0
    base_np[y1:y2, x1:x2, :3] = (pr[:, :, :3] * a + br[:, :, :3] * (1 - a)).astype(np.uint8)
    base_np[y1:y2, x1:x2, 3]  = (pr[:, :, 3]  + br[:, :, 3] * (1 - a[:, :, 0])).astype(np.uint8)


# ─── 載入 info.json + offset.json ───
def load_folder(folder_path):
    with open(os.path.join(folder_path, 'info.json'), 'r', encoding='utf-8-sig') as f:
        info = json.load(f)
    with open(os.path.join(folder_path, 'offset.json'), 'r', encoding='utf-8-sig') as f:
        offsets = json.load(f)

    offset_map = {it['Key']: tuple(it['Value']) for it in offsets}
    base_key = None
    group_map = {}
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


# ─── 預載資料夾所有圖層為 numpy array ───
def preload_images(folder_path, group_map, base_key):
    np_cache = {}
    all_fns = [base_key]
    for items in group_map.values():
        all_fns.extend(items.values())
    for fn in all_fns:
        p = os.path.join(folder_path, fn + '.png')
        if os.path.isfile(p):
            np_cache[fn] = np.array(Image.open(p).convert("RGBA"), dtype=np.uint8)
    return np_cache


# ─── 計算統一畫布 ───
def calc_canvas(np_cache, offset_map):
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for fn, arr in np_cache.items():
        pos = offset_map.get(fn)
        if pos is None:
            continue
        h, w = arr.shape[:2]
        min_x, min_y = min(min_x, pos[0]), min(min_y, pos[1])
        max_x, max_y = max(max_x, pos[0] + w), max(max_y, pos[1] + h)
    if min_x == float('inf'):
        return None, None
    return (max_x - min_x, max_y - min_y), (-min_x, -min_y)


# ─── 從 group_map 生成所有笛卡爾積組合 ───
def enumerate_all_combos(group_map):
    if not group_map:
        return set()
    sorted_groups = sorted(group_map.keys())
    group_items = [sorted(group_map[g].keys()) for g in sorted_groups]
    return {tuple(combo) for combo in _product(*group_items)}


# ─── 主程式 ───
def main():
    global _total

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_root = os.path.join(script_dir, 'output')
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else os.cpu_count()

    # 1) 搜尋所有含 offset.json + info.json 的資料夾
    folder_index = {}
    for root, dirs, files in os.walk(script_dir):
        if 'output' in dirs:
            dirs.remove('output')
        if 'offset.json' in files and 'info.json' in files:
            folder_index[os.path.basename(root)] = root

    print(f'Found {len(folder_index)} folders with offset.json')
    print(f'Using {workers} threads\n')

    # 2) 收集所有任務
    os.makedirs(out_root, exist_ok=True)
    tasks = []  # [(body_base, overlays, out_path), ...]

    for folder_name, folder_path in sorted(folder_index.items()):
        m = re.match(r'^(c[a-d]\d\d)', folder_name)
        if not m:
            continue

        try:
            group_map, offset_map, base_key = load_folder(folder_path)
        except Exception as e:
            print(f'[SKIP] {folder_name}: {e}')
            continue
        if base_key is None:
            continue

        combos = enumerate_all_combos(group_map)

        # 預載所有圖層
        np_cache = preload_images(folder_path, group_map, base_key)
        if base_key not in np_cache:
            continue

        canvas_size, origin = calc_canvas(np_cache, offset_map)
        if canvas_size is None:
            continue

        # 底圖
        base_canvas = np.zeros((canvas_size[1], canvas_size[0], 4), dtype=np.uint8)
        bp = offset_map.get(base_key, (0, 0))
        _composite_onto(base_canvas, np_cache[base_key],
                        (bp[0] + origin[0], bp[1] + origin[1]))

        # 輸出目錄
        char_out = os.path.join(out_root, folder_name)
        os.makedirs(char_out, exist_ok=True)

        # 按 G1 分組
        g1_groups = defaultdict(list)
        for combo in combos:
            g1_groups[combo[0]].append(combo)

        ox, oy = origin

        for g1_val, g1_combos in g1_groups.items():
            # body_base = base + G1
            body_base = base_canvas.copy()
            g1_fn = group_map.get(1, {}).get(g1_val)
            if g1_fn and g1_fn in np_cache:
                g1_pos = offset_map.get(g1_fn)
                if g1_pos:
                    _composite_onto(body_base, np_cache[g1_fn],
                                    (g1_pos[0] + ox, g1_pos[1] + oy))

            for combo in g1_combos:
                combo_str = '_'.join(c if c else '0' for c in combo)
                out_name = f'{folder_name}_{combo_str}.png'
                out_path = os.path.join(char_out, out_name)

                if os.path.exists(out_path):
                    continue

                # 收集 G2+ overlay
                overlays = []
                for gi, item_code in enumerate(combo[1:], start=2):
                    if not item_code:
                        continue
                    fn = group_map.get(gi, {}).get(item_code)
                    if not fn or fn not in np_cache:
                        continue
                    pos = offset_map.get(fn)
                    if pos is None:
                        continue
                    overlays.append((np_cache[fn], (pos[0] + ox, pos[1] + oy)))

                tasks.append((body_base, overlays, out_path))

        # np_cache 在此保留引用直到所有任務完成

    _total = len(tasks)
    print(f'Submitting {_total} composite tasks...\n')

    # 4) 多線程執行
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(composite_task, bb, ov, op) for bb, ov, op in tasks]
        for f in as_completed(futures):
            exc = f.exception()
            if exc:
                print(f'[ERROR] {exc}')

    print(f'\nDone! {_done}/{_total} composited.')

if __name__ == '__main__':
    main()

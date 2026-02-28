"""
gen_bustup_dict.py
放置: CatSystem\
功能: 解壓 scene/*.cstx，提取所有立繪組合，輸出 bustup_dict.json
格式: ["ca11,f,1,1", "ca11,m,2,t", "cd11,f,1,t,1", ...]
"""
import os, sys, zlib, re, json
sys.stdout.reconfigure(encoding='utf-8')

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scene_dir = os.path.join(script_dir, 'scene')

    if not os.path.isdir(scene_dir):
        print(f'Error: scene/ not found')
        return

    all_specs = set()
    count = 0

    for fname in sorted(os.listdir(scene_dir)):
        if not fname.endswith('.cstx'):
            continue
        with open(os.path.join(scene_dir, fname), 'rb') as f:
            raw = f.read()
        if raw[:4] != b'CSTX' or len(raw) <= 16:
            continue
        try:
            result = zlib.decompress(raw[16:], -15)
        except Exception:
            continue
        count += 1
        for s in re.findall(rb'[\x20-\x7e]{4,}', result):
            m = re.match(rb'(?:cg|fw)\s+\d+\s+(c[a-d]\d\d,\S+)', s)
            if m:
                spec = m.group(1).decode('ascii').split(' ')[0].rstrip('"')
                parts = spec.split(',')
                if len(parts) >= 4 and parts[1] in ('f', 'm', 'l'):
                    all_specs.add(spec)

    output = sorted(all_specs)
    out_path = os.path.join(script_dir, 'bustup_dict.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'Scanned {count} cstx, saved {len(output)} entries to bustup_dict.json')

if __name__ == '__main__':
    main()

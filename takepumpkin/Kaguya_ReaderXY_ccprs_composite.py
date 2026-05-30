import os
import re
from PIL import Image

def main():
    # 設定檔案與路徑
    txt_path = 'Kaguya_XY_Offset.txt'
    images_dir = 'images'
    output_dir = 'output'
    
    # 自動建立輸出資料夾
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(txt_path):
        print(f"❌ 錯誤：找不到座標檔案：{txt_path}")
        return
        
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. 清洗資料：移除 標籤
    content = re.sub(r'\\', '', content)
    
    # 2. 解析資料：匹配「檔名.prs : X, Y」
    pattern = r'([\w\.]+)\s*:\s*(\d+),\s*(\d+)'
    matches = re.findall(pattern, content)
    
    bodies = {}         # 存放身體：{ 角色代號: [(檔名, x, y), ...] }
    expressions = {}    # 存放表情：{ 角色代號: [(檔名, x, y), ...] }
    seen_filenames = set()  # 用於記錄已處理過的檔名，防止重複
    
    for filename, x_str, y_str in matches:
        # 【防錯機制 1】如果檔名重複，直接跳過
        if filename in seen_filenames:
            print(f"⚠️ 提示：偵測到重複文字紀錄 {filename}，已自動跳過。")
            continue
        seen_filenames.add(filename)
        
        x, y = int(x_str), int(y_str)
        
        if filename.startswith('s_'):
            char_match = re.match(r's_([a-zA-Z]{3})', filename)
            if char_match:
                char_code = char_match.group(1)
                bodies.setdefault(char_code, []).append((filename, x, y))
        else:
            char_match = re.search(r'_([a-zA-Z]{3})\d+', filename)
            if char_match:
                char_code = char_match.group(1)
                expressions.setdefault(char_code, []).append((filename, x, y))
                
    # 3. 遍歷角色進行交叉合成
    all_chars = set(bodies.keys()).union(expressions.keys())
    
    for char_code in all_chars:
        char_bodies = bodies.get(char_code, [])
        char_exprs = expressions.get(char_code, [])
        
        if not char_bodies or not char_exprs:
            continue
            
        # 預先篩選出實際存在的圖片
        valid_bodies = []
        for filename, x, y in char_bodies:
            png_name = filename.replace('.prs', '.png')
            path = os.path.join(images_dir, png_name)
            if os.path.exists(path):
                valid_bodies.append((filename, x, y))
            else:
                print(f"❌ 錯誤：找不到實體身體圖片 {path}")
                
        # 【防錯機制 2】如果該角色找不到任何可用的身體圖片，直接跳過該角色
        if not valid_bodies:
            print(f"⚠️ 警告：角色 [{char_code}] 缺少所有身體圖片，已跳過該角色合成！")
            continue
            
        valid_exprs = []
        for filename, x, y in char_exprs:
            png_name = filename.replace('.prs', '.png')
            path = os.path.join(images_dir, png_name)
            if os.path.exists(path):
                valid_exprs.append((filename, x, y))
            else:
                print(f"⚠️ 提示：找不到表情圖片 {path}，已跳過此表情。")
                
        if not valid_exprs:
            print(f"⚠️ 提示：角色 [{char_code}] 沒有可用的有效表情，跳過組合。")
            continue
            
        print(f"🎬 正在處理角色 [{char_code}]：使用 {len(valid_bodies)} 個身體與 {len(valid_exprs)} 個表情進行合成...")
        
        # 4. 開始組合合成
        for b_file, b_x, b_y in valid_bodies:
            b_png = b_file.replace('.prs', '.png')
            b_path = os.path.join(images_dir, b_png)
            
            with Image.open(b_path).convert("RGBA") as b_img:
                b_w, b_h = b_img.size
                
                for e_file, e_x, e_y in valid_exprs:
                    e_png = e_file.replace('.prs', '.png')
                    e_path = os.path.join(images_dir, e_png)
                    
                    with Image.open(e_path).convert("RGBA") as e_img:
                        e_w, e_h = e_img.size
                        
                        # 計算緊湊型最大長寬邊界
                        min_x = min(b_x, e_x)
                        min_y = min(b_y, e_y)
                        max_x = max(b_x + b_w, e_x + e_w)
                        max_y = max(b_y + b_h, e_y + e_h)
                        
                        canvas_w = max_x - min_x
                        canvas_h = max_y - min_y
                        
                        # 建立畫布
                        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                        
                        # 計算相對貼上位置
                        paste_b_x = b_x - min_x
                        paste_b_y = b_y - min_y
                        paste_e_x = e_x - min_x
                        paste_e_y = e_y - min_y
                        
                        # 合成
                        canvas.paste(b_img, (paste_b_x, paste_b_y), b_img)
                        canvas.paste(e_img, (paste_e_x, paste_e_y), e_img)
                        
                        # 儲存
                        b_name = os.path.splitext(b_png)[0]
                        e_name = os.path.splitext(e_png)[0]
                        out_name = f"{b_name}_{e_name}.png"
                        
                        canvas.save(os.path.join(output_dir, out_name), "PNG")
                        
    print("✨ 緊湊型安全合成完畢！")

if __name__ == '__main__':
    main()
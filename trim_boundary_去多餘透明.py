import os
from PIL import Image
import concurrent.futures
from functools import partial

# 建議安裝 tqdm 以顯示進度條 (pip install tqdm)
try:
    from tqdm import tqdm
except ImportError:
    # 如果沒有安裝 tqdm，則定義一個假的 tqdm 函式，讓程式碼依然可以執行
    def tqdm(iterable, *args, **kwargs):
        return iterable

"""
遞迴遍歷當前資料夾及子資料夾下的所有 PNG 圖片，裁剪透明邊界 (多進程版本)
裁剪後圖片保存在 output/ 資料夾中，保持相對目錄結構
請先確保安裝了 Pillow 和 tqdm 函式庫
"""

def crop_transparent_border(image_path):
    """
    裁剪單一圖片的透明邊界。
    這是核心的圖片處理邏輯，保持不變。
    """
    with Image.open(image_path) as img:
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        alpha = img.split()[-1]  # 提取 alpha 通道（透明度）
        bbox = alpha.getbbox()   # 獲取非完全透明區域的邊界框
        if bbox:
            return img.crop(bbox)    # 將原圖裁剪成這個矩形區域
        else:
            return img.copy()  # 若完全透明或無裁剪需求，則原樣返回

def process_and_save_image(input_path, input_root, output_root):
    """
    處理單一圖片的完整流程：裁剪、建立輸出目錄並儲存。
    這個函式將會被每個子進程獨立呼叫。

    Args:
        input_path (str): 輸入圖片的完整路徑。
        input_root (str): 輸入的根目錄。
        output_root (str): 輸出的根目錄。
    
    Returns:
        str: 處理結果的訊息。
    """
    try:
        # 構造輸出路徑，保持目錄結構
        relative_path = os.path.relpath(input_path, input_root)
        output_path = os.path.join(output_root, relative_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 裁剪並保存
        cropped_image = crop_transparent_border(input_path)
        cropped_image.save(output_path, format='PNG')  # 保持無損格式
        return f"成功儲存到：{output_path}"
    except Exception as e:
        return f"處理失敗 {input_path}: {e}"

def main(input_root='.', output_root='output'):
    """
    主函式，負責收集圖片路徑並使用多進程處理。
    """
    # 步驟 1: 收集所有需要處理的 PNG 圖片路徑
    print("正在掃描圖片，請稍候...")
    image_paths = []
    # 確保不會處理 output 資料夾內的圖片，避免無限循環
    abs_output_root = os.path.abspath(output_root)

    for foldername, _, filenames in os.walk(input_root):
        # 如果當前資料夾在輸出目錄內，則跳過
        if os.path.abspath(foldername).startswith(abs_output_root):
            continue
            
        for filename in filenames:
            if filename.lower().endswith('.png'):
                image_paths.append(os.path.join(foldername, filename))
    
    if not image_paths:
        print("在指定目錄下未找到任何 PNG 圖片。")
        return

    print(f"找到 {len(image_paths)} 張圖片，開始多進程處理...")

    # 步驟 2: 使用 ProcessPoolExecutor 進行平行處理
    # max_workers=None 會自動設定為你的 CPU 核心數
    with concurrent.futures.ProcessPoolExecutor(max_workers=None) as executor:
        # functools.partial 可以幫我們把固定的參數 (input_root, output_root) 包裝起來
        # 這樣 executor.map 就可以只傳入會變動的參數 (image_path)
        task_func = partial(process_and_save_image, input_root=input_root, output_root=output_root)
        
        # 步驟 3: 分發任務並使用 tqdm 顯示進度
        # executor.map 會將 image_paths 列表中的每一個元素，作為參數傳給 task_func 執行
        results = list(tqdm(executor.map(task_func, image_paths), total=len(image_paths), desc="處理進度"))

    # (可選) 印出所有處理結果
    # for res in results:
    #     print(res)
    print("\n所有圖片處理完成！")


# if __name__ == '__main__': 是多進程程式碼的保護機制
# 確保主邏輯只在主進程中執行，而不是在每個子進程中都執行一次
if __name__ == '__main__':
    # 執行主函式，處理當前目錄下的圖片，並輸出到 'output' 資料夾
    main('.', 'output')
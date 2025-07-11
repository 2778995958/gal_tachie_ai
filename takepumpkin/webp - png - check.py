import os
import re
import subprocess
import binascii
import shutil
from collections import defaultdict

def calculate_crc(file_path):
    """计算文件的 CRC32 值"""
    with open(file_path, 'rb') as f:
        file_data = f.read()
        return binascii.crc32(file_data) & 0xffffffff

def get_png_filenames(png_directory):
    """获取所有符合格式的 PNG 文件名，忽略后面的部分"""
    pattern = r'^cg(\d{3})-(\d{1,3})'  # 只检查到第二个连字符
    png_filenames = set()

    for filename in os.listdir(png_directory):
        match = re.match(pattern, filename)
        if match:
            # 只保留前面部分
            png_filenames.add(match.group(0))

    return png_filenames

def check_filenames_in_directory(directory, png_filenames, log_file):
    """检查目录中的文件名是否与 PNG 文件名匹配，并记录缺漏"""
    found_filenames = set()

    for filename in os.listdir(directory):
        base_name = re.match(r'^(cg\d{3}-\d{1,3})', filename)
        if base_name and base_name.group(1) in png_filenames:
            found_filenames.add(base_name.group(1))

    missing_filenames = png_filenames - found_filenames

    with open(log_file, 'w', encoding='utf-8') as f:
        if missing_filenames:
            f.write("有缺漏，以下没有:\n")
            for missing in sorted(missing_filenames):
                f.write(f"{missing}\n")
        else:
            f.write("没有缺漏，以下是文件名:\n")
            for found in sorted(found_filenames):
                f.write(f"{found}\n")

# 设置图像文件夹路径
image_folder = 'png'
output_folder = 'webpout'
creation_log_file = 'webp_creation_log.txt'
ffmpeg_log_file = 'ffmpeg_process_log.txt'
check_log_file = 'check.txt'  # 检查结果的日志文件

# 创建输出文件夹
os.makedirs(output_folder, exist_ok=True)

# 获取所有图像文件
files = [f for f in os.listdir(image_folder) if f.endswith('.png')]
grouped_images = defaultdict(list)

# 正则表达式匹配前缀
pattern = re.compile(r'^(cg\d{3}-\d{2}-)(\d{3})\.png$')

# 创建创建日志文件
with open(creation_log_file, 'w') as creation_log:
    creation_log.write("WebP Creation Log\n" + "=" * 30 + "\n")
    
    # 按前缀分组 PNG 文件
    for filename in files:
        match = pattern.match(filename)
        if match:
            prefix = match.group(1)
            grouped_images[prefix].append(filename)
        else:
            # 复制不符合组合的 PNG 文件到输出文件夹
            source_path = os.path.join(image_folder, filename)
            shutil.copy(source_path, output_folder)
            creation_log.write(f"Copied non-matching PNG: {filename}\n")

    crc_map = {}

    for prefix, image_files in grouped_images.items():
        if image_files:
            first_image_file = f"{prefix}001.png"
            first_image_path = os.path.join(image_folder, first_image_file)
            crc = calculate_crc(first_image_path)

            output_webp = os.path.join(output_folder, f"{prefix[:-1]}.webp")
            input_pattern = os.path.join(image_folder, f"{prefix}%03d.png")

            if crc in crc_map:
                # CRC 已存在，使用 28.572 fps 生成 WebP
                result = subprocess.run([
                    'ffmpeg', '-hide_banner', '-y', '-r', '28.572', '-i', input_pattern,
                    '-c:v', 'libwebp', '-q', '100', '-loop', '0', output_webp
                ], capture_output=True, text=True)

                creation_log.write(f"Recreated WebP (same CRC): {output_webp}\n")
                print(f"Recreating WebP due to same CRC: {output_webp}")
            else:
                # CRC 不存在，使用 14.286 fps 生成 WebP
                result = subprocess.run([
                    'ffmpeg', '-hide_banner', '-y', '-r', '14.286', '-i', input_pattern,
                    '-c:v', 'libwebp', '-q', '100', '-loop', '0', output_webp
                ], capture_output=True, text=True)

                creation_log.write(f"Created WebP: {output_webp}\n")
                crc_map[crc] = output_webp
                print(f"Created WebP: {output_webp}")

            # 记录 ffmpeg 过程输出
            with open(ffmpeg_log_file, 'a') as ffmpeg_log:
                ffmpeg_log.write(f"FFmpeg process for {output_webp}:\n")
                ffmpeg_log.write(result.stderr)
                ffmpeg_log.write("\n")

            # 记录使用的文件和 CRC
            used_files = [f" - {image_file}, CRC: {calculate_crc(os.path.join(image_folder, image_file))}" for image_file in sorted(image_files)]
            creation_log.write("Used files:\n")
            creation_log.write("\n".join(used_files) + "\n")

# 检查生成的 WebP 文件
png_filenames = get_png_filenames(image_folder)
check_filenames_in_directory(output_folder, png_filenames, check_log_file)

print(f"所有 WebP 创建记录已保存到: {creation_log_file}")
print(f"FFmpeg 过程日志已保存到: {ffmpeg_log_file}")
print(f"检查结果已保存到: {check_log_file}")
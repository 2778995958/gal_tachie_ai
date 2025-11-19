import sys

def merge_files(webp_filepath, zip_filepath, output_filepath):
    with open(webp_filepath, 'rb') as webp_file:
        webp_data = webp_file.read()

    with open(zip_filepath, 'rb') as zip_file:
        zip_data = zip_file.read()

    # 合并数据
    combined_data = webp_data + zip_data
    
    with open(output_filepath, 'wb') as output_file:
        output_file.write(combined_data)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python merge.py <webp_file> <zip_file> <output_file>")
    else:
        webp_file = sys.argv[1]
        zip_file = sys.argv[2]
        output_file = sys.argv[3]

        merge_files(webp_file, zip_file, output_file)
        print(f"已成功合成文件: {output_file}")
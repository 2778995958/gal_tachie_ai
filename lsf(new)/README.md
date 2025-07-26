找了一輪，找到Chenx221大佬寫的[EscudeTools](https://github.com/Chenx221/EscudeTools)

但對於不懂程序的人，只好全丟ai處理，換成python，經過一輪ai debug幾百次，粗用應該可以，雖然只能解圖

v2做法
```
usage: escude_tools_2.py [-h] [-d <bin_dir>] [-a <LsfPath>] [-ev <EvPath> <db_path>] [-s <StPath> <db_path>]
                         [-b <modes>] [-export_lsf <LsfPath>] [-j <num>]

一個用於處理 Escude 遊戲引擎資源的 Python 整合工具。

options:
  -h, --help            show this help message and exit
  -d <bin_dir>          [解包] 將指定目錄下的所有 .bin 檔案轉換為 .db 資料庫。
                                 範例: -d "C:\path\to\your\bin_files"
  -a <LsfPath>          [通用合成] 強制合成指定目錄下所有LSF檔案(組合全部圖層)。註：所有圖縫合，正常不用
  -ev <EvPath> <db_path>
                        [合成] 合成事件 (EV) 圖片 (檔名會包含CG鑑賞ID)。
  -s <StPath> <db_path>
                        [合成] 合成角色立繪 (ST) 圖片 (檔名已優化，可搭配-b)。
  -b <modes>            [用於 -s] 指定臉紅模式 (可多選，用逗號分隔):
                          0 = 無臉紅 (移除 p2)
                          1 = 原始定義 (通常為 p2:1)
                          2 = 臉紅B (使用 p2:2)
                          範例: -b 0,2 (只生成無臉紅和臉紅B)
  -export_lsf <LsfPath>
                        [匯出] 匯出 LSF 圖層資訊到 CSV。
  -j, --jobs <num>      [優化] 指定使用的 CPU 核心數量 (預設: 全部可用核心)。
```

```
用法:
GARbro解出CG整個資料夾=<EvPath>或ST整個資料夾<StPath>
解data.bin裡面的db_graphics.bin

escude_tools_2.py -d "C:\path\to\your\放bin資料夾"
escude_tools_2.py -ev "C:\path\to\your\放圖檔連lsf的資料夾" "C:\path\to\your\unpacked_output\db_graphics.db"

完成
```

v1做法
```
usage: escude_tools_1.py [-h] [-d <bin_dir>] [-c <EvPath> <db_path>] [-s <StPath> <db_path>] [-b <mode>]
                         [-export_lsf <LsfPath>]

一個用於處理 Escude 遊戲引擎資源的 Python 整合工具。

options:
  -h, --help            show this help message and exit
  -d <bin_dir>          [解包] 將指定目錄下的所有 .bin 檔案轉換為 .db 資料庫。
  -c <EvPath> <db_path>
                        [合成] 合成事件 (EV) 圖片 (檔名會包含CG鑑賞ID)。
  -s <StPath> <db_path>
                        [合成] 合成角色立繪 (ST) 圖片 (可搭配-b選項)。
  -b <mode>             [用於 -s] 指定臉紅模式:
                          0=無臉紅, 1=原始定義, 2=臉紅B
  -export_lsf <LsfPath>
                        [匯出] 匯出 LSF 圖層資訊到 CSV。
```

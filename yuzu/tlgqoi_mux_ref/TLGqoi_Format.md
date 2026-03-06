# TLGqoi+QHDR Container Format

TLGqoi+QHDR 是 Kirikiri/吉里吉里引擎新版的多圖片容器格式，將多張尺寸相同的完整 CG 圖片交錯壓縮在一個檔案中。本文以 `ev104__n5djit.tlg`（8 張 2560x1440 RGBA）為範例。

---

## 1. 檔案總覽

```
ev104__n5djit.tlg (5,294,676 bytes)
├── File Header         (20 bytes)
├── QHDR Tag + Size     (8 bytes)
├── QHDR Data           (48 bytes)
├── QOI Prefix          (8 bytes)         ← 全零，跳過
├── QOI Stream          (4,462,166 bytes) ← 像素顏色編碼
├── DTBL Chunk          (33 bytes)        ← 條帶定位表
├── RTBL Chunk          (21 bytes)        ← 條帶分布資料大小表
└── LZ4 Dist Data       (832,372 bytes)   ← 分布資料（LZ4 壓縮）
```

---

## 2. File Header (20 bytes)

```
Offset  Size  Value                Description
──────  ────  ───────────────────  ──────────────────────────
0x00    11    "TLGqoi\x00raw\x1a"  魔術數字（所有 TLGqoi 共用）
0x0B    1     0x03 (或 0x04)       channels（3=RGB, 4=RGBA）
0x0C    4     2560                 width（小端序 uint32）
0x10    4     1440                 height（小端序 uint32）
```

判斷是否為容器：offset 0x14 開始是否為 `"QHDR"` 標籤。
- 有 QHDR → 多圖片容器
- 無 QHDR → 單張 TLGqoi 圖片（直接開始 QOI 串流）

---

## 3. QHDR Tag + Data (8 + 48 bytes)

```
Offset  Size  Description
──────  ────  ────────────────────────
0x14    4     "QHDR" 標籤
0x18    4     QHDR data size = 48
```

### QHDR Data (48 bytes)

以 ev104 為例，raw hex：`9e4d6299 08000000 68010000 04000000 64392900 00000000 56164400 00000000 77164400 00000000 00ca5000 00000000`

```
Offset  Size  Value        Description
──────  ────  ──────────── ──────────────────────────────────────────
0x00    4     0x99624D9E   容器 hash（與 TLGref 的 QREF hash 匹配）
0x04    4     8            num_images（容器內圖片張數）
0x08    4     360          band_height（條帶高度，像素）
0x0C    4     4            num_bands = ceil(1440 / 360)
0x10    8     2,701,668    total_symbols（QOI 符號總數，近似值）
0x18    8     4,462,166    total_qoi_bytes（QOI 串流大小）
0x20    8     4,462,199    total_qoi + DTBL chunk size
0x28    8     5,294,592    total_qoi + DTBL + RTBL + dist data size
```

**檔案大小公式**：`file_size = 28 + qhdr_size + 8 + QHDR[0x28]`

QHDR[0x20] 和 QHDR[0x28] 是累積偏移量，用於快速定位各區段：
- QOI 串流起始 = `28 + qhdr_size + 8`（跳過 8-byte prefix）
- DTBL 起始 = `28 + qhdr_size + 8 + QHDR[0x18]`
- RTBL 起始 = `28 + qhdr_size + 8 + QHDR[0x20]`
- Dist data 起始 = RTBL 起始 + RTBL chunk size

---

## 4. TLGref 引用檔案 (86 bytes)

每個 CG 變體對應一個微小的 TLGref 檔案，僅記錄「指向哪個容器的第幾張圖」。

以 `ev104aa.tlg`（86 bytes）為例：

```
0000: 54 4C 47 72 65 66 00 72 61 77 1A 03 00 0A 00 00   TLGref.raw......
0010: A0 05 00 00 51 52 45 46 32 00 00 00 9E 4D 62 99   ....QREF2....Mb.
0020: 01 00 00 00 08 00 00 00 22 00 00 00 65 00 76 00   ........"...e.v.
0030: 31 00 30 00 34 00 5F 00 5F 00 6E 00 35 00 64 00   1.0.4._._.n.5.d.
0040: 6A 00 69 00 74 00 2E 00 74 00 6C 00 67 00 00 00   j.i.t...t.l.g...
0050: 00 00 00 00 00 00                                 ......
```

```
Offset  Size  Value               Description
──────  ────  ─────────────────── ──────────────────────────────────
0x00    6     "TLGref"             魔術數字
0x06    5     "\x00raw\x1a"        格式標識
0x0B    1     0x03                 channels
0x0C    2     0x000A               (unknown)
0x0E    2     0x0000               (padding)
0x10    4     0x000005A0           (unknown, 可能是圖片相關資訊)
0x14    4     "QREF"               引用區段標籤
0x18    4     0x00000032 = 50      QREF data size
0x1C    4     0x99624D9E           容器 hash（與容器 QHDR[0:4] 匹配）
0x20    4     1                    index（容器內第幾張圖，0-based）
0x24    4     8                    count（容器總圖片數 = num_images）
0x28    4     0x00000022 = 34      容器名字串長度（bytes）
0x2C    34    "ev104__n5djit.tlg"  容器檔名（UTF-16LE, null 終止）
0x4E    8     0x0000000000000000   padding
```

遊戲載入 `ev104aa` 時：
1. 讀取 TLGref → 得知容器名 `ev104__n5djit.tlg`、index=1
2. 開啟容器，解碼第 1 張圖（0-based）
3. 直接顯示完整 2560x1440 圖片

---

## 5. 交錯壓縮原理

### 5.1 條帶（Band）分割

圖片按高度分割成多個條帶。ev104 中：band_height=360, height=1440 → 4 bands。

```
Band 0: row   0 ~ 359  (360 rows)
Band 1: row 360 ~ 719  (360 rows)
Band 2: row 720 ~ 1079 (360 rows)
Band 3: row 1080~ 1439 (360 rows)
```

### 5.2 像素交錯順序

每個 band 內，所有圖片的像素按「同行、跨圖片」交錯排列：

```
Band 0 像素序列（total = 2560 × 8 × 360 = 7,372,800 pixels）：

  img0[0,0] img1[0,0] img2[0,0] ... img7[0,0]     ← 第 0 行, 第 0 列
  img0[0,1] img1[0,1] img2[0,1] ... img7[0,1]     ← 第 0 行, 第 1 列
  ...
  img0[0,2559] img1[0,2559] ... img7[0,2559]       ← 第 0 行, 第 2559 列
  img0[1,0] img1[1,0] ... img7[1,0]                ← 第 1 行, 第 0 列
  ...
```

**為什麼交錯？** 同一位置的 8 張圖片通常只有局部差異（如表情不同），大部分像素完全相同。交錯後連續像素高度重複，QOI 的 run-length 編碼可以一次跳過大量相同像素。

### 5.3 雙串流編碼

每個 band 使用兩個並行的資料串流：

```
┌─────────────────┐    ┌──────────────────────┐
│   QOI Stream    │    │  Distribution Data   │
│  (全域連續)      │    │  (per-band LZ4 壓縮)  │
│                 │    │                      │
│  每個符號編碼    │    │  每個符號附帶一個      │
│  一個像素顏色    │    │  mask (LEB128)        │
└─────────────────┘    └──────────────────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
            rc = qoi_count + mask
            連續 rc 個像素 = 該顏色
```

**QOI Stream**：類 QOI 格式，支援以下操作碼：
- `0xFE` + 3B：RGB（繼承前一像素的 alpha）
- `0xFF` + 4B：RGBA
- `0x00-0x3F`（2bit tag=00）：索引表查找（64 槽位）
- `0x40-0x7F`（2bit tag=01）：小差分 Δr/Δg/Δb ∈ [-2,+1]
- `0x80-0xBF`（2bit tag=10）：luma 差分（綠色基準 + r/b 偏移）
- `0xC0-0xFF`（2bit tag=11）：run-length（1~64 個重複）

**Distribution Data**：對每個 QOI 符號，記錄額外重複數 `mask`。實際像素數 = `qoi_count + mask`。例如 QOI 發出 run=3，mask=20，則該顏色覆蓋 23 個像素。

### 5.4 Band 解碼流程（虛擬碼）

```python
for band_idx in range(num_bands):
    # 計算本 band 的總像素數
    band_h = min(band_height, height - band_idx * band_height)
    total_interleaved = width * num_images * band_h

    # 解壓本 band 的 distribution data (LZ4)
    dist = decompress_lz4(dist_data, band_dist_sizes[band_idx])

    # 重置 QOI 狀態 + 跳過 2 個初始符號
    qoi.reset()
    qoi.decode_one()  # skip
    qoi.decode_one()  # skip

    # 跳過 dist 的第 1 個 LEB128 值
    skip_leb128(dist)

    # 主解碼迴圈
    pixels = []
    while len(pixels) < total_interleaved:
        color, qoi_count = qoi.decode_one()   # 從 QOI stream
        mask = read_leb128(dist)               # 從 dist data
        repeat_count = qoi_count + mask
        pixels.extend([color] * repeat_count)

    # 將交錯的像素拆分回各圖片
    flat = reshape(pixels, [band_h, width, num_images, 4])
    for img_idx in range(num_images):
        images[img_idx][band_y : band_y+band_h] = flat[:, :, img_idx, :]
```

---

## 6. DTBL (Distribution Table)

位於 QOI 串流之後，格式：`"DTBL" + uint32(size) + LEB128 data`。

每 band 存 2 個 LEB128 值，共 `num_bands × 2` 個：

```
DTBL[2i]     = 該 band 的 QOI 串流位元組數
DTBL[2i + 1] = 該 band 的 QOI 符號數量（= dist entry 數量）
```

ev104 的 DTBL：

```
Band  QOI Bytes    Symbols     累積 QOI Bytes   Avg px/sym
────  ──────────   ────────    ──────────────── ──────────
  0      794,370    508,013          794,370      14.5
  1      993,490    640,769        1,787,860      11.5
  2    1,153,650    676,603        2,941,510      10.9
  3    1,520,651    876,274        4,462,161       8.4
────  ──────────   ────────    ────────────────
Sum   4,462,161  2,701,659    ≈ total_qoi_bytes
```

**用途**：允許引擎跳過前面的 band，直接定位到特定 band 的 QOI 資料開始解碼（parallel decoding / partial rendering）。

---

## 7. RTBL (Run Table)

緊接 DTBL 之後，格式：`"RTBL" + uint32(size) + LEB128 data`。

存 `num_bands` 個 LEB128 值，每個值是該 band 的 LZ4 壓縮 dist data 大小：

```
Band  LZ4 Compressed Size
────  ───────────────────
  0          221,558
  1          242,436
  2          175,350
  3          193,028
────  ───────────────────
Sum          832,372
```

RTBL 之後緊接所有 band 的 LZ4 壓縮 dist data，依序排列。

---

## 8. LZ4 壓縮塊格式

每個 band 的 dist data 由多個 LZ4 塊組成：

```
每個塊：
  uint32 header:
    [31:16] input_size   (壓縮後大小)
    [15]    carryover    (是否使用前一塊作為字典)
    [14:0]  output_size  (解壓後大小, 0=32768)

  bytes[input_size] compressed_data
```

carryover=1 時，使用前一塊的解壓結果作為 LZ4 字典，提高跨塊壓縮率。

---

## 9. 壓縮效率分析

ev104（8 張 2560×1440 RGBA）：

```
原始大小：8 × 2560 × 1440 × 4 = 117,964,800 bytes (112.5 MB)
容器大小：5,294,676 bytes (5.05 MB)
壓縮比：22.3:1

其中：
  QOI 串流：4,462,166 bytes (84.3%)  ← 像素顏色
  Dist data：  832,372 bytes (15.7%)  ← 分布資訊
```

效率來源：
- 8 張圖交錯後，同位置像素高度重複 → QOI run-length 大量命中
- LZ4 壓縮 dist data 進一步縮小
- 圖片間差異越小（只換表情），壓縮比越高

---

## 10. 完整解碼流程

```
輸入：ev104aa.tlg（TLGref）

1. 讀取 TLGref
   → container = "ev104__n5djit.tlg", index = 1

2. 開啟容器，讀取 File Header
   → width=2560, height=1440, 確認 "QHDR" 存在

3. 解析 QHDR
   → num_images=8, band_height=360, num_bands=4

4. 定位 DTBL → 解析（可選，用於 seeking）
   定位 RTBL → 解析 band_dist_sizes[]
   定位 dist data 起始位置

5. 逐 band 解碼：
   a. 解壓該 band 的 dist data（LZ4）
   b. 從 QOI stream 讀取符號 + 從 dist 讀取 mask
   c. 展開為交錯像素序列
   d. 拆分到 8 張圖片的對應行

6. 取出 images[index=1]
   → 2560×1440 RGBA numpy array

7. 輸出 PNG
```

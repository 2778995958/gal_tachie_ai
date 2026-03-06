# decode_single.py — 單張 TLGqoi 解碼器

解碼 **standalone 單張 TLGqoi** 檔案（無容器、無分塊），如 `ev102ab.tlg`。

---

## 適用對象

不是所有 CG 都存在容器中。部分 CG 是獨立的單張 TLGqoi 檔案：

```
ev102ab.tlg   (11 MB, 3118×2458, 單張 TLGqoi)
ev203aa.tlg   (3.8 MB, standalone)
ev606aa.tlg   (4.3 MB, standalone)
```

這類檔案的特徵：
- 魔術數字為 `TLGqoi\x00raw\x1a`（與容器相同）
- **沒有 QHDR 標籤**（offset 0x14 不是 "QHDR"）
- 檔案較大（數 MB，不像 TLGref 只有 88 bytes）
- 直接包含一張圖片的 QOI 編碼資料

---

## 檔案結構

```
┌──────────────────────────────────────────────┐
│ "TLGqoi\x00raw\x1a"  (11 bytes)  魔術數字    │
│ channels (1 byte)                             │
│ width    (4 bytes, uint32 LE)                 │
│ height   (4 bytes, uint32 LE)                 │
├───────────────── offset 20 ────────────────── │
│ 8 bytes padding/unknown (通常為 0)            │
├───────────────── offset 28 ────────────────── │
│ QOI Stream（直到檔案結尾）                     │
│   純 QOI 編碼的像素資料                        │
│   無 DTBL / RTBL / LZ4 分布資料                │
│   無交錯（只有一張圖，不需要）                  │
└──────────────────────────────────────────────┘
```

與容器格式的差異：

| | 容器 (QHDR) | 單張 TLGqoi |
|---|---|---|
| 圖片數 | N 張交錯 | 1 張 |
| QOI 起始 | offset 28 + qhdr_size + 8 | offset 28 |
| 額外資料 | DTBL + RTBL + LZ4 dist | 無 |
| run-length | QOI count + dist mask | 純 QOI count |

---

## QOI 編碼格式

與容器中的 QOI Stream 完全相同的操作碼，但更簡單——沒有 distribution data 的加成，每個 run-length 就是實際像素數。

```
操作碼          編碼                    說明
──────────────  ──────────────────────  ──────────────────────
0xFE + 3B       RGB                     設定 R/G/B，繼承前一像素的 A
0xFF + 4B       RGBA                    設定 R/G/B/A
0x00~0x3F       INDEX (1B)              從 64 槽位的雜湊表取回像素
0x40~0x7F       DIFF (1B)               R/G/B 各 ±1 的小差分
0x80~0xBF       LUMA (2B)               以綠色為基準的亮度差分
0xC0~0xFF       RUN (1B)                重複前一像素 1~64 次
```

雜湊函數（索引表定位）：
```
hash = (R*3 + G*5 + B*7 + A*11) % 64
```

---

## 解碼流程

```python
def decode_qoi(data, pos, width, height):
    index = [(0,0,0,0)] * 64    # 64 槽位的顏色索引表
    px = (0, 0, 0, 255)          # 前一像素（初始黑色不透明）
    pixels = []

    while len(pixels) < width * height:
        b1 = data[pos]; pos += 1

        if b1 == 0xFE:                          # RGB
            px = (data[pos], data[pos+1], data[pos+2], px[3])
            pos += 3; count = 1

        elif b1 == 0xFF:                         # RGBA
            px = (data[pos], data[pos+1], data[pos+2], data[pos+3])
            pos += 4; count = 1

        elif (b1 & 0xC0) == 0x00:                # INDEX
            px = index[b1 & 0x3F]; count = 1

        elif (b1 & 0xC0) == 0x40:                # DIFF
            dr = ((b1>>4) & 3) - 2
            dg = ((b1>>2) & 3) - 2
            db = (b1 & 3) - 2
            px = ((px[0]+dr)&0xFF, (px[1]+dg)&0xFF, (px[2]+db)&0xFF, px[3])
            count = 1

        elif (b1 & 0xC0) == 0x80:                # LUMA
            b2 = data[pos]; pos += 1
            dg = (b1 & 0x3F) - 32
            dr = dg + ((b2>>4) & 0xF) - 8
            db = dg + (b2 & 0xF) - 8
            px = ((px[0]+dr)&0xFF, (px[1]+dg)&0xFF, (px[2]+db)&0xFF, px[3])
            count = 1

        else:                                    # RUN
            count = (b1 & 0x3F) + 1

        # 更新索引表
        index[(px[0]*3 + px[1]*5 + px[2]*7 + px[3]*11) % 64] = px

        # 輸出 count 個像素
        pixels.extend([px] * count)

    return pixels
```

---

## 注意事項

- 此腳本**不處理**容器格式（TLGqoi+QHDR），遇到會輸出錯誤圖片
- 此腳本**不處理**TLGref（88 bytes 的指標檔），會靜默失敗或輸出空圖
- 此腳本**不處理**TLGmux（立繪分塊格式），魔術數字不同會被跳過
- QOI 起始位置硬編碼為 offset 28，跳過了 header 中 offset 20~27 的 8 bytes

找了一輪，找到Chenx221大佬寫的(EscudeTools)[https://github.com/Chenx221/EscudeTools]

但對於不懂程序的人，只好全丟ai處理，換成python，經過一輪觀察應該可以了，雖然只能解圖

*  **執行命令**：

      * **只產生「無臉紅」版本：**
        在 `-s` 命令後加上 `-b 0`。輸出的檔名會像 `..._b0.png`。

        ```bash
        python escude_tools.py -s "C:\path\to\images" "C:\path\to\db.db" -b 0
        ```

      * **只產生「原始定義」版本：**
        在 `-s` 命令後加上 `-b 1`。輸出的檔名會像 `..._b1.png`。

        ```bash
        python escude_tools.py -s "C:\path\to\images" "C:\path\to\db.db" -b 1
        ```

      * **只產生「臉紅 B」版本：**
        在 `-s` 命令後加上 `-b 2`。輸出的檔名會像 `..._b2.png`。

        ```bash
        python escude_tools.py -s "C:\path\to\images" "C:\path\to\db.db" -b 2
        ```

      * **產生所有可用版本（預設行為）：**
        不加 `-b` 選項，行為和上一版一樣，會自動產生所有版本。

        ```bash
        python escude_tools.py -s "C:\path\to\images" "C:\path\to\db.db"
        ```

      * **合成 CG：**
        ```bash
        python escude_tools.py -c "C:\path\to\images" "C:\path\to\db.db"
        ```
        
      * **將 .bin 轉換為 .db：**
        ```bash
        python escude_tools.py -d "C:\path\to\your\data"
        ```

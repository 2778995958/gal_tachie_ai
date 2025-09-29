在立繪.py目錄下要有

1a.txt(pbd.json轉換)

1a.sinfo.txt(sinfo另存txt)

1a(所有1a部件資料夾)

批量自動做對應txt和sinfo的合拼


jsontxt.py用於把無密碼pbd轉txt

movepng.py只是方便搬編號的表情出來(例如臉紅.png)

yuzu立繪.py本體，一鍵合圖，不太完善(可能只用在柚子

檔名角色分資料夾.py如名

```
pbd拿到json，用jsontxt.py轉成txt，檔名刪.pbd(過程遺物，懶得改回去變成每次都要刪.pbd檔名最後就懂)
sinfo用[github.com] sinfotxt.py轉txt，留意txt有沒亂碼去改編碼
把立繪分類，第一個底線分資料夾
檔名角色分資料夾.py
月望a,月望b這樣
然後一個pbd對應一個sinfo
月望a.txt,月望a.sinfo.txt,月望b.sinfo.txt,月望b.txt
(如果沒刪.pbd會是月望a.pbd.txt然後執行不了)，沒叫gemini改

結構
images/
├── 月望a/
├── 月望b/
├── 月望a.txt
├── 月望a.sinfo.txt
├── 月望b.txt
└── 月望b.sinfo.txt
├── 檔名角色分資料夾.py
└── yuzu立繪.py

運行yuzu立繪.py合拼```

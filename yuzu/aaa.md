感覺開一帖比較好

首先，立繪目前只能裡站可看

然後，合立繪一定有坐標和說明規則，如果dump你會找到sinfo和pbd(tab分格)

最後，我立繪合成全都用gemini寫，所以不太能給人用，我原本就合完發e站不管，沒要教人，因為教得很差，而且想低調

正題

git庫:

[gal\_tachie\_ai](https://github.com/2778995958/gal_tachie_ai)

[柚子](https://github.com/2778995958/gal_tachie_ai/tree/main/yuzu)

[krkr](https://github.com/2778995958/gal_tachie_ai/tree/main/krkr)

先說參考過的大佬，即一般做法

cg那個json也是坐標，不知為什麼沒人用，sd的mtn也有，但很多層子母層圖gemini還沒做到，cg有興趣請看*composite\_images.py*，這邊的pimg和mtn丟FreeMote/PsbDecompile才有json和圖，我發e站也是用這坐標搓的cg合成，但這帖不說這個

[《天使騒々RE-BOOT!》解包及CG、立绘合成浅谈](https://www.bilibili.com/read/cv23429919/?from=search\&spm_id_from=333.337.0.0\&jump_opus=1)，讓我了解結構

[吉里吉里立绘合成](https://www.bilibili.com/read/cv17622983/?spm_id_from=333.999.0.0\&jump_opus=1)，讓我了解pbd sinfo關係

對，因為一個一個合，只能說可勉強用，所以我自己搓ai合成

<br />

pbd要用大佬的pbd2json.exe，我留了一個已經是歷史文物請在krkr裡找

批量for %i in (\*.pbd) do (pbd2json.exe %i)

如果你想一步步來可以先試其他大佬的一個一個弄，才再看我的

流程

KirikiriTools去dump立繪所有角色，只刷姿勢就好，主要拿pbd有分姿勢

如果你有看狠狠厥烂KiriKiriZ Cxdec拆包，我的回覆你拿到pbd就懂我做了什麼

linuxdo那邊要驗證，這邊來回一下感謝大佬的思路

我在做立繪，所以很難拿全部立繪檔，看了一下這思路

dump一次遊戲拿到角色pbd檔，一般tlg立繪是檔名+圖id.tlg

pbd有圖id，檔名就是pbd底線前綴，可以一下子搞全立繪tlg檔了

pbd大約這樣，layer\_id是圖id，appconfig.tjs用utf-16

```javascript
#layer_type	name	left	top	width	height	type	opacity	visible	layer_id	group_layer_id
				3117	4409					
0	op1	885	230	1063	4106	13	255	1	2115	
0	眉d	1469	669	236	82	13	255	1	2113	2010
0	眉c2	1467	697	211	162	13	255	1	2108	2010
0	眉c	1467	697	211	162	13	255	1	2103	2010
0	眉b	1469	669	236	82	13	255	1	2098	2010
0	眉a	1466	679	226	98	13	255	1	2048	2010
...
```

```javascript
...
try { Scripts.evalStorage("tyozc01_l_2255.tlg"); }
catch{}
try { Scripts.evalStorage("tyozc01_l_2256.tlg"); }
catch{}
try { Scripts.evalStorage("tyozc01_l_2257.tlg"); }
catch{}
try { Scripts.evalStorage("tyozc01_l_586.tlg"); }
catch{}
System.exit();
```


pbd拿到json，用*jsontxt.py*轉成txt，檔名刪.pbd(過程遺物，懶得改回去變成每次都要刪.pbd檔名最後就懂)

把以上txt拖去*generate\_dumper\_appconfig.py*(在krkr的git)，會得到appconfig.tjs

把appconfig.tjs丟去遊戲能拿全部tlg立繪圖=KirikiriTools用法(前一步txt沒刪.pbd檔名，會沒東西拿到)

用garbro Create archive，勾起retain discretion structure(保留資料夾結構)，轉無加密xp3，然後再打開xp3導出png

sinfo用*sinfotxt.py*轉txt，留意txt有沒亂碼去改編碼(可嘗試用復原txt.py或修改py指定編碼)，pbd用之前的txt就好不用再轉

用*檔名角色分資料夾.py*把立繪分類，最後一個底線分資料夾

月望a,月望b這樣

然後一個pbd對應一個sinfo

月望a.txt,月望a.sinfo.txt,月望b.sinfo.txt,月望b.txt

(如果沒刪.pbd會是月望a.pbd.txt然後執行不了)，沒叫gemini改(能用不管了)

結構

```
images/
├── output
├── 月望a/*零件.png
├── 月望b/*零件.png
├── 月望a.txt
├── 月望a.sinfo.txt
├── 月望b.txt
└── 月望b.sinfo.txt
├── 檔名角色分資料夾.py
└── yuzu立繪.py
```

運行*yuzu立繪.py*合拼

這個只能合柚子，其他krkr理論上也有各種解說，主要是看懂sinfo結構

理論上sinfo不會寫2種臉紅，例如只有弱臉紅，有需要則要自己改強臉紅

有編碼問題請在yuzu立繪.py裡改裡面的encoding，有2個對應sinfo,pbd，不懂就問ai，或者改txt那邊

柚子只有dress和face相對簡單

像紫社要用krkr那邊，有組合結構fgname,fgalias

我一般所有立繪py都在裡面，不過全都只是基於我習慣去用

想了解可以把整個code丟給ai，第一行寫"分析"，第二行胋code

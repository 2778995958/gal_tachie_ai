"""
hxv4 自動反混淆腳本
自動搜尋關鍵檔案並還原 hxv4 混淆的檔案名稱

用法: python auto_deobf.py <Extractor_Output目錄> [--dry-run] [--skip-psb]
  <目錄>       提取輸出的根目錄（包含 data, voice, patch 等子目錄）
  --dry-run    只顯示會重命名的檔案，不實際執行
  --skip-psb   跳過 PSB 反編譯（較慢但能找到更多檔名）
"""

import argparse
import csv
import ctypes
import io
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from itertools import product
from pathlib import Path
from contextlib import suppress

# 修正 Windows 終端編碼問題
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# === 配置 ===
TOOL_DIR = Path(__file__).resolve().parent
DLL_PATH = TOOL_DIR / "binaries" / "KrkrHxv4Hash.dll"
PSBDECOMPILE_EXE = TOOL_DIR / "binaries" / "psb_decompile" / "PsbDecompile.exe"
PBD2JSON_EXE = TOOL_DIR / "binaries" / "pbd2json.exe"
TEMP_DIR = TOOL_DIR / "temp"
PSB_TYPE_CACHE_PKL = TEMP_DIR / "psb_type_cache.pkl"

# === 解析命令列 ===
parser = argparse.ArgumentParser(description="hxv4 自動反混淆工具")
parser.add_argument("target_dir", help="Extractor_Output 目錄路徑")
parser.add_argument("--dry-run", action="store_true", help="模擬模式，不實際重命名")
parser.add_argument("--skip-psb", action="store_true", help="跳過 PSB 反編譯")
parser.add_argument("--clean-lst", action="store_true", help="完成後生成乾淨的 HxNames_clean*.lst")
parser.add_argument("--clean-lst-only", action="store_true", help="只生成乾淨的 HxNames_clean*.lst，跳過反混淆")
parser.add_argument("--dict-only", action="store_true", help="只用 lst/txt 字典重命名，跳過所有檔案解析")
args = parser.parse_args()

TARGET_DIR = Path(args.target_dir).resolve()
if not TARGET_DIR.is_dir():
    print(f"錯誤：目錄不存在 - {TARGET_DIR}")
    sys.exit(1)

HXNAMES_FILE = TARGET_DIR / "HxNames.lst"

# 要掃描的 xp3 提取目錄（排除工具目錄和 .alst 檔案）
EXCLUDE_NAMES = {"hxv4_deobf_tools-master"}
XP3_DIRS = [d for d in TARGET_DIR.iterdir()
            if d.is_dir() and d.name not in EXCLUDE_NAMES and not d.name.endswith(".alst")]

# === 初始化 Hash 函式 ===
if not DLL_PATH.exists():
    print(f"錯誤：找不到 {DLL_PATH}")
    sys.exit(1)

mylib = ctypes.CDLL(str(DLL_PATH.resolve()))
mylib.get_filename_hash.argtypes = [ctypes.c_wchar_p]
mylib.get_filename_hash.restype = ctypes.POINTER(ctypes.c_uint8)
mylib.get_path_hash.argtypes = [ctypes.c_wchar_p]
mylib.get_path_hash.restype = ctypes.c_uint64


def get_file_hash(filename: str) -> str:
    buf = ctypes.create_string_buffer(filename.encode("utf-16le") + b"\x00\x00")
    ptr = ctypes.cast(buf, ctypes.c_wchar_p)
    arr_ptr = mylib.get_filename_hash(ptr)
    return "".join(f"{arr_ptr[i]:02X}" for i in range(32))


def get_path_hash(pathname: str) -> str:
    buf = ctypes.create_string_buffer(pathname.encode("utf-16le") + b"\x00\x00")
    ptr = ctypes.cast(buf, ctypes.c_wchar_p)
    num = mylib.get_path_hash(ptr)
    return f"{num:016X}"


def is_file_hash(name: str) -> bool:
    return len(name) == 64 and all(c.isdigit() or c.isupper() for c in name)


def is_path_hash(name: str) -> bool:
    return len(name) == 16 and all(c.isdigit() or c.isupper() for c in name)


# === 字典集合 ===
filename_plaintexts: set[str] = set()
pathname_plaintexts: set[str] = set()

# 種子路徑名
KNOWN_PATHS = [
    "/", "main/", "scenario/", "scn/", "thum/", "bgimage/", "sound/", "bgm/",
    "voice/", "fgimage/", "evimage/", "image/", "video/", "system/",
    "locale/", "locale/jp/", "locale/en/", "locale/cn/", "locale/tw/",
    "chthum/", "thum/chthum/", "sysscn/", "rule/", "font/", "uipsd/",
    "se/", "movie/", "config/", "savedata/", "plugin/", "motion/",
]
pathname_plaintexts.update(KNOWN_PATHS)

# 種子檔名
SEED_FILENAMES = [
    "base.stage", "cglist.csv", "soundlist.csv", "charvoice.csv",
    "imagediffmap.csv", "savelist.csv", "scenelist.csv",
    "replay.ks", "_chthum_index.pbd", "exchview.ini",
    "initialize.tjs", "startup.tjs", "override.tjs", "envinit.tjs",
    "gameconfig.tjs", "AfterInit.tjs", "phase.tjs", "env.tjs",
    "scnchartdata.tjs", "imageevalmap.csv", "imagenamemap.txt",
    "imagemulti.txt", "imagepropmap.txt", "imagedressmap.txt",
    "sysse.ini", "systrans.ini", "anim_title.ini",
    "filegain.csv", "soundgain.csv",
]
filename_plaintexts.update(SEED_FILENAMES)


# === 工具函式 ===

def find_file_by_hash(file_hash: str, plaintext_name: str = "") -> str | None:
    """搜尋檔案：先找 hash 名，再找明文名（已被重命名的情況）"""
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            if file_hash in files:
                return os.path.join(root, file_hash)
            if plaintext_name and plaintext_name in files:
                return os.path.join(root, plaintext_name)
    return None


def safe_read_csv(filepath: str):
    for enc in ("utf-16le", "utf-8-sig", "utf-8", "shift_jis"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return list(csv.reader(f.read().splitlines()))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []


def safe_read_text(filepath: str) -> str:
    for enc in ("utf-16le", "utf-8-sig", "utf-8", "shift_jis"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ""


def convert_ext(filename: str, new_ext: str) -> str:
    if not new_ext.startswith("."):
        new_ext = "." + new_ext
    if "." in filename and not filename.startswith("."):
        base = ".".join(filename.split(".")[:-1])
    else:
        base = filename
    return base + new_ext


def get_unique_name(dest_path: str) -> str:
    base, ext = os.path.splitext(dest_path)
    counter = 1
    new_path = dest_path
    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{ext}"
        counter += 1
    return new_path


def merge_dir(src: str, dest: str):
    import hashlib as hl

    def files_identical(fp1, fp2, chunk=8192):
        if os.path.getsize(fp1) != os.path.getsize(fp2):
            return False
        h1, h2 = hl.blake2b(), hl.blake2b()
        with open(fp1, "rb") as f1, open(fp2, "rb") as f2:
            while True:
                b1, b2 = f1.read(chunk), f2.read(chunk)
                if not b1 and not b2:
                    break
                h1.update(b1)
                h2.update(b2)
        return h1.digest() == h2.digest()

    for item in os.listdir(src):
        src_item = os.path.join(src, item)
        dest_item = os.path.join(dest, item)
        if os.path.exists(dest_item):
            if os.path.isdir(src_item) and os.path.isdir(dest_item):
                merge_dir(src_item, dest_item)
            elif os.path.isfile(src_item) and os.path.isfile(dest_item):
                if files_identical(src_item, dest_item):
                    os.remove(src_item)
                else:
                    shutil.move(src_item, get_unique_name(dest_item))
            else:
                shutil.move(src_item, get_unique_name(dest_item))
        else:
            shutil.move(src_item, dest_item)
    if not os.listdir(src):
        os.rmdir(src)


# === 字典來源函式 ===

def from_cglist_csv(filepath: str):
    rows = safe_read_csv(filepath)
    count = 0
    for row in rows:
        if not row:
            continue
        cg_filename = row[0].strip().lower()
        if cg_filename.startswith("#") or ":" in cg_filename:
            continue
        cg_name = cg_filename.replace("thum_", "")
        filename_plaintexts.update([
            f"{cg_filename}.jpg", f"{cg_filename}.png", f"{cg_filename}.tlg",
            f"{cg_filename}_censored.jpg", f"{cg_filename}_censored.png",
            f"{cg_filename}_censored.tlg",
            f"{cg_filename}.psb", f"{cg_filename}_censored.psb",
            f"{cg_filename}.pimg", f"{cg_filename}_censored.pimg",
            f"{cg_name}.tlg", f"{cg_name}.png", f"{cg_name}.pimg",
            f"{cg_name}_censored.tlg", f"{cg_name}_censored.png",
            f"{cg_name}_censored.pimg",
        ])
        count += 1
        if cg_filename.startswith("thum_"):
            filename_plaintexts.update([
                f"save{cg_filename}.jpg", f"save{cg_filename}.png",
                f"save{cg_filename}.psb",
            ])
        if cg_filename.startswith("thum_ev"):
            for cg_diffs in row[1:]:
                for cg_diff in cg_diffs.replace("*", "").split("|"):
                    cg_diff = cg_diff.strip().replace("\t", "")
                    if not cg_diff.startswith(cg_name):
                        continue
                    pos = cg_diff.find(cg_name) + len(cg_name)
                    for end in range(pos, len(cg_diff) + 1):
                        fn = f"{cg_name}{cg_diff[pos:end]}"
                        for loc in ("", "_en", "_cn", "_tw"):
                            filename_plaintexts.update([
                                f"{fn}{loc}.pimg", f"{fn}{loc}_censored.pimg",
                                f"{fn}{loc}.tlg", f"{fn}{loc}_censored.tlg",
                                f"thum_{fn}.png", f"thum_{fn}.jpg",
                                f"thum_{fn}_censored.png", f"thum_{fn}_censored.jpg",
                                f"savethum_{fn}.png", f"savethum_{fn}.jpg",
                                f"{fn}{loc}.psb", f"{fn}{loc}_censored.psb",
                                f"thum_{fn}.psb", f"thum_{fn}_censored.psb",
                                f"savethum_{fn}.psb", f"{fn}{loc}.png",
                            ])
        if cg_filename.startswith("thum_sd"):
            sd_name = cg_filename[5:]
            filename_plaintexts.update([f"{sd_name}.mtn", f"{sd_name}.psb"])
            for sd_diff in row[1:]:
                sd_diff = sd_diff.strip().replace("\t", "")
                if not sd_diff:
                    continue
                for loc in ("", "_en", "_cn", "_tw"):
                    filename_plaintexts.update([
                        f"{sd_diff}{loc}.jpg", f"{sd_diff}{loc}.png",
                        f"{sd_diff}{loc}.tlg", f"{sd_diff}{loc}.pimg",
                        f"{sd_diff}{loc}.asd", f"{sd_diff}{loc}.psb",
                        f"{sd_diff}{loc}_censored.jpg", f"{sd_diff}{loc}_censored.png",
                        f"{sd_diff}{loc}_censored.tlg", f"{sd_diff}{loc}_censored.pimg",
                    ])
    print(f"  [cglist.csv] 提取了 {count} 個 CG 條目")


def from_soundlist_csv(filepath: str):
    rows = safe_read_csv(filepath)
    count = 0
    for row in rows:
        if row and not row[0].startswith("#"):
            h = row[0]
            filename_plaintexts.update([
                f"{h}.opus", f"{h}.opus.sli", f"{h}.ogg", f"{h}.ogg.sli",
                f"{h}.mchx", f"{h}.mchx.sli",
            ])
            count += 1
    print(f"  [soundlist.csv] 提取了 {count} 個音效條目")


def from_charvoice_csv(filepath: str):
    rows = safe_read_csv(filepath)
    suffixes = (
        "after", "attention0", "attention1", "attention2", "attention3",
        "backlog", "chart", "config", "config_easy", "custom", "dialog",
        "end", "extra", "extra_bu", "extra_cg", "extra_scene", "game", "game2",
        "goodbye", "jump", "load", "mouse", "pad", "rec", "reset", "save",
        "shortcut", "sound", "text", "tittle", "tittleback", "voice", "volume",
        "window", "yuzu", "title", "titleback",
    )
    count = 0
    for row in rows:
        if not row:
            continue
        header = row[0].replace("\ufeff", "")
        if not header.startswith("#") and not header.startswith("DEFAULT") and len(row) > 1:
            prefix = row[1].split("_")[0]
            for s in suffixes:
                filename_plaintexts.add(f"{prefix}_{s}.ogg")
            count += 1
    print(f"  [charvoice.csv] 提取了 {count} 個角色語音前綴")


def from_imagediffmap_csv(filepath: str):
    rows = safe_read_csv(filepath)
    count = 0
    for row in rows:
        if not row or len(row) < 2:
            continue
        header = row[0].replace("\ufeff", "")
        if header.startswith("#"):
            continue
        fn = row[1]
        if "." in fn:
            names_part, ext = fn.split(".", 1)
            for name in names_part.split("|"):
                filename_plaintexts.add(f"{name}.{ext}")
        else:
            filename_plaintexts.update([
                f"{fn}.pimg", f"{fn}_censored.pimg",
                f"savethum_{fn}.jpg", f"savethum_{fn}.png",
                f"{fn}.psb", f"{fn}_censored.psb", f"savethum_{fn}.psb",
            ])
        count += 1
    print(f"  [imagediffmap.csv] 提取了 {count} 個圖片差分條目")


def from_savelist_csv(filepath: str):
    rows = safe_read_csv(filepath)
    count = 0
    for row in rows:
        if not row:
            continue
        header = row[0].replace("\ufeff", "")
        if header.startswith("#"):
            continue
        fn = row[0]
        filename_plaintexts.update([
            f"{fn}.jpg", f"{fn}.png",
            f'{fn.replace("savethum_", "thum_")}.jpg',
            f'{fn.replace("savethum_", "thum_")}.png',
            f"{fn}.psb", f'{fn.replace("savethum_", "thum_")}.psb',
        ])
        count += 1
    print(f"  [savelist.csv] 提取了 {count} 個存檔條目")


def from_scenelist_csv(filepath: str):
    rows = safe_read_csv(filepath)
    count = 0
    for row in rows:
        if not row:
            continue
        header = row[0].replace("\ufeff", "")
        if header.startswith("#") or ":" in header:
            continue
        for fn in row[0].split("|"):
            filename_plaintexts.update([
                f"{fn}.jpg", f"{fn}.png",
                f"{fn}_censored.jpg", f"{fn}_censored.png",
                f"{fn}.psb", f"{fn}_censored.psb",
            ])
        count += 1
    print(f"  [scenelist.csv] 提取了 {count} 個場景條目")


def from_base_stage(filepath: str):
    try:
        sys.path.insert(0, str(TOOL_DIR))
        sys.path.insert(0, str(TOOL_DIR / "utils"))
        from utils.tjs_parser import parse_base_stage_to_json5
        import json5 as json5_mod

        content = safe_read_text(filepath)
        base_stage = json5_mod.loads(parse_base_stage_to_json5(content))
        time_prefixes, season_prefixes = {""}, {""}
        for key, value in base_stage.items():
            if isinstance(value, dict):
                if key == "times":
                    for t in value.values():
                        time_prefixes.add(t.get("prefix"))
                elif key == "seasons":
                    for s in value.values():
                        season_prefixes.add(s.get("prefix"))
        count = 0
        for stage in base_stage["stages"].values():
            tmpl = stage["image"]
            for tp, sp in product(time_prefixes, season_prefixes):
                if tp is not None and sp is not None:
                    img = tmpl.replace("TIME", tp).replace("SEASON", sp)
                    # Also generate lowercase prefix variant (SCN uses lowercase)
                    img_lower = tmpl.replace("TIME", tp.lower()).replace("SEASON", sp.lower())
                    for im in {img, img_lower}:
                        filename_plaintexts.update([
                            f"{im}.png", f"{im}.jpg", f"{im}.tlg",
                            f"bgthum_{im}.jpg", f"bgthum_{im}.png",
                        ])
                    count += 1
        print(f"  [base.stage] 提取了 {count} 個背景圖條目")
    except Exception:
        print(f"  [base.stage] 解析失敗:")
        traceback.print_exc()


def from_replay_ks(filepath: str):
    content = safe_read_text(filepath)
    if not content:
        print("  [replay.ks] 無法讀取")
        return
    content = content.replace("\ufeff", "")
    movie_names = ["op"]
    languages = ("en", "cn", "tw")
    extensions = ("mp4", "wmv")
    pattern = r'\[(?:sysmovie|edmovie)\s+file=([^\s\]]+)\s*\]'
    movie_names.extend(re.findall(pattern, content))
    for name, lang, ext in product(movie_names, languages, extensions):
        filename_plaintexts.update([
            f"{name}.{ext}", f"{lang}_{name}.{ext}",
            f"{name}1080.{ext}", f"{lang}_{name}1080.{ext}",
            f"{name}_1080.{ext}", f"{lang}_{name}_1080.{ext}",
            f"{name}720p.{ext}", f"{lang}_{name}720p.{ext}",
        ])
    print(f"  [replay.ks] 提取了 {len(movie_names)} 個影片名稱")


# === PSB 掃描 ===

def is_psb_file(path) -> bool:
    path = Path(path)
    if not path.is_file():
        return False
    try:
        with path.open("rb") as f:
            header = f.read(3)
            return header in (b"PSB", b"mdf")
    except OSError:
        return False


def handle_voice(raw: str):
    base_exts = {"ogg", "ogg.sli", "opus", "opus.sli", "ini"}
    for vf in raw.split("|"):
        if "." in vf:
            vname, ext = vf.split(".", 1)
        else:
            vname, ext = vf, None
        exts = base_exts.copy()
        if ext is not None:
            exts.add(ext)
        for e in exts:
            filename_plaintexts.add(f"{vname}.{e}")


def handle_data_item(item: dict):
    if item.get("name") in ("bgm", "live", "liveout") and "replay" in item:
        fn = item["replay"].get("filename")
        if fn:
            filename_plaintexts.update([
                f"{fn}.ogg", f"{fn}.ogg.sli", f"{fn}.opus", f"{fn}.opus.sli",
                f"{fn}.mchx", f"{fn}.mchx.sli",
            ])
    elif item.get("name") in ("lse", "lse2", "se", "se2") and "replay" in item:
        fn_raw = item["replay"].get("filename")
        if fn_raw:
            for fn in fn_raw.split("|"):
                filename_plaintexts.update([f"{fn}.ogg", f"{fn}.ogg.sli", f"{fn}.ini"])
    elif item.get("name") == "stage" and "redraw" in item:
        fn = item["redraw"]["imageFile"]["file"]
        filename_plaintexts.update([
            f"{fn}.png", f"{fn}.jpg", f"{fn}.tlg",
            f"bgthum_{fn}.jpg", f"bgthum_{fn}.png",
        ])
    elif item.get("class") in ("msgwin", "character"):
        sname = None
        if "redraw" in item:
            sname = item["redraw"]["imageFile"]["file"]
            if "clip" in item["redraw"]:
                filename_plaintexts.add(f'{item["redraw"]["clip"]["image"]}.png')
        elif "stand" in item:
            sname = item["stand"]["file"]
        if isinstance(sname, str) and sname.endswith(".stand"):
            filename_plaintexts.add(sname)
    elif item.get("class") == "event":
        if item.get("name") == "ev" and "redraw" in item:
            filename_plaintexts.add(f'{item["redraw"]["imageFile"]["file"]}.png')
        elif item.get("name") == "bg_voice" and "redraw" in item:
            try:
                filename_plaintexts.add(item["redraw"]["imageFile"]["file"]["storage"])
            except (KeyError, TypeError):
                pass
    elif item.get("class") == "phonechat" and item.get("name") == "phonescreen" and "redraw" in item:
        filename_plaintexts.add(f'{item["redraw"]["imageFile"]["file"]}.tlg')
    elif item.get("class") == "sdlayer" and "redraw" in item:
        filename_plaintexts.add(f'{item["redraw"]["imageFile"]["file"]}.png')
    elif item.get("class") in ("event2", "stage2") and "redraw" in item:
        fn = None
        if "clip" in item["redraw"]:
            fn = item["redraw"]["clip"]["image"]
        elif "imageFile" in item["redraw"]:
            fn = item["redraw"]["imageFile"]["file"]
        if fn:
            filename_plaintexts.add(f"{fn}.png")


def handle_data_block(block: list):
    for data in block:
        if isinstance(data, list):
            for it in data:
                if isinstance(it, dict):
                    handle_data_item(it)


def scan_psb_and_decompile():
    if not PSBDECOMPILE_EXE.exists():
        print("  [PSB] PsbDecompile.exe 不存在，跳過")
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    psb_type_cache = {"scn": set(), "pimg": set(), "motion": set()}
    if PSB_TYPE_CACHE_PKL.exists():
        with suppress(pickle.UnpicklingError, EOFError):
            with open(PSB_TYPE_CACHE_PKL, "rb") as f:
                psb_type_cache = pickle.load(f)

    scn_count = 0
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for file in files:
                filepath = os.path.join(root, file)
                file_prefix = Path(root).name + "_"
                cache_key = file_prefix + file

                if not is_psb_file(filepath):
                    continue
                if cache_key in psb_type_cache["pimg"] or cache_key in psb_type_cache["motion"]:
                    continue

                try:
                    json_fn = file_prefix + convert_ext(file, ".json")
                    json_fp = os.path.join(TEMP_DIR, json_fn)

                    if not os.path.exists(json_fp):
                        tmp_fp = os.path.join(TEMP_DIR, cache_key)
                        shutil.copy(filepath, tmp_fp)
                        subprocess.run(
                            [str(PSBDECOMPILE_EXE), "-raw", tmp_fp],
                            check=True, capture_output=True, text=True,
                        )
                        if os.path.exists(tmp_fp):
                            os.remove(tmp_fp)
                        resx = os.path.join(TEMP_DIR, file_prefix + convert_ext(file, ".resx.json"))
                        if os.path.exists(resx):
                            os.remove(resx)

                    if not os.path.exists(json_fp):
                        continue

                    with open(json_fp, "r", encoding="UTF-8") as jf:
                        psb_json = json.load(jf)

                    if "scenes" in psb_json and "name" in psb_json:
                        psb_type_cache["scn"].add(cache_key)
                        filename_plaintexts.add(f"{psb_json['name']}.scn")
                        scn_count += 1

                        for scene in psb_json["scenes"]:
                            if "texts" not in scene:
                                continue
                            for text in scene["texts"]:
                                for ti in text:
                                    if isinstance(ti, list):
                                        for sub in ti:
                                            if isinstance(sub, dict) and "voice" in sub:
                                                handle_voice(sub["voice"])
                                    elif isinstance(ti, dict):
                                        if "data" in ti:
                                            handle_data_block(ti["data"])
                                        if "phonechat" in ti:
                                            for chat in ti["phonechat"]:
                                                if isinstance(chat, dict):
                                                    icon = chat.get("icon")
                                                    if icon:
                                                        filename_plaintexts.add(f"chaticon_{icon}.png")
                                                    stamp = chat.get("stamp")
                                                    if stamp:
                                                        filename_plaintexts.add(f"{stamp}.png")
                                        if "loopVoiceList" in ti:
                                            for lv in ti["loopVoiceList"]:
                                                handle_voice(lv["voice"])

                            for line in scene["lines"]:
                                if isinstance(line, list):
                                    for idx, li in enumerate(line):
                                        if isinstance(li, dict) and "data" in li:
                                            handle_data_block(li["data"])
                                        elif isinstance(li, list):
                                            for it in li:
                                                if isinstance(it, dict):
                                                    handle_data_item(it)
                                        elif isinstance(li, str) and line[idx - 1] == "voice":
                                            handle_voice(li)

                    elif "height" in psb_json and "width" in psb_json:
                        psb_type_cache["pimg"].add(cache_key)
                        os.remove(json_fp)
                    elif psb_json.get("id") == "motion":
                        psb_type_cache["motion"].add(cache_key)
                        os.remove(json_fp)
                    else:
                        os.remove(json_fp)
                except Exception:
                    traceback.print_exc()

    with open(PSB_TYPE_CACHE_PKL, "wb") as f:
        pickle.dump(psb_type_cache, f)

    for item in TEMP_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)

    print(f"  [PSB] 掃描了 {scn_count} 個 SCN 檔案")


def from_bgv_csv():
    count = 0
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for file in files:
                if not (file.startswith("bgv") and file.endswith(".csv")):
                    continue
                rows = safe_read_csv(os.path.join(root, file))
                for row in rows:
                    if row and not row[0].replace("\ufeff", "").startswith("#") and len(row) > 2:
                        vn = row[2]
                        filename_plaintexts.update([
                            f"{vn}.ogg", f"{vn}.ogg.sli",
                            f"{vn}.opus", f"{vn}.opus.sli", f"{vn}.ini",
                        ])
                        count += 1
    if count:
        print(f"  [bgv_csv] 提取了 {count} 個背景語音條目")


def from_stand_files():
    count = 0
    for xp3_dir in XP3_DIRS:
        for child in Path(xp3_dir).rglob("*.stand"):
            if child.is_file():
                content = safe_read_text(str(child))
                for fn in re.findall(r"filename:'([^']+)'", content):
                    filename_plaintexts.update([
                        f"{fn}.pbd", f"{fn}.sinfo", f"{fn}_0.pbd", f"{fn}_0.sinfo",
                        f"{fn}_info.txt",
                    ])
                    count += 1
    # Also add common fgimage utility files
    filename_plaintexts.update([
        "charlist.csv", "standlevel.tjs", "facepos.txt", "facepos.csv",
    ])
    if count:
        print(f"  [stand] 提取了 {count} 個立繪條目")


def from_pbd_files():
    """從 .stand 引用的 pbd 檔案中提取 tlg 圖層檔名"""
    if not PBD2JSON_EXE.exists():
        print("  [pbd] pbd2json.exe 不存在，跳過")
        return

    pbd_names = set()
    for xp3_dir in XP3_DIRS:
        for child in Path(xp3_dir).rglob("*.stand"):
            if child.is_file():
                content = safe_read_text(str(child))
                for fn in re.findall(r"filename:'([^']+)'", content):
                    pbd_names.add(fn)

    count = 0
    for pbd_name in pbd_names:
        # Check both .pbd and _0.pbd variants
        for pbd_suffix in [".pbd", "_0.pbd"]:
            pbd_fn = f"{pbd_name}{pbd_suffix}"
            pbd_hash = get_file_hash(pbd_fn)
            pbd_path = None
            for xp3_dir in XP3_DIRS:
                for root, _, files in os.walk(xp3_dir):
                    if pbd_hash in files:
                        pbd_path = os.path.join(root, pbd_hash)
                        break
                    if pbd_fn in files:
                        pbd_path = os.path.join(root, pbd_fn)
                        break
                if pbd_path:
                    break

            if not pbd_path or not os.path.exists(pbd_path):
                continue

            with open(pbd_path, "rb") as f:
                hdr = f.read(7)
            if hdr != b"TJS/4s0":
                continue

            # Determine output prefix: 梓a for .pbd, 梓a_0 for _0.pbd
            out_prefix = pbd_name if pbd_suffix == ".pbd" else f"{pbd_name}_0"

            try:
                r = subprocess.run(
                    [str(PBD2JSON_EXE), str(Path(pbd_path).resolve())],
                    capture_output=True, text=True, check=True,
                )
                if r.stdout:
                    pbd_json = json.loads(r.stdout)
                    for item in pbd_json:
                        if isinstance(item, dict) and "layer_id" in item:
                            lid = item["layer_id"]
                            filename_plaintexts.update([
                                f"{out_prefix}_{lid}.tlg",
                                f"{out_prefix}_{lid}.png",
                            ])
                            count += 1
            except Exception:
                pass

    if count:
        print(f"  [pbd] 提取了 {count} 個 tlg 圖層檔名")


def from_chthum_index():
    """從 _chthum_index.pbd 提取角色縮圖檔名 (chthum_xxx_hash.png)"""
    seed = "_chthum_index.pbd"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    count = 0
    try:
        with open(found, "rb") as f:
            data = f.read()
        # Extract chthum_ strings from binary
        i = 0
        while i < len(data) - 10:
            if data[i:i+2] == b'c\x00' and data[i+2:i+4] == b'h\x00':
                end = i
                while end < len(data) - 1:
                    if data[end] == 0 and data[end+1] == 0:
                        break
                    end += 2
                try:
                    s = data[i:end].decode("utf-16le").strip()
                    if s.startswith("chthum_") and len(s) > 10:
                        for ext in (".png", ".jpg"):
                            filename_plaintexts.add(f"{s}{ext}")
                        filename_plaintexts.add(s)
                        count += 1
                except (UnicodeDecodeError, ValueError):
                    pass
            i += 2
    except Exception:
        pass
    if count:
        print(f"  [chthum] 提取了 {count} 個角色縮圖檔名")


def from_uipsd_files():
    """從已命名的 uipsd 檔案推導多語言變體"""
    uipsd_bases = set()
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            if "uipsd" not in root.lower():
                continue
            for f in files:
                m = re.match(
                    r"^(.+?)(?:_(?:jp|en|cn|tw))?(?:__(?:bg\d+|pack))?\.(?:pbd|tlg)$", f
                )
                if m:
                    uipsd_bases.add(m.group(1))
    count = 0
    suffixes = [
        ".pbd", "__bg0.tlg", "__pack.tlg",
        "_jp.pbd", "_jp__pack.tlg",
        "_en.pbd", "_en__pack.tlg",
        "_cn.pbd", "_cn__pack.tlg",
        "_tw.pbd", "_tw__pack.tlg",
    ]
    for bn in uipsd_bases:
        for sfx in suffixes:
            fn = f"{bn}{sfx}"
            filename_plaintexts.add(fn)
            count += 1
    if count:
        print(f"  [uipsd] 從 {len(uipsd_bases)} 個 UI 基底名生成了 {count} 個檔名")


def from_tlgref_files():
    """從 TLGref 檔案中提取嵌入的被引用檔名"""
    import struct as st
    count = 0
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    with open(fp, "rb") as fh:
                        hdr = fh.read(0x80)
                    if len(hdr) < 0x30 or hdr[:6] != b"TLGref":
                        continue
                    raw = hdr[0x2c:]
                    chars = []
                    for i in range(0, len(raw) - 1, 2):
                        code = st.unpack_from("<H", raw, i)[0]
                        if code == 0:
                            break
                        if 0x20 <= code < 0x10000:
                            chars.append(chr(code))
                        else:
                            chars = []
                            break
                    name = "".join(chars)
                    if name and ".tlg" in name:
                        filename_plaintexts.add(name)
                        count += 1
                except OSError:
                    pass
    if count:
        print(f"  [tlgref] 提取了 {count} 個被引用的 TLG 檔名")


def bruteforce_ev_sd():
    """暴力窮舉 ev/sd 差分圖層的所有 a-z 組合"""
    # 收集已知的 ev/sd 基底名
    ev_bases = set()
    sd_bases = set()
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for f in files:
                m = re.match(r"^(ev\d+)", f, re.I)
                if m:
                    ev_bases.add(m.group(1).lower())
                m = re.match(r"^(sd\d+)", f, re.I)
                if m:
                    sd_bases.add(m.group(1).lower())

    letters = "abcdefghijklmnopqrstuvwxyz"
    exts = [".tlg", ".png", ".pimg", ".psb",
            "_censored.tlg", "_censored.png", "_censored.pimg", "_censored.psb"]
    count = 0

    # ev: 雙字母 aa-zz (第一字母 a-z, 第二字母 a-z)
    for base in ev_bases:
        for c1 in letters:
            for c2 in letters:
                suffix = c1 + c2
                for ext in exts:
                    filename_plaintexts.add(f"{base}{suffix}{ext}")
                    count += 1

    # sd: 單字母 a-z
    for base in sd_bases:
        for c in letters:
            for ext in [".tlg", ".png", ".pimg", ".psb", ".asd",
                        "_censored.tlg", "_censored.png", "_censored.pimg",
                        ".jpg", ".mtn"]:
                filename_plaintexts.add(f"{base}{c}{ext}")
                count += 1

    if count:
        print(f"  [bruteforce] 從 {len(ev_bases)} ev + {len(sd_bases)} sd 基底生成了 {count} 個候選檔名")


def from_ending_and_locale_variants():
    """從已知檔名推導 ending roll、edthum、opthum 等地區變體"""
    locales = ["jp", "en", "cn", "tw"]
    count = 0

    # 自動收集 edthum_{name} 基底名
    edthum_names = set()
    # 自動收集 ed_{name}_roll 基底名（硬寫 fallback：全名無法從設定檔推導）
    ed_roll_names = {"azusa", "elina", "miu", "nicola", "rio"}
    # 自動收集 route_{name} 基底名
    route_names = set()

    for fn in list(filename_plaintexts):
        m = re.match(r"^edthum_([a-z]+?)(?:_(?:jp|en|cn|tw))?\.(?:png|psb)$", fn)
        if m:
            edthum_names.add(m.group(1))
        m = re.match(r"^ed_([a-z]+)_roll", fn)
        if m:
            ed_roll_names.add(m.group(1))
        m = re.match(r"^route_([a-z]+?)(?:_(?:jp|en|cn|tw))?\.ks", fn)
        if m:
            route_names.add(m.group(1))

    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for f in files:
                m = re.match(r"^edthum_([a-z]+?)(?:_(?:jp|en|cn|tw))?\.(?:png|psb)$", f)
                if m:
                    edthum_names.add(m.group(1))
                m = re.match(r"^ed_([a-z]+)_roll", f)
                if m:
                    ed_roll_names.add(m.group(1))
                m = re.match(r"^route_([a-z]+?)(?:_(?:jp|en|cn|tw))?\.ks", f)
                if m:
                    route_names.add(m.group(1))

    # edthum_{name}_{locale}.png
    for ch in edthum_names:
        for loc in locales:
            filename_plaintexts.update([
                f"edthum_{ch}_{loc}.png", f"edthum_{ch}_{loc}.psb",
                f"edthum_{ch}.png", f"edthum_{ch}.psb",
            ])
            count += 4

    # opthum_{locale}.png
    for loc in locales:
        filename_plaintexts.update([
            f"opthum_{loc}.png", f"opthum_{loc}.psb",
        ])
        count += 2

    # ed_{name}_roll: .tjs + _{locale}.ini + _{locale}.png + _{locale}_{000-150}.png
    for ch in ed_roll_names:
        filename_plaintexts.add(f"ed_{ch}_roll.tjs")
        count += 1
        for loc in locales:
            base = f"ed_{ch}_roll_{loc}"
            filename_plaintexts.update([
                f"{base}.ini", f"{base}.png", f"{base}.psb",
            ])
            count += 3
            for n in range(150):
                filename_plaintexts.add(f"{base}_{n:03d}")
                filename_plaintexts.add(f"{base}_{n:03d}.png")
                count += 2

    # route_{name}_{locale}.ks.scn
    for ch in route_names:
        for loc in locales:
            filename_plaintexts.add(f"route_{ch}_{loc}.ks.scn")
            count += 1

    # thum_ev/sd 的地區和 censored 變體
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for f in files:
                m = re.match(r"^(thum_(?:ev|sd)\d+)(?:_censored)?\.(?:png|psb)$", f)
                if m:
                    base = m.group(1)
                    for loc in ("_en", "_cn", "_tw", ""):
                        for cen in ("", "_censored"):
                            filename_plaintexts.update([
                                f"{base}{loc}{cen}.png",
                                f"{base}{loc}{cen}.psb",
                            ])
                            count += 2

    # bgthum 地區變體
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for f in files:
                m = re.match(r"^(bgthum_.+)\.jpg$", f)
                if m:
                    base = m.group(1)
                    for loc in ("_en", "_cn", "_tw"):
                        filename_plaintexts.add(f"{base}{loc}.jpg")
                        count += 1

    if count:
        print(f"  [locale_variants] 生成了 {count} 個地區變體檔名"
              f"（edthum:{len(edthum_names)} ed_roll:{len(ed_roll_names)} route:{len(route_names)}）")


def from_scn_all_refs():
    """從 SCN JSON 檔中提取所有檔案引用（imageFile、filename、storage 等）"""
    json_dir = TEMP_DIR
    if not json_dir.exists():
        return
    img_names = set()
    snd_names = set()
    scn_names = set()
    for jf in json_dir.glob("*.json"):
        try:
            content = jf.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in re.finditer(r'"file":\s*"([^"]+)"', content):
            img_names.add(m.group(1))
        for m in re.finditer(r'"image":\s*"([^"]+)"', content):
            img_names.add(m.group(1))
        for m in re.finditer(r'"filename":\s*"([^"]+)"', content):
            snd_names.add(m.group(1))
        for m in re.finditer(r'"storage":\s*"([^"]+)"', content):
            scn_names.add(m.group(1))

    count = 0
    for name in img_names:
        if name.startswith("ev") or name.startswith("sd") or name.endswith(".stand"):
            continue
        for ext in (".jpg", ".png", ".tlg", ".pimg", ".sinfo"):
            filename_plaintexts.add(f"{name}{ext}")
            count += 1
        filename_plaintexts.add(f"bgthum_{name}.jpg")
        filename_plaintexts.add(f"bgthum_{name}.png")
        count += 2
    for name in snd_names:
        for ext in (".ogg", ".ogg.sli", ".opus", ".opus.sli", ".mchx", ".mchx.sli", ".ini"):
            filename_plaintexts.add(f"{name}{ext}")
            count += 1
    for name in scn_names:
        if not name.endswith(".ks"):
            continue
        filename_plaintexts.update([name, f"{name}.scn"])
        count += 2

    if count:
        print(f"  [scn_refs] 從 SCN 提取了 {len(img_names)} 個圖片、{len(snd_names)} 個音效、{len(scn_names)} 個腳本引用（共 {count} 個候選）")


def from_hash_logs():
    """從遊戲運行時 hash 日誌 (FileNameHash.log / DirectoryHash.log) 提取檔名和路徑"""
    fn_log = TOOL_DIR / "FileNameHash.log"
    dir_log = TOOL_DIR / "DirectoryHash.log"
    fn_count = 0
    pn_count = 0

    if fn_log.exists():
        try:
            with open(fn_log, "r", encoding="utf-16le") as f:
                for line in f:
                    line = line.strip().replace("\ufeff", "")
                    if "##YSig##" not in line:
                        continue
                    name = line.split("##YSig##", 1)[0].strip()
                    if name and name != "%EmptyString%":
                        filename_plaintexts.add(name)
                        fn_count += 1
        except Exception:
            traceback.print_exc()

    if dir_log.exists():
        try:
            with open(dir_log, "r", encoding="utf-16le") as f:
                for line in f:
                    line = line.strip().replace("\ufeff", "")
                    if "##YSig##" not in line:
                        continue
                    name = line.split("##YSig##", 1)[0].strip()
                    if name and name != "%EmptyString%":
                        pathname_plaintexts.add(name)
                        pn_count += 1
        except Exception:
            traceback.print_exc()

    if fn_count or pn_count:
        print(f"  [hash_logs] 提取了 {fn_count} 個檔名、{pn_count} 個路徑名")


def from_filelist_txts():
    """從工具目錄下的 .txt 檔案載入舊版檔案清單（每行一個路徑）"""
    txt_files = [f for f in TOOL_DIR.glob("*.txt") if f.stem != "requirements"]
    fn_count = 0
    pn_count = 0
    for txt_file in txt_files:
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    line = line.replace("\\", "/")
                    if "/" in line:
                        parts = line.split("/")
                        fn = parts[-1]
                        # 加入所有子路徑
                        for i in range(1, len(parts)):
                            subpath = "/".join(parts[:i]) + "/"
                            pathname_plaintexts.add(subpath)
                            pn_count += 1
                        if fn:
                            filename_plaintexts.add(fn)
                            fn_count += 1
                    elif "." in line:
                        filename_plaintexts.add(line)
                        fn_count += 1
                    else:
                        pathname_plaintexts.add(line + "/")
                        pn_count += 1
        except Exception:
            traceback.print_exc()
    if fn_count or pn_count:
        print(f"  [filelist_txts] 從 {len(txt_files)} 個 txt 載入了 {fn_count} 個檔名、{pn_count} 個路徑名")


def from_scnchartdata_tjs():
    """從 scnchartdata.tjs 提取 .ks 劇本檔名"""
    seed = "scnchartdata.tjs"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    content = safe_read_text(found)
    if not content:
        return
    count = 0
    seen = set()
    for m in re.finditer(r'"([^"]+\.ks)"', content):
        ks = m.group(1)
        if ks not in seen:
            seen.add(ks)
            filename_plaintexts.update([ks, f"{ks}.scn"])
            count += 1
    if count:
        print(f"  [scnchartdata] 提取了 {count} 個 ks 檔名")


def _add_image_variants(name: str):
    """為圖片名加入常見副檔名和 _censored 變體"""
    for ext in (".pimg", ".tlg", ".png", ".psb"):
        filename_plaintexts.add(f"{name}{ext}")
        filename_plaintexts.add(f"{name}_censored{ext}")


def from_imageevalmap_csv():
    """從 imageevalmap.csv 提取圖片映射"""
    seed = "imageevalmap.csv"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    rows = safe_read_csv(found)
    count = 0
    for row in rows:
        if not row:
            continue
        header = row[0].replace("\ufeff", "").strip()
        if header.startswith("#") or not header:
            continue
        for field in row[:2]:
            name = field.strip()
            if name and not name.startswith("&") and not name.startswith("#"):
                _add_image_variants(name)
                count += 1
    if count:
        print(f"  [imageevalmap] 提取了 {count} 個圖片名")


def from_imagenamemap_txt():
    """從 imagenamemap.txt 提取圖片名和 censored 映射"""
    seed = "imagenamemap.txt"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    content = safe_read_text(found)
    if not content:
        return
    count = 0
    for line in content.splitlines():
        line = line.strip().replace("\ufeff", "")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        for part in parts:
            part = part.strip()
            if part and not part.startswith("_"):
                _add_image_variants(part)
                count += 1
    if count:
        print(f"  [imagenamemap] 提取了 {count} 個圖片名")


def from_imagemulti_txt():
    """從 imagemulti.txt 提取多解析度立繪名"""
    seed = "imagemulti.txt"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    content = safe_read_text(found)
    if not content:
        return
    count = 0
    for line in content.splitlines():
        line = line.strip().replace("\ufeff", "")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        for part in parts:
            part = part.strip()
            # Remove resolution prefix like "200:" or "100:"
            if ":" in part:
                part = part.split(":", 1)[1].strip()
            if not part:
                continue
            for ext in (".pbd", ".sinfo", ".pimg", ".stand"):
                filename_plaintexts.add(f"{part}{ext}")
            count += 1
    if count:
        print(f"  [imagemulti] 提取了 {count} 個立繪名")


def from_imagepropmap_txt():
    """從 imagepropmap.txt 提取特殊資源名"""
    seed = "imagepropmap.txt"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    content = safe_read_text(found)
    if not content:
        return
    count = 0
    for line in content.splitlines():
        line = line.strip().replace("\ufeff", "")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        name = parts[0].strip()
        if not name:
            continue
        if name.endswith(".mtn"):
            filename_plaintexts.add(name)
            base = name[:-4]
            filename_plaintexts.update([f"{base}.psb", f"{base}.pimg", f"{base}.png"])
        else:
            for ext in (".pimg", ".tlg", ".png", ".psb", ".mtn", ".wmv", ".stand"):
                filename_plaintexts.add(f"{name}{ext}")
        count += 1
    if count:
        print(f"  [imagepropmap] 提取了 {count} 個資源名")


def from_imagedressmap_txt():
    """從 imagedressmap.txt 提取 .stand 檔名"""
    seed = "imagedressmap.txt"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    content = safe_read_text(found)
    if not content:
        return
    count = 0
    for line in content.splitlines():
        line = line.strip().replace("\ufeff", "")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        name = parts[0].strip()
        if name:
            if not name.endswith(".stand"):
                filename_plaintexts.add(f"{name}.stand")
            filename_plaintexts.add(name)
            count += 1
    if count:
        print(f"  [imagedressmap] 提取了 {count} 個 stand 檔名")


def from_sysse_ini():
    """從 sysse.ini 提取系統音效名稱"""
    seed = "sysse.ini"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    content = safe_read_text(found)
    if not content:
        return
    count = 0
    for line in content.splitlines():
        line = line.strip().replace("\ufeff", "")
        if not line or line.startswith("#") or line.startswith("?"):
            continue
        if "=" not in line:
            continue
        rhs = line.split("=", 1)[1].strip()
        if rhs.startswith("@") or rhs.startswith("alias"):
            continue
        sound = rhs.split(":")[0].strip()
        if not sound or " " in sound or sound.startswith("%"):
            continue
        for ext in (".ogg", ".ogg.sli", ".opus", ".opus.sli"):
            filename_plaintexts.add(f"{sound}{ext}")
        count += 1
    if count:
        print(f"  [sysse] 提取了 {count} 個音效名")


def from_systrans_ini():
    """從 systrans.ini 提取轉場 rule 名稱"""
    seed = "systrans.ini"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    content = safe_read_text(found)
    if not content:
        return
    rules = set()
    for line in content.splitlines():
        line = line.strip().replace("\ufeff", "")
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        rhs = line.split("=", 1)[1].strip()
        if rhs.startswith("@") or rhs.startswith("0:&"):
            continue
        for part in rhs.split(":"):
            part = part.strip()
            if part and not part.isdigit() and not part.startswith("@"):
                rules.add(part)
    count = 0
    for rule in rules:
        for ext in (".png", ".pimg", ".tlg", ".psb"):
            filename_plaintexts.add(f"{rule}{ext}")
        count += 1
    if count:
        print(f"  [systrans] 提取了 {count} 個轉場規則名")


def from_tjs_scripts():
    """從已命名的 .tjs 檔案中提取字串中的檔名引用"""
    count = 0
    seen = set()
    pattern = re.compile(
        r'["\']([^"\'\s]+\.(?:tjs|ks|ini|csv|txt|png|jpg|tlg|pimg|ogg|mp4|wmv|psb|pbd|stand|sinfo|mtn|stage|toml))["\']'
    )
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for f in files:
                if not f.endswith(".tjs"):
                    continue
                fp = os.path.join(root, f)
                content = safe_read_text(fp)
                if not content:
                    continue
                for m in pattern.finditer(content):
                    ref = m.group(1)
                    if "/" in ref:
                        ref = ref.split("/")[-1]
                    if ref not in seen:
                        seen.add(ref)
                        filename_plaintexts.add(ref)
                        if ref.endswith(".ks"):
                            filename_plaintexts.add(f"{ref}.scn")
                        count += 1
    if count:
        print(f"  [tjs_scripts] 提取了 {count} 個檔名引用")


def from_locale_files():
    """從已命名的 locale 檔案推導其他語言變體"""
    locale_suffixes = ["_cn", "_en", "_tw", "_jp"]
    locale_bases = set()
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            if "locale" not in root.lower():
                continue
            for f in files:
                if is_file_hash(f):
                    continue
                for sfx in locale_suffixes:
                    idx = f.rfind(sfx + ".")
                    if idx != -1:
                        base = f[:idx]
                        ext = f[idx + len(sfx):]
                        locale_bases.add((base, ext))
                        break
                    idx = f.rfind(sfx)
                    if idx != -1 and idx == len(f) - len(sfx):
                        base = f[:idx]
                        locale_bases.add((base, ""))
                        break
    count = 0
    for base, ext in locale_bases:
        for sfx in locale_suffixes:
            fn = f"{base}{sfx}{ext}"
            filename_plaintexts.add(fn)
            count += 1
        # Also add the base without locale suffix
        fn_base = f"{base}{ext}"
        filename_plaintexts.add(fn_base)
    if count:
        print(f"  [locale_files] 從 {len(locale_bases)} 個基底名生成了 {count} 個語言變體")


def from_filegain_csv():
    """從 filegain.csv 提取音效/BGM 名稱"""
    seed = "filegain.csv"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    rows = safe_read_csv(found)
    count = 0
    for row in rows:
        if not row:
            continue
        name = row[0].replace("\ufeff", "").strip()
        if name.startswith("#") or not name:
            continue
        for ext in (".ogg", ".ogg.sli", ".opus", ".opus.sli", ".mchx", ".mchx.sli"):
            filename_plaintexts.add(f"{name}{ext}")
        count += 1
    if count:
        print(f"  [filegain] 提取了 {count} 個音效/BGM 名")


def from_soundgain_csv():
    """從 soundgain.csv 提取音效區分名"""
    seed = "soundgain.csv"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    if not found:
        return
    rows = safe_read_csv(found)
    count = 0
    for row in rows:
        if not row:
            continue
        name = row[0].replace("\ufeff", "").strip()
        if name.startswith("#") or not name:
            continue
        # soundgain 主要是分類名，但也可能直接用作音效前綴
        for ext in (".ogg", ".ogg.sli"):
            filename_plaintexts.add(f"{name}{ext}")
        count += 1
    if count:
        print(f"  [soundgain] 提取了 {count} 個音效區分名")


def from_scn_label_remap():
    """從 TJS const 標籤映射檔中提取 .ks 檔名"""
    count = 0
    for xp3_dir in XP3_DIRS:
        for root, _, files in os.walk(xp3_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    with open(fp, "rb") as fh:
                        hdr = fh.read(20)
                    if hdr[:2] != b"\xff\xfe":
                        continue
                    if b"(const)%[" not in hdr:
                        continue
                    with open(fp, "r", encoding="utf-16le") as fh:
                        content = fh.read()
                    for m in re.finditer(r'"([^"]+\.ks)"', content):
                        ks = m.group(1)
                        filename_plaintexts.update([f"{ks}.scn", ks])
                        count += 1
                except (OSError, UnicodeDecodeError):
                    pass
    if count:
        print(f"  [label_remap] 提取了 {count} 個 ks 檔名")


def find_missing_voices():
    prefixes_map = {}

    def handle_vname(vn: str):
        if "_" not in vn:
            return
        prefix, num = vn.rsplit("_", 1)
        m = re.match(r"^\d+", num)
        if m:
            n, sz = int(m.group(0)), len(m.group(0))
            if prefix not in prefixes_map:
                prefixes_map[prefix] = [sz, n]
            elif n > prefixes_map[prefix][1]:
                prefixes_map[prefix][1] = n

    for xp3_dir in XP3_DIRS:
        for child in Path(xp3_dir).rglob("*"):
            if child.is_file() and child.suffix in (".ogg", ".sli"):
                handle_vname(child.stem)
            elif child.is_file() and child.suffix == ".csv" and child.stem.startswith("bgv"):
                rows = safe_read_csv(str(child))
                for row in rows:
                    if row and len(row) > 2 and not row[0].replace("\ufeff", "").startswith("#"):
                        handle_vname(row[2])

    count = 0
    for prefix, (sz, mx) in prefixes_map.items():
        mx += 5
        for num in range(1, mx + 1):
            vn = f"{prefix}_{num:0{sz}d}"
            for sfx in ("", "a", "b", "c"):
                filename_plaintexts.update([f"{vn}{sfx}.ogg", f"{vn}{sfx}.ogg.sli"])
                count += 1
    if count:
        print(f"  [missing_voices] 生成了 {count} 個可能的語音檔名")


def derive_voice_variants():
    """從所有已知的語音檔名推導 .ogg.sli、a/b/c 變體、loop 變體、abc→無印"""
    known_ogg = set()
    for fn in list(filename_plaintexts):
        if fn.endswith(".ogg") and not fn.endswith(".ogg.sli"):
            known_ogg.add(fn)

    count = 0
    for fn in known_ogg:
        base = fn[:-4]  # remove .ogg

        # 每個 .ogg → 推 .ogg.sli
        filename_plaintexts.add(f"{base}.ogg.sli")
        count += 1

        # xxx000_000.ogg → xxx000_000a/b/c.ogg + .ogg.sli
        m = re.match(r"^([a-z]{3}\d{3}_\d{3})$", base)
        if m:
            for sfx in ("a", "b", "c"):
                filename_plaintexts.update([
                    f"{base}{sfx}.ogg", f"{base}{sfx}.ogg.sli",
                ])
                count += 2

        # xxx000_000a.ogg → 推回無印 xxx000_000.ogg + .ogg.sli，以及其他 b/c
        m = re.match(r"^([a-z]{3}\d{3}_\d{3})[abc]$", base)
        if m:
            stem = m.group(1)
            filename_plaintexts.update([f"{stem}.ogg", f"{stem}.ogg.sli"])
            count += 2
            for sfx in ("a", "b", "c"):
                filename_plaintexts.update([
                    f"{stem}{sfx}.ogg", f"{stem}{sfx}.ogg.sli",
                ])
                count += 2

        # loop_xxx_000.ogg → loop_xxx_000b.ogg + .ogg.sli
        m = re.match(r"^(loop_[a-z]+_\d{3})$", base)
        if m:
            filename_plaintexts.update([
                f"{base}b.ogg", f"{base}b.ogg.sli",
            ])
            count += 2

        # loop_xxx_000b.ogg → 推回無印 loop_xxx_000.ogg + .ogg.sli
        m = re.match(r"^(loop_[a-z]+_\d{3})[b]$", base)
        if m:
            stem = m.group(1)
            filename_plaintexts.update([f"{stem}.ogg", f"{stem}.ogg.sli"])
            count += 2

    if count:
        print(f"  [voice_variants] 從 {len(known_ogg)} 個已知 ogg 推導了 {count} 個變體")


def bruteforce_character_voices():
    """用 charvoice.csv 的前綴模式 + 已知場景號窮舉所有可能的語音檔名"""
    # 從 charvoice.csv 讀取前綴模式
    seed = "charvoice.csv"
    fh = get_file_hash(seed)
    found = find_file_by_hash(fh, seed)
    voice_patterns: list[str] = []
    if found:
        rows = safe_read_csv(found)
        for row in rows:
            if not row:
                continue
            h = row[0].replace("\ufeff", "")
            if h.startswith("#") or h.startswith("DEFAULT") or len(row) < 2:
                continue
            voice_patterns.append(row[1].strip())

    # 解析模式：兩種格式
    # 1. "miu%s_%03d" → prefix=miu, format="{prefix}{scene}_{line:03d}"
    # 2. "x101_%s_%03d" → prefix=x101, format="{prefix}_{scene}_{line:03d}"
    # 3. "gos00%s0%03d" → 特殊，跳過
    prefix_info: dict[str, dict] = {}

    for pat in voice_patterns:
        if pat.count("%") != 2:
            continue
        # 嘗試解析
        m = re.match(r"^([a-z]{2,4})%s_%03d$", pat)
        if m:
            # Type 1: miu%s_%03d → miu{scene}_{line}
            pfx = m.group(1)
            prefix_info.setdefault(pfx, {"type": 1, "scenes": set(), "max_line": 0})
            continue
        m = re.match(r"^(x[x\d]{2,3})_%s_%03d$", pat)
        if m:
            # Type 2: x101_%s_%03d → x101_{scene}_{line}
            pfx = m.group(1)
            prefix_info.setdefault(pfx, {"type": 2, "scenes": set(), "max_line": 0})
            continue

    # 從已知檔名收集場景號和最大行號
    for fn in list(filename_plaintexts):
        for pfx, info in prefix_info.items():
            if info["type"] == 1:
                m = re.match(rf"^{re.escape(pfx)}(\d{{3}})_(\d{{3}})", fn)
            else:
                m = re.match(rf"^{re.escape(pfx)}_(\d{{3}})_(\d{{3}})", fn)
            if m:
                info["scenes"].add(int(m.group(1)))
                info["max_line"] = max(info["max_line"], int(m.group(2)))

    # 也收集 loop_ 前綴
    loop_prefixes: dict[str, int] = {}
    for fn in list(filename_plaintexts):
        m = re.match(r"^(loop_[a-z]+)_(\d{3})", fn)
        if m:
            lp, n = m.group(1), int(m.group(2))
            loop_prefixes[lp] = max(loop_prefixes.get(lp, 0), n)

    count = 0
    for pfx, info in prefix_info.items():
        if not info["scenes"]:
            continue
        max_line = info["max_line"] + 5
        for scene in info["scenes"]:
            for line in range(1, max_line + 1):
                if info["type"] == 1:
                    vn = f"{pfx}{scene:03d}_{line:03d}"
                else:
                    vn = f"{pfx}_{scene:03d}_{line:03d}"
                for sfx in ("", "a", "b", "c"):
                    filename_plaintexts.update([
                        f"{vn}{sfx}.ogg", f"{vn}{sfx}.ogg.sli",
                    ])
                    count += 2

    for lp, mx in loop_prefixes.items():
        for n in range(1, mx + 5):
            for sfx in ("", "b"):
                filename_plaintexts.update([
                    f"{lp}_{n:03d}{sfx}.ogg", f"{lp}_{n:03d}{sfx}.ogg.sli",
                ])
                count += 2

    active = sum(1 for v in prefix_info.values() if v["scenes"])
    if count:
        print(f"  [bruteforce_voices] 從 {active} 個角色前綴 + {len(loop_prefixes)} 個 loop 前綴生成了 {count} 個候選")


# === 主流程 ===
def main():
    print("=" * 60)
    print("hxv4 自動反混淆工具")
    print(f"目標目錄: {TARGET_DIR}")
    print("=" * 60)

    if args.dry_run:
        print("** 模擬模式：不會實際重命名檔案 **\n")

    print(f"掃描到 {len(XP3_DIRS)} 個子目錄: {', '.join(d.name for d in XP3_DIRS)}")

    iteration = 0
    total_renamed_files = 0
    total_renamed_dirs = 0
    total_failed_files = 0
    total_failed_dirs = 0
    all_log_lines: list[str] = []

    while True:
        iteration += 1
        prev_fn_count = len(filename_plaintexts)
        prev_pn_count = len(pathname_plaintexts)
        print(f"\n{'=' * 60}")
        print(f"迭代 #{iteration}")
        print(f"{'=' * 60}")

        # Step 1-3: 檔案解析來源
        if args.dict_only:
            print("\n[Step 1-3] 跳過（--dict-only 模式，只用 lst/txt 字典）")
            from_filelist_txts()
        else:
            # Step 1: 種子檔案
            print("\n[Step 1] 搜尋已知種子檔案...")
            seed_sources = {
                "cglist.csv": from_cglist_csv,
                "soundlist.csv": from_soundlist_csv,
                "charvoice.csv": from_charvoice_csv,
                "imagediffmap.csv": from_imagediffmap_csv,
                "savelist.csv": from_savelist_csv,
                "scenelist.csv": from_scenelist_csv,
                "base.stage": from_base_stage,
                "replay.ks": from_replay_ks,
            }
            for seed_name, handler in seed_sources.items():
                fh = get_file_hash(seed_name)
                found = find_file_by_hash(fh, seed_name)
                if found:
                    print(f"  找到 {seed_name}")
                    handler(found)
                else:
                    print(f"  未找到 {seed_name}")

            # Step 2: PSB
            if not args.skip_psb:
                print("\n[Step 2] 掃描 PSB/SCN 檔案...")
                scan_psb_and_decompile()
            else:
                print("\n[Step 2] 跳過 PSB 掃描")

            # Step 3: 其他來源
            print("\n[Step 3] 處理其他來源...")
            from_hash_logs()
            from_filelist_txts()
            from_scnchartdata_tjs()
            from_imageevalmap_csv()
            from_imagenamemap_txt()
            from_imagemulti_txt()
            from_imagepropmap_txt()
            from_imagedressmap_txt()
            from_sysse_ini()
            from_systrans_ini()
            from_tjs_scripts()
            from_locale_files()
            from_filegain_csv()
            from_soundgain_csv()
            from_bgv_csv()
            from_stand_files()
            from_pbd_files()
            from_chthum_index()
            from_uipsd_files()
            from_tlgref_files()
            from_ending_and_locale_variants()
            from_scn_all_refs()
            from_scn_label_remap()
            bruteforce_ev_sd()

        # Step 3.5: 從已知語音推導變體（所有來源收集完後）
        derive_voice_variants()
        bruteforce_character_voices()

        # Step 4: 小寫副本
        print("\n[Step 4] 生成小寫副本...")
        filename_plaintexts.update(fn.lower() for fn in list(filename_plaintexts))
        pathname_plaintexts.update(pn.lower() for pn in list(pathname_plaintexts))

        new_fn = len(filename_plaintexts) - prev_fn_count
        new_pn = len(pathname_plaintexts) - prev_pn_count
        print(f"  共 {len(filename_plaintexts)} 個檔名（+{new_fn}），{len(pathname_plaintexts)} 個路徑名（+{new_pn}）")

        # Step 5: 計算 hash
        print("\n[Step 5] 計算 hash 值...")
        path_hash_map: dict[str, str] = {}
        file_hash_map: dict[str, str] = {}

        # 載入已有的 HxNames.lst 及工具目錄下的 .lst 檔案
        lst_files = list(TOOL_DIR.glob("*.lst"))
        if HXNAMES_FILE.exists():
            lst_files.append(HXNAMES_FILE)
        for lst_file in lst_files:
            try:
                with open(lst_file, "r", encoding="UTF-8") as h:
                    for line in h:
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split(":", 1)
                        if len(parts) != 2:
                            continue
                        hx_hash, hx_name = parts
                        if len(hx_hash) == 16:
                            path_hash_map.setdefault(hx_name, hx_hash)
                        elif len(hx_hash) == 64:
                            file_hash_map.setdefault(hx_name, hx_hash)
            except Exception:
                pass
        if lst_files:
            extra = [f.name for f in lst_files if f != HXNAMES_FILE]
            if extra:
                print(f"  載入了額外字典: {', '.join(extra)}")

        new_p, new_f = 0, 0
        for pn in pathname_plaintexts:
            pn = pn.strip().replace("\ufeff", "")
            if pn and pn not in path_hash_map and ("/" in pn or pn == ""):
                path_hash_map[pn] = get_path_hash(pn)
                new_p += 1
        for fn in filename_plaintexts:
            fn = fn.strip().replace("\ufeff", "")
            if fn and fn not in file_hash_map:
                file_hash_map[fn] = get_file_hash(fn)
                new_f += 1

        print(f"  新增 {new_p} 個路徑 hash，{new_f} 個檔案 hash")
        print(f"  共 {len(path_hash_map)} 個路徑，{len(file_hash_map)} 個檔案")

        # Step 6: 儲存
        print("\n[Step 6] 儲存 HxNames.lst...")
        with open(HXNAMES_FILE, "w", encoding="UTF-8") as h:
            for name, hv in path_hash_map.items():
                if name.strip():
                    h.write(f"{hv}:{name}\n")
            for name, hv in file_hash_map.items():
                if name.strip():
                    h.write(f"{hv}:{name}\n")

        # Step 7: 重命名
        print("\n[Step 7] 重命名檔案和目錄...")
        hash_to_path = {v: k for k, v in path_hash_map.items()}
        hash_to_file = {v: k for k, v in file_hash_map.items()}

        renamed_files = 0
        renamed_dirs = 0
        failed_files = 0
        failed_dirs = 0

        for xp3_dir in XP3_DIRS:
            for root, dirs, files in os.walk(xp3_dir, topdown=False):
                for f in files:
                    if f not in hash_to_file:
                        continue
                    old = os.path.join(root, f)
                    new_name = hash_to_file[f]
                    new = get_unique_name(os.path.join(root, new_name))
                    rel_old = os.path.relpath(old, TARGET_DIR)
                    rel_new = os.path.relpath(new, TARGET_DIR)
                    try:
                        if args.dry_run:
                            print(f"  [模擬] {rel_old} -> {rel_new}")
                        else:
                            os.rename(old, new)
                        all_log_lines.append(f"OK FILE {rel_old} -> {rel_new}")
                        renamed_files += 1
                    except Exception as e:
                        all_log_lines.append(f"FAIL FILE {rel_old} -> {rel_new}: {e}")
                        print(f"  失敗: {rel_old} -> {rel_new}: {e}")
                        failed_files += 1

                for d in dirs:
                    if d not in hash_to_path:
                        continue
                    old_dir = os.path.join(root, d)
                    if not os.path.exists(old_dir):
                        continue
                    target_rel = hash_to_path[d].rstrip("/\\")
                    new_dir = os.path.join(root, target_rel)
                    parent = os.path.dirname(new_dir)
                    rel_old = os.path.relpath(old_dir, TARGET_DIR)
                    rel_new = os.path.relpath(new_dir, TARGET_DIR)
                    try:
                        if args.dry_run:
                            print(f"  [模擬] {rel_old}/ -> {rel_new}/")
                        else:
                            os.makedirs(parent, exist_ok=True)
                            if os.path.exists(new_dir):
                                merge_dir(old_dir, new_dir)
                            else:
                                shutil.move(old_dir, new_dir)
                        all_log_lines.append(f"OK DIR {rel_old}/ -> {rel_new}/")
                        renamed_dirs += 1
                    except Exception as e:
                        all_log_lines.append(f"FAIL DIR {rel_old}/ -> {rel_new}/: {e}")
                        print(f"  失敗: {rel_old}/ -> {rel_new}/: {e}")
                        failed_dirs += 1

        total_renamed_files += renamed_files
        total_renamed_dirs += renamed_dirs
        total_failed_files += failed_files
        total_failed_dirs += failed_dirs

        print(f"\n  本輪: 重命名 {renamed_files} 檔案, {renamed_dirs} 目錄")

        # 如果本輪沒有新重命名，就結束迭代
        if renamed_files == 0 and renamed_dirs == 0:
            print("  沒有新的重命名，結束迭代。")
            break
        if args.dict_only:
            print("  --dict-only 模式，單輪完成。")
            break
        if iteration >= 10:
            print("  達到最大迭代次數，結束。")
            break

    # Final report
    LOG_FILE = TARGET_DIR / "deobf_log.txt"

    print(f"\n{'=' * 70}")
    print(f"全部完成！共迭代 {iteration} 輪")
    verb = "會重命名" if args.dry_run else "已重命名"
    print(f"{verb} {total_renamed_files} 個檔案，{total_renamed_dirs} 個目錄")
    if total_failed_files or total_failed_dirs:
        print(f"失敗: {total_failed_files} 個檔案，{total_failed_dirs} 個目錄")

    # Per-directory statistics
    print(f"\n{'目錄':<20} {'已還原':>8} {'未還原':>8} {'總計':>8} {'還原率':>8}")
    print("-" * 60)

    grand_renamed = 0
    grand_remaining = 0
    dir_stats: list[str] = []

    for d in sorted(TARGET_DIR.iterdir()):
        if not d.is_dir() or d.name in EXCLUDE_NAMES or d.name.endswith(".alst"):
            continue
        renamed = 0
        remaining = 0
        for f in d.rglob("*"):
            if f.is_file():
                if is_file_hash(f.name):
                    remaining += 1
                else:
                    renamed += 1
        total = renamed + remaining
        if total > 0:
            pct = renamed / total * 100
            line = f"{d.name:<20} {renamed:>8} {remaining:>8} {total:>8} {pct:>7.1f}%"
            print(line)
            dir_stats.append(line)
        grand_renamed += renamed
        grand_remaining += remaining

    grand_total = grand_renamed + grand_remaining
    grand_pct = grand_renamed / grand_total * 100 if grand_total > 0 else 0
    print("-" * 60)
    total_line = f"{'總計':<20} {grand_renamed:>8} {grand_remaining:>8} {grand_total:>8} {grand_pct:>7.1f}%"
    print(total_line)
    print(f"\nHxNames.lst 已儲存（可供 GARbro 等工具使用）")

    # Write log file
    with open(LOG_FILE, "w", encoding="utf-8") as lf:
        lf.write(f"hxv4 auto_deobf log - {datetime.now().isoformat()}\n")
        lf.write(f"Target: {TARGET_DIR}\n")
        lf.write(f"Mode: {'dry-run' if args.dry_run else 'live'}\n")
        lf.write(f"PSB scan: {'skipped' if args.skip_psb else 'enabled'}\n")
        lf.write(f"Iterations: {iteration}\n")
        lf.write(f"\n{'=' * 60}\n")
        lf.write(f"Results: {total_renamed_files} files renamed, {total_renamed_dirs} dirs renamed\n")
        lf.write(f"Failed:  {total_failed_files} files, {total_failed_dirs} dirs\n")
        lf.write(f"\n--- Per-directory stats ---\n")
        lf.write(f"{'Dir':<20} {'Renamed':>8} {'Remain':>8} {'Total':>8} {'Rate':>8}\n")
        for s in dir_stats:
            lf.write(s + "\n")
        lf.write(f"{'-' * 60}\n")
        lf.write(total_line + "\n")
        lf.write(f"\n--- Rename log ({len(all_log_lines)} entries) ---\n")
        for entry in all_log_lines:
            lf.write(entry + "\n")
    print(f"詳細日誌已儲存到 {LOG_FILE}")

    # 生成乾淨的 HxNames lst
    if args.clean_lst:
        generate_clean_hxnames(HXNAMES_FILE, TARGET_DIR, TOOL_DIR)


def generate_clean_hxnames(hxnames_file: Path, target_dir: Path, tool_dir: Path):
    """從已還原的目錄生成只包含實際使用條目的乾淨 HxNames lst"""
    timestamp = datetime.now().strftime("%m%d%S")
    output_file = tool_dir / f"HxNames_clean{timestamp}.lst"

    path_hash_map: dict[str, str] = {}
    file_hash_map: dict[str, str] = {}

    with open(hxnames_file, "r", encoding="UTF-8") as h:
        for line in h:
            line = line.strip()
            if not line:
                continue
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            hx_hash, hx_name = parts
            if len(hx_hash) == 16:
                path_hash_map[hx_name] = hx_hash
            elif len(hx_hash) == 64:
                file_hash_map[hx_name] = hx_hash

    saved_items: set[str] = set()
    ignored = 0

    exclude_names = {tool_dir.name}
    with open(output_file, "w", encoding="UTF-8") as out:
        for xp3_dir in sorted(target_dir.iterdir()):
            if not xp3_dir.is_dir() or xp3_dir.name in exclude_names or xp3_dir.name.endswith(".alst"):
                continue
            for child in xp3_dir.rglob("*"):
                if child.is_file():
                    name = child.name
                    if is_file_hash(name):
                        continue
                    if name not in file_hash_map:
                        ignored += 1
                        continue
                    if name not in saved_items:
                        out.write(f"{file_hash_map[name]}:{name}\n")
                        saved_items.add(name)
                elif child.is_dir():
                    rel = str(child.relative_to(xp3_dir)).replace("\\", "/") + "/"
                    if any(is_path_hash(p) for p in rel.rstrip("/").split("/")):
                        continue
                    if rel not in path_hash_map:
                        ignored += 1
                        continue
                    if rel not in saved_items:
                        out.write(f"{path_hash_map[rel]}:{rel}\n")
                        saved_items.add(rel)

    print(f"\n已生成乾淨字典: {output_file.name}（{len(saved_items)} 條，忽略 {ignored} 條）")


if __name__ == "__main__":
    if args.clean_lst_only:
        generate_clean_hxnames(HXNAMES_FILE, TARGET_DIR, TOOL_DIR)
    else:
        main()

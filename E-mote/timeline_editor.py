import json
import copy
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter.scrolledtext import ScrolledText

class TimelineEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("程式夥伴 - 動畫時間軸高級編輯器 (2026 Pro Ultimate Edition)")
        self.root.geometry("950x820")  
        
        self.data = None
        self.file_path = "max_converted_modified.json"
        
        self.create_widgets()
        self.load_default_file()

    def create_widgets(self):
        # ---- 頂部檔案控制列 ----
        file_frame = ttk.LabelFrame(self.root, text=" 檔案控制 ")
        file_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_status = ttk.Label(file_frame, text="尚未載入檔案", foreground="red")
        self.lbl_status.pack(side="left", padx=10, pady=5)
        
        btn_browse = ttk.Button(file_frame, text="瀏覽並載入 JSON", command=self.browse_file)
        btn_browse.pack(side="right", padx=10, pady=5)
        
        btn_save = ttk.Button(file_frame, text="另存新檔", command=self.save_file)
        btn_save.pack(side="right", padx=5, pady=5)

        # ---- 中間主操作區 (左右分開) ----
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 左側：控制面板
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(side="left", fill="y", padx=(0, 10))
        
        # 功能 1：查詢與重複管理
        query_frame = ttk.LabelFrame(ctrl_frame, text=" 功能一、查詢與重複管理 ")
        query_frame.pack(fill="x", pady=2)
        
        ttk.Label(query_frame, text="秒數 A (或查詢秒數):").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.ent_time_a = ttk.Entry(query_frame, width=10)
        self.ent_time_a.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(query_frame, text="秒數 B (僅限比較):").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.ent_time_b = ttk.Entry(query_frame, width=10)
        self.ent_time_b.grid(row=1, column=1, padx=5, pady=2)
        
        btn_show = ttk.Button(query_frame, text="顯示秒數 A 屬性", command=self.query_attributes)
        btn_show.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=1)
        
        btn_compare = ttk.Button(query_frame, text="比較 A 與 B 秒數", command=self.compare_attributes)
        btn_compare.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=1)
        
        btn_find_dup = ttk.Button(query_frame, text="🔍 自動尋找並列出所有重複格", command=self.find_all_duplicates)
        btn_find_dup.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=1)
        
        btn_clean_dup = ttk.Button(query_frame, text="✂️ 一鍵清除重複格 (每組只留第一格)", command=self.clean_all_duplicates)
        btn_clean_dup.grid(row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=1)
        
        # 功能 2：複製與右移
        copy_frame = ttk.LabelFrame(ctrl_frame, text=" 功能二、複製影格（右移遞補） ")
        copy_frame.pack(fill="x", pady=2)
        
        ttk.Label(copy_frame, text="來源秒數 (Copy From):").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.ent_copy_src = ttk.Entry(copy_frame, width=10)
        self.ent_copy_src.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(copy_frame, text="目標秒數 (留空則為下一秒):").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.ent_copy_dst = ttk.Entry(copy_frame, width=10)
        self.ent_copy_dst.grid(row=1, column=1, padx=5, pady=2)
        
        btn_copy = ttk.Button(copy_frame, text="執行複製 (後方影格右移+1)", command=self.copy_and_shift)
        btn_copy.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        
        # 功能 3：刪除單一秒數與左移
        del_frame = ttk.LabelFrame(ctrl_frame, text=" 功能三、刪除單一影格（左移密合） ")
        del_frame.pack(fill="x", pady=2)
        
        ttk.Label(del_frame, text="要刪除的秒數:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.ent_del_target = ttk.Entry(del_frame, width=10)
        self.ent_del_target.grid(row=0, column=1, padx=5, pady=2)
        
        btn_del = ttk.Button(del_frame, text="執行單格刪除 (後方影格左移-1)", command=self.delete_and_shift)
        btn_del.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        # 功能 4：指定屬性條件刪除
        cond_frame = ttk.LabelFrame(ctrl_frame, text=" 功能四、指定屬性條件刪除（左移密合） ")
        cond_frame.pack(fill="x", pady=2)
        
        ttk.Label(cond_frame, text="選擇屬性標籤:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.cb_cond_label = ttk.Combobox(cond_frame, width=15, state="readonly")
        self.cb_cond_label.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(cond_frame, text="指定刪除數值:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.ent_cond_val = ttk.Entry(cond_frame, width=10)
        self.ent_cond_val.grid(row=1, column=1, padx=5, pady=2)
        
        btn_cond_del = ttk.Button(cond_frame, text="執行條件刪除 (連坐左移遞補)", command=self.conditional_delete_and_shift)
        btn_cond_del.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        # 功能 5：條件複製並修改
        copy_mod_frame = ttk.LabelFrame(ctrl_frame, text=" 功能五、條件複製並修改（右移遞補） ")
        copy_mod_frame.pack(fill="x", pady=2)
        
        ttk.Label(copy_mod_frame, text="搜尋屬性標籤:").grid(row=0, column=0, padx=5, pady=3, sticky="w")
        self.cb_copy_cond_label = ttk.Combobox(copy_mod_frame, width=15, state="readonly")
        self.cb_copy_cond_label.grid(row=0, column=1, padx=5, pady=3)
        
        ttk.Label(copy_mod_frame, text="搜尋符合數值:").grid(row=1, column=0, padx=5, pady=3, sticky="w")
        self.ent_copy_cond_val = ttk.Entry(copy_mod_frame, width=10)
        self.ent_copy_cond_val.grid(row=1, column=1, padx=5, pady=3)
        
        ttk.Label(copy_mod_frame, text="修改目標標籤:").grid(row=2, column=0, padx=5, pady=3, sticky="w")
        self.cb_copy_mod_label = ttk.Combobox(copy_mod_frame, width=15, state="readonly")
        self.cb_copy_mod_label.grid(row=2, column=1, padx=5, pady=3)
        
        ttk.Label(copy_mod_frame, text="指定修改數值:").grid(row=3, column=0, padx=5, pady=3, sticky="w")
        self.ent_copy_mod_val = ttk.Entry(copy_mod_frame, width=10)
        self.ent_copy_mod_val.grid(row=3, column=1, padx=5, pady=3)
        
        btn_copy_mod = ttk.Button(copy_mod_frame, text="執行條件複製並修改 (連坐右移)", command=self.conditional_copy_and_shift)
        btn_copy_mod.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        # 功能 6：自動尾端接續追加外部 JSON
        import_frame = ttk.LabelFrame(ctrl_frame, text=" 功能六、自動尾端接續追加外部 JSON ")
        import_frame.pack(fill="x", pady=2)
        
        btn_import = ttk.Button(import_frame, text="📥 選擇 1 至多個 JSON 直接追加到最後面", command=self.import_multiple_jsons_at_tail)
        btn_import.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=8)

        # 右側：大型數據結果顯示區
        display_frame = ttk.LabelFrame(main_frame, text=" 數據與日誌顯示主視窗 ")
        display_frame.pack(side="right", fill="both", expand=True)
        
        self.txt_log = ScrolledText(display_frame, font=("Courier New", 11))
        self.txt_log.pack(fill="both", expand=True, padx=5, pady=5)

    def update_dropdowns(self, labels):
        sorted_labels = sorted(labels)
        self.cb_cond_label['values'] = sorted_labels
        self.cb_copy_cond_label['values'] = sorted_labels
        self.cb_copy_mod_label['values'] = sorted_labels
        
        if labels:
            self.cb_cond_label.current(0)
            self.cb_copy_cond_label.current(0)
            self.cb_copy_mod_label.current(0)

    def load_default_file(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.lbl_status.config(text=f"已自動載入預設檔: {self.file_path}", foreground="green")
            labels, _ = self.get_timeline_matrix()
            self.update_dropdowns(labels)
            self.log("成功載入時間軸數據，所有選單功能已解鎖。")
        except FileNotFoundError:
            self.log("提示: 未找到預設的 max_converted_modified.json 檔案，請點擊右側按鈕手動載入。")

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self.file_path = path
                self.lbl_status.config(text=f"已載入: {path.split('/')[-1]}", foreground="green")
                labels, _ = self.get_timeline_matrix()
                self.update_dropdowns(labels)
                self.log(f"成功載入新檔案: {path}")
            except Exception as e:
                messagebox.showerror("錯誤", f"無法讀取 JSON 檔案:\n{e}")

    def save_file(self):
        if not self.data:
            return messagebox.showwarning("警告", "沒有可儲存的數據。")
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1, ensure_ascii=False)
            messagebox.showinfo("成功", "時間軸檔案另存成功！")
            self.log(f"檔案已成功另存至: {path}")

    def log(self, text):
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def get_timeline_matrix(self):
        if not self.data:
            return [], {}
        v_list = self.data.get("value", {}).get("variableList", [])
        labels = [v.get("label") for v in v_list]
        
        time_set = set()
        for v in v_list:
            for f in v.get("frameList", []):
                if f.get("time") is not None:
                    time_set.add(f.get("time"))
        all_times = sorted(list(time_set))
        
        matrix = {t: {} for t in all_times}
        for v in v_list:
            lbl = v.get("label")
            for f in v.get("frameList", []):
                if f.get("time") is not None:
                    matrix[f.get("time")][lbl] = f
        return labels, matrix

    def query_attributes(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
        try:
            t = int(self.ent_time_a.get())
        except ValueError:
            return messagebox.showerror("錯誤", "請在秒數 A 輸入正確的整數時間！")
            
        labels, matrix = self.get_timeline_matrix()
        self.clear_log()
        self.log(f"=== 查詢秒數: {t} 的全通道屬性 ===")
        
        if t not in matrix:
            self.log(f"⚠️ 警告: 時間軸中目前不存在第 {t} 格！")
            return
            
        self.log(f"{'通道標籤 (Channel Label)':<25} | {'數值 (Value)':<15}")
        self.log("-" * 45)
        for lbl in labels:
            frame = matrix[t].get(lbl)
            if frame:
                content = frame.get("content")
                val = content.get("value") if content is not None else "null(結尾)"
                self.log(f"{lbl:<25} | {str(val):<15}")
            else:
                self.log(f"{lbl:<25} | {'-':<15}")

    def compare_attributes(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
        try:
            t1 = int(self.ent_time_a.get())
            t2 = int(self.ent_time_b.get())
        except ValueError:
            return messagebox.showerror("錯誤", "請在秒數 A 和 B 輸入正確的整數時間！")
            
        labels, matrix = self.get_timeline_matrix()
        self.clear_log()
        self.log(f"=== 比較秒數 [{t1}] 與 [{t2}] 的屬性差異 ===")
        self.log(f"{'通道標籤 (Channel)':<25} | {'秒數 ' + str(t1):<12} ➔ {'秒數 ' + str(t2):<12} | 狀態")
        self.log("-" * 65)
        
        diff_count = 0
        for lbl in labels:
            f1 = matrix.get(t1, {}).get(lbl)
            f2 = matrix.get(t2, {}).get(lbl)
            v1 = f1["content"].get("value") if (f1 and f1.get("content")) else ("null" if f1 else "-")
            v2 = f2["content"].get("value") if (f2 and f2.get("content")) else ("null" if f2 else "-")
            
            if v1 != v2:
                self.log(f"{lbl:<25} | {str(v1):<12} ➔ {str(v2):<12} | 🔴 變更")
                diff_count += 1
            else:
                self.log(f"{lbl:<25} | {str(v1):<12} ➔ {str(v2):<12} | 相同")
        self.log("-" * 65)
        self.log(f"總結：共發現 {diff_count} 個通道屬性發生變化。")

    def get_duplicate_groups(self):
        labels, matrix = self.get_timeline_matrix()
        state_groups = {}
        for t in sorted(matrix.keys()):
            current_snapshot = []
            for lbl in labels:
                frame = matrix[t].get(lbl)
                val = frame["content"].get("value") if (frame and frame.get("content") is not None) else "EMPTY_OR_EOF"
                current_snapshot.append((lbl, val))
            state_key = tuple(current_snapshot)
            if state_key not in state_groups:
                state_groups[state_key] = []
            state_groups[state_key].append(t)
        return state_groups

    def find_all_duplicates(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
        state_groups = self.get_duplicate_groups()
        self.clear_log()
        self.log("==================================================")
        self.log(" 🔍 自動尋找全屬性完全相同的秒數格結果：")
        self.log("==================================================")
        
        duplicate_group_count = 0
        for state_key, times in state_groups.items():
            if len(times) > 1:
                duplicate_group_count += 1
                self.log(f"【重複群組 {duplicate_group_count}】➔ 秒數群: {times}")
                self.log("  * 共同屬性狀態:")
                for lbl, val in state_key:
                    if val != "EMPTY_OR_EOF":
                        self.log(f"    - {lbl:<20}: {val}")
                self.log("-" * 50)
                
        if duplicate_group_count == 0:
            self.log("🎉 掃描完成：目前沒有任何完全相同的重複格。")
        else:
            self.log(f"統計完畢：共發現 {duplicate_group_count} 組重複動作結構。")

    def batch_delete_and_shift(self, target_times):
        if not target_times:
            return 0
        sorted_targets = sorted(list(set(target_times)), reverse=True)
        v_list = self.data["value"]["variableList"]
        
        for t in sorted_targets:
            for var in v_list:
                var["frameList"] = [f for f in var.get("frameList", []) if f.get("time") != t]
            for var in v_list:
                for frame in var.get("frameList", []):
                    if frame.get("time") > t:
                        frame["time"] -= 1
        return len(sorted_targets)

    def clean_all_duplicates(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
        state_groups = self.get_duplicate_groups()
        delete_targets = []
        for times in state_groups.values():
            if len(times) > 1:
                delete_targets.extend(times[1:])
                
        if not delete_targets:
            return messagebox.showinfo("提示", "時間軸中目前已經沒有任何重複格需要清除！")
            
        if messagebox.askyesno("確認去重", f"偵測到有 {len(delete_targets)} 個重複格，是否執行一鍵去重並自動向左遞補？"):
            deleted_count = self.batch_delete_and_shift(delete_targets)
            self.clear_log()
            self.log(f"✂️【一鍵自動去重成功】➔ 已成功刪除共 {deleted_count} 個冗餘重複影格，時間軸已完美對齊密合！")

    def conditional_delete_and_shift(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
        chosen_label = self.cb_cond_label.get()
        val_str = self.ent_cond_val.get().strip()
        
        if not chosen_label or not val_str:
            return messagebox.showerror("錯誤", "請選擇一個屬性標籤，並輸入要刪除的指定數值！")
            
        def parse_val(s):
            try: return int(s)
            except ValueError:
                try: return float(s)
                except ValueError: return s
                
        target_value = parse_val(val_str)
        labels, matrix = self.get_timeline_matrix()
        delete_targets = []
        
        for t in matrix.keys():
            frame = matrix[t].get(chosen_label)
            if frame and frame.get("content") is not None:
                if frame["content"].get("value") == target_value:
                    delete_targets.append(t)
                    
        if not delete_targets:
            return messagebox.showinfo("提示", f"找不到任何符合 [{chosen_label} == {target_value}] 的格子。")
            
        if messagebox.askyesno("確認刪除", f"找到了 {len(delete_targets)} 個符合的影格，確定要將這些秒數連坐刪除並左移密合嗎？"):
            deleted_count = self.batch_delete_and_shift(delete_targets)
            self.clear_log()
            self.log(f"🔥【屬性條件刪除成功】➔ 已清除符合條件的 {deleted_count} 格，時間軸自動往前遞補！")

    def conditional_copy_and_shift(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
            
        cond_label = self.cb_copy_cond_label.get()
        cond_val_str = self.ent_copy_cond_val.get().strip()
        mod_label = self.cb_copy_mod_label.get()
        mod_val_str = self.ent_copy_mod_val.get().strip()
        
        if not all([cond_label, cond_val_str, mod_label, mod_val_str]):
            return messagebox.showerror("錯誤", "所有搜尋與修改欄位皆為必填！")
            
        def parse_val(s):
            try: return int(s)
            except ValueError:
                try: return float(s)
                except ValueError: return s
                
        cond_val = parse_val(cond_val_str)
        mod_val = parse_val(mod_val_str)
        
        labels, matrix = self.get_timeline_matrix()
        matching_times = []
        
        for t in sorted(matrix.keys()):
            frame = matrix[t].get(cond_label)
            if frame and frame.get("content") is not None:
                if frame["content"].get("value") == cond_val:
                    matching_times.append(t)
                    
        if not matching_times:
            return messagebox.showinfo("提示", f"全時間軸找不到任何符合 [{cond_label} == {cond_val}] 的秒數。")
            
        if messagebox.askyesno("條件複製確認", f"共找到 {len(matching_times)} 個符合的秒數格。\n將在下一秒插入複製格，並將 [{mod_label}] 修改為 [{mod_val}]，確定執行？"):
            v_list = self.data["value"]["variableList"]
            for t in sorted(matching_times, reverse=True):
                dst = t + 1
                for var in v_list:
                    for frame in var.get("frameList", []):
                        if frame.get("time") >= dst:
                            frame["time"] += 1
                for var in v_list:
                    lbl = var.get("label")
                    src_frame = next((f for f in var.get("frameList", []) if f.get("time") == t), None)
                    if src_frame:
                        new_frame = copy.deepcopy(src_frame)
                        new_frame["time"] = dst
                        if lbl == mod_label and new_frame.get("content") is not None:
                            new_frame["content"]["value"] = mod_val
                        var["frameList"].append(new_frame)
                        var["frameList"].sort(key=lambda x: x["time"])
            self.clear_log()
            self.log(f"🎉【條件複製並修改成功】➔ 符合條件的秒數: {sorted(matching_times)} 後方皆已自動插入並向右右移遞補。")

    def import_multiple_jsons_at_tail(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入主 JSON 檔案。")

        labels, matrix = self.get_timeline_matrix()
        if matrix:
            current_insert_point = max(matrix.keys())
        else:
            current_insert_point = -1 

        paths = filedialog.askopenfilenames(filetypes=[("JSON Files", "*.json")])
        if not paths:
            return

        base_v_list = self.data["value"]["variableList"]
        total_inserted_files = 0
        
        self.clear_log()
        self.log(f"==================================================")
        self.log(f" 📥 自動尾端追加外部 JSON 產線啟動...")
        self.log(f" ➔ 目前主動畫尾端位於第: {current_insert_point if current_insert_point >= 0 else '無(空白軸)'} 秒")
        self.log("==================================================")

        for path in paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    incoming_data = json.load(f)
                
                inc_v_list = incoming_data.get("value", {}).get("variableList", [])
                if not inc_v_list:
                    self.log(f" ⚠️ 跳過檔案 {path.split('/')[-1]}：結構內沒有動畫資料。")
                    continue
                
                inc_times = set()
                for v in inc_v_list:
                    for f_node in v.get("frameList", []):
                        if f_node.get("time") is not None:
                            inc_times.add(f_node.get("time"))
                
                if not inc_times:
                    self.log(f" ⚠️ 跳過檔案 {path.split('/')[-1]}：無任何有效影格。")
                    continue
                    
                min_inc_t = min(inc_times)
                max_inc_t = max(inc_times)
                duration = max_inc_t - min_inc_t + 1 
                
                for inc_var in inc_v_list:
                    lbl = inc_var.get("label")
                    inc_frames = inc_var.get("frameList", [])
                    
                    base_var = next((v for v in base_v_list if v.get("label") == lbl), None)
                    if not base_var:
                        base_var = {"label": lbl, "frameList": []}
                        base_v_list.append(base_var)
                        
                    for f_node in inc_frames:
                        new_f = copy.deepcopy(f_node)
                        new_f["time"] = f_node["time"] - min_inc_t + current_insert_point + 1
                        base_var["frameList"].append(new_f)
                
                file_name = path.split('/')[-1]
                self.log(f" ✅ 成功對齊追加 [{file_name}] 到尾端！")
                self.log(f"    * 片段長度: {duration} 格")
                self.log(f"    * 佔用秒數區間: [{current_insert_point + 1} ~ {current_insert_point + duration}] 格")
                self.log("-" * 50)
                
                current_insert_point += duration
                total_inserted_files += 1
                
            except Exception as e:
                self.log(f" ❌ 讀取檔案失敗 [{path.split('/')[-1]}]: {e}")
                
        for var in base_v_list:
            var["frameList"].sort(key=lambda x: x["time"])
            
        labels, _ = self.get_timeline_matrix()
        self.update_dropdowns(labels) 
        
        self.log(f"🎉【尾端接續追加大功告成】")
        self.log(f" ➔ 總共無縫串接了 {total_inserted_files} 個外部動畫片段。")
        self.log(f" ➔ 現在全新的總動畫長度已完美擴展到第 {current_insert_point} 秒！")

    def copy_and_shift(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
        try:
            src = int(self.ent_copy_src.get())
            dst_str = self.ent_copy_dst.get().strip()
            dst = int(dst_str) if dst_str else src + 1
        except ValueError:
            return messagebox.showerror("錯誤", "來源秒數與目標秒數必須為整數！")
            
        labels, matrix = self.get_timeline_matrix()
        if src not in matrix:
            return messagebox.showerror("錯誤", f"找不到來源秒數 {src} 的影格數據。")
            
        v_list = self.data["value"]["variableList"]
        for var in v_list:
            for frame in var.get("frameList", []):
                if frame.get("time") >= dst:
                    frame["time"] += 1
                    
        for var in v_list:
            src_frame = next((f for f in var.get("frameList", []) if f.get("time") == src), None)
            if src_frame:
                new_frame = copy.deepcopy(src_frame)
                new_frame["time"] = dst
                var["frameList"].append(new_frame)
                var["frameList"].sort(key=lambda x: x["time"])
        self.clear_log()
        self.log(f"🎉【複製並右移成功】➔ 複製 {src} 到 {dst}，其後影格右移 +1。")

    def delete_and_shift(self):
        if not self.data:
            return messagebox.showwarning("提示", "請先載入 JSON 檔案。")
        try:
            target = int(self.ent_del_target.get())
        except ValueError:
            return messagebox.showerror("錯誤", "要刪除的秒數必須為整數！")
            
        labels, matrix = self.get_timeline_matrix()
        if target not in matrix:
            return messagebox.showerror("錯誤", f"時間軸中沒有第 {target} 秒的資料。")
            
        self.batch_delete_and_shift([target])
        self.clear_log()
        self.log(f"🔥【刪除並左移成功】➔ 刪除第 {target} 秒，其後影格左移 -1。")


if __name__ == "__main__":
    root = tk.Tk()
    app = TimelineEditorApp(root)
    root.mainloop()
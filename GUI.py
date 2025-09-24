#!/usr/bin/env python3
import json
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import tkinter as tk
from tkinter import ttk  # for Sizegrip

import requests
from pythonosc import udp_client

# Modern themed ttk
import ttkbootstrap as tb
from ttkbootstrap.scrolled import ScrolledFrame

# ---- Optional toast import (older ttkbootstrap may not have it) ----
try:
    from ttkbootstrap.toast import ToastNotification
    TOAST_AVAILABLE = True
except Exception:
    TOAST_AVAILABLE = False

CONFIG_FILE = "config.json"
LOCAL_TZ = ZoneInfo("America/Chicago")

# Fixed dark theme
DARK_THEME = "darkly"

# --------------------------- Utilities ---------------------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def log_safe(widget: tk.Text, msg: str):
    widget.configure(state="normal")
    widget.insert("end", msg + "\n")
    widget.see("end")
    widget.configure(state="disabled")

def notify(title: str, message: str):
    """Show a small toast if supported, otherwise a standard info dialog."""
    if TOAST_AVAILABLE:
        try:
            ToastNotification(title=title, message=message, duration=2000).show_toast()
            return
        except Exception:
            pass
    # Fallback
    try:
        tb.dialogs.Messagebox.show_info(message, title)
    except Exception:
        # Last resort: print
        print(f"{title}: {message}")

def get_pco_data(url, params=None, app_id=None, secret=None):
    try:
        headers = {'User-Agent': 'PCO-Integration-GUI/2.5'}
        r = requests.get(url, params=params, auth=(app_id, secret), headers=headers, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as err:
        return {"__error__": str(err)}

def fetch_service_types(app_id, secret):
    url = "https://api.planningcenteronline.com/services/v2/service_types"
    data = get_pco_data(url, params={'per_page': 200, 'order': 'name'}, app_id=app_id, secret=secret)
    if "__error__" in data:
        return None, data["__error__"]
    if not data or "data" not in data:
        return [], None
    types = [{"id": d["id"], "name": d["attributes"]["name"]} for d in data["data"]]
    seen, out = set(), []
    for t in types:
        if t["id"] not in seen:
            seen.add(t["id"])
            out.append(t)
    out.sort(key=lambda t: t["name"].lower())
    return out, None

def fetch_plans(app_id, secret, service_type_id, per_page=5):
    url = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans"
    data = get_pco_data(url, params={'filter': 'future', 'order': 'sort_date', 'per_page': per_page},
                        app_id=app_id, secret=secret)
    if "__error__" in data:
        return None, data["__error__"]
    if not data or "data" not in data:
        return [], None
    return data["data"], None

def fetch_plan_items_and_times(app_id, secret, service_type_id, plan_id):
    base = f"https://api.planningcenteronline.com/services/v2/service_types/{service_type_id}/plans/{plan_id}"
    items_data = get_pco_data(base + "/items", params={'per_page': 100, 'include': 'item_times'},
                              app_id=app_id, secret=secret)
    if "__error__" in items_data:
        return None, None, items_data["__error__"]
    if not items_data or "data" not in items_data:
        return None, None, "No items returned."

    times_data = get_pco_data(base + "/plan_times", params={'per_page': 50}, app_id=app_id, secret=secret)
    if "__error__" in times_data:
        return None, None, times_data["__error__"]

    return items_data, times_data, None

def format_time_label(pt_attrs):
    """
    Build a label that keeps the plan-time NAME and adds the local (America/Chicago) time.
    Examples:
      - name + time: "2:00 PM Service — 9:00 AM"
      - only time:   "9:00 AM"
      - only name:   "2:00 PM Service"
    """
    name = (pt_attrs.get("name") or "").strip()
    local_str = ""
    starts = pt_attrs.get("starts_at")
    if starts:
        try:
            if starts.endswith("Z"):
                starts = starts[:-1] + "+00:00"
            dt_utc = datetime.fromisoformat(starts)
            if dt_utc.tzinfo is None:
                from zoneinfo import ZoneInfo as ZI
                dt_utc = dt_utc.replace(tzinfo=ZI("UTC"))
            local_dt = dt_utc.astimezone(LOCAL_TZ)
            local_str = local_dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            local_str = ""

    if name and local_str:
        return f"{name} — {local_str}"
    if local_str:
        return local_str
    return name or ""

# --------------------------- App ---------------------------
class App(tb.Window):
    def __init__(self):
        # Always start in dark theme
        super().__init__(themename=DARK_THEME)

        self.title("PCO → DiGiCo Snapshot Builder")
        self.geometry("1140x820")
        self.minsize(1200, 900)

        # Layout grid
        self.rowconfigure(0, weight=1)   # content row
        self.columnconfigure(0, weight=1)

        self.cfg = load_config()

        # State
        self.service_types = []
        self.plans = []
        self.plan_times = []       # list of (id, label, starts_at_dt)
        self.selected_service_type = None
        self.selected_plan = None

        self.items_data = None
        self.times_data = None
        self.preview_rows = []     # dicts: {"seq", "name", "snap_index"}

        self._build_ui()
        self._load_config_into_fields()
        self._update_send_button_style()

    # helper to autosize combobox width (in characters)
    def _set_combobox_width(self, combo: tb.Combobox, values, min_chars=28, max_chars=80):
        try:
            longest = max((len(v) for v in values), default=min_chars)
            combo.configure(width=max(min_chars, min(longest + 2, max_chars)))
        except Exception:
            combo.configure(width=min_chars)

    # --------------------------- UI ---------------------------
    def _build_ui(self):
        # Scrollable content area (row=0, minimal padding)
        scroller = ScrolledFrame(self, autohide=True, padding=(8, 8, 8, 8), bootstyle="secondary")
        scroller.grid(row=0, column=0, sticky="nsew")
        root = scroller
        root.columnconfigure(0, weight=1)

        # ---- Connections ----
        creds = tb.Labelframe(root, text="Connections", padding=12, bootstyle="info")
        creds.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for i in range(6):
            creds.columnconfigure(i, weight=1)
        creds.columnconfigure(5, minsize=170)

        tb.Label(creds, text="PCO App ID:").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.var_app_id = tk.StringVar()
        tb.Entry(creds, textvariable=self.var_app_id).grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        tb.Label(creds, text="PCO Secret:").grid(row=0, column=2, sticky="e", padx=6, pady=6)
        self.var_secret = tk.StringVar()
        tb.Entry(creds, textvariable=self.var_secret, show="•").grid(row=0, column=3, sticky="ew", padx=6, pady=6)

        self.btn_test_pco = tb.Button(creds, text="Test PCO", bootstyle="outline", command=self.on_test_pco)
        self.btn_test_pco.grid(row=0, column=5, sticky="e", padx=6, pady=6)

        tb.Label(creds, text="DiGiCo IP/Host:").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.var_ip = tk.StringVar()
        tb.Entry(creds, textvariable=self.var_ip).grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        tb.Label(creds, text="OSC Receive Port:").grid(row=1, column=2, sticky="e", padx=6, pady=6)
        self.var_port = tk.StringVar()
        tb.Entry(creds, textvariable=self.var_port, width=10).grid(row=1, column=3, sticky="w", padx=6, pady=6)

        tb.Button(creds, text="Save Config", bootstyle="secondary", command=self.on_save_config)\
          .grid(row=1, column=5, sticky="e", padx=6, pady=6)

        # ---- Service Types & Plans ----
        sp = tb.Labelframe(root, text="Service Types & Plans", padding=12)
        sp.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for i in range(6):
            sp.columnconfigure(i, weight=1)
        sp.columnconfigure(5, minsize=170)

        self.btn_fetch_types = tb.Button(sp, text="Fetch Service Types", bootstyle="primary", command=self.on_fetch_types)
        self.btn_fetch_types.grid(row=0, column=0, padx=6, pady=6, sticky="w")

        tb.Label(sp, text="Service Type:").grid(row=0, column=1, sticky="e", padx=6)
        self.var_service = tk.StringVar()
        self.cmb_service = tb.Combobox(sp, textvariable=self.var_service, state="readonly")
        self.cmb_service.configure(width=50)
        self.cmb_service.grid(row=0, column=2, sticky="ew", padx=6)
        self.cmb_service.bind("<<ComboboxSelected>>", self.on_service_selected)

        tb.Label(sp, text="Show next (plans):").grid(row=0, column=3, sticky="e", padx=6)
        self.var_plan_count = tk.StringVar(value="5")
        tb.Entry(sp, textvariable=self.var_plan_count, width=6).grid(row=0, column=4, sticky="w", padx=6)

        self.btn_fetch_plans = tb.Button(sp, text="Fetch Plans", bootstyle="primary", command=self.on_fetch_plans, state="disabled")
        self.btn_fetch_plans.grid(row=0, column=5, padx=6, sticky="e")

        tb.Label(sp, text="Plan:").grid(row=1, column=0, sticky="e", padx=6)
        self.var_plan = tk.StringVar()
        self.cmb_plan = tb.Combobox(sp, textvariable=self.var_plan, state="disabled")
        self.cmb_plan.configure(width=70)
        self.cmb_plan.grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=6)
        self.cmb_plan.bind("<<ComboboxSelected>>", self.on_plan_selected)

        self.btn_load_plan_times = tb.Button(sp, text="Load Plan Times", bootstyle="primary", command=self.on_load_plan_times, state="disabled")
        self.btn_load_plan_times.grid(row=1, column=5, padx=6, sticky="e")

        # ---- Times & Snapshot Settings ----
        ts = tb.Labelframe(root, text="Times & Snapshot Settings", padding=12)
        ts.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        ts.columnconfigure(1, weight=1)

        tb.Label(ts, text="Plan Times (single-select):").grid(row=0, column=0, sticky="ne", padx=6)
        # Use plain Tk Listbox
        self.lst_times = tk.Listbox(ts, selectmode="extended", height=6, exportselection=False)
        self.lst_times.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        right = tb.Frame(ts)
        right.grid(row=0, column=2, sticky="ne", padx=10)
        self.chk_has_existing = tk.BooleanVar(value=False)
        tb.Checkbutton(
            right, text="Show already has snapshots",
            variable=self.chk_has_existing, bootstyle="round-toggle",
            command=lambda: self._toggle_existing()
        ).grid(row=0, column=0, sticky="w")
        row2 = tb.Frame(right)
        row2.grid(row=1, column=0, sticky="w", pady=(8, 0))
        tb.Label(row2, text="Existing snapshot count:").grid(row=0, column=0, sticky="w")
        self.var_existing_count = tk.StringVar(value="0")
        self.ent_existing_count = tb.Entry(row2, textvariable=self.var_existing_count, width=8, state="disabled")
        self.ent_existing_count.grid(row=0, column=1, sticky="w", padx=(8, 0))

        # ---- Preview & Actions ----
        actions = tb.Frame(root, padding=(0, 6, 0, 0))
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        self.btn_preview = tb.Button(actions, text="Preview Snapshots", bootstyle="info", command=self.on_preview, state="disabled")
        self.btn_preview.grid(row=0, column=0, sticky="w")
        self.btn_send = tb.Button(actions, text="Send to DiGiCo", command=self.on_send, state="disabled")
        self.btn_send.grid(row=0, column=1, sticky="w", padx=(10, 0))

        # ---- Preview Table ----
        prevf = tb.Labelframe(root, text="Preview (nothing is sent until you click 'Send to DiGiCo')", padding=8)
        prevf.grid(row=4, column=0, sticky="nsew", pady=(0, 12))
        root.rowconfigure(4, weight=1)

        cols = ("seq", "name", "snap")
        self.tree = tb.Treeview(prevf, columns=cols, show="headings")
        self.tree.heading("seq", text="#")
        self.tree.heading("name", text="Cue / Snapshot Name")
        self.tree.heading("snap", text="DiGiCo Index (0-based)")
        self.tree.column("seq", width=70, anchor="e")
        self.tree.column("name", width=700, anchor="w")
        self.tree.column("snap", width=220, anchor="e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        prevf.rowconfigure(0, weight=1)
        prevf.columnconfigure(0, weight=1)
        self._apply_tree_striping()  # zebra striping for dark theme

        # ---- Log ----
        logf = tb.Labelframe(root, text="Log", padding=8)
        logf.grid(row=5, column=0, sticky="nsew")
        root.rowconfigure(5, weight=1)
        self.txt_log = tk.Text(logf, height=8, wrap="word")
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        logf.rowconfigure(0, weight=1)
        logf.columnconfigure(0, weight=1)

        # Sizegrip
        ttk.Sizegrip(self).grid(row=999, column=999, sticky="se")

    # --------------------------- Appearance ---------------------------
    def _apply_tree_striping(self):
        """Apply zebra striping to the preview Treeview for dark theme."""
        bg_even = "#1f1f1f"
        bg_odd  = "#262626"
        self.tree.tag_configure("evenrow", background=bg_even)
        self.tree.tag_configure("oddrow", background=bg_odd)

    # --------------------------- Event Handlers ---------------------------
    def on_save_config(self):
        try:
            cfg = load_config()
            cfg["pco_app_id"] = self.var_app_id.get().strip()
            cfg["pco_secret"] = self.var_secret.get().strip()
            cfg["digico_ip"] = self.var_ip.get().strip()
            port_str = self.var_port.get().strip()
            cfg["digico_port"] = int(port_str) if port_str.isdigit() else port_str
            if self.selected_service_type:
                cfg["service_type"] = self.selected_service_type
            save_config(cfg)
            notify("Saved", f"Settings saved to {CONFIG_FILE}.")
        except Exception as e:
            tb.dialogs.Messagebox.show_error(str(e), "Error")

    def on_test_pco(self):
        app_id = self.var_app_id.get().strip()
        secret = self.var_secret.get().strip()
        if not app_id or not secret:
            tb.dialogs.Messagebox.show_error("Enter PCO App ID and Secret first.", "Missing")
            return

        def task():
            log_safe(self.txt_log, "Testing PCO connection…")
            data = get_pco_data("https://api.planningcenteronline.com/services/v2/service_types",
                                params={"per_page": 1}, app_id=app_id, secret=secret)
            if "__error__" in data or not data:
                log_safe(self.txt_log, f"❌ Failed to connect: {data.get('__error__') if isinstance(data, dict) else 'Unknown error'}")
                tb.dialogs.Messagebox.show_error("Failed to authenticate. Check App ID/Secret.", "PCO")
            else:
                log_safe(self.txt_log, "✅ Connected to PCO successfully!")
                notify("PCO", "Connected successfully!")
        threading.Thread(target=task, daemon=True).start()

    def on_fetch_types(self):
        app_id = self.var_app_id.get().strip()
        secret = self.var_secret.get().strip()
        if not app_id or not secret:
            tb.dialogs.Messagebox.show_error("Enter PCO App ID and Secret first.", "Missing")
            return

        def task():
            self.btn_fetch_types.configure(state="disabled")
            log_safe(self.txt_log, "Fetching service types…")
            types, err = fetch_service_types(app_id, secret)
            if err is not None:
                log_safe(self.txt_log, f"❌ {err}")
            elif types is None:
                log_safe(self.txt_log, "❌ Could not load service types.")
            else:
                self.service_types = types
                values = [t["name"] for t in types]
                self.cmb_service.configure(values=values, state="readonly")
                self._set_combobox_width(self.cmb_service, values, min_chars=40)
                self.btn_fetch_plans.configure(state="normal")
                st_saved = self.cfg.get("service_type", {})
                if st_saved and st_saved.get("name") in values:
                    self.cmb_service.set(st_saved["name"])
                    self.selected_service_type = st_saved
                log_safe(self.txt_log, f"Found {len(types)} service types.")
            self.btn_fetch_types.configure(state="normal")

        threading.Thread(target=task, daemon=True).start()

    def on_service_selected(self, _evt=None):
        idx = self.cmb_service.current()
        if idx < 0:
            return
        st = self.service_types[idx]
        self.selected_service_type = {"id": st["id"], "name": st["name"]}
        cfg = load_config()
        cfg["service_type"] = self.selected_service_type
        save_config(cfg)
        log_safe(self.txt_log, f"Selected Service Type: {st['name']} (ID: {st['id']})")
        self._clear_preview()
        self._update_send_button_style()

    def on_fetch_plans(self):
        if not self.selected_service_type:
            tb.dialogs.Messagebox.show_error("Select a Service Type first.", "Missing")
            return
        try:
            n = int(self.var_plan_count.get().strip())
        except Exception:
            n = 5

        app_id = self.var_app_id.get().strip()
        secret = self.var_secret.get().strip()
        stid = self.selected_service_type["id"]

        def task():
            self.btn_fetch_plans.configure(state="disabled")
            log_safe(self.txt_log, f"Fetching next {n} plan(s)…")
            plans, err = fetch_plans(app_id, secret, stid, per_page=n)
            if err is not None:
                log_safe(self.txt_log, f"❌ {err}")
                self.btn_fetch_plans.configure(state="normal")
                return
            self.plans = plans or []
            if not self.plans:
                self.cmb_plan.configure(state="disabled", values=[])
                self.btn_load_plan_times.configure(state="disabled")
                self.btn_preview.configure(state="disabled")
                self._clear_preview()
                self._update_send_button_style()
                log_safe(self.txt_log, "No future plans found.")
                self.btn_fetch_plans.configure(state="normal")
                return
            labels = []
            for p in self.plans:
                date = p["attributes"]["sort_date"][:10] if p["attributes"].get("sort_date") else "Unknown date"
                title = p["attributes"].get("title", "Untitled")
                labels.append(f"{date} — {title}")
            self.cmb_plan.configure(values=labels, state="readonly")
            self._set_combobox_width(self.cmb_plan, labels, min_chars=60)
            self.cmb_plan.current(0)
            self.on_plan_selected()
            self.btn_load_plan_times.configure(state="normal")
            self.btn_fetch_plans.configure(state="normal")

        threading.Thread(target=task, daemon=True).start()

    def on_plan_selected(self, _evt=None):
        idx = self.cmb_plan.current()
        if idx < 0 or idx >= len(self.plans):
            self.selected_plan = None
            return
        self.selected_plan = self.plans[idx]
        log_safe(self.txt_log, f"Selected Plan: {self.cmb_plan.get()}")
        self._clear_preview()
        self._update_send_button_style()

    def on_load_plan_times(self):
        if not self.selected_service_type or not self.selected_plan:
            tb.dialogs.Messagebox.show_error("Select a Service Type and Plan first.", "Missing")
            return
        app_id = self.var_app_id.get().strip()
        secret = self.var_secret.get().strip()
        stid = self.selected_service_type["id"]
        pid = self.selected_plan["id"]

        def task():
            self.btn_load_plan_times.configure(state="disabled")
            log_safe(self.txt_log, "Loading plan items and times…")
            items_data, times_data, err = fetch_plan_items_and_times(app_id, secret, stid, pid)
            if err:
                log_safe(self.txt_log, f"❌ {err}")
                self.btn_load_plan_times.configure(state="normal")
                return
            self.items_data = items_data
            self.times_data = times_data

            times = times_data.get("data") if times_data and "data" in times_data else []
            self.plan_times = []
            for pt in times or []:
                attrs = pt.get("attributes", {})
                label = format_time_label(attrs)
                starts_at_dt = None
                s = attrs.get("starts_at")
                if s:
                    try:
                        if s.endswith("Z"):
                            s = s[:-1] + "+00:00"
                        starts_at_dt = datetime.fromisoformat(s)
                    except Exception:
                        starts_at_dt = None
                self.plan_times.append((pt["id"], label, starts_at_dt))

            if not self.plan_times:
                self.plan_times = [("default", "(default)", None)]

            self.lst_times.delete(0, "end")
            for _, label, _ in sorted(self.plan_times, key=lambda x: x[2] or datetime.max):
                self.lst_times.insert("end", label or "(default)")

            # Preselect common local time by substring (handles "Name — 9:00 AM")
            for i in range(self.lst_times.size()):
                if "9:00 AM" in self.lst_times.get(i):
                    self.lst_times.selection_set(i)

            self.btn_preview.configure(state="normal")
            self.btn_send.configure(state="disabled")
            self._update_send_button_style()
            self._clear_preview()

            self.btn_load_plan_times.configure(state="normal")
            log_safe(self.txt_log, f"Loaded {len(self.plan_times)} time(s). Select and click 'Preview Snapshots'.")

        threading.Thread(target=task, daemon=True).start()

    # ---- Preview / Send ----
    def _collect_preview_rows(self):
        if not hasattr(self, "items_data") or not hasattr(self, "times_data"):
            return [], 0, "Load plan times first."

        sel = self.lst_times.curselection()
        if not sel:
            return [], 0, "Select at least one plan time."

        selected_time_labels = [self.lst_times.get(i) for i in sel]

        # labels -> time ids (allow duplicates)
        time_id_by_label = {}
        for tid, label, _ in self.plan_times:
            key = label or "(default)"
            time_id_by_label.setdefault(key, []).append(tid)

        selected_time_ids = []
        for lbl in selected_time_labels:
            selected_time_ids.extend(time_id_by_label.get(lbl or "(default)", []))

        # offset
        has_existing = self.chk_has_existing.get()
        try:
            existing_count = int(self.var_existing_count.get().strip() or "0")
        except Exception:
            existing_count = 0
        if existing_count < 0:
            existing_count = 0
        snapshot_offset = existing_count if has_existing else 0

        included_item_times = self.items_data.get("included", [])
        plan_items = self.items_data.get("data", [])

        by_time = {tid: [] for tid in selected_time_ids}
        for it in included_item_times:
            if it.get("type") != "ItemTime":
                continue
            rel = it.get("relationships", {}).get("plan_time", {}).get("data", {})
            tid = rel.get("id")
            if tid in by_time:
                by_time[tid].append(it)

        sequences = []
        for lbl in selected_time_labels:
            tids = time_id_by_label.get(lbl or "(default)", [])
            for tid in tids:
                arr = by_time.get(tid, [])
                arr.sort(key=lambda x: x["attributes"].get("live_start_at")
                                      or x["attributes"].get("starts_at")
                                      or "")
                sequences.append((lbl, arr))

        rows = []
        for _lbl, arr in sequences:
            for it in arr:
                it_attrs = it["attributes"]
                if it_attrs.get("exclude", False):
                    continue
                item_id = it.get("relationships", {}).get("item", {}).get("data", {}).get("id")
                if not item_id:
                    continue
                item = next((p for p in plan_items if p["id"] == item_id), None)
                if not item:
                    continue
                item_attrs = item["attributes"]
                if item_attrs.get("item_type") not in ("item", "song"):
                    continue

                title = (item_attrs.get("title") or "Untitled Cue").replace('"', "'")
                rows.append({"name": title})

        for i, row in enumerate(rows):
            row["snap_index"] = snapshot_offset + i
            row["seq"] = i + 1

        return rows, snapshot_offset, None

    def on_preview(self):
        rows, snapshot_offset, err = self._collect_preview_rows()
        if err:
            tb.dialogs.Messagebox.show_error(err, "Preview")
            return

        for r in self.tree.get_children():
            self.tree.delete(r)
        for idx, row in enumerate(rows):
            tag = "oddrow" if idx % 2 else "evenrow"
            self.tree.insert("", "end", values=(row["seq"], row["name"], row["snap_index"]), tags=(tag,))

        self.preview_rows = rows
        log_safe(self.txt_log, f"Preview ready: {len(rows)} snapshot(s), starting at DiGiCo index {snapshot_offset}.")
        self.btn_send.configure(state=("normal" if rows else "disabled"))
        self._update_send_button_style()

    def on_send(self):
        ip = self.var_ip.get().strip()
        port_s = self.var_port.get().strip()
        if not (ip and port_s):
            tb.dialogs.Messagebox.show_error("Please fill DiGiCo IP/port.", "Missing")
            return
        try:
            port = int(port_s)
        except Exception:
            tb.dialogs.Messagebox.show_error("OSC Port must be a number.", "Port")
            return

        if not self.preview_rows:
            tb.dialogs.Messagebox.show_error("Click 'Preview Snapshots' first.", "Nothing to send")
            return

        if not tb.dialogs.Messagebox.yesno(f"Send {len(self.preview_rows)} snapshot(s) to DiGiCo at {ip}:{port}?", "Confirm"):
            return

        def task():
            self.btn_send.configure(state="disabled")
            self._update_send_button_style()
            try:
                client = udp_client.SimpleUDPClient(ip, port)
            except Exception as e:
                log_safe(self.txt_log, f"❌ Failed to create OSC client: {e}")
                self.btn_send.configure(state="normal")
                self._update_send_button_style()
                return

            created = 0
            for row in self.preview_rows:
                name = row["name"]
                snap_index = row["snap_index"]
                try:
                    client.send_message(f"/Snapshots/New_Snapshot/{snap_index}", 0)
                    time.sleep(0.2)
                    client.send_message(f"/Snapshots/Rename_Snapshot/{snap_index}", name)
                    time.sleep(0.2)
                    created += 1
                    log_safe(self.txt_log, f"Snapshot {snap_index}: {name}")
                except Exception as e:
                    log_safe(self.txt_log, f"❌ OSC error at index {snap_index}: {e}")

            log_safe(self.txt_log, f"✅ Done. Created/renamed {created} snapshot(s).")
            self.btn_send.configure(state="normal")
            self._update_send_button_style()

        threading.Thread(target=task, daemon=True).start()

    # --------------------------- Helpers ---------------------------
    def _toggle_existing(self):
        if self.chk_has_existing.get():
            self.ent_existing_count.configure(state="normal")
        else:
            self.ent_existing_count.configure(state="disabled")
        self._clear_preview()
        self._update_send_button_style()

    def _clear_preview(self):
        self.preview_rows = []
        for r in self.tree.get_children():
            self.tree.delete(r)

    def _update_send_button_style(self):
        has_rows = bool(self.preview_rows) and str(self.btn_send['state']) == "normal"
        self.btn_send.configure(bootstyle=("success" if has_rows else "secondary"))

    # --------------------------- Prefill ---------------------------
    def _load_config_into_fields(self):
        self.var_app_id.set(self.cfg.get("pco_app_id", ""))
        self.var_secret.set(self.cfg.get("pco_secret", ""))
        self.var_ip.set(self.cfg.get("digico_ip", ""))
        self.var_port.set(str(self.cfg.get("digico_port", "")))
        st = self.cfg.get("service_type")
        if st and "name" in st:
            self.var_service.set(st["name"])
            self.selected_service_type = st

# --------------------------- Run ---------------------------
if __name__ == "__main__":
    app = App()
    app.mainloop()

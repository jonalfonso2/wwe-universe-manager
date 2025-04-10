import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3, datetime, json, os, re, shutil
from PIL import Image, ImageTk
from tkcalendar import DateEntry, Calendar

# Ensure folders exist
os.makedirs("data", exist_ok=True)
os.makedirs("images", exist_ok=True)

class StorylineApp:
    def __init__(self, root):
        self.root = root
        root.title("WWE Universe Manager")
        root.geometry("1600x1000")

        # Database
        self.conn = sqlite3.connect("data/roster.db")
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.update_schema()
        self.load_settings()

        # State
        self.selected_wrestler_id = None
        self._scroll_widget = None
        self.mg_pool = []
        self.booked_matches = []
        self.card_ids = []

        # Apply saved font
        self.root.option_add("*Font", (self.font, 10))

        # Notebook
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True)
        self.roster_tab    = tk.Frame(nb)
        self.match_gen_tab = tk.Frame(nb)
        self.settings_tab  = tk.Frame(nb)
        self.cards_tab     = tk.Frame(nb)
        nb.add(self.roster_tab,    text="Roster Management")
        nb.add(self.match_gen_tab, text="Match Generator")
        nb.add(self.settings_tab,  text="Settings")
        nb.add(self.cards_tab,     text="Cards")

        # Build UI
        self.build_roster_tab(self.roster_tab)
        self.build_match_generator_tab(self.match_gen_tab)
        self.build_settings_tab(self.settings_tab)
        self.build_cards_tab(self.cards_tab)

        # Initial load
        self.refresh_gallery()
        self.refresh_stats()
        self.refresh_rc_tree()
        self.refresh_stables()
        self.reset_mg_pool()
        self.load_match_gen_roster()
        self.refresh_card()
        self.on_card_date_selected()

        # Mouse-wheel scrolling
        root.bind_all("<MouseWheel>", self._on_mousewheel)

    # Utility for sorting
    def _sort_key(self, name):
        return name.lstrip('"\'' ).lower()

    # Database & Schema
    def create_tables(self):
        # Drop and recreate match_history to ensure correct schema
        self.cursor.execute("DROP TABLE IF EXISTS match_history")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_date TEXT,
                match_number INTEGER,
                winner TEXT,
                losers TEXT,
                style TEXT,
                championship TEXT
            )""")
        # Other tables
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS wrestlers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                gender TEXT,
                alignment TEXT,
                brand TEXT,
                champion TEXT,
                image_path TEXT
            )""")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                wrestler TEXT PRIMARY KEY,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0
            )""")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS championships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                brand TEXT,
                current_holder TEXT,
                type TEXT,
                won_on TEXT,
                gender TEXT
            )""")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS stables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stable_name TEXT,
                members TEXT
            )""")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                brand TEXT,
                card_date TEXT,
                card_data TEXT
            )""")
        self.conn.commit()

    def update_schema(self):
        self.cursor.execute("PRAGMA table_info(wrestlers)")
        cols = [c[1] for c in self.cursor.fetchall()]
        if "champion" not in cols:
            self.cursor.execute("ALTER TABLE wrestlers ADD COLUMN champion TEXT")
        if "image_path" not in cols:
            self.cursor.execute("ALTER TABLE wrestlers ADD COLUMN image_path TEXT")
        self.conn.commit()

    # Settings Persistence
    def load_settings(self):
        if os.path.exists("settings.json"):
            with open("settings.json","r") as f:
                data = json.load(f)
            self.custom_match_types = data.get("custom_match_types", [])
            self.font = data.get("font", "Arial")
        else:
            self.custom_match_types = ["Ladder","TLC","Tables","Submission","Extreme","Intergender"]
            self.font = "Arial"

    def save_settings(self):
        with open("settings.json","w") as f:
            json.dump({
                "custom_match_types": self.custom_match_types,
                "font": self.font
            }, f)

    # Mousewheel Handler
    def _on_mousewheel(self, event):
        if self._scroll_widget:
            self._scroll_widget.yview_scroll(int(-1*(event.delta/120)), "units")

    # Roster Management Tab
    def build_roster_tab(self, frame):
        paned = tk.PanedWindow(frame, sashrelief="raised", orient="horizontal")
        paned.pack(fill="both", expand=True)
        form = tk.Frame(paned, width=300)
        paned.add(form)

        # CRUD fields
        tk.Label(form, text="Name:").grid(row=0,column=0,sticky="e")
        self.name_e = tk.Entry(form); self.name_e.grid(row=0,column=1)
        tk.Label(form, text="Gender:").grid(row=1,column=0,sticky="e")
        self.gender_v = tk.StringVar()
        ttk.Combobox(form, textvariable=self.gender_v,
                     values=["Male","Female"], state="readonly").grid(row=1,column=1)
        tk.Label(form, text="Alignment:").grid(row=2,column=0,sticky="e")
        self.align_v = tk.StringVar()
        ttk.Combobox(form, textvariable=self.align_v,
                     values=["Face","Heel","Both"], state="readonly").grid(row=2,column=1)
        tk.Label(form, text="Brand:").grid(row=3,column=0,sticky="e")
        self.brand_v = tk.StringVar()
        ttk.Combobox(form, textvariable=self.brand_v,
                     values=["All","RAW","SmackDown","NXT"], state="readonly").grid(row=3,column=1)
        self.brand_v.set("All")
        tk.Label(form, text="Image:").grid(row=4,column=0,sticky="e")
        self.image_path_v = tk.StringVar()
        tk.Entry(form, textvariable=self.image_path_v, state="readonly").grid(row=4,column=1)
        tk.Button(form, text="Upload", command=self.upload_image).grid(row=4,column=2)
        tk.Button(form, text="Add", command=self.add_wrestler).grid(row=5,column=0,pady=5)
        tk.Button(form, text="Update", command=self.update_wrestler).grid(row=5,column=1,pady=5)
        tk.Button(form, text="Delete", command=self.delete_wrestler).grid(row=5,column=2,pady=5)

        # Stats
        self.stats_label = tk.Label(form, text="", justify="left")
        self.stats_label.grid(row=6,column=0,columnspan=3,pady=10)

        # Assign Championship
        champ_frame = tk.LabelFrame(form, text="Assign Championship")
        champ_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=5)
        tk.Label(champ_frame, text="Brand:").grid(row=0, column=0, sticky="e")
        self.rc_champ_brand_v = tk.StringVar(value="All")
        ttk.Combobox(champ_frame, textvariable=self.rc_champ_brand_v,
                     values=["All","RAW","SmackDown","NXT"], state="readonly").grid(row=0,column=1)
        self.rc_champ_brand_v.trace("w", lambda *a: self.refresh_rc_titles())
        tk.Label(champ_frame, text="Title:").grid(row=1,column=0,sticky="e")
        self.rc_title_v = tk.StringVar()
        self.rc_title_cb = ttk.Combobox(champ_frame, textvariable=self.rc_title_v, state="readonly")
        self.rc_title_cb.grid(row=1,column=1,sticky="ew")
        self.rc_title_v.trace("w", lambda *a: self.update_assign_list())
        ml_canvas = tk.Canvas(champ_frame, height=100)
        ml_vsb = ttk.Scrollbar(champ_frame, orient="vertical", command=ml_canvas.yview)
        ml_frame = tk.Frame(ml_canvas)
        ml_canvas.configure(yscrollcommand=ml_vsb.set)
        ml_canvas.grid(row=2,column=0,columnspan=3,sticky="nsew")
        ml_vsb.grid(row=2,column=3,sticky="ns")
        ml_canvas.create_window((0,0),window=ml_frame,anchor="nw")
        ml_frame.bind("<Configure>",lambda e:ml_canvas.configure(scrollregion=ml_canvas.bbox("all")))
        ml_canvas.bind("<Enter>",lambda e:setattr(self,"_scroll_widget",ml_canvas))
        ml_canvas.bind("<Leave>",lambda e:setattr(self,"_scroll_widget",None))
        tk.Label(champ_frame,text="Hold CTRL to select multiple",font=("Arial",8,"italic")).grid(row=3,column=0,columnspan=3)
        self.rc_multilist = tk.Listbox(ml_frame,selectmode="extended",height=5,width=60)
        self.rc_multilist.pack(fill="both",expand=True)
        tk.Button(champ_frame,text="Assign",command=self.assign_roster_champ).grid(row=1,column=2,padx=5)

        # Manage Championships
        tk.Label(form,text="Manage Championships:").grid(row=8,column=0,columnspan=3,pady=(10,0))
        tk.Label(form,text="Filter Brand:").grid(row=9,column=0,sticky="e")
        self.rc_manage_brand_v = tk.StringVar(value="All")
        ttk.Combobox(form,textvariable=self.rc_manage_brand_v,values=["All","RAW","SmackDown","NXT"],state="readonly").grid(row=9,column=1)
        self.rc_manage_brand_v.trace("w",lambda *a:self.refresh_rc_tree())
        self.rc_tree = ttk.Treeview(form,columns=("Title","Holder"),show="headings",height=5)
        self.rc_tree.heading("Title",text="Title");self.rc_tree.heading("Holder",text="Holder")
        self.rc_tree.grid(row=10,column=0,columnspan=3,sticky="nsew")
        self.rc_tree.bind("<Enter>",lambda e:setattr(self,"_scroll_widget",self.rc_tree))
        self.rc_tree.bind("<Leave>",lambda e:setattr(self,"_scroll_widget",None))
        btnf = tk.Frame(form);btnf.grid(row=11,column=0,columnspan=3,pady=5)
        tk.Button(btnf,text="Add",command=self.open_champ_popup).pack(side="left",padx=5)
        tk.Button(btnf,text="Update",command=self.open_champ_update_popup).pack(side="left",padx=5)
        tk.Button(btnf,text="Delete",command=self.delete_champ_via_roster).pack(side="left",padx=5)

        # Stable management
        tk.Label(form,text="Stable Name:").grid(row=12,column=0,sticky="e")
        self.stable_name_e = tk.Entry(form)
        self.stable_name_e.grid(row=12,column=1,columnspan=2,sticky="ew")
        sl_canvas = tk.Canvas(form,height=100)
        sl_vsb = ttk.Scrollbar(form,orient="vertical",command=sl_canvas.yview)
        sl_frame = tk.Frame(sl_canvas)
        sl_canvas.configure(yscrollcommand=sl_vsb.set)
        sl_canvas.grid(row=13,column=0,columnspan=3,sticky="nsew")
        sl_vsb.grid(row=13,column=3,sticky="ns")
        sl_canvas.create_window((0,0),window=sl_frame,anchor="nw")
        sl_frame.bind("<Configure>",lambda e:sl_canvas.configure(scrollregion=sl_canvas.bbox("all")))
        sl_canvas.bind("<Enter>",lambda e:setattr(self,"_scroll_widget",sl_canvas))
        sl_canvas.bind("<Leave>",lambda e:setattr(self,"_scroll_widget",None))
        tk.Label(form,text="Hold CTRL to select members",font=("Arial",8,"italic")).grid(row=14,column=0,columnspan=3)
        self.stable_multilist = tk.Listbox(sl_frame,selectmode="extended",height=5,width=60)
        self.stable_multilist.pack(fill="both",expand=True)
        btns = tk.Frame(form);btns.grid(row=15,column=0,columnspan=3,pady=5)
        tk.Button(btns,text="Add Stable",command=self.add_stable).pack(side="left",padx=5)
        tk.Button(btns,text="Update Stable",command=self.update_stable).pack(side="left",padx=5)
        tk.Button(btns,text="Delete Stable",command=self.delete_stable).pack(side="left",padx=5)
        self.st_tree = ttk.Treeview(form,columns=("Name","Members"),show="headings",height=5)
        self.st_tree.heading("Name",text="Name");self.st_tree.heading("Members",text="Members")
        self.st_tree.grid(row=16,column=0,columnspan=3,sticky="nsew")
        self.st_tree.bind("<Enter>",lambda e:setattr(self,"_scroll_widget",self.st_tree))
        self.st_tree.bind("<Leave>",lambda e:setattr(self,"_scroll_widget",None))
        self.refresh_stable_list()

        # Roster gallery
        right = tk.Frame(paned);paned.add(right)
        filt = tk.Frame(right);filt.pack(fill="x",pady=5)
        tk.Label(filt,text="Filter Brand:").pack(side="left",padx=5)
        self.gallery_filter = tk.StringVar(value="All")
        ttk.Combobox(filt,textvariable=self.gallery_filter,values=["All","RAW","SmackDown","NXT"],state="readonly").pack(side="left")
        self.gallery_filter.trace("w",lambda *a:(self.refresh_gallery(),self.refresh_stats()))
        canvas = tk.Canvas(right)
        vsb = ttk.Scrollbar(right,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right",fill="y");canvas.pack(side="left",fill="both",expand=True)
        canvas.bind("<Enter>",lambda e:setattr(self,"_scroll_widget",canvas))
        canvas.bind("<Leave>",lambda e:setattr(self,"_scroll_widget",None))
        self.gallery_inner = tk.Frame(canvas)
        canvas.create_window((0,0),window=self.gallery_inner,anchor="nw")
        self.gallery_inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        right.bind("<Configure>",lambda e:(setattr(self,"gallery_cols",max(1,e.width//140)),self.refresh_gallery()))
        self.gallery_cols=5
        self._thumb_refs=[]

    # ... all helper methods here (upload_image, add_wrestler, update_wrestler, delete_wrestler,
    # refresh_gallery, refresh_stats, championship methods, stable methods, match generator methods,
    # record_result, finalize_card, cards tab methods, settings methods) ...

if __name__ == "__main__":
    root = tk.Tk()
    app = StorylineApp(root)
    root.mainloop()

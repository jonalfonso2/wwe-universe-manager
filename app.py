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

    # ---------- Helper Methods for Roster ----------
    def sanitize_filename(self, name):
        name = name.replace('"','').replace("'", "")
        return re.sub(r'[^A-Za-z0-9_\-]', '_', name)

    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images","*.png *.jpg *.jpeg *.gif")])
        if not path: return
        base = self.sanitize_filename(self.name_e.get().strip().lower())
        ext = os.path.splitext(path)[1]
        dst = os.path.join("images", f"{base}{ext}")
        shutil.copy(path, dst)
        self.image_path_v.set(dst)

    def add_wrestler(self):
        n,g,a,b,img = (
            self.name_e.get().strip(),
            self.gender_v.get().strip(),
            self.align_v.get().strip(),
            self.brand_v.get().strip(),
            self.image_path_v.get().strip()
        )
        if not all([n,g,a,b]):
            return messagebox.showwarning("Missing Info", "Please fill in all fields.")
        try:
            self.cursor.execute(
                "INSERT INTO wrestlers(name,gender,alignment,brand,champion,image_path) VALUES(?,?,?,?,?,?)",
                (n,g,a,b,"",img)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            return messagebox.showerror("Error", "A wrestler with that name already exists.")
        self.refresh_gallery(); self.refresh_stats(); self.refresh_stable_list()

    def select_wrestler(self, name):
        self.cursor.execute(
            "SELECT id,name,gender,alignment,brand,image_path FROM wrestlers WHERE name=?", (name,)
        )
        row = self.cursor.fetchone()
        if not row: return
        wid,n,g,a,b,img = row
        self.selected_wrestler_id = wid
        self.name_e.delete(0, tk.END); self.name_e.insert(0, n)
        self.gender_v.set(g); self.align_v.set(a)
        self.brand_v.set(b); self.image_path_v.set(img or "")

    def update_wrestler(self):
        if self.selected_wrestler_id is None:
            return messagebox.showwarning("No Selection", "Please select a wrestler to update.")
        n,g,a,b,img = (
            self.name_e.get().strip(),
            self.gender_v.get().strip(),
            self.align_v.get().strip(),
            self.brand_v.get().strip(),
            self.image_path_v.get().strip()
        )
        if not all([n,g,a,b]):
            return messagebox.showwarning("Missing Info", "Please fill in all fields for the update.")
        self.cursor.execute(
            "UPDATE wrestlers SET name=?,gender=?,alignment=?,brand=?,image_path=? WHERE id=?",
            (n,g,a,b,img,self.selected_wrestler_id)
        )
        self.conn.commit()
        self.refresh_gallery(); self.refresh_stats(); self.refresh_stable_list()

    def delete_wrestler(self):
        if self.selected_wrestler_id is None:
            return messagebox.showwarning("No Selection", "Please select a wrestler to delete.")
        self.cursor.execute("DELETE FROM wrestlers WHERE id=?", (self.selected_wrestler_id,))
        self.conn.commit()
        self.selected_wrestler_id = None
        self.refresh_gallery(); self.refresh_stats(); self.refresh_stable_list()

    def refresh_gallery(self):
        for w in self.gallery_inner.winfo_children(): w.destroy()
        self._thumb_refs.clear()
        f = self.gallery_filter.get()
        if f == "All":
            self.cursor.execute("SELECT id,name,image_path FROM wrestlers")
        else:
            self.cursor.execute(
                "SELECT id,name,image_path FROM wrestlers WHERE brand=?", (f,)
            )
        rows = self.cursor.fetchall()
        rows.sort(key=lambda r: self._sort_key(r[1]))
        cols = self.gallery_cols
        for idx, (wid, name, imgpath) in enumerate(rows):
            r,c = divmod(idx, cols)
            cell = tk.Frame(self.gallery_inner, bd=1, relief="solid", padx=5, pady=5)
            cell.grid(row=r, column=c, padx=10, pady=10)
            if imgpath and os.path.exists(imgpath):
                img = Image.open(imgpath); img.thumbnail((100,100))
                photo = ImageTk.PhotoImage(img)
            else:
                photo = ImageTk.PhotoImage(Image.new("RGB",(100,100),(200,200,200)))
            lbl = tk.Label(cell, image=photo); lbl.image=photo; lbl.pack()
            self._thumb_refs.append(photo)
            self.cursor.execute("SELECT wins,losses FROM records WHERE wrestler=?", (name,))
            rec = self.cursor.fetchone() or (0,0)
            tk.Label(cell, text=f"{name}\n{rec[0]}–{rec[1]}", wraplength=100).pack()
            self.cursor.execute(
                "SELECT title FROM championships WHERE current_holder LIKE ?", (f"%{name}%",)
            )
            titles = [r[0] for r in self.cursor.fetchall()]
            if titles:
                tk.Label(cell, text="Titles: "+", ".join(titles),
                         wraplength=100, font=(self.font,8,"italic")).pack()
            lbl.bind("<Button-1>", lambda e,nm=name: self.select_wrestler(nm))

    def refresh_stats(self):
        f = self.gallery_filter.get()
        if f == "All":
            total = self.cursor.execute("SELECT COUNT(*) FROM wrestlers").fetchone()[0]
            face  = self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE alignment='Face'").fetchone()[0]
            heel  = self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE alignment='Heel'").fetchone()[0]
            male  = self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE gender='Male'").fetchone()[0]
            female= self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE gender='Female'").fetchone()[0]
        else:
            total = self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE brand=?", (f,)).fetchone()[0]
            face  = self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE brand=? AND alignment='Face'", (f,)).fetchone()[0]
            heel  = self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE brand=? AND alignment='Heel'", (f,)).fetchone()[0]
            male  = self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE brand=? AND gender='Male'", (f,)).fetchone()[0]
            female= self.cursor.execute("SELECT COUNT(*) FROM wrestlers WHERE brand=? AND gender='Female'", (f,)).fetchone()[0]
        self.stats_label.config(
            text=f"Stats for {f}:\nTotal: {total} | Face: {face} | Heel: {heel}\nMale: {male} | Female: {female}"
        )

    # ---------- Championship Methods ----------
    def refresh_rc_titles(self):
        b = self.rc_champ_brand_v.get()
        if b == "All":
            self.cursor.execute("SELECT title FROM championships")
        else:
            self.cursor.execute("SELECT title FROM championships WHERE brand=?", (b,))
        titles = [r[0] for r in self.cursor.fetchall()]
        titles.sort(key=self._sort_key)
        self.rc_title_cb['values'] = titles
        self.rc_title_v.set("")
        self.rc_multilist.delete(0, tk.END)

    def update_assign_list(self):
        title = self.rc_title_v.get().strip()
        self.rc_multilist.delete(0, tk.END)
        if not title: return
        self.cursor.execute("SELECT gender,brand FROM championships WHERE title=?", (title,))
        row = self.cursor.fetchone()
        gender, champ_brand = (row if row else (None,None))
        q = "SELECT name FROM wrestlers WHERE 1=1"
        params = []
        if gender:
            q += " AND gender=?"; params.append(gender)
        if champ_brand and champ_brand != "All":
            q += " AND brand=?"; params.append(champ_brand)
        self.cursor.execute(q, tuple(params))
        names = [r[0] for r in self.cursor.fetchall()]
        names.sort(key=self._sort_key)
        for nm in names:
            self.rc_multilist.insert(tk.END, nm)

    def assign_roster_champ(self):
        title = self.rc_title_v.get().strip()
        sels = [self.rc_multilist.get(i) for i in self.rc_multilist.curselection()]
        if not title or not sels:
            return messagebox.showwarning("Missing", "Select a title and at least one wrestler.")
        holder = " & ".join(sels)
        today = datetime.date.today().strftime("%Y-%m-%d")
        self.cursor.execute(
            "UPDATE championships SET current_holder=?,won_on=? WHERE title=?",
            (holder, today, title)
        )
        self.conn.commit()
        self.refresh_rc_tree()
        self.refresh_gallery()

    def open_champ_popup(self):
        win = tk.Toplevel(); win.title("Add Championship")
        tk.Label(win, text="Title:").grid(row=0, column=0, sticky="e")
        title_v = tk.StringVar(); tk.Entry(win, textvariable=title_v).grid(row=0, column=1)
        tk.Label(win, text="Brand:").grid(row=1, column=0, sticky="e")
        brand_v = tk.StringVar()
        ttk.Combobox(win, textvariable=brand_v, values=["RAW","SmackDown","NXT"], state="readonly").grid(row=1, column=1)
        brand_v.set("RAW")
        tk.Label(win, text="Type:").grid(row=2, column=0, sticky="e")
        type_v = tk.StringVar()
        ttk.Combobox(win, textvariable=type_v, values=["Singles","Tag"], state="readonly").grid(row=2, column=1)
        type_v.set("Singles")
        tk.Label(win, text="Gender:").grid(row=3, column=0, sticky="e")
        gender_v = tk.StringVar()
        ttk.Combobox(win, textvariable=gender_v, values=["Male","Female"], state="readonly").grid(row=3, column=1)
        def save():
            t,b,ty,g = title_v.get().strip(), brand_v.get(), type_v.get(), gender_v.get().strip()
            if not all([t,b,ty,g]):
                return messagebox.showwarning("Missing", "Fill all fields.", parent=win)
            self.cursor.execute("""
                INSERT INTO championships(title,brand,current_holder,type,won_on,gender)
                VALUES(?,?,?,?,?,?)
            """, (t,b,"",ty,"",g))
            self.conn.commit()
            self.refresh_rc_tree(); win.destroy()
        tk.Button(win, text="Save", command=save).grid(row=4, column=0, pady=5)
        tk.Button(win, text="Cancel", command=win.destroy).grid(row=4, column=1)

    def open_champ_update_popup(self):
        sel = self.rc_tree.selection()
        if not sel: return messagebox.showwarning("Select", "Select a championship.")
        old = self.rc_tree.item(sel[0], "values")[0]
        win = tk.Toplevel(); win.title("Update Championship")
        tk.Label(win, text="Title:").grid(row=0, column=0, sticky="e")
        title_v = tk.StringVar(value=old); tk.Entry(win, textvariable=title_v).grid(row=0, column=1)
        def save():
            new = title_v.get().strip()
            if not new: return
            self.cursor.execute("UPDATE championships SET title=? WHERE title=?", (new,old))
            self.conn.commit()
            self.refresh_rc_tree(); win.destroy()
        tk.Button(win, text="Save", command=save).grid(row=1, column=0, pady=5)
        tk.Button(win, text="Cancel", command=win.destroy).grid(row=1, column=1)

    def delete_champ_via_roster(self):
        sel = self.rc_tree.selection()
        if not sel: return messagebox.showwarning("Select", "Select a championship.")
        title = self.rc_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Delete", f"Delete '{title}'?"):
            self.cursor.execute("DELETE FROM championships WHERE title=?", (title,))
            self.conn.commit()
            self.refresh_rc_tree()
            self.refresh_gallery()

    def refresh_rc_tree(self):
        self.rc_tree.delete(*self.rc_tree.get_children())
        b = self.rc_manage_brand_v.get()
        if b == "All":
            self.cursor.execute("SELECT title,current_holder FROM championships")
        else:
            self.cursor.execute("SELECT title,current_holder FROM championships WHERE brand=?", (b,))
        rows = self.cursor.fetchall()
        rows.sort(key=lambda r: self._sort_key(r[0]))
        for title, holder in rows:
            self.rc_tree.insert("", "end", values=(title, holder))

    # ---------- Stable Methods ----------
    def refresh_stable_list(self):
        self.stable_multilist.delete(0, tk.END)
        self.cursor.execute("SELECT name FROM wrestlers")
        names = [r[0] for r in self.cursor.fetchall()]
        names.sort(key=self._sort_key)
        for nm in names:
            self.stable_multilist.insert(tk.END, nm)

    def add_stable(self):
        name = self.stable_name_e.get().strip()
        sels = [self.stable_multilist.get(i) for i in self.stable_multilist.curselection()]
        if not name or len(sels)<2:
            return messagebox.showwarning("Missing", "Enter a name and select at least 2 members.")
        members = ", ".join(sels)
        self.cursor.execute("INSERT INTO stables(stable_name,members) VALUES(?,?)", (name, members))
        self.conn.commit()
        self.refresh_stables()

    def update_stable(self):
        sel = self.st_tree.selection()
        if not sel:
            return messagebox.showwarning("Select", "Select a stable to update.")
        old_name, _ = self.st_tree.item(sel[0], "values")
        name = self.stable_name_e.get().strip()
        sels = [self.stable_multilist.get(i) for i in self.stable_multilist.curselection()]
        if not name or len(sels)<2:
            return messagebox.showwarning("Missing", "Enter a name and select at least 2 members.")
        members = ", ".join(sels)
        self.cursor.execute("UPDATE stables SET stable_name=?,members=? WHERE stable_name=?", (name, members, old_name))
        self.conn.commit()
        self.refresh_stables()

    def delete_stable(self):
        sel = self.st_tree.selection()
        if not sel:
            return messagebox.showwarning("Select", "Select a stable to delete.")
        name = self.st_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Delete", f"Delete '{name}'?"):
            self.cursor.execute("DELETE FROM stables WHERE stable_name=?", (name,))
            self.conn.commit()
            self.refresh_stables()

    def refresh_stables(self):
        self.st_tree.delete(*self.st_tree.get_children())
        self.cursor.execute("SELECT stable_name,members FROM stables")
        rows = self.cursor.fetchall()
        rows.sort(key=lambda r: self._sort_key(r[0]))
        for stable_name, members in rows:
            self.st_tree.insert("", "end", values=(stable_name, members))

    # ---------- Match Generator Tab ----------
    def build_match_generator_tab(self, frame):
        frame.bind("<Configure>", lambda e: self._resize_mg_gallery(e.width))

        gf = tk.Frame(frame); gf.pack(fill="both", expand=True, padx=10, pady=10)
        cf = tk.Frame(gf); cf.pack(fill="x", pady=5)

        tk.Label(cf, text="Brand:").pack(side="left", padx=5)
        self.mg_brand = tk.StringVar(value="All")
        ttk.Combobox(cf, textvariable=self.mg_brand,
                     values=["All","RAW","SmackDown","NXT"],
                     state="readonly", width=12).pack(side="left")
        self.mg_brand.trace("w", lambda *a: self.reset_mg_pool())

        tk.Label(cf, text="# Wrestlers:").pack(side="left", padx=5)
        self.mg_num = tk.IntVar(value=2)
        ttk.Combobox(cf, textvariable=self.mg_num,
                     values=list(range(2,9)), state="readonly", width=3).pack(side="left")
        self.mg_num.trace("w", lambda *a: self.update_mg_formats())

        tk.Label(cf, text="Format:").pack(side="left", padx=5)
        self.mg_fmt = tk.StringVar()
        self.mg_fmt_cb = ttk.Combobox(cf, textvariable=self.mg_fmt, state="readonly", width=12)
        self.mg_fmt_cb.pack(side="left")

        tk.Label(cf, text="Style:").pack(side="left", padx=5)
        self.mg_style = tk.StringVar()
        self.mg_style_cb = ttk.Combobox(cf, textvariable=self.mg_style,
                                        values=self.custom_match_types,
                                        state="readonly", width=12)
        self.mg_style_cb.pack(side="left")
        tk.Button(cf, text="+", width=2, command=self.open_style_add).pack(side="left", padx=2)
        tk.Button(cf, text="–", width=2, command=self.open_style_del).pack(side="left", padx=2)

        tk.Label(cf, text="Championship:").pack(side="left", padx=5)
        self.mg_champ = tk.StringVar()
        self.mg_champ_cb = ttk.Combobox(cf, textvariable=self.mg_champ, state="readonly", width=18)
        self.mg_champ_cb.pack(side="left")
        self.mg_champ.trace("w", lambda *a: self.on_mg_champ_selected())

        tk.Button(cf, text="Add to Card", command=self.add_to_card).pack(side="left", padx=5)
        tk.Button(cf, text="Clear Card",  command=self.clear_card).pack(side="left")

        compf = tk.Frame(gf); compf.pack(pady=5)
        self.mg_vars = []; self.mg_cbs = []
        for i in range(8):
            v = tk.StringVar()
            cb = ttk.Combobox(compf, textvariable=v, state="readonly", width=12)
            cb.grid(row=i//4, column=i%4, padx=5, pady=2)
            cb.grid_remove()
            self.mg_vars.append(v); self.mg_cbs.append(cb)

        mg_right = tk.Frame(gf); mg_right.pack(fill="both", expand=True)
        canvas = tk.Canvas(mg_right)
        vsb = ttk.Scrollbar(mg_right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.bind("<Enter>", lambda e: setattr(self, "_scroll_widget", canvas))
        canvas.bind("<Leave>", lambda e: setattr(self, "_scroll_widget", None))

        self.mg_gallery = tk.Frame(canvas)
        canvas.create_window((0,0), window=self.mg_gallery, anchor="nw")
        self.mg_gallery.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.mg_gallery_cols = 8
        self.mg_thumb_refs = []

        # Match Card area
        cardf = tk.LabelFrame(gf, text="Match Card")
        cardf.pack(fill="both", expand=True, padx=10, pady=10)
        self.card_frame = cardf

        # Finalize & Lock
        btnf = tk.Frame(gf); btnf.pack(pady=5)
        tk.Button(btnf, text="Finalize & Save Card", command=self.finalize_card).pack(side="left", padx=5)

    # ---------- Match Generator Helpers ----------
    def on_mg_champ_selected(self):
        champ = self.mg_champ.get()
        for v,cb in zip(self.mg_vars, self.mg_cbs):
            v.set(""); cb.grid_remove()
        self.reset_mg_pool()
        if champ and champ != "None":
            self.cursor.execute("SELECT current_holder FROM championships WHERE title=?", (champ,))
            row = self.cursor.fetchone()
            if row and row[0]:
                holders = row[0].split(" & ")
                for i,h in enumerate(holders):
                    if h in self.mg_pool:
                        self.mg_vars[i].set(h)
                        self.mg_cbs[i].grid()
                        self.mg_pool.remove(h)
                self.mg_pool.sort(key=self._sort_key)
                for cb in self.mg_cbs:
                    if cb.winfo_ismapped():
                        cb['values'] = self.mg_pool.copy()

    def open_style_add(self):
        win = tk.Toplevel(); win.title("Add Style")
        tk.Label(win, text="New Style:").grid(row=0, column=0, sticky="e")
        v = tk.StringVar(); tk.Entry(win, textvariable=v).grid(row=0, column=1)
        def save():
            s = v.get().strip()
            if s and s not in self.custom_match_types:
                self.custom_match_types.append(s)
                self.save_settings()
                self.mg_style_cb['values'] = self.custom_match_types
            win.destroy()
        tk.Button(win, text="Add",    command=save).grid(row=1, column=0)
        tk.Button(win, text="Cancel", command=win.destroy).grid(row=1, column=1)

    def open_style_del(self):
        win = tk.Toplevel(); win.title("Delete Style")
        lb = tk.Listbox(win, selectmode="single")
        lb.pack()
        for s in self.custom_match_types: lb.insert(tk.END, s)
        def delete():
            sel = lb.curselection()
            if sel:
                s = lb.get(sel[0])
                self.custom_match_types.remove(s)
                self.save_settings()
                self.mg_style_cb['values'] = self.custom_match_types
            win.destroy()
        tk.Button(win, text="Delete", command=delete).pack()
        tk.Button(win, text="Cancel", command=win.destroy).pack()

    def reset_mg_pool(self):
        b = self.mg_brand.get()
        if b == "All":
            self.cursor.execute("SELECT name FROM wrestlers")
        else:
            self.cursor.execute("SELECT name FROM wrestlers WHERE brand=?", (b,))
        names = [r[0] for r in self.cursor.fetchall()]
        names.sort(key=self._sort_key)
        self.mg_pool = names
        for v in self.mg_vars: v.set("")
        for cb in self.mg_cbs: cb.grid_remove()
        self.load_match_gen_roster()

    def _resize_mg_gallery(self, width):
        self.mg_gallery_cols = max(1, width // 100)
        self.refresh_match_gallery()

    def load_match_gen_roster(self):
        self.update_mg_formats()

        b = self.mg_brand.get()
        # Show all titles if Brand is “All”
        if b == "All":
            self.cursor.execute("SELECT title FROM championships")
        else:
            self.cursor.execute("SELECT title FROM championships WHERE brand=?", (b,))

        titles = ["None"] + [r[0] for r in self.cursor.fetchall()]
        titles.sort(key=self._sort_key)

        self.mg_champ_cb['values'] = titles
        if self.mg_champ.get() not in titles:
            self.mg_champ.set("None")
        
            # After resetting self.mg_pool...
        champ = self.mg_champ.get()
        if champ and champ != "None":
            # Lookup the championship’s gender
            self.cursor.execute("SELECT gender, type FROM championships WHERE title=?", (champ,))
            row = self.cursor.fetchone()
            if row:
                gender, ctype = row
                # Filter by gender
                self.mg_pool = [w for w in self.mg_pool if self.get_wrestler_gender(w) == gender]
    def get_wrestler_gender(self, name):
        self.cursor.execute("SELECT gender FROM wrestlers WHERE name=?", (name,))
        r = self.cursor.fetchone()
        return r[0] if r else None

    def refresh_match_gallery(self):
        booked = {p for m in self.booked_matches for team in m["teams"] for p in team}
        available = [w for w in self.mg_pool if w not in booked]
        for w in self.mg_gallery.winfo_children(): w.destroy()
        self.mg_thumb_refs.clear()
        for idx,name in enumerate(self.mg_pool):
            imgpath = self.cursor.execute("SELECT image_path FROM wrestlers WHERE name=?", (name,)).fetchone()[0]
            r, c = divmod(idx, self.mg_gallery_cols)
            cell = tk.Frame(self.mg_gallery, bd=1, relief="solid", padx=3, pady=3)
            cell.grid(row=r, column=c, padx=5, pady=5)
            if imgpath and os.path.exists(imgpath):
                img = Image.open(imgpath); img.thumbnail((60,60))
                photo = ImageTk.PhotoImage(img)
            else:
                photo = ImageTk.PhotoImage(Image.new("RGB",(60,60),(200,200,200)))
            lbl = tk.Label(cell, image=photo); lbl.image=photo; lbl.pack()
            self.mg_thumb_refs.append(photo)
            tk.Label(cell, text=name, wraplength=60).pack()
            lbl.bind("<Button-1>", lambda e,nm=name: self.add_competitor(nm))

    def add_competitor(self, name):
        if name not in self.mg_pool: return
        self.mg_pool.remove(name)
        for v,cb in zip(self.mg_vars, self.mg_cbs):
            if cb.winfo_ismapped() and not v.get():
                v.set(name)
                break
        self.refresh_match_gallery()
        for cb in self.mg_cbs:
            if cb.winfo_ismapped():
                cb['values'] = self.mg_pool.copy()

    def update_mg_formats(self, *_):
        opts = {
            2:["1 v 1"], 3:["1 v 1 v 1","1 v 2"], 4:["1 v 1 v 1 v 1","2 v 2","1 v 3"],
            5:["1 v 1 v 1 v 1 v 1","2 v 3"], 6:["1 v 1 v 1 v 1 v 1 v 1","3 v 3","2 v 2 v 2"],
            7:["1 v 1 v 1 v 1 v 1 v 1 v 1"], 8:["1 v 1 v 1 v 1 v 1 v 1 v 1 v 1","2 v 2 v 2 v 2","4 v 4"]
        }
        n = self.mg_num.get(); fmts = opts.get(n, [])
        self.mg_fmt_cb['values'] = fmts
        if fmts: self.mg_fmt.set(fmts[0])
        fmt = self.mg_fmt.get()
        if fmt:
            nums = list(map(int, fmt.split(" v "))); total = sum(nums)
            for cb in self.mg_cbs: cb.grid_remove()
            for i in range(total): self.mg_cbs[i].grid()

    def add_to_card(self):
        fmt, style, champ = self.mg_fmt.get(), self.mg_style.get(), self.mg_champ.get()
        nums = list(map(int, fmt.split(" v ")))
        comps = [v.get() for v in self.mg_vars if v.get()]
        for p in comps:
            if p in self.mg_pool: self.mg_pool.remove(p)
        self.mg_pool.sort(key=self._sort_key)
        for cb in self.mg_cbs:
            if cb.winfo_ismapped():
                cb['values'] = self.mg_pool.copy()
        teams = []; idx = 0
        for n in nums:
            teams.append(comps[idx:idx+n]); idx += n
        self.booked_matches.append({
            "teams": teams,
            "style": style,
            "championship": champ if champ and champ!="None" else None
        })
        for v in self.mg_vars: v.set("")
        self.refresh_card()
        self.refresh_match_gallery()

    def clear_card(self):
        b = self.mg_brand.get()
        for m in self.booked_matches:
            for team in m["teams"]:
                for p in team:
                    if p not in self.mg_pool:
                        if b=="All" or self.get_wrestler_brand(p)==b:
                            self.mg_pool.append(p)
        self.mg_pool.sort(key=self._sort_key)
        self.booked_matches = []
        self.refresh_card()
        self.refresh_match_gallery()

    def get_wrestler_brand(self, name):
        self.cursor.execute("SELECT brand FROM wrestlers WHERE name=?", (name,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    # ---------- Match Card Display & Reordering ----------
    def refresh_card(self):
        for w in self.card_frame.winfo_children(): w.destroy()
        for i, m in enumerate(self.booked_matches):
            mf = tk.LabelFrame(self.card_frame, text=f"Match {i+1}", bd=1, relief="solid", padx=5, pady=5)
            row, col = divmod(i, 2)
            mf.grid(row=row, column=col, padx=5, pady=5, sticky="nw")
            # Teams
            for ti,team in enumerate(m["teams"]):
                tf = tk.Frame(mf); tf.pack(side="left", padx=2)
                for p in team:
                    imgpath = self.cursor.execute(
                        "SELECT image_path FROM wrestlers WHERE name=?", (p,)
                    ).fetchone()[0]
                    if imgpath and os.path.exists(imgpath):
                        img = Image.open(imgpath); img.thumbnail((60,60))
                        photo = ImageTk.PhotoImage(img)
                    else:
                        photo = ImageTk.PhotoImage(Image.new("RGB",(60,60),(200,200,200)))
                    lbl = tk.Label(tf, image=photo); lbl.image=photo; lbl.pack()
                    tk.Label(tf, text=p, wraplength=60).pack()
                if ti < len(m["teams"]) - 1:
                    tk.Label(mf, text="v.", font=("Arial",12,"bold")).pack(side="left", padx=2)
            # Champion vs Challenger line
            if m["championship"]:
                self.cursor.execute("SELECT current_holder FROM championships WHERE title=?", (m["championship"],))
                holders = self.cursor.fetchone()[0].split(" & ")
                champ_team = next(t for t in m["teams"] if any(h in t for h in holders))
                chall_team = next(t for t in m["teams"] if t is not champ_team)
                text = f"{' & '.join(champ_team)} (Champion) vs {' & '.join(chall_team)} (Challenger)"
                tk.Label(mf, text=text, font=(self.font,9,"italic")).pack(pady=(2,2))
            # Style & Title info
            info = f"Style: {m['style']}"
            if m["championship"]:
                info += f"  |  Title: {m['championship']}"
            tk.Label(mf, text=info, font=(self.font,9,"italic")).pack(pady=(2,5))
            # Controls
            ctrl = tk.Frame(mf); ctrl.pack(pady=2)
            tk.Label(ctrl, text="Winner:").pack(side="left")
            win_v = tk.StringVar()
            tlabels = [" & ".join(t) for t in m["teams"]]
            win_cb = ttk.Combobox(ctrl, textvariable=win_v, values=tlabels,
                                  state="readonly", width=12)
            win_cb.pack(side="left")
            win_cb.bind("<<ComboboxSelected>>", lambda e, idx=i: self.record_result(idx))
            tk.Button(ctrl, text="↑", command=lambda idx=i: self.move_match(idx, -1)).pack(side="left")
            tk.Button(ctrl, text="↓", command=lambda idx=i: self.move_match(idx, 1)).pack(side="left")
            tk.Button(ctrl, text="Delete", command=lambda idx=i: self.delete_match(idx)).pack(side="left", padx=2)

    def move_match(self, idx, delta):
        new = max(0, min(len(self.booked_matches)-1, idx + delta))
        if new != idx:
            m = self.booked_matches.pop(idx)
            self.booked_matches.insert(new, m)
            self.refresh_card()

    def record_result(self, index):
        m = self.booked_matches[index]
        mf = self.card_frame.grid_slaves(row=index//2, column=index%2)[0]
        ctrl = mf.winfo_children()[-1]
        win_cb = ctrl.winfo_children()[1]
        winner_label = win_cb.get()
        if not winner_label: return
        teams = m["teams"]
        winners = next((t for t in teams if " & ".join(t) == winner_label), [])
        losers = [p for team in teams for p in team if p not in winners]
        # Update records
        for w in winners:
            self.cursor.execute("INSERT OR IGNORE INTO records(wrestler) VALUES(?)", (w,))
            self.cursor.execute("UPDATE records SET wins=wins+1 WHERE wrestler=?", (w,))
        for l in losers:
            self.cursor.execute("INSERT OR IGNORE INTO records(wrestler) VALUES(?)", (l,))
            self.cursor.execute("UPDATE records SET losses=losses+1 WHERE wrestler=?", (l,))
        # Championship change
        champ = m["championship"]
        if champ and winners:
            today_str = self.card_calendar.get_date()
            self.cursor.execute("UPDATE championships SET current_holder=?,won_on=? WHERE title=?", (winners[0], today_str, champ))
        # Save to match_history
        card_date = self.card_calendar.get_date()
        self.cursor.execute("""
            INSERT INTO match_history(card_date,match_number,winner,losers,style,championship)
            VALUES(?,?,?,?,?,?)
        """, (
            card_date,
            index+1,
            winner_label,
            ",".join(losers),
            m["style"],
            champ or ""
        ))
        self.conn.commit()
        # Return losers to pool
        for p in losers:
            if p not in self.mg_pool:
                if self.mg_brand.get()=="All" or self.get_wrestler_brand(p)==self.mg_brand.get():
                    self.mg_pool.append(p)
        self.mg_pool.sort(key=self._sort_key)
        self.refresh_stats()
        self.refresh_match_gallery()
        # Gray out combobox & disable buttons
        win_cb.config(state="disabled")
        for w in ctrl.winfo_children():
            if isinstance(w, tk.Button):
                w.config(state="disabled")

    def delete_match(self, index):
        m = self.booked_matches.pop(index)
        for team in m["teams"]:
            for p in team:
                if p not in self.mg_pool:
                    if self.mg_brand.get()=="All" or self.get_wrestler_brand(p)==self.mg_brand.get():
                        self.mg_pool.append(p)
        self.mg_pool.sort(key=self._sort_key)
        self.refresh_card(); self.refresh_match_gallery()

    # ---------- Finalize & Save Card ----------
    def finalize_card(self):
        win = tk.Toplevel(); win.title("Finalize & Save Card")
        tk.Label(win, text="Card Name:").grid(row=0, column=0, sticky="e")
        name_v = tk.StringVar()
        date_str = self.card_calendar.get_date()
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        default_brand = self.mg_brand.get()
        name_v.set(f"{default_brand} - {date_obj.strftime('%B %d %Y')}")
        tk.Entry(win, textvariable=name_v).grid(row=0, column=1)
        tk.Label(win, text="Brand:").grid(row=1, column=0, sticky="e")
        brand_v = tk.StringVar()
        ttk.Combobox(win, textvariable=brand_v,
            values=["RAW","SmackDown","NXT"], state="readonly").grid(row=1, column=1)
        brand_v.set(default_brand)
        tk.Label(win, text="Date:").grid(row=2, column=0, sticky="e")
        date_e = DateEntry(win, date_pattern="yyyy-mm-dd")
        date_e.set_date(date_obj)
        date_e.grid(row=2, column=1)
        def save():
            nm = name_v.get().strip()
            bd = brand_v.get().strip()
            dt = date_e.get_date().strftime("%Y-%m-%d")
            if not nm or not bd:
                return messagebox.showwarning("Missing", "Name & Brand required.", parent=win)
            data = json.dumps(self.booked_matches)
            self.cursor.execute("""
                INSERT INTO cards(name,brand,card_date,card_data)
                VALUES(?,?,?,?)
            """, (nm,bd,dt,data))
            self.conn.commit()
            self.on_card_date_selected()
            self.refresh_stats()
            self.refresh_gallery()
            win.destroy()
        tk.Button(win, text="Save", command=save).grid(row=3, column=0, pady=5)
        tk.Button(win, text="Cancel", command=win.destroy).grid(row=3, column=1)

    # ---------- Cards Tab ----------
    def build_cards_tab(self, frame):
        left = tk.Frame(frame)
        left.pack(side="left", fill="y", padx=10, pady=10)
        tk.Label(left, text="Select Date:").pack()
        self.card_calendar = Calendar(left, selectmode="day", date_pattern="yyyy-mm-dd")
        self.card_calendar.pack()
        self.card_calendar.bind("<<CalendarSelected>>", lambda e: self.on_card_date_selected())

        right = tk.Frame(frame)
        right.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        tk.Label(right, text="Cards on Selected Date:").pack()
        self.card_listbox = tk.Listbox(right)
        self.card_listbox.pack(fill="both", expand=True)
        self.card_listbox.bind("<Double-Button-1>", lambda e: self.show_card_details())
        btnf = tk.Frame(right); btnf.pack(pady=5)
        tk.Button(btnf, text="Load", command=self.load_card_from_list).pack(side="left", padx=5)
        tk.Button(btnf, text="Delete", command=self.delete_card_from_list).pack(side="left", padx=5)

    def on_card_date_selected(self):
        date = self.card_calendar.get_date()
        self.card_listbox.delete(0, tk.END)
        self.card_ids = []
        self.cursor.execute("SELECT id,name FROM cards WHERE card_date=?", (date,))
        rows = self.cursor.fetchall()
        rows.sort(key=lambda r: self._sort_key(r[1]))
        for cid, nm in rows:
            self.card_listbox.insert(tk.END, nm)
            self.card_ids.append(cid)

    def load_card_from_list(self):
        sel = self.card_listbox.curselection()
        if not sel: return messagebox.showwarning("Select", "Select a card to load.")
        cid = self.card_ids[sel[0]]
        self.load_card_by_id(cid)

    def delete_card_from_list(self):
        sel = self.card_listbox.curselection()
        if not sel: return messagebox.showwarning("Select", "Select a card to delete.")
        cid = self.card_ids[sel[0]]
        if messagebox.askyesno("Delete", "Delete this saved card?"):
            self.cursor.execute("DELETE FROM cards WHERE id=?", (cid,))
            self.conn.commit()
            self.on_card_date_selected()

    def load_card_by_id(self, cid):
        self.cursor.execute("SELECT card_data FROM cards WHERE id=?", (cid,))
        data = self.cursor.fetchone()[0]
        self.booked_matches = json.loads(data)
        self.refresh_card()
        messagebox.showinfo("Loaded", "Card loaded into Match Generator.")

    def show_card_details(self):
        sel = self.card_listbox.curselection()
        if not sel: return
        cid = self.card_ids[sel[0]]
        self.cursor.execute("SELECT name,brand,card_date FROM cards WHERE id=?", (cid,))
        name, brand, card_date = self.cursor.fetchone()
        self.cursor.execute("SELECT card_data FROM cards WHERE id=?", (cid,))
        card_data = json.loads(self.cursor.fetchone()[0])
        self.cursor.execute("""
            SELECT match_number,winner,losers,style,championship
            FROM match_history WHERE card_date=? ORDER BY match_number
        """, (card_date,))
        history = self.cursor.fetchall()

        win = tk.Toplevel(); win.title(f"Card Details: {name}")
        tk.Label(win, text=name, font=("Arial",14,"bold")).pack(pady=5)
        tk.Label(win, text=f"Brand: {brand}    Date: {card_date}", font=("Arial",10)).pack(pady=5)
        for mn, m in enumerate(card_data):
            frame = tk.Frame(win, bd=1, relief="solid", padx=5, pady=5)
            frame.pack(fill="x", padx=10, pady=5)
            prefix = "[Championship Match] " if m["championship"] else ""
            style = m["style"]
            champ = m["championship"]
            h = next((h for h in history if h[0]==mn+1), None)
            winner, losers = ("TBD","")
            if h: _, winner, losers, _, _ = h
            text = f"{prefix}Match {mn+1}: {style}"
            if champ: text += f" (Title: {champ})"
            text += f"\nWinner: {winner}"
            if losers:
                text += f"\nLosers: {losers}"
            tk.Label(frame, text=text, justify="left").pack()

    # ---------- Settings Tab ----------
    def build_settings_tab(self, frame):
        tk.Label(frame, text="Settings", font=("Arial",16,"bold")).pack(pady=10)
        tk.Button(frame, text="Reset Match History", command=self.reset_history).pack(pady=5)
        tk.Button(frame, text="Reset Win/Loss",       command=self.reset_records).pack(pady=5)
        tk.Label(frame, text="Select Font:").pack(pady=(20,0))
        self.font_v = tk.StringVar(value=self.font)
        fonts = ["Arial","Helvetica","Times","Courier","Comic Sans MS"]
        ttk.Combobox(frame, textvariable=self.font_v, values=fonts, state="readonly").pack()
        tk.Button(frame, text="Apply Font", command=self.apply_font).pack(pady=5)

    def apply_font(self):
        self.font = self.font_v.get()
        self.root.option_add("*Font", (self.font, 10))
        self.save_settings()
        messagebox.showinfo("Font Applied", f"Global font set to {self.font}.")

    def reset_history(self):
        if messagebox.askyesno("Reset", "Delete all match history?"):
            self.cursor.execute("DELETE FROM match_history")
            self.conn.commit()

    def reset_records(self):
        if messagebox.askyesno("Reset", "Reset all win/loss?"):
            self.cursor.execute("UPDATE records SET wins=0,losses=0")
            self.conn.commit()

if __name__ == "__main__":
    root = tk.Tk()
    app = StorylineApp(root)
    root.mainloop()

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
        self.cursor.execute(\"\"\"CREATE TABLE IF NOT EXISTS match_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_date TEXT,
            match_number INTEGER,
            winner TEXT,
            losers TEXT,
            style TEXT,
            championship TEXT
        )\"\"\")
        # Other tables...
        self.cursor.execute(\"\"\"CREATE TABLE IF NOT EXISTS wrestlers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            gender TEXT,
            alignment TEXT,
            brand TEXT,
            champion TEXT,
            image_path TEXT
        )\"\"\")
        self.cursor.execute(\"\"\"CREATE TABLE IF NOT EXISTS records (
            wrestler TEXT PRIMARY KEY,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0
        )\"\"\")
        self.cursor.execute(\"\"\"CREATE TABLE IF NOT EXISTS championships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            brand TEXT,
            current_holder TEXT,
            type TEXT,
            won_on TEXT,
            gender TEXT
        )\"\"\")
        self.cursor.execute(\"\"\"CREATE TABLE IF NOT EXISTS stables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stable_name TEXT,
            members TEXT
        )\"\"\")
        self.cursor.execute(\"\"\"CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            brand TEXT,
            card_date TEXT,
            card_data TEXT
        )\"\"\")
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

    # Roster Management Tab (and ALL helper methods: upload_image, add_wrestler, update_wrestler, delete_wrestler, refresh_gallery, refresh_stats, 
    # championship methods, stable methods, match generator methods, card methods, settings methods)
    # **(Paste the full implementations here exactly as in the last full snippet.)**

if __name__ == "__main__":
    root = tk.Tk()
    app = StorylineApp(root)
    root.mainloop()
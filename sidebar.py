import io
import base64
import os
import threading
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageTk
import components_data
from components_data import EMBEDDED_COMPONENTS

COMPONENTS_FILE = components_data.__file__  # points to the bridge module
MAX_IMPORT_SIDE = 1600  # bigger photos are shrunk on import so modules don't bloat


class SidebarManagerMixin:

  def init_sidebar(self):
    self.sidebar_frame = ctk.CTkFrame(self, width=210, corner_radius=0)
    self.sidebar_frame.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=10)
    self.sidebar_frame.pack_propagate(False)

    self.search_entry = ctk.CTkEntry(
        self.sidebar_frame, placeholder_text="🔍 Search components...", width=190
    )
    self.search_entry.pack(side="top", padx=10, pady=(10, 5))
    self.search_entry.bind("<KeyRelease>", self.filter_components)

    self.add_btn = ctk.CTkButton(
        self.sidebar_frame, text="➕ Import Custom", width=190, height=28,
        command=self.add_new_component
    )
    self.add_btn.pack(side="top", padx=10, pady=(0, 4))

    self.counter_label = ctk.CTkLabel(
        self.sidebar_frame,
        text=f"Total saved: {len(EMBEDDED_COMPONENTS)}",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=("gray40", "gray60")
    )
    self.counter_label.pack(side="top", padx=10, pady=(0, 5))

    self.comp_inner_frame = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="transparent")
    self.comp_inner_frame.pack(side="top", fill="both", expand=True, padx=2, pady=(0, 5))

    self.temp_hidden_components = set()
    self.thumb_cache = {}      # name -> CTkImage (decoded once, kept alive)
    self.card_by_name = {}     # name -> card frame
    self.component_cards = []
    self._write_lock = threading.Lock()
    self._persist_seq = 0

  def update_counter(self):
    if hasattr(self, "counter_label"):
      self.counter_label.configure(text=f"Total saved: {len(EMBEDDED_COMPONENTS)}")

  # ---------------- saving (runs off the UI thread) ----------------

  def persist_components(self):
    """Rewrite part1 and part2 files in a background thread so the window never freezes."""
    self._persist_seq += 1
    threading.Thread(
        target=self._write_components, args=(self._persist_seq, list(EMBEDDED_COMPONENTS.items()))
    ).start()

  def _write_components(self, seq, items):
    with self._write_lock:
      if seq != self._persist_seq:  # a newer save is queued, skip this stale one
        return
      try:
        # Automatically split items list 50/50 down the middle to balance file sizes
        mid = len(items) // 2
        part1_items = items[:mid]
        part2_items = items[mid:]

        base_dir = os.path.dirname(os.path.abspath(COMPONENTS_FILE))

        # 1. Write Part 1 safely using a temporary file
        path1 = os.path.join(base_dir, "components_part1.py")
        tmp1 = path1 + ".tmp"
        with open(tmp1, "w", encoding="utf-8") as f:
          f.write("# Auto-generated component part 1\n")
          f.write("PART_1_COMPONENTS = {\n")
          for comp_name, comp_b64 in part1_items:
            f.write(f'    {comp_name!r}: "{comp_b64}",\n')
          f.write("}\n")
        os.replace(tmp1, path1)

        # 2. Write Part 2 safely using a temporary file
        path2 = os.path.join(base_dir, "components_part2.py")
        tmp2 = path2 + ".tmp"
        with open(tmp2, "w", encoding="utf-8") as f:
          f.write("# Auto-generated component part 2\n")
          f.write("PART_2_COMPONENTS = {\n")
          for comp_name, comp_b64 in part2_items:
            f.write(f'    {comp_name!r}: "{comp_b64}",\n')
          f.write("}\n")
        os.replace(tmp2, path2)

      except Exception as e:
        print(f"Error saving split components to code modules: {e}")

  def save_component_to_module(self, name, b64_str):
    """Saves new component and places it at the very top of the dictionary"""
    new_dict = {name: b64_str}
    for k, v in EMBEDDED_COMPONENTS.items():
      if k != name:
        new_dict[k] = v
    EMBEDDED_COMPONENTS.clear()
    EMBEDDED_COMPONENTS.update(new_dict)
    self.persist_components()
    self.update_counter()

  def drop_card(self, name):
    card = self.card_by_name.pop(name, None)
    if card is not None:
      self.component_cards = [c for c in self.component_cards if c[1] is not card]
      card.destroy()

  def remove_permanently(self, name):
    try:
      EMBEDDED_COMPONENTS.pop(name, None)
      self.thumb_cache.pop(name, None)
      self.drop_card(name)
      self.persist_components()
      self.update_counter()
    except Exception as e:
      print(f"Error permanently removing component: {e}")

  def remove_from_list_session(self, name):
    self.temp_hidden_components.add(name)
    self.drop_card(name)

  def show_component_context_menu(self, event, display_name):
    popup = ctk.CTkToplevel(self)
    popup.title("")
    popup.geometry("180x110")
    popup.resizable(False, False)
    popup.attributes("-topmost", True)
    
    x = max(10, self.winfo_pointerx() - 190)
    y = max(10, self.winfo_pointery() - 20)
    popup.geometry(f"+{x}+{y}")

    ctk.CTkLabel(popup, text=display_name, font=ctk.CTkFont(size=11, weight="bold"), text_color="orange").pack(pady=(6, 4))

    btn1 = ctk.CTkButton(
        popup, text="🗑️ Remove from list", width=160, height=24, fg_color="#34495e", hover_color="#2c3e50",
        command=lambda: [self.remove_from_list_session(display_name), popup.destroy()]
    )
    btn1.pack(pady=2)

    btn2 = ctk.CTkButton(
        popup, text="❌ Permanent delete", width=160, height=24, fg_color="#c0392b", hover_color="#e74c3c",
        command=lambda: [self.remove_permanently(display_name), popup.destroy()]
    )
    btn2.pack(pady=2)

  # ---------------- cards ----------------

  def get_thumb(self, name, data):
    """Decode + shrink once per component; later reloads reuse the cached CTkImage."""
    thumb = self.thumb_cache.get(name)
    if thumb is None:
      img = Image.open(io.BytesIO(data))
      if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
      img.thumbnail((45, 45), Image.Resampling.LANCZOS)  # shrink BEFORE converting (much cheaper)
      img = img.convert("RGBA")
      thumb = ctk.CTkImage(light_image=img, dark_image=img, size=(45, 45))
      self.thumb_cache[name] = thumb
    return thumb

  def build_card(self, name, image_bytes):
    ctk_img = self.get_thumb(name, image_bytes)  # may raise, so do it before creating any widget

    card_frame = ctk.CTkFrame(self.comp_inner_frame, fg_color=("gray90", "gray20"), corner_radius=6)
    card_frame.pack(side="top", fill="x", padx=5, pady=4)

    img_label = ctk.CTkLabel(card_frame, text="", image=ctk_img)
    img_label.pack(side="top", pady=(4, 2))

    name_label = ctk.CTkLabel(
        card_frame,
        text=name,
        anchor="center",
        wraplength=160,
        justify="center",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=("black", "white")
    )
    name_label.pack(side="top", fill="x", padx=4, pady=(0, 6))

    spawn_action = lambda e, n=name, d=image_bytes: self.spawn_embedded_component(n, d)
    card_frame.bind("<Button-1>", spawn_action)
    img_label.bind("<Button-1>", spawn_action)
    name_label.bind("<Button-1>", spawn_action)

    double_action = lambda e, n=name: self.show_component_context_menu(e, n)
    card_frame.bind("<Double-Button-1>", double_action)
    img_label.bind("<Double-Button-1>", double_action)
    name_label.bind("<Double-Button-1>", double_action)

    card_frame.bind("<Enter>", lambda e, f=card_frame: f.configure(fg_color=("#dcdcdc", "#2b2b2b")))
    card_frame.bind("<Leave>", lambda e, f=card_frame: f.configure(fg_color=("gray90", "gray20")))

    self.card_by_name[name] = card_frame
    self.component_cards.append((name.lower(), card_frame, image_bytes))
    return card_frame

  def load_components_to_sidebar(self):
    for widget in self.comp_inner_frame.winfo_children():
      widget.destroy()
    self.component_cards = []
    self.card_by_name = {}
    self.update_counter()

    for display_name, b64_str in EMBEDDED_COMPONENTS.items():
      if display_name in self.temp_hidden_components:
        continue
      try:
        self.build_card(display_name, base64.b64decode(b64_str))
      except Exception as e:
        print(f"Error loading embedded component {display_name}: {e}")

  def filter_components(self, event=None):
    query = self.search_entry.get().lower().strip()
    for _, card_frame, _ in self.component_cards:
      card_frame.pack_forget()
    for name, card_frame, data in self.component_cards:
      if not query or query in name:
        card_frame.pack(side="top", fill="x", padx=5, pady=4)

  # ---------------- importing ----------------

  def prepare_import_bytes(self, path):
    """Read the file; shrink only if it is huge. Raises if it isn't a valid image."""
    with open(path, "rb") as f:
      raw = f.read()
    img = Image.open(io.BytesIO(raw))
    if max(img.size) <= MAX_IMPORT_SIDE:
      return raw
    img.thumbnail((MAX_IMPORT_SIDE, MAX_IMPORT_SIDE), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if "A" in img.getbands() or img.mode == "P":
      img.convert("RGBA").save(buf, "PNG")
    else:
      img.convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()

  def add_new_component(self):
    file_path = filedialog.askopenfilename(
        master=self,
        title="Select Component Image",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp")]
    )
    if not file_path:
      return
    try:
      data = self.prepare_import_bytes(file_path)
      name = os.path.splitext(os.path.basename(file_path))[0].replace("_", " ")

      self.thumb_cache.pop(name, None)
      self.get_thumb(name, data)  # validates the image BEFORE anything is saved
      self.drop_card(name)  # re-importing the same name replaces the old card
      self.temp_hidden_components.discard(name)

      self.save_component_to_module(name, base64.b64encode(data).decode("utf-8"))
      self.build_card(name, data)
      self.component_cards.insert(0, self.component_cards.pop())  # newest first
      self.filter_components()  # re-packs the cards in the new order (new one on top)
      try:
        self.comp_inner_frame._parent_canvas.yview_moveto(0)
      except Exception:
        pass
    except Exception as e:
      print(f"Import component error: {e}")

  def find_smart_spawn_position(self):
    xs = [self.canvas.coords(i)[0] for i in self.image_refs]
    x = max(xs) + 160 if xs else self.canvas.canvasx(150)
    if x > 11000:
      x = self.canvas.canvasx(150)
    return x, self.canvas.canvasy(150)

  def render_image(self, item_id):
    ref = self.image_refs[item_id]
    s = self.item_scales[item_id] * ref.get("base", 1.0)
    img = ref["pil_img"]
    
    crop = ref.get("crop", [0.0, 0.0, 0.0, 0.0])
    if any(crop):
      cw, ch = img.size
      img = img.crop((int(crop[0] * cw), int(crop[1] * ch), int((1 - crop[2]) * cw), int((1 - crop[3]) * ch)))

    img = img.resize((max(10, int(img.width * s)), max(10, int(img.height * s))), Image.Resampling.LANCZOS)
    img = img.rotate(self.item_rotations[item_id], expand=True, resample=Image.Resampling.BICUBIC)
    ref["tk_img"] = ImageTk.PhotoImage(img)
    self.canvas.itemconfig(item_id, image=ref["tk_img"])
    if item_id == self.selected_item:
      self.show_handles()

  def spawn_embedded_component(self, name, image_data, x=None, y=None, scale=1.0, rotation=0, crop=None):
    try:
      base = Image.open(io.BytesIO(image_data)).convert("RGBA")
      if x is None or y is None:
        x, y = self.find_smart_spawn_position()

      item_id = self.canvas.create_image(x, y, anchor="center", tags="component")
      self.image_refs[item_id] = {
          "path": name, "pil_img": base, "orig_pil": base.copy(),
          "base": min(1.0, 190 / base.width),
          "crop": crop if crop else [0.0, 0.0, 0.0, 0.0]
      }
      self.item_scales[item_id] = scale
      self.item_rotations[item_id] = rotation
      self.render_image(item_id)
      return item_id
    except Exception as e:
      print(f"Error spawning embedded image: {e}")

  def add_component(self, path_or_data):
    pass

  def set_mode(self, mode):
    self.mode = mode
    self.highlight_toolbar_button(mode)
    self.show_handles()

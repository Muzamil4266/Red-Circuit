import math
import customtkinter as ctk
from tkinter import colorchooser, simpledialog, filedialog
from PIL import Image, ImageColor, ImageDraw, ImageGrab, ImageTk

CORNERS = {"cropBL": (-1, 1, "↙"), "cropBR": (1, 1, "↘"), "cropL": (-1, 0, "↔"), "cropR": (1, 0, "↔"),
           "cropT": (0, -1, "↕"), "cropB": (0, 1, "↕")}
AA = 4  # supersampling factor for smooth (anti-aliased) strokes
SWATCHES = ["#e74c3c", "#f1c40f", "#2ecc71", "#3498db", "#000000", "#ffffff"]
DEFAULT_BG = "#1e1e1e"


class CanvasRendererMixin:

  def _btn(self, parent, text, width, command, color=None, side="left", padx=2):
    kw = {"fg_color": color} if color else {}
    b = ctk.CTkButton(parent, text=text, width=width, command=command, **kw)
    b.pack(side=side, padx=padx, pady=4)
    return b

  def init_canvas_and_toolbar(self):
    self.crop_corner = None
    self.editing_text = None
    self.text_pre = None
    self.press_x = 0
    self.press_y = 0
    self.temp_box_id = None
    self.stroke_w = {}   # real pen width per stroke (the canvas item itself is kept thin)
    self.aa_ids = {}     # stroke -> smooth image item
    self.aa_tk = {}
    self.live = set()    # strokes currently being edited (shown unsmoothed for speed)
    self._aa_job = None
    self._zoom_job = None
    self.box_op = None      # "rotate" / "resize" while a box handle is being dragged
    self.box_ang = 0.0

    self.canvas_container = ctk.CTkFrame(self, fg_color="transparent")
    self.canvas_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    self.canvas_container.grid_rowconfigure(1, weight=1)
    self.canvas_container.grid_columnconfigure(0, weight=1)

    toolbar = ctk.CTkFrame(self.canvas_container)
    toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    row1 = ctk.CTkFrame(toolbar, fg_color="transparent")
    row1.pack(fill="x")
    row2 = ctk.CTkFrame(toolbar, fg_color="transparent")
    row2.pack(fill="x")

    for mode, label, w in [("select", "👆 Select", 75), ("draw", "✏️ Pen", 65), ("straight_line", "📏 Line", 65),
                           ("box", "🔲 Box", 60), ("eraser", "🧹 Eraser", 75)]:
      self.toolbar_buttons[mode] = self._btn(row1, label, w, lambda m=mode: self.set_mode(m))

    ctk.CTkLabel(row1, text="Size:").pack(side="left", padx=(6, 2))
    self.size_slider = ctk.CTkSlider(row1, from_=1, to=20, number_of_steps=19, width=70, command=self.update_tool_size)
    self.size_slider.set(self.tool_size)
    self.size_slider.pack(side="left", padx=2)

    ctk.CTkLabel(row1, text="Zoom: 0%").pack(side="left", padx=(8, 0))
    self.univ_zoom_slider = ctk.CTkSlider(row1, from_=0, to=100, number_of_steps=10, width=95, command=self.on_universal_slider_zoom)
    self.univ_zoom_slider.set(50.0)
    self.univ_zoom_slider.pack(side="left", padx=2)
    ctk.CTkLabel(row1, text="100%").pack(side="left", padx=(0, 6))

    ctk.CTkLabel(row1, text="Color:").pack(side="left", padx=(6, 2))
    for c in SWATCHES:
      ctk.CTkButton(row1, text="", width=22, height=22, fg_color=c, hover=False, border_width=1,
                    border_color="gray50", command=lambda c=c: self.set_pen_color(c)).pack(side="left", padx=2)
    self.color_btn = self._btn(row1, "🎨", 45, self.change_pen_color, self.pen_color, padx=4)

    self._btn(row2, "↩️ Undo", 65, self.perform_undo, "#34495e")
    self._btn(row2, "🔁 Redo", 65, self.perform_redo, "#34495e")
    self._btn(row2, "💾 Save", 60, self.save_circuit, "#27ae60", padx=4)
    self._btn(row2, "📂 Load", 60, self.load_circuit, "#2980b9")
    self._btn(row2, "🖼️ BG", 55, self.change_background_color, "#9b59b6", padx=4)
    self._btn(row2, "📄 PDF", 65, self.export_to_pdf, "#16a085")
    self._btn(row2, "🗑️ Del", 55, self.delete_selected, "#e74c3c", side="right", padx=6)

    self.highlight_toolbar_button("select")

    canvas_frame = ctk.CTkFrame(self.canvas_container, fg_color="transparent")
    canvas_frame.grid(row=1, column=0, sticky="nsew")
    canvas_frame.grid_rowconfigure(0, weight=1)
    canvas_frame.grid_columnconfigure(0, weight=1)

    self.canvas = ctk.CTkCanvas(canvas_frame, bg=DEFAULT_BG, highlightthickness=0, insertbackground="red")
    self.canvas.configure(scrollregion=(0, 0, 11520, 11520))

    h_scrollbar = ctk.CTkScrollbar(canvas_frame, orientation="horizontal", command=self.canvas.xview)
    v_scrollbar = ctk.CTkScrollbar(canvas_frame, orientation="vertical", command=self.canvas.yview)
    self.canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

    self.canvas.grid(row=0, column=0, sticky="nsew")
    v_scrollbar.grid(row=0, column=1, sticky="ns")
    h_scrollbar.grid(row=1, column=0, sticky="ew")

    self.canvas.bind("<MouseWheel>", lambda e: self.scroll_view(e, self.canvas.yview))
    self.canvas.bind("<Control-MouseWheel>", self.on_two_finger_component_zoom)
    self.canvas.bind("<Shift-MouseWheel>", lambda e: self.scroll_view(e, self.canvas.xview))

    self.canvas.bind("<Button-1>", self.on_canvas_press)
    self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
    self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
    self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
    self.canvas.bind("<Key>", self.on_text_key)

    self.current_zoom_scale = 1.0

  def scroll_view(self, e, view):
    view("moveto", max(0, view()[0] - e.delta / 120 * 40 / 11520))

  def highlight_toolbar_button(self, active_mode):
    for mode, btn in self.toolbar_buttons.items():
      if mode == active_mode:
        btn.configure(width=64, height=64, corner_radius=32, fg_color="#d35400", font=ctk.CTkFont(size=13, weight="bold"))
      else:
        btn.configure(width=75, height=28, corner_radius=6,
                      fg_color="#e67e22" if mode == "eraser" else "#1f6aa5",
                      font=ctk.CTkFont(size=12, weight="normal"))

  def update_tool_size(self, value):
    self.tool_size = int(float(value))

  def set_pen_color(self, color):
    self.pen_color = color
    self.color_btn.configure(fg_color=color)

  def change_pen_color(self):
    color = colorchooser.askcolor(title="Choose Pen / Line Color", color=self.pen_color)[1]
    if color:
      self.set_pen_color(color)

  def change_background_color(self):
    color = colorchooser.askcolor(title="Choose Workspace Background Color")[1]
    if color:
      self.begin_change()
      self.canvas.configure(bg=color)
      self.commit_change()

  def corner_point(self, item, sx, sy):
    ref = self.image_refs[item]
    s = self.item_scales[item] * ref.get("base", 1.0)
    w, h = ref["pil_img"].size
    l, t, r, b = ref.get("crop", [0.0, 0.0, 0.0, 0.0])
    lx, ly = sx * w * (1 - l - r) * s / 2, sy * h * (1 - t - b) * s / 2
    a = math.radians(self.item_rotations[item])
    cx, cy = self.canvas.coords(item)
    return cx + lx * math.cos(a) + ly * math.sin(a), cy - lx * math.sin(a) + ly * math.cos(a)

  def is_box(self, item):
    return bool(item) and "box_shape" in self.canvas.gettags(item)

  def box_pts(self, item):
    c = self.canvas.coords(item) if item else []
    return [(c[i], c[i + 1]) for i in range(0, 8, 2)] if len(c) == 8 else []

  def stroke_points(self, item):
    c = self.canvas.coords(item)
    pts = [(c[i], c[i + 1]) for i in range(0, len(c) - 1, 2)]
    if self.is_box(item):
      return pts + pts[:1]
    if len(pts) < 3:
      return pts
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    n = 12 if len(pts) < 300 else 4
    out = [pts[0], mid(pts[0], pts[1])]
    for i in range(1, len(pts) - 1):
      a, p, e = mid(pts[i - 1], pts[i]), pts[i], mid(pts[i], pts[i + 1])
      for k in range(1, n + 1):
        t = k / n
        out.append(((1 - t) ** 2 * a[0] + 2 * t * (1 - t) * p[0] + t * t * e[0],
                    (1 - t) ** 2 * a[1] + 2 * t * (1 - t) * p[1] + t * t * e[1]))
    out.append(pts[-1])
    return out

  def aa_render(self, item):
    c = self.canvas
    pts = self.stroke_points(item)
    if len(pts) < 2 or not c.type(item):
      return
    w = self.stroke_w.get(item, 1.0)
    pad = w / 2 + 2
    x0, y0 = min(p[0] for p in pts) - pad, min(p[1] for p in pts) - pad
    W, H = int(max(p[0] for p in pts) + pad - x0) + 1, int(max(p[1] for p in pts) + pad - y0) + 1
    ss = AA
    while ss > 1 and W * H * ss * ss > 25_000_000:
      ss -= 1
    mask = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(mask)
    sp = [((x - x0) * ss, (y - y0) * ss) for x, y in pts]
    d.line(sp, fill=255, width=max(1, round(w * ss)), joint="curve")
    r = w * ss / 2
    for ex, ey in (sp[0], sp[-1]):
      d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=255)
    mask = mask.resize((W, H), Image.Resampling.LANCZOS)
    color = ImageColor.getrgb(c.itemcget(item, "outline" if self.is_box(item) else "fill"))
    img = Image.new("RGBA", (W, H), color + (0,))
    img.putalpha(mask)
    tk_img = ImageTk.PhotoImage(img)
    aid = self.aa_ids.get(item)
    if aid is None:
      aid = c.create_image(x0, y0, image=tk_img, anchor="nw", tags="aa", state="disabled")
      self.aa_ids[item] = aid
    else:
      c.coords(aid, x0, y0)
      c.itemconfig(aid, image=tk_img, state="disabled")
    self.aa_tk[item] = tk_img
    c.itemconfig(item, width=max(1, w - 2))

  def aa_live(self, item):
    if item in self.live or not self.canvas.type(item):
      return
    self.live.add(item)
    self.canvas.itemconfig(item, width=self.stroke_w.get(item, 1.0))
    aid = self.aa_ids.get(item)
    if aid:
      self.canvas.itemconfig(aid, state="hidden")

  def aa_finish(self):
    for i in list(self.live):
      self.aa_render(i)
    self.live.clear()

  def aa_all(self):
    self._aa_job = None
    for i in self.canvas.find_withtag("wire") + self.canvas.find_withtag("box_shape"):
      self.aa_render(i)

  def schedule_aa_all(self):
    if self._aa_job:
      self.after_cancel(self._aa_job)
    self._aa_job = self.after(50, self.aa_all)

  def draw_frame(self, pts):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    frame = []
    for px, py in pts:
      d = math.hypot(px - cx, py - cy) or 1
      frame.append((px + (px - cx) / d * 7, py + (py - cy) / d * 7))
    self.canvas.create_polygon(*[v for p in frame for v in p], outline="white", fill="", dash=(4, 3),
                               state="disabled", tags="handle")
    return frame

  def draw_handle(self, x, y, icon, name, r=13):
    tags = ("handle", name)
    self.canvas.create_oval(x - r, y - r, x + r, y + r, fill="white", outline="#888888", tags=tags)
    self.canvas.create_text(x, y, text=icon, fill="#222222", font=("Arial", 12 if r > 10 else 9, "bold"), tags=tags)

  def show_handles(self):
    self.canvas.delete("handle")
    item = self.selected_item
    if not item or (self.mode != "select" and not (self.mode == "box" and self.is_box(item))):
      return
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    if item in self.image_refs:
      F = self.draw_frame([self.corner_point(item, sx, sy) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
      self.draw_handle(*F[0], "×", "delete")
      self.draw_handle(*F[1], "↻", "img_rotate")
      self.draw_handle(*F[3], "↙", "cropBL")
      self.draw_handle(*F[2], "↘", "cropBR")
      self.draw_handle(*mid(F[0], F[3]), "↔", "cropL", 9)
      self.draw_handle(*mid(F[1], F[2]), "↔", "cropR", 9)
      self.draw_handle(*mid(F[0], F[1]), "↕", "cropT", 9)
      self.draw_handle(*mid(F[3], F[2]), "↕", "cropB", 9)
    elif self.is_box(item):
      pts = self.box_pts(item)
      if not pts:
        return
      F = self.draw_frame(pts)
      self.draw_handle(*F[0], "×", "box_delete")
      self.draw_handle(*F[1], "↻", "box_rotate")
      self.draw_handle(*F[2], "⤡", "box_resize")

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

  def export_to_pdf(self):
    path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Document", "*.pdf")])
    c = self.canvas
    c.delete("handle")
    box = c.bbox("all")
    if path and box:
      x0, y0 = max(0, int(box[0]) - 20), max(0, int(box[1]) - 20)
      x1, y1 = int(box[2]) + 20, int(box[3]) + 20
      w, h = c.winfo_width(), c.winfo_height()
      sx, sy = c.xview()[0], c.yview()[0]
      out = Image.new("RGB", (x1 - x0, y1 - y0), c.cget("bg"))
      for ty in range(y0, y1, h):
        for tx in range(x0, x1, w):
          c.xview_moveto(tx / 11520)
          c.yview_moveto(ty / 11520)
          self.update()
          tile = ImageGrab.grab((c.winfo_rootx(), c.winfo_rooty(), c.winfo_rootx() + w, c.winfo_rooty() + h))
          out.paste(tile, (int(c.canvasx(0)) - x0, int(c.canvasy(0)) - y0))
      
      out.save(path, "PDF", resolution=100.0)
      c.xview_moveto(sx)
      c.yview_moveto(sy)
    self.show_handles()

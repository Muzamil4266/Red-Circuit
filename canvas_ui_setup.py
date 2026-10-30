import customtkinter as ctk
from tkinter import colorchooser

SWATCHES = ["#e74c3c", "#f1c40f", "#2ecc71", "#3498db", "#000000", "#ffffff"]
DEFAULT_BG = "#1e1e1e"


class CanvasUISetupMixin:

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
    self.temp_circle_id = None
    self.temp_star_id = None
    self.stroke_w = {}   # real pen width per stroke
    self.aa_ids = {}     # stroke -> smooth image item
    self.aa_tk = {}
    self.live = set()    # strokes currently being edited
    self._aa_job = None
    self._zoom_job = None
    self.box_op = None      # "rotate" / "resize" while a shape handle is being dragged
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
                           ("box", "🔲 Box", 55), ("circle", "🔵 Circle", 65), ("star", "⭐ Star", 55), ("eraser", "🧹 Eraser", 75)]:
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
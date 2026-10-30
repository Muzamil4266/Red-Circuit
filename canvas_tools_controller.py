import math
from tkinter import simpledialog


class CanvasToolsControllerMixin:

  def box_transform(self, x, y):
    p = self.box_pts(self.selected_item)
    if not p:
      return
    
    if self.box_op == "rotate":
      xs, ys = [pt[0] for pt in p], [pt[1] for pt in p]
      x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
      cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
      a = math.atan2(y - cy, x - cx)
      d, self.box_ang = a - self.box_ang, a
      cs, sn = math.cos(d), math.sin(d)
      pts = [(cx + (px - cx) * cs - (py - cy) * sn, cy + (px - cx) * sn + (py - cy) * cs) for px, py in p]
      self.canvas.coords(self.selected_item, *[v for pt in pts for v in pt])
    elif self.box_op == "resize":
      x1, y1 = getattr(self, "resize_anchor", (p[0][0], p[0][1]))
      nx2, ny2 = max(x1 + 15, x), max(y1 + 15, y)
      
      if self.is_box(self.selected_item):
        self.canvas.coords(self.selected_item, x1, y1, nx2, y1, nx2, ny2, x1, ny2)
      elif self.is_circle(self.selected_item):
        new_coords = self.make_circle_pts(x1, y1, nx2, ny2)
        self.canvas.coords(self.selected_item, *new_coords)
      elif self.is_star(self.selected_item):
        new_coords = self.make_star_pts(x1, y1, nx2, ny2)
        self.canvas.coords(self.selected_item, *new_coords)
    self.show_handles()

  def handle_action(self, name):
    if name == "delete":
      self.delete_selected()
      return
    if name == "text":
      text = simpledialog.askstring("Add Text Note", "Enter Label:")
      if text:
        self.begin_change()
        x, y = self.canvas.coords(self.selected_item) if self.selected_item else (self.canvas.canvasx(150), self.canvas.canvasy(150))
        self.canvas.create_text(x + 80, y, text=text, anchor="nw", font=("Arial", max(6, int(12 * self.current_zoom_scale)), "bold"), fill=self.pen_color, tags="text_note")
        self.commit_change()
      return
    {
        "rotl": lambda: self.rotate_selected(15),
        "rotr": lambda: self.rotate_selected(-15),
        "zoomin": lambda: self.scale_specific_item(self.selected_item, 1.15),
        "zoomout": lambda: self.scale_specific_item(self.selected_item, 0.87),
    }.get(name, lambda: None)()

  def rotate_selected(self, delta):
    item = self.selected_item
    if item in self.image_refs:
      self.item_rotations[item] = (self.item_rotations[item] + delta) % 360
      self.render_image(item)

  def rotate_drag(self, x, y):
    item = self.selected_item
    coords = self.canvas.coords(item)
    if len(coords) == 2:
      cx, cy = coords
      a = math.atan2(y - cy, x - cx)
      new = round(self.rot_start - math.degrees(a - self.box_ang)) % 360
      if new != self.item_rotations[item]:
        self.item_rotations[item] = new
        self.render_image(item)

  def scale_specific_item(self, item, factor):
    if item in self.image_refs:
      self.item_scales[item] = max(0.01, min(self.item_scales[item] * factor, 30.0))
      self.render_image(item)

  def crop_drag(self, dx, dy):
    item = self.selected_item
    if item not in self.image_refs:
      return
    ref = self.image_refs[item]
    from canvas_graphics_engine import CORNERS
    sx, sy, _ = CORNERS.get(self.crop_corner, (0, 0, ""))
    a = math.radians(self.item_rotations[item])
    lx, ly = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    s = self.item_scales[item] * ref.get("base", 1.0)
    w, h = ref["pil_img"].size
    old = ref.setdefault("crop", [0.0, 0.0, 0.0, 0.0])
    l, t, r, b = old
    if sx < 0: l += lx / (w * s)
    elif sx > 0: r -= lx / (w * s)
    if sy < 0: t += ly / (h * s)
    elif sy > 0: b -= ly / (h * s)
    l = max(0, min(l, 0.9 - r)); r = max(0, min(r, 0.9 - l))
    t = max(0, min(t, 0.9 - b)); b = max(0, min(b, 0.9 - t))
    ax = ((l - old[0]) - (r - old[2])) * w * s / 2
    ay = ((t - old[1]) - (b - old[3])) * h * s / 2
    self.canvas.move(item, ax * math.cos(a) + ay * math.sin(a), -ax * math.sin(a) + ay * math.cos(a))
    ref["crop"] = [l, t, r, b]
    self.render_image(item)

  def on_two_finger_component_zoom(self, event):
    if self.selected_item and self.selected_item in self.image_refs:
      factor = 1.1 if event.delta > 0 else 0.9
      self.begin_change()
      self.scale_specific_item(self.selected_item, factor)
      self.commit_change()

  def on_universal_slider_zoom(self, value):
    val = float(value)
    if val == 50.0:
      target = 1.0
    elif val < 50.0:
      target = 0.02 + (val / 50.0) * 0.98
    else:
      t = (val - 50.0) / 50.0
      target = 1.0 + t * 5.0

    factor = target / self.current_zoom_scale
    self.current_zoom_scale = target

    cx = self.canvas.canvasx(self.canvas.winfo_width() / 2)
    cy = self.canvas.canvasy(self.canvas.winfo_height() / 2)

    self.canvas.itemconfigure("aa", state="hidden")
    self.canvas.scale("all", cx, cy, factor, factor)

    for item in self.image_refs:
      self.item_scales[item] = max(0.01, min(self.item_scales[item] * factor, 30.0))

    for i in self.canvas.find_withtag("wire") + self.canvas.find_withtag("box_shape") + self.canvas.find_withtag("circle_shape") + self.canvas.find_withtag("star_shape"):
      self.stroke_w[i] = max(0.5, self.stroke_w.get(i, 1.0) * factor)

    new_font_size = max(4, int(12 * self.current_zoom_scale))
    for i in self.canvas.find_withtag("text_note"):
      self.canvas.itemconfig(i, font=("Arial", new_font_size, "bold"))

    self.show_handles()

    if self._zoom_job:
      self.after_cancel(self._zoom_job)
    self._zoom_job = self.after(150, self.finalize_zoom)

    def finalize_zoom(self):
      self._zoom_job = None
      for item in self.image_refs:
        self.render_image(item)
      self.aa_all()
      self.show_handles()

  def finalize_zoom(self):
    self._zoom_job = None
    for item in self.image_refs:
      self.render_image(item)
    self.aa_all()
    self.show_handles()

  def on_canvas_double_click(self, event):
    self.finish_text_edit()
    x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
    items = self.canvas.find_withtag("current")
    self.text_pre = self.get_state()
    if items and "text_note" in self.canvas.gettags(items[0]):
      item = items[0]
    else:
      item = self.canvas.create_text(x, y, text="", anchor="nw", fill=self.pen_color, tags="text_note",
                                     font=("Arial", max(6, int(12 * self.current_zoom_scale)), "bold"))
    self.editing_text = item
    self.canvas.focus_set()
    self.canvas.focus(item)
    self.canvas.icursor(item, "end")

  def on_text_key(self, e):
    item = self.editing_text
    if item is None:
      return
    c = self.canvas
    i = c.index(item, "insert")
    if e.keysym == "BackSpace":
      if i > 0:
        c.dchars(item, i - 1, i - 1)
    elif e.keysym == "Delete":
      c.dchars(item, i, i)
    elif e.keysym == "Left":
      c.icursor(item, max(0, i - 1))
    elif e.keysym == "Right":
      c.icursor(item, i + 1)
    elif e.keysym == "Return":
      c.insert(item, "insert", "\n")
    elif e.keysym == "Escape":
      self.finish_text_edit()
    elif e.char and e.char.isprintable():
      c.insert(item, "insert", e.char)
    return "break"

  def finish_text_edit(self):
    item = self.editing_text
    if item is None:
      return
    self.editing_text = None
    self.canvas.focus("")
    if self.canvas.type(item) and not self.canvas.itemcget(item, "text").strip():
      self.canvas.delete(item)
    self.pre_state = self.text_pre
    self.commit_change()

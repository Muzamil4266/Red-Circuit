import math
from tkinter import simpledialog, filedialog


class CanvasInteractionsMixin:

  def pick_item(self, tol=5):
    items = self.canvas.find_withtag("current")
    if items:
      return items[0]
    x, y = self.last_x, self.last_y
    for i in reversed(self.canvas.find_overlapping(x - tol, y - tol, x + tol, y + tol)):
      if self.is_box(i):
        return i
    return None

  def box_transform(self, x, y):
    p = self.box_pts(self.selected_item)
    if not p:
      return
    if self.box_op == "rotate":
      cx, cy = (p[0][0] + p[2][0]) / 2, (p[0][1] + p[2][1]) / 2
      a = math.atan2(y - cy, x - cx)
      d, self.box_ang = a - self.box_ang, a
      cs, sn = math.cos(d), math.sin(d)
      pts = [(cx + (px - cx) * cs - (py - cy) * sn, cy + (px - cx) * sn + (py - cy) * cs) for px, py in p]
    else:
      (x0, y0), (x1, y1), _, (x3, y3) = p
      ul = math.hypot(x1 - x0, y1 - y0) or 1
      vl = math.hypot(x3 - x0, y3 - y0) or 1
      ux, uy, vx, vy = (x1 - x0) / ul, (y1 - y0) / ul, (x3 - x0) / vl, (y3 - y0) / vl
      w = max(8, (x - x0) * ux + (y - y0) * uy)
      h = max(8, (x - x0) * vx + (y - y0) * vy)
      pts = [(x0, y0), (x0 + ux * w, y0 + uy * w),
             (x0 + ux * w + vx * h, y0 + uy * w + vy * h), (x0 + vx * h, y0 + vy * h)]
    self.canvas.coords(self.selected_item, *[v for pt in pts for v in pt])
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
    from canvas_renderer import CORNERS
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

    for i in self.canvas.find_withtag("wire") + self.canvas.find_withtag("box_shape"):
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

  def on_canvas_press(self, event):
    self.finish_text_edit()
    self.last_x = self.canvas.canvasx(event.x)
    self.last_y = self.canvas.canvasy(event.y)
    self.press_x = self.last_x
    self.press_y = self.last_y
    self.begin_change()
    self.dragging = False
    self.box_op = None
    self.crop_corner = None

    tags = self.canvas.gettags("current")
    if "handle" in tags:
      if "box_delete" in tags or "delete" in tags:
        self.delete_selected()
        return
      elif "img_rotate" in tags:
        coords = self.canvas.coords(self.selected_item)
        if len(coords) == 2:
          cx, cy = coords
          self.box_ang = math.atan2(self.last_y - cy, self.last_x - cx)
          self.rot_start = self.item_rotations.get(self.selected_item, 0)
          self.box_op = "img_rotate"
        return
      elif "box_rotate" in tags:
        self.aa_live(self.selected_item)
        pts = self.box_pts(self.selected_item)
        if pts:
          cx, cy = (pts[0][0] + pts[2][0]) / 2, (pts[0][1] + pts[2][1]) / 2
          self.box_ang = math.atan2(self.last_y - cy, self.last_x - cx)
          self.box_op = "rotate"
        return
      elif "box_resize" in tags:
        self.aa_live(self.selected_item)
        self.box_op = "resize"
        return
      else:
        from canvas_renderer import CORNERS
        for tag in tags:
          if tag in CORNERS:
            self.crop_corner = tag
            return
        if len(tags) > 1:
          self.handle_action(tags[1])
        return

    if self.mode == "select":
      top_item = self.pick_item()
      if top_item and (top_item in self.image_refs or self.is_box(top_item)):
        self.selected_item = top_item
        self.dragging = True
        if self.is_box(top_item):
          self.aa_live(top_item)
      else:
        self.selected_item = None
      self.show_handles()
    elif self.mode in ("draw", "straight_line"):
      x, y = self.last_x, self.last_y
      self.temp_line_id = self.canvas.create_line(
          x, y, x, y, fill=self.pen_color, width=self.tool_size, capstyle="round", joinstyle="round", smooth=True, splinesteps=64, tags="wire"
      )
      self.stroke_w[self.temp_line_id] = self.tool_size
      self.live.add(self.temp_line_id)
    elif self.mode == "box":
      hit = self.pick_item(3)
      if hit and self.is_box(hit):
        self.selected_item = hit
        self.dragging = True
        self.aa_live(hit)
      else:
        x, y = self.last_x, self.last_y
        self.selected_item = None
        self.temp_box_id = self.canvas.create_polygon(
            x, y, x, y, x, y, x, y, outline=self.pen_color, fill="", width=self.tool_size, tags="box_shape"
        )
        self.stroke_w[self.temp_box_id] = self.tool_size
        self.live.add(self.temp_box_id)
      self.show_handles()
    elif self.mode == "eraser":
      self.erase_at(self.last_x, self.last_y)

  def on_canvas_drag(self, event):
    x = self.canvas.canvasx(event.x)
    y = self.canvas.canvasy(event.y)

    if self.box_op == "img_rotate" and self.selected_item in self.image_refs:
      self.rotate_drag(x, y)
    elif self.box_op and self.is_box(self.selected_item):
      self.box_transform(x, y)
    elif self.crop_corner:
      self.crop_drag(x - self.last_x, y - self.last_y)
    elif self.mode == "draw" and self.temp_line_id:
      coords = list(self.canvas.coords(self.temp_line_id))
      coords.extend([x, y])
      self.canvas.coords(self.temp_line_id, *coords)
    elif self.mode == "straight_line" and self.temp_line_id:
      c = self.canvas.coords(self.temp_line_id)
      self.canvas.coords(self.temp_line_id, c[0], c[1], x, y)
    elif self.mode == "box" and self.temp_box_id:
      l, r = sorted((self.press_x, x))
      t, b = sorted((self.press_y, y))
      self.canvas.coords(self.temp_box_id, l, t, r, t, r, b, l, b)
    elif self.mode == "eraser":
      self.erase_at(x, y)
    elif self.dragging and self.selected_item:
      dx, dy = x - self.last_x, y - self.last_y
      self.canvas.move(self.selected_item, dx, dy)
      self.show_handles()
    self.last_x, self.last_y = x, y

  def on_canvas_release(self, event):
    if self.temp_box_id:
      pts = self.box_pts(self.temp_box_id)
      if abs(pts[2][0] - pts[0][0]) < 6 or abs(pts[2][1] - pts[0][1]) < 6:
        self.remove_item(self.temp_box_id)
        self.temp_box_id = None
      else:
        self.selected_item = self.temp_box_id
    self.temp_line_id = None
    self.temp_box_id = None
    self.crop_corner = None
    self.box_op = None
    self.aa_finish()
    self.commit_change()
    self.show_handles()

  def remove_item(self, item):
    self.canvas.delete(item)
    aid = self.aa_ids.pop(item, None)
    if aid:
      self.canvas.delete(aid)
    self.aa_tk.pop(item, None)
    self.stroke_w.pop(item, None)
    self.live.discard(item)
    self.image_refs.pop(item, None)
    self.item_scales.pop(item, None)
    self.item_rotations.pop(item, None)
    if item == self.selected_item:
      self.selected_item = None

  def erase_at(self, x, y):
    r = self.tool_size + 4
    for item in self.canvas.find_overlapping(x - r, y - r, x + r, y + r):
      if "aa" not in self.canvas.gettags(item):
        self.remove_item(item)

  def delete_selected(self):
    if self.selected_item:
      self.begin_change()
      self.remove_item(self.selected_item)
      self.show_handles()
      self.commit_change()

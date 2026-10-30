import math


class CanvasMouseEventsMixin:

  def pick_item(self, tol=5):
    items = self.canvas.find_withtag("current")
    if items:
      return items[0]
    x, y = self.last_x, self.last_y
    for i in reversed(self.canvas.find_overlapping(x - tol, y - tol, x + tol, y + tol)):
      if self.is_shape(i):
        return i
    return None

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
          xs, ys = [p[0] for p in pts], [p[1] for p in pts]
          cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
          self.box_ang = math.atan2(self.last_y - cy, self.last_x - cx)
          self.box_op = "rotate"
        return
      elif "box_resize" in tags:
        self.aa_live(self.selected_item)
        pts = self.box_pts(self.selected_item)
        if pts:
          xs, ys = [p[0] for p in pts], [p[1] for p in pts]
          # Store the fixed top-left anchor for smooth proportional resizing
          self.resize_anchor = (min(xs), min(ys))
        self.box_op = "resize"
        return
      else:
        from canvas_graphics_engine import CORNERS
        for tag in tags:
          if tag in CORNERS:
            self.crop_corner = tag
            return
        if len(tags) > 1:
          self.handle_action(tags[1])
        return

    if self.mode == "select":
      top_item = self.pick_item()
      if top_item and (top_item in self.image_refs or self.is_shape(top_item)):
        self.selected_item = top_item
        self.dragging = True
        if self.is_shape(top_item):
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
    elif self.mode == "circle":
      hit = self.pick_item(3)
      if hit and self.is_circle(hit):
        self.selected_item = hit
        self.dragging = True
        self.aa_live(hit)
      else:
        x, y = self.last_x, self.last_y
        self.selected_item = None
        pts = self.make_circle_pts(x, y, x, y)
        self.temp_circle_id = self.canvas.create_polygon(
            *pts, outline=self.pen_color, fill="", width=self.tool_size, tags="circle_shape"
        )
        self.stroke_w[self.temp_circle_id] = self.tool_size
        self.live.add(self.temp_circle_id)
      self.show_handles()
    elif self.mode == "star":
      hit = self.pick_item(3)
      if hit and self.is_star(hit):
        self.selected_item = hit
        self.dragging = True
        self.aa_live(hit)
      else:
        x, y = self.last_x, self.last_y
        self.selected_item = None
        pts = self.make_star_pts(x, y, x, y)
        self.temp_star_id = self.canvas.create_polygon(
            *pts, outline=self.pen_color, fill="", width=self.tool_size, tags="star_shape"
        )
        self.stroke_w[self.temp_star_id] = self.tool_size
        self.live.add(self.temp_star_id)
      self.show_handles()
    elif self.mode == "eraser":
      self.erase_at(self.last_x, self.last_y)

  def on_canvas_drag(self, event):
    x = self.canvas.canvasx(event.x)
    y = self.canvas.canvasy(event.y)

    if self.box_op == "img_rotate" and self.selected_item in self.image_refs:
      self.rotate_drag(x, y)
    elif self.box_op and self.is_shape(self.selected_item):
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
    elif self.mode == "circle" and self.temp_circle_id:
      pts = self.make_circle_pts(self.press_x, self.press_y, x, y)
      self.canvas.coords(self.temp_circle_id, *pts)
    elif self.mode == "star" and self.temp_star_id:
      pts = self.make_star_pts(self.press_x, self.press_y, x, y)
      self.canvas.coords(self.temp_star_id, *pts)
    elif self.mode == "eraser":
      self.erase_at(self.last_x, self.last_y)
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
    elif self.temp_circle_id:
      self.selected_item = self.temp_circle_id
    elif self.temp_star_id:
      self.selected_item = self.temp_star_id

    self.temp_line_id = None
    self.temp_box_id = None
    self.temp_circle_id = None
    self.temp_star_id = None
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

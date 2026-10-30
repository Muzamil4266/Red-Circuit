import math
from tkinter import filedialog
from PIL import Image, ImageColor, ImageDraw, ImageGrab, ImageTk

CORNERS = {"cropBL": (-1, 1, "↙"), "cropBR": (1, 1, "↘"), "cropL": (-1, 0, "↔"), "cropR": (1, 0, "↔"),
           "cropT": (0, -1, "↕"), "cropB": (0, 1, "↕")}
AA = 4


class CanvasGraphicsEngineMixin:

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

  def is_circle(self, item):
    return bool(item) and "circle_shape" in self.canvas.gettags(item)

  def is_star(self, item):
    return bool(item) and "star_shape" in self.canvas.gettags(item)

  def is_shape(self, item):
    return self.is_box(item) or self.is_circle(item) or self.is_star(item)

  def box_pts(self, item):
    c = self.canvas.coords(item) if item else []
    return [(c[i], c[i + 1]) for i in range(0, len(c), 2)] if len(c) >= 6 else []

  def make_circle_pts(self, x1, y1, x2, y2, steps=36):
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    rx, ry = abs(x2 - x1) / 2, abs(y2 - y1) / 2
    pts = []
    for i in range(steps):
      angle = i * 2 * math.pi / steps
      pts.extend([cx + rx * math.cos(angle), cy + ry * math.sin(angle)])
    return pts

  def make_star_pts(self, x1, y1, x2, y2, points=5):
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    outer_r = min(abs(x2 - x1), abs(y2 - y1)) / 2
    inner_r = outer_r * 0.4
    pts = []
    for i in range(2 * points):
      r = outer_r if i % 2 == 0 else inner_r
      angle = i * math.pi / points - math.pi / 2
      pts.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])
    return pts

  def stroke_points(self, item):
    c = self.canvas.coords(item)
    pts = [(c[i], c[i + 1]) for i in range(0, len(c) - 1, 2)]
    if self.is_shape(item):
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
    color = ImageColor.getrgb(c.itemcget(item, "outline" if self.is_shape(item) else "fill"))
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
    for i in self.canvas.find_withtag("wire") + self.canvas.find_withtag("box_shape") + self.canvas.find_withtag("circle_shape") + self.canvas.find_withtag("star_shape"):
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
    if not item or (self.mode != "select" and not (self.mode in ("box", "circle", "star") and self.is_shape(item))):
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
    elif self.is_box(item) or self.is_star(item):
      pts = self.box_pts(item)
      if not pts:
        return
      xs, ys = [p[0] for p in pts], [p[1] for p in pts]
      x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
      F = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
      self.draw_handle(*F[0], "×", "box_delete")
      self.draw_handle(*F[1], "↻", "box_rotate")
      self.draw_handle(*F[2], "⤡", "box_resize")
    elif self.is_circle(item):
      pts = self.box_pts(item)
      if not pts:
        return
      xs, ys = [p[0] for p in pts], [p[1] for p in pts]
      x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
      self.draw_handle(x1, y1, "×", "box_delete")
      self.draw_handle(x2, y2, "⤡", "box_resize")

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
import os
import json
import base64
from components_data import EMBEDDED_COMPONENTS
from tkinter import filedialog


class SerializationManagerMixin:

  def get_state(self):
    """Whole drawing as plain data (used by save AND undo/redo)."""
    c = self.canvas
    return {
        "background_color": c.cget("bg"),
        "components": [
            {"path": r["path"], "x": c.coords(i)[0], "y": c.coords(i)[1],
             "scale": self.item_scales[i], "rotation": self.item_rotations[i],
             "crop": r.get("crop", [0.0, 0.0, 0.0, 0.0])}
            for i, r in self.image_refs.items()
        ],
        "wires": [
            {"coords": c.coords(i), "color": c.itemcget(i, "fill"), "size": self.stroke_w.get(i, 1.0)}
            for i in c.find_withtag("wire")
        ],
        "boxes": [
            {"coords": c.coords(i), "color": c.itemcget(i, "outline"), "size": self.stroke_w.get(i, 1.0)}
            for i in c.find_withtag("box_shape")
        ],
        "circles": [
            {"coords": c.coords(i), "color": c.itemcget(i, "outline"), "size": self.stroke_w.get(i, 1.0)}
            for i in c.find_withtag("circle_shape")
        ],
        "stars": [
            {"coords": c.coords(i), "color": c.itemcget(i, "outline"), "size": self.stroke_w.get(i, 1.0)}
            for i in c.find_withtag("star_shape")
        ],
        "texts": [
            {"text": c.itemcget(i, "text"), "x": c.coords(i)[0], "y": c.coords(i)[1]}
            for i in c.find_withtag("text_note")
        ],
    }

  def set_state(self, s):
    self.canvas.delete("all")
    self.image_refs.clear()
    self.item_scales.clear()
    self.item_rotations.clear()
    self.stroke_w.clear()
    self.aa_ids.clear()
    self.aa_tk.clear()
    self.live.clear()
    self.selected_item = None
    self.canvas.configure(bg=s.get("background_color", "#1e1e1e"))

    for c in s.get("components", []):
      if c["path"] in EMBEDDED_COMPONENTS:
        self.spawn_embedded_component(
            c["path"], base64.b64decode(EMBEDDED_COMPONENTS[c["path"]]), c["x"], c["y"],
            c.get("scale", 1.0), c.get("rotation", 0),
            c.get("crop", [0.0, 0.0, 0.0, 0.0])
        )
    for w in s.get("wires", []):
      i = self.canvas.create_line(*w["coords"], fill=w["color"], width=w["size"], capstyle="round", smooth=True, tags="wire")
      self.stroke_w[i] = w["size"]
      self.aa_render(i)
    for b in s.get("boxes", []):
      i = self.canvas.create_polygon(*b["coords"], outline=b["color"], width=b["size"], fill="", tags="box_shape")
      self.stroke_w[i] = b["size"]
      self.aa_render(i)
    for ci in s.get("circles", []):
      i = self.canvas.create_polygon(*ci["coords"], outline=ci["color"], width=ci["size"], fill="", tags="circle_shape")
      self.stroke_w[i] = ci["size"]
      self.aa_render(i)
    for st in s.get("stars", []):
      i = self.canvas.create_polygon(*st["coords"], outline=st["color"], width=st["size"], fill="", tags="star_shape")
      self.stroke_w[i] = st["size"]
      self.aa_render(i)
    for t in s.get("texts", []):
      self.canvas.create_text(t["x"], t["y"], text=t["text"], anchor="nw", font=("Arial", 12, "bold"), fill="black", tags="text_note")
    self.show_handles()

  def save_circuit(self):
    file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("JSON Circuit Files", "*.json")])
    if file_path:
      try:
        with open(file_path, "w") as f:
          json.dump(self.get_state(), f, indent=4)
        print("Circuit successfully saved!")
      except Exception as e:
        print(f"Save error: {e}")

  def load_circuit(self):
    file_path = filedialog.askopenfilename(filetypes=[("JSON Circuit Files", "*.json")])
    if file_path:
      try:
        with open(file_path, "r") as f:
          data = json.load(f)
        self.set_state(data)
        self.undo_stack.clear()
        self.redo_stack.clear()
        print("Circuit successfully loaded!")
      except Exception as e:
        print(f"Load error: {e}")

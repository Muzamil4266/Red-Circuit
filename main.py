import customtkinter as ctk
from canvas_ui_setup import CanvasUISetupMixin
from canvas_graphics_engine import CanvasGraphicsEngineMixin
from canvas_mouse_events import CanvasMouseEventsMixin
from canvas_tools_controller import CanvasToolsControllerMixin
from sidebar import SidebarManagerMixin
from history import HistoryManagerMixin
from serialization import SerializationManagerMixin

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class CircuitBuilderApp(
    ctk.CTk,
    CanvasUISetupMixin,
    CanvasGraphicsEngineMixin,
    CanvasMouseEventsMixin,
    CanvasToolsControllerMixin,
    SidebarManagerMixin,
    HistoryManagerMixin,
    SerializationManagerMixin,
):
  """Pure CustomTkinter Visual Circuit Builder - Ultimate Edition."""

  def __init__(self):
    super().__init__()
    self.title("Visual Circuit Builder Pro - Ultimate Edition")
    self.geometry("1500x950")

    self.mode = "select"
    self.pen_color = "#e74c3c"
    self.tool_size = 3
    self.last_x = 0
    self.last_y = 0
    self.line_start_x = None
    self.line_start_y = None
    self.temp_line_id = None
    self.dragging = False
    self.pre_state = None
    
    self.selected_item = None
    self.image_refs = {}      
    self.item_scales = {}     
    self.item_rotations = {}  
    self.sidebar_img_refs = [] 

    self.undo_stack = []
    self.redo_stack = []
    self.toolbar_buttons = {}

    self.grid_columnconfigure(0, weight=1)
    self.grid_columnconfigure(1, weight=0)
    self.grid_rowconfigure(0, weight=1)

    self.init_canvas_and_toolbar()
    self.init_sidebar()
    self.load_components_to_sidebar()


if __name__ == "__main__":
  app = CircuitBuilderApp()
  app.mainloop()

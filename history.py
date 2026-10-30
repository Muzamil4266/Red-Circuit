class HistoryManagerMixin:
  """Snapshot-based undo/redo: call begin_change() before an edit, commit_change() after."""

  def begin_change(self):
    self.pre_state = self.get_state()

  def commit_change(self):
    if self.pre_state is not None and self.get_state() != self.pre_state:
      self.undo_stack.append(self.pre_state)
      del self.undo_stack[:-50]
      self.redo_stack.clear()
    self.pre_state = None

  def _swap(self, src, dst):
    if src:
      dst.append(self.get_state())
      self.set_state(src.pop())

  def perform_undo(self):
    self._swap(self.undo_stack, self.redo_stack)

  def perform_redo(self):
    self._swap(self.redo_stack, self.undo_stack)

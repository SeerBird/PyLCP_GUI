from PySide6.QtCore import Qt
from PySide6.QtGui import QRgba64

transition_thickness = 40
transition_hover_color = Qt.GlobalColor.green
transition_color = Qt.GlobalColor.black
transition_line_thickness = 3
diagram_rearrange_margin_fraction = 0.1
# region pens
state_line_color = QRgba64.fromRgba(255, 255, 255, 255)
state_line_thickness = 5
# endregion
# region diagram sizes
fine_state_width = 100
fine_state_height = 50
curly_bracket_thickness = 1
curly_bracket_width = 20

hyperfine_state_width = 100
hyperfine_state_height = 40

magnetic_state_width = 60
magnetic_state_height = 40
magnetic_state_spacing_half = 5
# endregion

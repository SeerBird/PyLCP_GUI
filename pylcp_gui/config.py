from PySide6.QtCore import Qt
from PySide6.QtGui import QRgba64, QColor

transition_thickness = 10
transition_hover_color = Qt.GlobalColor.green
transition_color = Qt.GlobalColor.black
transition_line_thickness = 3
diagram_rearrange_margin_fraction = 0.1
# region pens
state_line_color = QColor.fromRgb(255, 255, 255, 255)
mf_add_color = QColor.fromRgb(0, 255, 0, 80)
mf_remove_color = QColor.fromRgb(255, 0, 0, 200)
state_line_thickness = 3
# endregion
# region diagram sizes
fine_state_width = 100
fine_state_height = 50
curly_bracket_thickness = 1
curly_bracket_width = 20

hyperfine_state_width = 100
hyperfine_state_height = 40
hyperfine_width_drawn_proportion = 0.8

magnetic_state_width = 60
magnetic_state_height = 40
magnetic_state_spacing_half = 5

arrow_length = 12.0
arrow_flare_angle = 0.4

draggable_line_grab_width = 8.
# endregion
# region debug
debug_highlight = QColor.fromRgb(255, 0, 0, 255)
debug_thickness = 1
# endregion

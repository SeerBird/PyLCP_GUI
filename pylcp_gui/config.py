from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

transition_thickness = 10
transition_hover_color = Qt.GlobalColor.green
transition_color = Qt.GlobalColor.black
transition_line_thickness = 3
diagram_rearrange_margin_fraction = 0.1
# region pens and colors
state_line_color = QColor.fromRgb(255, 255, 255, 255)
mf_add_color = QColor.fromRgb(0, 255, 0, 80)
mf_remove_color = QColor.fromRgb(255, 0, 0, 200)
state_line_thickness = 3
toggle_checked_bg = QColor.fromRgb(60, 100, 10, 255).darker()
toggle_unchecked_bg = QColor.fromRgb(100, 10, 20, 255).darker()
# region themes and theme colors
from enum import Enum, auto


class DiagramElementType(Enum):
    FINE_STATE = auto()
    HYPERFINE_STATE = auto()
    TRANSITION = auto()
    LASER_DISPLAY = auto()
    MAGNETIC_STATE = auto()


class ElementColorRole(Enum):
    NORMAL = auto()
    HOVER = auto()
    SELECTED = auto()
    DISABLED = auto()
    ADD_HOVER = auto()
    REMOVE_HOVER = auto()

theme_colors = {
    DiagramElementType.FINE_STATE: {
        ElementColorRole.NORMAL: QColor.fromRgb(255, 255, 255, 255),
        ElementColorRole.HOVER: QColor.fromRgb(0, 229, 255, 255),
        ElementColorRole.SELECTED: QColor.fromRgb(255, 215, 0, 255),
    },
    DiagramElementType.HYPERFINE_STATE: {
        ElementColorRole.NORMAL: QColor.fromRgb(255, 255, 255, 255),
        ElementColorRole.HOVER: QColor.fromRgb(0, 229, 255, 255),
        ElementColorRole.SELECTED: QColor.fromRgb(255, 215, 0, 255),
    },
    DiagramElementType.TRANSITION: {
        ElementColorRole.NORMAL: QColor.fromRgb(200, 200, 200, 255),
        ElementColorRole.HOVER: QColor.fromRgb(0, 255, 102, 255),
        ElementColorRole.SELECTED: QColor.fromRgb(255, 215, 0, 255),
    },
    DiagramElementType.LASER_DISPLAY: {
        ElementColorRole.NORMAL: QColor.fromRgb(255, 255, 255, 255),
        ElementColorRole.HOVER: QColor.fromRgb(0, 229, 255, 255),
        ElementColorRole.SELECTED: QColor.fromRgb(255, 215, 0, 255),
    },
    DiagramElementType.MAGNETIC_STATE: {
        ElementColorRole.NORMAL: QColor.fromRgb(255, 255, 255, 255),
        ElementColorRole.DISABLED: QColor.fromRgb(255, 255, 255, 64),
        ElementColorRole.ADD_HOVER: QColor.fromRgb(0, 255, 0, 200),
        ElementColorRole.REMOVE_HOVER: QColor.fromRgb(255, 0, 0, 200),
    }
}
# endregion
# endregion
# region diagram sizes
diagram_fine_state_view_proportion = 0.3
diagram_fine_state_spacer_view_proportion = 0.1
fine_state_vertical_empty_space_proportion = 0.5

fine_state_width = 100
fine_state_height = 50
fine_state_hover_width = 18
curly_bracket_thickness = 1
curly_bracket_width = 20
fine_label_font = QFont("Arial", 18, QFont.Weight.Bold)

hf_state_width = 100
hf_state_height = 40
hf_state_hover_width = 18
hf_width_drawn_proportion = 0.8
hf_label_font = QFont("Arial", 12, QFont.Weight.Bold)

magnetic_state_width = 60
magnetic_state_height = 40
magnetic_state_spacing_half = 5

arrow_length = 12.0
arrow_flare_angle = 0.4
laser_display_hover_width = 18

draggable_line_grab_width = 8.


label_color = QColor.fromRgb(255, 255, 255, 255)
# endregion
# region toggle button colors

# endregion
# region debug
debug_highlight = QColor.fromRgb(255, 0, 0, 0)
debug_thickness = 1
# endregion

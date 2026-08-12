from PySide6.QtWidgets import QApplication, QStyleFactory

from pylcp_gui import MainDialog, dialog_from_dataframe, DataFrame
from pylcp_gui.dataframe.dataframe import LaserDisplayData
from testutil import make_rubidium_frame, add_laser_display
from pathlib import Path

file_path = Path("laser_displays_frame")
if file_path.is_file():
    frame = DataFrame.load_from_file(file_path)
else:
    frame = make_rubidium_frame(-2, 1, 1)
frame = dialog_from_dataframe(frame)
frame.save(file_path)

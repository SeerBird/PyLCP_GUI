from PySide6.QtWidgets import QApplication, QStyleFactory

from pylcp_gui import MainDialog
from pylcp_gui.dataframe.dataframe import LaserDisplayData
from testutil import make_rubidium_frame, add_laser_display

frame = make_rubidium_frame(-2, 1)
app = QApplication()
app.setStyle(QStyleFactory.create('Fusion'))
dialog = MainDialog(frame)
add_laser_display(dialog,0,1,0)
res = dialog.exec()
app.shutdown()
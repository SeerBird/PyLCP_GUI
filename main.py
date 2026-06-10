import os.path

from pylcp import obe

import pylcp_gui as gui
from pylcp_gui import DataFrame

path = "myFrame"
if os.path.exists(path):
    newframe = gui.dialog(DataFrame.load_from_file("myFrame"))
else:

    newframe = gui.dialog()
newframe.save("myFrame")
print(newframe.hamiltonian()) # what do we do


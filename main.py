import os.path

from pylcp import obe
import faulthandler

# Force Python to print a dump of the active thread stack traces upon a hard crash
faulthandler.enable()
import pylcp_gui as gui
from pylcp_gui import DataFrame

path = "myFrame"
if os.path.exists(path):
    newframe = gui.dialog(DataFrame.load_from_file("myFrame"))
else:

    newframe = gui.dialog()
newframe.save("myFrame")
print(newframe.hamiltonian()) # what do we do


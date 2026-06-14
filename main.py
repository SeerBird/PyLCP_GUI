import os.path

from pylcp import obe
import faulthandler

# Force Python to print a dump of the active thread stack traces upon a hard crash
faulthandler.enable()
import pylcp_gui as gui
from pylcp_gui import DataFrame

path = "myFrame"
newframe = DataFrame.load_from_file(path)
newframe._change_values_for_debug()
print(newframe.obe())
newframe.save(path)



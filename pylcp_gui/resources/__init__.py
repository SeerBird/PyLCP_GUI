import os
from enum import Enum
from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap
from importlib import resources


def get_file(name: str | os.PathLike[str]):
    name: str
    return Path(__file__).parent / name


class MyIcon(Enum):
    delete_state = "cross.png"
    add_state = "plus.png"
    mF_state = "line.png"


loaded_icons: dict[MyIcon, QIcon] = {}


def get_icon(name: MyIcon):
    global loaded_icons
    if name in loaded_icons:
        return loaded_icons[name]
    icon = QIcon(QPixmap(get_file(name.value)))
    loaded_icons[name] = icon
    return icon

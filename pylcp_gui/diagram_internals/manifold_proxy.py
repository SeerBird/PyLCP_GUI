from PySide6.QtWidgets import QGraphicsProxyWidget


class ManifoldProxy(QGraphicsProxyWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptHoverEvents(True)
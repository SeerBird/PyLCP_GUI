from PySide6.QtWidgets import QWidget, QFrame, QLineEdit, QGridLayout


class VectorTextInput(QFrame):
    def __init__(self, /):
        super().__init__()
        self.textboxes = (QLineEdit(), QLineEdit(), QLineEdit())
        self._layout = QGridLayout(self)
        for i in range(len(self.textboxes)):
            self._layout.addWidget(self.textboxes[i], 0, i)
    def value(self):
        # TODO: add validation etc.
        return (textbox.text() for textbox in self.textboxes)

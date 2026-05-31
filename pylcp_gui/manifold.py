from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy


class Manifold(QFrame):
    def __init__(self, label:str, energy:float):
        # TODO: maybe an energy, maybe an F-number,
        super().__init__()
        self.label = label
        self.energy = energy
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel(label))
        self.layout.addWidget(QLabel(f"H_0: {energy:.3E}"))
        self.setFrameShape(QFrame.Shape.HLine) # TODO: make this contain multiple states
        self.setFixedSize(self.size())
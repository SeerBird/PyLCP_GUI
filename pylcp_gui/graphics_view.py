from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene

SCALE_FACTOR = 1.25


class GraphicsView(QGraphicsView):
    coordinatesChanged = Signal(QtCore.QPoint)

    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self._scene = scene
        self._zoom = 0
        self._pinned = False
        self._empty = True
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)

    def zoom(self, step):
        factor = SCALE_FACTOR ** step
        self.scale(factor, factor)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.zoom(delta and delta // abs(delta))
        self.resetView()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resetView()

    def toggleDragMode(self):
        if self.dragMode() == QtWidgets.QGraphicsView.DragMode.ScrollHandDrag:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)

    def leaveEvent(self, event):
        self.coordinatesChanged.emit(QtCore.QPoint())
        super().leaveEvent(event)

    def resetView(self):
        viewrect = self.viewport().rect()
        scenerect = self.transform().mapRect(QtCore.QRectF(self._scene.sceneRect()))
        if scenerect.isNull():
            return
        factor = min(viewrect.width() / scenerect.width(),
                     viewrect.height() / scenerect.height())
        if factor >= 1:
            self.scale(factor, factor)

    def zoomPinned(self):
        return self._pinned

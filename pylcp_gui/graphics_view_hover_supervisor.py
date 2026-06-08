from PySide6.QtCore import QObject, QEvent, QCoreApplication, QPointF
from PySide6.QtGui import QHoverEvent, QMouseEvent
from PySide6.QtWidgets import QPushButton, QGraphicsView, QGraphicsProxyWidget, QWidget


class GraphicsViewHoverSupervisor(QObject):
    def __init__(self, view):
        super().__init__(view)
        self.hovered: QWidget | None = None
        self.lastGlobalPos = QPointF()
        self.view = view

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # region handle mouse movement
        if event.type() == QEvent.Type.MouseMove:
            assert isinstance(event, QMouseEvent)

            globalPos = event.globalPos()
            # region if we were hovering over something, check if we left it
            if self.hovered is not None:
                selfHoveredPos = self.hovered.mapFromGlobal(globalPos)
                if not self.hovered.rect().contains(selfHoveredPos):
                    self.issue_hover_leave_event(selfHoveredPos)
            # endregion
            # region if we just left a QWidget or were never hovering over one, check if we entered one
            if self.hovered is None:
                # get hovered QWidget and its local mouse event position
                item = self.view.scene().itemAt(self.view.mapToScene(event.pos()),
                                                self.view.transform())
                if isinstance(item, QGraphicsProxyWidget):
                    embedded_widget = item.widget()
                    embeddedPos = embedded_widget.mapFromGlobal(globalPos)
                    hovered = embedded_widget.childAt(embeddedPos)
                    if hovered is None: # also send these events to the embedded item if appropriate
                        if embedded_widget.rect().contains(embeddedPos):
                            hovered = embedded_widget  # TODO: check if the embedded widget already receives these events
                    if hovered is not None:
                        hovered_local_pos = hovered.mapFromGlobal(globalPos)
                        self.issue_hover_enter_event(hovered, hovered_local_pos)
            # endregion
            self.lastGlobalPos = globalPos

        # endregion
        # region handle window changes etc
        elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.WindowDeactivate,
                QEvent.Type.FocusOut,
                QEvent.Type.Hide):
            self.issue_hover_leave_event(QPointF())
        # endregion

        return super().eventFilter(watched, event)

    def issue_hover_leave_event(self, pos):
        print(f"Left {self.hovered}")
        if self.hovered is not None:
            hoverLeaveEvent = QHoverEvent(QEvent.Type.HoverLeave, pos,
                                          self.hovered.mapFromGlobal(self.lastGlobalPos))
            QCoreApplication.sendEvent(self.hovered, hoverLeaveEvent)
            self.hovered = None

    def issue_hover_enter_event(self, hovered, pos):
        print(f"Entered {hovered}")
        hoverEnterEvent = QHoverEvent(QEvent.Type.HoverEnter, pos,
                                      hovered.mapFromGlobal(self.lastGlobalPos))
        QCoreApplication.sendEvent(hovered, hoverEnterEvent)
        self.hovered = hovered

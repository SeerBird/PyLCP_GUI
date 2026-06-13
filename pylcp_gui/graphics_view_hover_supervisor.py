from PySide6.QtCore import QObject, QEvent, QCoreApplication, QPointF
from PySide6.QtGui import QHoverEvent, QMouseEvent
from PySide6.QtWidgets import QPushButton, QGraphicsView, QGraphicsProxyWidget, QWidget


def get_ancestry_up_to_view(child: QWidget | None):
    if child is None:
        return []
    traversed = child  # TODO: is this line necessary?
    path = []
    while traversed is not None:
        # TODO: this condition requires that all my embeds have no parents,
        #  and all their children have an ancestry tree leading up to the embeds
        # TODO: replace all asserts with proper exceptions later
        path.append(traversed)
        traversed = traversed.parent()
    return path


class GraphicsViewHoverSupervisor(QObject):
    def __init__(self, view):
        super().__init__(view)
        self.last_hovered: QWidget | None = None
        self.lastGlobalPos = QPointF()
        self.view = view

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # get all currently hovered items
        last_hovered_ancestry = get_ancestry_up_to_view(self.last_hovered)
        # region handle mouse movement
        if event.type() == QEvent.Type.MouseMove:
            assert isinstance(event, QMouseEvent)

            globalPos = event.globalPos()
            # region get currently hovered item current_hovered
            current_hovered = None
            item = self.view.scene().itemAt(self.view.mapToScene(event.pos()),
                                            self.view.transform())
            if isinstance(item, QGraphicsProxyWidget):
                embedded_widget = item.widget()
                embeddedPos = embedded_widget.mapFromGlobal(globalPos)
                current_hovered = embedded_widget.childAt(embeddedPos)
                if current_hovered is None:  # also send these events to the embedded item if appropriate
                    if embedded_widget.rect().contains(embeddedPos):
                        current_hovered = embedded_widget  # TODO: check if the embedded widget already receives these events
            # endregion
            if self.last_hovered == current_hovered:  # a little optimization
                return super().eventFilter(watched, event)
            current_hovered_ancestry = get_ancestry_up_to_view(current_hovered)
            # region issue HoverLeave events to all the items we left
            for last_hovered_ancestor in last_hovered_ancestry:
                if not last_hovered_ancestor in current_hovered_ancestry:
                    pos = last_hovered_ancestor.mapFromGlobal(globalPos)
                    self.issue_hover_leave_event(last_hovered_ancestor, pos)
            # endregion
            # region issue HoverEnter events to all the items we entered
            for current_hovered_ancestor in current_hovered_ancestry:
                if not current_hovered_ancestor in last_hovered_ancestry:
                    pos = current_hovered_ancestor.mapFromGlobal(globalPos)
                    self.issue_hover_enter_event(current_hovered_ancestor, pos)
            # endregion
            self.lastGlobalPos = globalPos
            self.last_hovered = current_hovered
            if self.last_hovered is not None:
                self.last_hovered.destroyed.connect(self.last_hovered_destroyed)

        # endregion
        # region handle window changes etc
        elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.WindowDeactivate,
                QEvent.Type.FocusOut,
                QEvent.Type.Hide):
            for last_hovered_ancestor in last_hovered_ancestry:
                self.issue_hover_leave_event(last_hovered_ancestor, QPointF())
        # endregion
        return super().eventFilter(watched, event)

    def issue_hover_leave_event(self, target, pos):
        print(f"Leaving {target}")
        assert target is not None
        hoverLeaveEvent = QHoverEvent(QEvent.Type.HoverLeave, pos,
                                      target.mapFromGlobal(self.lastGlobalPos))
        assert isinstance(target, QObject)
        QCoreApplication.sendEvent(target, hoverLeaveEvent)

    def issue_hover_enter_event(self, target, pos):
        print(f"Entering {target}")
        hoverEnterEvent = QHoverEvent(QEvent.Type.HoverEnter, pos,
                                      target.mapFromGlobal(self.lastGlobalPos))
        QCoreApplication.sendEvent(target, hoverEnterEvent)

    def last_hovered_destroyed(self):
        self.last_hovered = None

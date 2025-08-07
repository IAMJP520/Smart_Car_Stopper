import sys
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem, QGraphicsLineItem,
    QPushButton, QComboBox, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout
)
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter
from PyQt5.QtCore import Qt, QPointF


class ParkingLotUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("실내 주차장 UI")
        self.setGeometry(100, 100, 1200, 900)

        self.scene_width = 2000
        self.scene_height = 2000

        self.scene = QGraphicsScene(0, 0, self.scene_width, self.scene_height)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.scale(0.5, 0.5)

        # 차량 유형 선택 및 안내 버튼
        self.combo = QComboBox()
        self.combo.addItems(["일반차", "전기차", "장애인차"])

        self.btn_start = QPushButton("입차 및 안내 시작")
        self.btn_next = QPushButton("다음 경로")
        self.btn_next.setEnabled(False)

        self.btn_start.clicked.connect(self.start_navigation)
        self.btn_next.clicked.connect(self.show_next_path_segment)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.combo)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_next)

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.draw_layout()

        self.path_points = []
        self.current_step = 0

    def flip_y(self, y, h):
        return self.scene_height - y - h

    def flip_y_point(self, point):
        return QPointF(point.x(), self.scene_height - point.y())

    def add_block(self, x, y, w, h, color, label_text):
        y_flipped = self.flip_y(y, h)
        rect = QGraphicsRectItem(x, y_flipped, w, h)
        rect.setBrush(QBrush(color))
        rect.setPen(QPen(Qt.black))
        self.scene.addItem(rect)

        if label_text.strip():
            label = QGraphicsSimpleTextItem(label_text)
            label.setPos(x + 5, y_flipped + 5)
            self.scene.addItem(label)

    def draw_layout(self):
        self.scene.clear()

        # 색상 정의
        color_disabled = QColor("#f4a261")
        color_electric = QColor("#2a9d8f")
        color_general = QColor("#264653")
        color_obstacle = QColor("#6c757d")
        color_empty = QColor("#ced4da")
        color_io = QColor("#e76f51")
        color_border = QColor("black")

        # 외곽
        border = QGraphicsRectItem(0, 0, self.scene_width, self.scene_height)
        border.setPen(QPen(color_border, 8))
        self.scene.addItem(border)

        self.add_block(0, 0, 400, 400, color_io, "입출차")
        self.add_block(0, 1600, 300, 400, color_disabled, "장애인")
        self.add_block(300, 1600, 300, 400, color_disabled, "장애인")

        # 일반 + 전기차 구역 (좌상단)
        self.add_block(600, 1600, 200, 400, color_general, "일반")
        self.add_block(800, 1600, 200, 400, color_general, "일반")
        self.add_block(1000, 1600, 200, 400, color_general, "일반")
        self.add_block(1200, 1600, 200, 400, color_electric, "전기차")
        self.add_block(1400, 1600, 200, 400, color_electric, "전기차")
        self.add_block(1600, 1600, 400, 400, color_empty, "빈기둥")

        self.add_block(600, 1050, 800, 300, color_obstacle, "장애물")
        self.add_block(1600, 400, 400, 400, color_empty, "빈기둥")

        for i in range(6):
            self.add_block(400 + i * 200, 400, 200, 400, color_general, "일반")

        for i in range(4):
            self.add_block(1600, 800 + i * 200, 400, 200, color_general, "일반")

        # 입구 표시 마커
        self.entrance = QPointF(200, 200)
        self.scene.addEllipse(self.entrance.x()-5, self.entrance.y()-5, 10, 10, QPen(Qt.black), QColor("blue"))
        self.scene.addText("입구").setPos(self.entrance.x() - 20, self.entrance.y() - 30)

        # 목적지들
        self.general_zone = QPointF(700, 600)
        self.electric_zone = QPointF(1300, 1800)
        self.disabled_zone = QPointF(200, 1800)

    def start_navigation(self):
        self.draw_layout()
        self.path_points = []
        self.current_step = 0
        self.btn_next.setEnabled(True)

        vehicle_type = self.combo.currentText()
        if vehicle_type == "일반차":
            self.path_points = self.generate_waypoints(self.entrance, self.general_zone)
        elif vehicle_type == "장애인차":
            self.path_points = self.generate_waypoints(self.entrance, self.disabled_zone)
        elif vehicle_type == "전기차":
            result = QMessageBox.question(self, "충전 여부", "충전이 필요합니까?", QMessageBox.Yes | QMessageBox.No)
            if result == QMessageBox.Yes:
                self.path_points = self.generate_waypoints(self.entrance, self.electric_zone)
            else:
                self.path_points = self.generate_waypoints(self.entrance, self.general_zone)

        self.show_next_path_segment()

    def generate_waypoints(self, start: QPointF, end: QPointF):
        mid1 = QPointF((start.x() + end.x()) / 2, start.y())
        mid2 = QPointF((start.x() + end.x()) / 2, end.y())
        return [
            self.flip_y_point(start),
            self.flip_y_point(mid1),
            self.flip_y_point(mid2),
            self.flip_y_point(end)
        ]

    def show_next_path_segment(self):
        if self.current_step < len(self.path_points) - 1:
            p1 = self.path_points[self.current_step]
            p2 = self.path_points[self.current_step + 1]
            line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
            pen = QPen(QColor("red"), 3)
            line.setPen(pen)
            self.scene.addItem(line)
            self.current_step += 1
        else:
            QMessageBox.information(self, "안내 완료", "도착지에 도착했습니다.")
            self.btn_next.setEnabled(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = ParkingLotUI()
    ui.show()
    sys.exit(app.exec_())

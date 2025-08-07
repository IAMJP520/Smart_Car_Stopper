import sys
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QWidget, QVBoxLayout
)
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter
from PyQt5.QtCore import Qt


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

        layout = QVBoxLayout()
        layout.addWidget(self.view)
        self.setLayout(layout)

        self.draw_layout()

    def draw_layout(self):
        # 색상 정의
        color_disabled = QColor("#f4a261")
        color_electric = QColor("#2a9d8f")
        color_general = QColor("#264653")
        color_obstacle = QColor("#6c757d")
        color_empty = QColor("#ced4da")
        color_io = QColor("#e76f51")
        color_border = QColor("black")

        # 외곽 경계선
        border = QGraphicsRectItem(0, 0, self.scene_width, self.scene_height)
        border.setPen(QPen(color_border, 8))
        self.scene.addItem(border)

        # 입출차 구역
        self.add_block(0, 0, 400, 400, color_io, "입출차")

        # 장애인 구역
        self.add_block(0, 1600, 300, 400, color_disabled, "장애인")
        self.add_block(300, 1600, 300, 400, color_disabled, "장애인")

        # 일반 주차칸 (좌상단 4칸)
        # for i in range(4):
            # self.add_block(600 + i * 200, 1600, 200, 400, color_general, "일반")
        # 일반 주차칸 + 전기차칸 (좌상단)
        self.add_block(600, 1600, 200, 400, color_general, "일반")
        self.add_block(800, 1600, 200, 400, color_general, "일반")
        self.add_block(1000, 1600, 200, 400, color_general, "일반")  # ← 전기차로 교체
        self.add_block(1200, 1600, 200, 400, color_electric, "전기차")


        # 전기차 구역
        self.add_block(1400, 1600, 200, 400, color_electric, "전기차")

        # 빈 공간 우상단
        self.add_block(1600, 1600, 400, 400, color_empty, "빈기둥")

        # 가운데 장애물
        self.add_block(600, 1050, 800, 300, color_obstacle, "장애물")

        # 빈 공간 우측 중단
        self.add_block(1600, 400, 400, 400, color_empty, "빈기둥")

        # ➕ 추가 일반 주차칸 (하단 중앙 6칸)
        for i in range(6):
            self.add_block(400 + i * 200, 400, 200, 400, color_general, "일반")

        # 🔄 수정된 우측 사이드 일반 주차칸 (가로로 긴 직사각형 4개, 세로로 배열)
        for i in range(4):
            self.add_block(1600, 800 + i * 200, 400, 200, color_general, "일반")

 
    def flip_y(self, y, h):
        """상하 반전을 위한 y 좌표 변환"""
        return self.scene_height - y - h

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = ParkingLotUI()
    ui.show()
    sys.exit(app.exec_())

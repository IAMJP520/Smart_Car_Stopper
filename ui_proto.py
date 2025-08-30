import sys
from PyQt5.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsLineItem, QPushButton, QComboBox, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout
)
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt, QPointF


class ParkingSystemUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("실내 주차장 안내 시스템")
        self.setGeometry(100, 100, 900, 700)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setFixedSize(800, 600)

        self.combo = QComboBox()
        self.combo.addItems(["일반차", "전기차", "장애인차"])

        self.btn_start = QPushButton("입차 및 안내 시작")
        self.btn_next = QPushButton("다음 경로")
        self.btn_next.setEnabled(False)

        self.btn_start.clicked.connect(self.start_navigation)
        self.btn_next.clicked.connect(self.show_next_path_segment)

        # 레이아웃 구성
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.combo)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_next)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.view)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        self.draw_parking_layout()

        # 웨이포인트 관련
        self.path_points = []
        self.current_step = 0

    def draw_parking_layout(self):
        # 입구/출구/목적지 위치 설정
        self.entrance = QPointF(50, 300)
        self.exit = QPointF(750, 300)
        self.general_zone = QPointF(700, 100)
        self.electric_zone = QPointF(700, 500)
        self.disabled_zone = QPointF(700, 300)

        self.scene.addEllipse(self.entrance.x()-5, self.entrance.y()-5, 10, 10, QPen(Qt.black), QColor("blue"))
        self.scene.addText("입구").setPos(self.entrance.x() - 20, self.entrance.y() - 30)

        self.scene.addEllipse(self.general_zone.x()-5, self.general_zone.y()-5, 10, 10, QPen(), QColor("gray"))
        self.scene.addEllipse(self.electric_zone.x()-5, self.electric_zone.y()-5, 10, 10, QPen(), QColor("green"))
        self.scene.addEllipse(self.disabled_zone.x()-5, self.disabled_zone.y()-5, 10, 10, QPen(), QColor("orange"))

        self.scene.addText("일반구역").setPos(self.general_zone.x() - 30, self.general_zone.y() - 30)
        self.scene.addText("전기차충전").setPos(self.electric_zone.x() - 30, self.electric_zone.y() - 30)
        self.scene.addText("장애인구역").setPos(self.disabled_zone.x() - 30, self.disabled_zone.y() - 30)

    def start_navigation(self):
        self.scene.clear()
        self.draw_parking_layout()
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

        self.show_next_path_segment()  # 첫 번째 경로 즉시 표시

    def generate_waypoints(self, start: QPointF, end: QPointF):
        # 간단한 3단계 경로 생성 예시
        mid1 = QPointF((start.x() + end.x()) / 2, start.y())      # X방향 먼저 이동
        mid2 = QPointF((start.x() + end.x()) / 2, end.y())        # 그 다음 Y방향
        return [start, mid1, mid2, end]

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
    window = ParkingSystemUI()
    window.show()
    sys.exit(app.exec_())

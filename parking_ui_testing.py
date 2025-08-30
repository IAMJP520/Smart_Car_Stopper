import sys
from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QLineEdit, QLabel, QMessageBox, QGraphicsItemGroup, QFrame, QGraphicsObject
)
from PyQt5.QtGui import QBrush, QPainter, QPen, QColor, QPainterPath, QFont, QPolygonF, QLinearGradient
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal

# ===================================================================
# 고급 HUD 위젯: 현대적인 자동차 네비게이션 스타일
# ===================================================================
class AdvancedHudWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumSize(400, 600)
        self.setStyleSheet("""
            AdvancedHudWidget { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0a0a, stop:0.3 #1a1a1a, stop:1 #0f0f0f);
                border: 3px solid #00aaff;
                border-radius: 15px;
            }
        """)
        
        # 현재 지시사항 정보
        self.current_direction = "직진"
        self.current_distance = 0.0
        self.next_direction = ""
        self.speed = 0  # km/h
        self.progress = 0  # 0-100%
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 전체 영역
        rect = self.rect()
        center_x = rect.width() // 2
        
        # === 1. 상단: 다음 방향 화살표 ===
        self.draw_direction_arrow(painter, center_x, 80)
        
        # === 2. 중앙: 거리 정보 ===
        self.draw_distance_info(painter, center_x, 200)
        
        # === 3. 속도 및 진행률 ===
        self.draw_speed_and_progress(painter, center_x, 320)
        
        # === 4. 하단: 다음 지시사항 미리보기 ===
        self.draw_next_instruction(painter, center_x, 450)
        
        # === 5. 장식적 요소들 ===
        self.draw_decorative_elements(painter, rect)

    def draw_direction_arrow(self, painter, center_x, y):
        """상단 대형 방향 화살표 - 거리 기반 제어"""
        painter.save()
        
        # 배경 원 - 방향에 따라 색상 변경
        if self.current_distance <= 5 and ("좌회전" in self.current_direction or "우회전" in self.current_direction or "목적지" in self.current_direction):
            # 5m 이내 턴이나 도착일 때 경고색
            painter.setBrush(QBrush(QColor(100, 50, 0, 150)))
            painter.setPen(QPen(QColor(255, 170, 0), 3))
        else:
            # 직진일 때 기본색
            painter.setBrush(QBrush(QColor(0, 50, 100, 150)))
            painter.setPen(QPen(QColor(0, 170, 255), 3))
        
        painter.drawEllipse(center_x - 60, y - 60, 120, 120)
        
        # 방향에 따른 화살표 그리기
        if self.current_distance <= 5:
            # 5m 이내일 때만 실제 방향 표시
            if "좌회전" in self.current_direction:
                painter.setPen(QPen(QColor(255, 170, 0), 8))
                painter.setBrush(QBrush(QColor(255, 170, 0)))
                self.draw_left_arrow(painter, center_x, y)
            elif "우회전" in self.current_direction:
                painter.setPen(QPen(QColor(255, 170, 0), 8))
                painter.setBrush(QBrush(QColor(255, 170, 0)))
                self.draw_right_arrow(painter, center_x, y)
            elif "목적지" in self.current_direction:
                painter.setPen(QPen(QColor(255, 100, 100), 8))
                painter.setBrush(QBrush(QColor(255, 100, 100)))
                self.draw_destination_flag(painter, center_x, y)
            else:
                painter.setPen(QPen(QColor(0, 255, 170), 8))
                painter.setBrush(QBrush(QColor(0, 255, 170)))
                self.draw_straight_arrow(painter, center_x, y)
        else:
            # 5m 초과일 때는 항상 직진 화살표
            painter.setPen(QPen(QColor(0, 255, 170), 8))
            painter.setBrush(QBrush(QColor(0, 255, 170)))
            self.draw_straight_arrow(painter, center_x, y)
        
        painter.restore()

    def draw_left_arrow(self, painter, x, y):
        """좌회전 화살표"""
        arrow = QPolygonF([
            QPointF(x - 30, y),
            QPointF(x - 10, y - 20),
            QPointF(x - 10, y - 10),
            QPointF(x + 20, y - 10),
            QPointF(x + 20, y + 10),
            QPointF(x - 10, y + 10),
            QPointF(x - 10, y + 20)
        ])
        painter.drawPolygon(arrow)

    def draw_right_arrow(self, painter, x, y):
        """우회전 화살표"""
        arrow = QPolygonF([
            QPointF(x + 30, y),
            QPointF(x + 10, y - 20),
            QPointF(x + 10, y - 10),
            QPointF(x - 20, y - 10),
            QPointF(x - 20, y + 10),
            QPointF(x + 10, y + 10),
            QPointF(x + 10, y + 20)
        ])
        painter.drawPolygon(arrow)

    def draw_straight_arrow(self, painter, x, y):
        """직진 화살표"""
        arrow = QPolygonF([
            QPointF(x, y - 30),
            QPointF(x - 15, y - 10),
            QPointF(x - 8, y - 10),
            QPointF(x - 8, y + 20),
            QPointF(x + 8, y + 20),
            QPointF(x + 8, y - 10),
            QPointF(x + 15, y - 10)
        ])
        painter.drawPolygon(arrow)

    def draw_destination_flag(self, painter, x, y):
        """목적지 깃발"""
        # 깃발 기둥
        painter.setPen(QPen(QColor(255, 100, 100), 6))
        painter.drawLine(x - 20, y - 25, x - 20, y + 25)
        
        # 깃발
        flag = QPolygonF([
            QPointF(x - 20, y - 25),
            QPointF(x + 15, y - 15),
            QPointF(x + 15, y - 5),
            QPointF(x - 20, y - 15)
        ])
        painter.setBrush(QBrush(QColor(255, 100, 100)))
        painter.drawPolygon(flag)

    def draw_distance_info(self, painter, center_x, y):
        """중앙 거리 정보 - 색상 변경으로 긴급도 표시"""
        painter.save()
        
        # 거리 숫자
        distance_text = f"{self.current_distance:.0f}m"
        if self.current_distance >= 1000:
            distance_text = f"{self.current_distance/1000:.1f}km"
        
        font = QFont("Arial", 48, QFont.Bold)
        painter.setFont(font)
        
        # 거리에 따른 색상 변경
        if self.current_distance <= 5:
            painter.setPen(QPen(QColor(255, 170, 0)))  # 주황색 (경고)
        elif self.current_distance <= 20:
            painter.setPen(QPen(QColor(255, 255, 100)))  # 노란색 (주의)
        else:
            painter.setPen(QPen(QColor(0, 255, 170)))  # 초록색 (안전)
        
        # 텍스트 중앙 정렬
        fm = painter.fontMetrics()
        text_width = fm.width(distance_text)
        painter.drawText(center_x - text_width//2, y, distance_text)
        
        # 하단 설명
        painter.setFont(QFont("Arial", 16))
        painter.setPen(QPen(QColor(170, 170, 170)))
        direction_text = self.current_direction
        if len(direction_text) > 20:
            direction_text = direction_text[:20] + "..."
        
        fm2 = painter.fontMetrics()
        text_width2 = fm2.width(direction_text)
        painter.drawText(center_x - text_width2//2, y + 35, direction_text)
        
        painter.restore()

    def draw_speed_and_progress(self, painter, center_x, y):
        """속도 및 진행률"""
        painter.save()
        
        # === 좌측: 속도 ===
        speed_rect = QRectF(center_x - 150, y - 30, 100, 60)
        painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
        painter.setPen(QPen(QColor(0, 170, 255), 2))
        painter.drawRoundedRect(speed_rect, 10, 10)
        
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.setPen(QPen(QColor(0, 170, 255)))
        painter.drawText(speed_rect, Qt.AlignCenter, f"{self.speed}")
        
        painter.setFont(QFont("Arial", 12))
        painter.setPen(QPen(QColor(170, 170, 170)))
        painter.drawText(center_x - 140, y + 50, "km/h")
        
        # === 우측: 진행률 ===
        progress_rect = QRectF(center_x + 50, y - 30, 100, 60)
        painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
        painter.setPen(QPen(QColor(255, 170, 0), 2))
        painter.drawRoundedRect(progress_rect, 10, 10)
        
        painter.setFont(QFont("Arial", 20, QFont.Bold))
        painter.setPen(QPen(QColor(255, 170, 0)))
        painter.drawText(progress_rect, Qt.AlignCenter, f"{self.progress:.0f}%")
        
        painter.setFont(QFont("Arial", 12))
        painter.setPen(QPen(QColor(170, 170, 170)))
        painter.drawText(center_x + 80, y + 50, "완료")
        
        painter.restore()

    def draw_next_instruction(self, painter, center_x, y):
        """다음 지시사항 미리보기 - 픽토그램 포함"""
        if not self.next_direction:
            return
            
        painter.save()
        
        # 배경
        bg_rect = QRectF(center_x - 180, y - 35, 360, 70)
        painter.setBrush(QBrush(QColor(20, 20, 20, 150)))
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.drawRoundedRect(bg_rect, 12, 12)
        
        # "다음" 라벨
        painter.setFont(QFont("Arial", 12))
        painter.setPen(QPen(QColor(120, 120, 120)))
        painter.drawText(center_x - 170, y - 15, "다음")
        
        # 다음 방향 픽토그램 (작은 버전)
        icon_x = center_x - 100
        icon_y = y + 5
        icon_size = 25  # 메인 화살표보다 작게
        
        # 픽토그램 배경 원 (작은 버전)
        painter.setBrush(QBrush(QColor(30, 30, 30, 180)))
        painter.setPen(QPen(QColor(150, 150, 150), 2))
        painter.drawEllipse(icon_x - icon_size//2, icon_y - icon_size//2, icon_size, icon_size)
        
        # 다음 방향별 작은 픽토그램
        painter.setPen(QPen(QColor(170, 170, 170), 4))
        painter.setBrush(QBrush(QColor(170, 170, 170)))
        
        if "좌회전" in self.next_direction:
            self.draw_small_left_arrow(painter, icon_x, icon_y)
        elif "우회전" in self.next_direction:
            self.draw_small_right_arrow(painter, icon_x, icon_y)
        elif "목적지" in self.next_direction or "도착" in self.next_direction:
            self.draw_small_destination_flag(painter, icon_x, icon_y)
        else:
            self.draw_small_straight_arrow(painter, icon_x, icon_y)
        
        # 텍스트
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        painter.setPen(QPen(QColor(200, 200, 200)))
        text = self.next_direction
        if len(text) > 15:
            text = text[:15] + "..."
        painter.drawText(icon_x + 35, y + 8, text)
        
        painter.restore()

    def draw_small_left_arrow(self, painter, x, y):
        """작은 좌회전 화살표"""
        arrow = QPolygonF([
            QPointF(x - 12, y),
            QPointF(x - 4, y - 8),
            QPointF(x - 4, y - 4),
            QPointF(x + 8, y - 4),
            QPointF(x + 8, y + 4),
            QPointF(x - 4, y + 4),
            QPointF(x - 4, y + 8)
        ])
        painter.drawPolygon(arrow)

    def draw_small_right_arrow(self, painter, x, y):
        """작은 우회전 화살표"""
        arrow = QPolygonF([
            QPointF(x + 12, y),
            QPointF(x + 4, y - 8),
            QPointF(x + 4, y - 4),
            QPointF(x - 8, y - 4),
            QPointF(x - 8, y + 4),
            QPointF(x + 4, y + 4),
            QPointF(x + 4, y + 8)
        ])
        painter.drawPolygon(arrow)

    def draw_small_straight_arrow(self, painter, x, y):
        """작은 직진 화살표"""
        arrow = QPolygonF([
            QPointF(x, y - 12),
            QPointF(x - 6, y - 4),
            QPointF(x - 3, y - 4),
            QPointF(x - 3, y + 8),
            QPointF(x + 3, y + 8),
            QPointF(x + 3, y - 4),
            QPointF(x + 6, y - 4)
        ])
        painter.drawPolygon(arrow)

    def draw_small_destination_flag(self, painter, x, y):
        """작은 목적지 깃발"""
        # 깃발 기둥
        painter.setPen(QPen(QColor(255, 150, 150), 3))
        painter.drawLine(x - 8, y - 10, x - 8, y + 10)
        
        # 깃발
        flag = QPolygonF([
            QPointF(x - 8, y - 10),
            QPointF(x + 6, y - 6),
            QPointF(x + 6, y - 2),
            QPointF(x - 8, y - 6)
        ])
        painter.setBrush(QBrush(QColor(255, 150, 150)))
        painter.drawPolygon(flag)

    def draw_decorative_elements(self, painter, rect):
        """장식적 요소들"""
        painter.save()
        
        # 상단 바
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        gradient.setColorAt(0, QColor(0, 170, 255, 0))
        gradient.setColorAt(0.5, QColor(0, 170, 255, 150))
        gradient.setColorAt(1, QColor(0, 170, 255, 0))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 20, rect.width(), 4)
        
        # 하단 바
        painter.drawRect(0, rect.height() - 24, rect.width(), 4)
        
        # 코너 장식
        painter.setPen(QPen(QColor(0, 255, 170), 2))
        painter.setBrush(Qt.NoBrush)
        
        # 좌상단
        painter.drawArc(20, 20, 30, 30, 90*16, 90*16)
        # 우상단
        painter.drawArc(rect.width()-50, 20, 30, 30, 0*16, 90*16)
        # 좌하단
        painter.drawArc(20, rect.height()-50, 30, 30, 180*16, 90*16)
        # 우하단
        painter.drawArc(rect.width()-50, rect.height()-50, 30, 30, 270*16, 90*16)
        
        painter.restore()

    def update_navigation_info(self, instructions, current_speed=0, route_progress=0):

        self.speed = current_speed
        self.progress = route_progress

        if not instructions:
            self.current_direction = "경로를 생성하세요"
            self.current_distance  = 0.0
            self.next_direction    = ""
            self.update()
            return

        direction, distance = instructions[0]  # 바로 앞 단계(다음 이벤트)와까지의 거리

        # --- 턴/도착까지 먼 경우: 상단은 직진, 하단은 '다음 턴'을 필요하면 예고 ---
        if distance > 5:
            self.current_direction = "직진"
            self.current_distance  = distance
            # 50m 이내면 '다음' 미리보기로 다음 턴을 띄움
            if ("좌회전" in direction or "우회전" in direction or "목적지" in direction) and distance <= 50:
                self.next_direction = direction
            else:
                self.next_direction = ""
            self.update()
            return

        # --- 턴/도착 5m 이내: 상단은 해당 이벤트(좌/우/도착) ---
        self.current_direction = direction
        self.current_distance  = distance

        # '다음'은 현재 턴 이후의 **직진 구간**을 보여준다
        if len(instructions) > 1:
            next_dir, next_dist = instructions[1]
            # 다음 이벤트가 목적지면 '직진 N m 후 도착' 형태
            if "목적지" in next_dir:
                self.next_direction = f"직진 {int(round(next_dist))}m 후 도착"
            else:
                # 다음 이벤트(다음 턴) 전까지는 직진
                self.next_direction = f"직진 {int(round(next_dist))}m"
        else:
            self.next_direction = ""

        self.update()


# ===================================================================
# 자동차 아이템: QObject를 상속받아 시그널 사용이 가능하도록 수정
# ===================================================================
class CarItem(QGraphicsObject):
    positionChanged = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.car_shape = QPolygonF([
            QPointF(-15, -8), QPointF(15, -8), QPointF(15, 8),
            QPointF(10, 12), QPointF(-10, 12), QPointF(-15, 8)
        ])
        self._brush = QBrush(QColor(66, 135, 245))
        self._pen = QPen(Qt.white, 2)
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(100)

    def boundingRect(self):
        return self.car_shape.boundingRect()

    def paint(self, painter, option, widget):
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawPolygon(self.car_shape)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)
        return super().itemChange(change, value)

# ===================================================================
# 메인 UI: 주차장 지도 및 컨트롤
# ===================================================================
class ParkingLotUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH, DRAW_DOTS = 30, 10, 8, False
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("실내 주차장 UI (고급 HUD 네비게이션)")
        self.setGeometry(50, 50, 1700, 900)

        main_layout = QHBoxLayout(self)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.view.scale(0.5, 0.5); self.view.scale(1, -1); self.view.translate(0, -self.SCENE_H)

        self.le1 = QLineEdit(); self.le1.setPlaceholderText("예: 1300,925 (필수)")
        self.le2 = QLineEdit(); self.le2.setPlaceholderText("예: 1475,925 (선택)")
        self.le3 = QLineEdit(); self.le3.setPlaceholderText("예: 1475,1300 (선택)")
        self.btn_apply = QPushButton("경로 안내")
        self.btn_apply.clicked.connect(self.apply_route_from_inputs)

        row1 = QHBoxLayout(); row1.addWidget(QLabel("W1:")); row1.addWidget(self.le1)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("W2:")); row2.addWidget(self.le2)
        row3 = QHBoxLayout(); row3.addWidget(QLabel("W3:")); row3.addWidget(self.le3)
        controls = QHBoxLayout(); controls.addStretch(1); controls.addWidget(self.btn_apply)

        left_layout.addWidget(self.view)
        left_layout.addLayout(row1); left_layout.addLayout(row2); left_layout.addLayout(row3)
        left_layout.addLayout(controls)

        # 고급 HUD 위젯 사용
        self.hud = AdvancedHudWidget()
        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(self.hud, 1)

        self.layer_static = QGraphicsItemGroup(); self.layer_path = QGraphicsItemGroup()
        self.scene.addItem(self.layer_static); self.scene.addItem(self.layer_path)

        self.full_path_points = []
        self.snapped_waypoints = []
        self.current_path_segment_index = 0
        
        self.car = CarItem()
        self.car.positionChanged.connect(self.update_hud_from_car_position)
        self.scene.addItem(self.car)
        self.car.hide()

        self.build_static_layout()
        self.build_occupancy()
        
        # 초기 HUD 상태
        self.hud.update_navigation_info([])

    def add_block(self, x, y, w, h, color, label=""):
        r = QGraphicsRectItem(QRectF(x, y, w, h)); r.setBrush(QBrush(color)); r.setPen(QPen(Qt.black)); r.setParentItem(self.layer_static)
        if label: t = QGraphicsSimpleTextItem(label); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setPos(x+5, y+h-20); t.setParentItem(self.layer_static)
    def add_hatched(self, x, y, w, h, edge=QColor("black"), fill=QColor(220, 20, 60, 90)):
        r = QGraphicsRectItem(QRectF(x, y, w, h)); b = QBrush(fill); b.setStyle(Qt.BDiagPattern); r.setBrush(b); r.setPen(QPen(edge, 2)); r.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem("통행 불가"); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setPos(x+10, y+h-25); t.setParentItem(self.layer_static)
    def add_dot_label_static(self, p: QPointF, text: str, color=QColor("blue")):
        d = QGraphicsEllipseItem(p.x()-5, p.y()-5, 10, 10); d.setBrush(QBrush(color)); d.setPen(QPen(Qt.black)); d.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem(text); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setPos(p.x()-20, p.y()+20); t.setParentItem(self.layer_static)
    def build_static_layout(self):
        c_dis=QColor("#f4a261"); c_ele=QColor("#2a9d8f"); c_gen=QColor("#264653"); c_obs=QColor("#6c757d"); c_emp=QColor("#ced4da"); c_io=QColor("#e76f51")
        border=QGraphicsRectItem(0,0,self.SCENE_W,self.SCENE_H); border.setPen(QPen(QColor("black"),8)); border.setParentItem(self.layer_static)
        base=[(0,1600,300,400,c_dis,"장애인"),(300,1600,300,400,c_dis,"장애인"),(600,1600,200,400,c_gen,"일반"),(800,1600,200,400,c_gen,"일반"),(1000,1600,200,400,c_gen,"일반"),(1200,1600,200,400,c_ele,"전기차"),(1400,1600,200,400,c_ele,"전기차"),(1600,1600,400,400,c_emp,"빈기둥"),(550,1050,800,300,c_obs,"장애물"),(1600,400,400,400,c_emp,"빈기둥"),(0,0,400,400,c_io,"입출차"),]
        for x,y,w,h,c,l in base: self.add_block(x,y,w,h,c,l)
        for i in range(6): self.add_block(400+i*200,400,200,400,c_gen,"일반")
        for i in range(4): self.add_block(1600,800+i*200,400,200,c_gen,"일반")
        self.add_hatched(400,0,1600,400); self.add_dot_label_static(self.ENTRANCE,"입구",QColor("blue"))
    def build_occupancy(self):
        W, H, C = self.SCENE_W, self.SCENE_H, self.CELL; gx, gy = (W + C - 1) // C, (H + C - 1) // C
        self.grid_w, self.grid_h = gx, gy; self.occ = bytearray(gx * gy)
        def idx(cx, cy): return cy * gx + cx
        def block_rect(x, y, w, h):
            x0, y0 = max(0, x - self.MARGIN), max(0, y - self.MARGIN); x1, y1 = min(W, x + w + self.MARGIN), min(H, y + h + self.MARGIN)
            cx0, cy0 = int(x0 // C), int(y0 // C); cx1, cy1 = int((x1 - 1) // C), int((y1 - 1) // C)
            cx0 = max(0, min(cx0, gx - 1)); cx1 = max(0, min(cx1, gx - 1)); cy0 = max(0, min(cy0, gy - 1)); cy1 = max(0, min(cy1, gy - 1))
            for cy in range(cy0, cy1 + 1):
                base = cy * gx
                for cx in range(cx0, cx1 + 1): self.occ[base + cx] = 1
        block_rect(550,1050,800,300); block_rect(400,0,1600,400); block_rect(1600,400,400,400); block_rect(1600,1600,400,400); block_rect(0,1600,300,400); block_rect(300,1600,300,400)
        for i in range(6): block_rect(400 + i*200, 400, 200, 400)
        for i in range(4): block_rect(1600, 800 + i*200, 400, 200)
        block_rect(600,1600,200,400); block_rect(800,1600,200,400); block_rect(1000,1600,200,400); block_rect(1200,1600,200,400); block_rect(1400,1600,200,400)
        self._occ_idx = idx

    def clamp_point(self, p: QPointF): return QPointF(min(self.SCENE_W - 1.0, max(0.0, p.x())), min(self.SCENE_H - 1.0, max(0.0, p.y())))
    def pt_to_cell(self, p: QPointF): cx = int(p.x() // self.CELL); cy = int(p.y() // self.CELL); return max(0, min(cx, self.grid_w - 1)), max(0, min(cy, self.grid_h - 1))
    def cell_to_pt_center(self, c): cx, cy = c; return QPointF(cx * self.CELL + self.CELL / 2.0, cy * self.CELL + self.CELL / 2.0)
    def is_cell_free(self, cx, cy):
        if not (0 <= cx < self.grid_w and 0 <= cy < self.grid_h): return False
        return self.occ[self._occ_idx(cx, cy)] == 0
    def find_nearest_free_cell_from_point(self, p: QPointF, max_radius_cells=30):
        sx, sy = self.pt_to_cell(p)
        if self.is_cell_free(sx, sy): return self.cell_to_pt_center((sx, sy))
        for r in range(1, max_radius_cells + 1):
            for dx in range(-r, r + 1):
                for dy in (-r, r):
                    if self.is_cell_free(sx + dx, sy + dy): return self.cell_to_pt_center((sx + dx, sy + dy))
            for dy in range(-r + 1, r):
                for dx in (-r, r):
                    if self.is_cell_free(sx + dx, sy + dy): return self.cell_to_pt_center((sx + dx, sy + dy))
        return self.cell_to_pt_center((sx, sy))
    def astar(self, start_pt: QPointF, goal_pt: QPointF):
        sx, sy = self.pt_to_cell(start_pt); gx, gy = self.pt_to_cell(goal_pt)
        W, H = self.grid_w, self.grid_h; occ, idx = self.occ, self._occ_idx
        def inb(x, y): return 0 <= x < W and 0 <= y < H
        if not inb(sx, sy) or not inb(gx, gy) or occ[idx(sx, sy)] or occ[idx(gx, gy)]: return None
        nbr = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)]; heur = lambda x, y: abs(x - gx) + abs(y - gy)
        openh = []; heappush(openh, (heur(sx, sy), 0, (sx, sy))); came = {}; g = {(sx, sy): 0}
        while openh:
            _, gc, (x, y) = heappop(openh)
            if (x, y) == (gx, gy):
                path = []; curr = (x, y)
                while curr in came: path.append(curr); curr = came[curr]
                path.append((sx, sy)); path.reverse(); return path
            for dx, dy, cst in nbr:
                nx, ny = x + dx, y + dy
                if not inb(nx, ny) or occ[idx(nx, ny)]: continue
                ng = gc + cst
                if (nx, ny) not in g or ng < g[(nx, ny)]: g[(nx, ny)] = ng; came[(nx, ny)] = (x, y); heappush(openh, (ng + heur(nx, ny), ng, (nx, ny)))
        return None

    def simplify_cells(self, cells):
        if not cells: return []
        simp = [cells[0]]; norm = lambda vx, vy: ((0 if vx == 0 else (1 if vx > 0 else -1)), (0 if vy == 0 else (1 if vy > 0 else -1)))
        for i in range(1, len(cells) - 1):
            x0, y0 = simp[-1]; x1, y1 = cells[i]; x2, y2 = cells[i+1]
            if norm(x1 - x0, y1 - y0) == norm(x2 - x1, y2 - y1): continue
            simp.append(cells[i])
        if len(cells) > 1 and cells[-1] != simp[-1]: simp.append(cells[-1])
        return simp

    def draw_smooth_path(self, pts):
        if len(pts) < 2: return
        path = QPainterPath(); path.moveTo(pts[0])
        if len(pts) == 2: path.lineTo(pts[1])
        else:
            t = 0.35; m1 = QPointF((pts[0].x() + pts[1].x()) / 2, (pts[0].y() + pts[1].y()) / 2); path.lineTo(m1)
            for i in range(1, len(pts) - 1):
                p0, p1, p2 = pts[i-1], pts[i], pts[i+1]
                m_in = QPointF(p1.x() + (p0.x() - p1.x()) * t, p1.y() + (p0.y() - p1.y()) * t)
                m_out = QPointF(p1.x() + (p2.x() - p1.x()) * t, p1.y() + (p2.y() - p1.y()) * t)
                path.lineTo(m_in); path.quadTo(p1, m_out)
            path.lineTo(pts[-1])
        item = self.scene.addPath(path, QPen(QColor(255, 77, 77, 220), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); item.setParentItem(self.layer_path)

    def generate_hud_instructions(self, pts):
        if len(pts) < 2: return []
        instructions = []; total_distance = 0
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i+1]
            dist_meters = sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2) / self.PIXELS_PER_METER
            total_distance += dist_meters
            if i < len(pts) - 2:
                p3 = pts[i+2]
                angle1 = degrees(atan2(p2.y() - p1.y(), p2.x() - p1.x())); angle2 = degrees(atan2(p3.y() - p2.y(), p3.x() - p2.x()))
                turn_angle = (angle2 - angle1 + 180) % 360 - 180
                direction = ""
                if turn_angle > 45: direction = "좌회전"
                elif turn_angle < -45: direction = "우회전"
                if direction: instructions.append((direction, total_distance)); total_distance = 0
        instructions.append(("목적지 도착", total_distance))
        return instructions

    def calculate_route_progress(self, car_pos):
        """전체 경로 대비 현재 진행률 정확히 계산"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return 0
        
        # 전체 경로 길이 계산
        total_length = 0
        for i in range(len(self.full_path_points) - 1):
            p1, p2 = self.full_path_points[i], self.full_path_points[i + 1]
            total_length += sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
        
        if total_length == 0:
            return 0
        
        # 현재 위치에서 가장 가까운 경로상의 점과 구간 찾기
        min_dist = float('inf')
        closest_segment = 0
        projection_ratio = 0
        
        for i in range(len(self.full_path_points) - 1):
            p1 = self.full_path_points[i]
            p2 = self.full_path_points[i + 1]
            
            # 벡터 계산
            segment_vec = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
            car_vec = QPointF(car_pos.x() - p1.x(), car_pos.y() - p1.y())
            
            segment_length_sq = segment_vec.x()**2 + segment_vec.y()**2
            
            if segment_length_sq == 0:
                continue
            
            # 투영 비율 계산 (0~1 사이로 클램핑)
            t = max(0, min(1, (car_vec.x() * segment_vec.x() + car_vec.y() * segment_vec.y()) / segment_length_sq))
            
            # 투영된 점
            projection = QPointF(p1.x() + t * segment_vec.x(), p1.y() + t * segment_vec.y())
            
            # 자동차와 투영점 사이의 거리
            dist = sqrt((car_pos.x() - projection.x())**2 + (car_pos.y() - projection.y())**2)
            
            if dist < min_dist:
                min_dist = dist
                closest_segment = i
                projection_ratio = t
        
        # 시작점부터 현재 위치까지의 거리 계산
        traveled_length = 0
        
        # 현재 구간 이전의 모든 구간 길이 합산
        for i in range(closest_segment):
            p1, p2 = self.full_path_points[i], self.full_path_points[i + 1]
            traveled_length += sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
        
        # 현재 구간에서의 진행 거리 추가
        if closest_segment < len(self.full_path_points) - 1:
            p1, p2 = self.full_path_points[closest_segment], self.full_path_points[closest_segment + 1]
            segment_length = sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
            traveled_length += segment_length * projection_ratio
        
        progress = min(100, (traveled_length / total_length) * 100)
        return progress

    def clear_path_layer(self):
        for child in self.layer_path.childItems(): child.setParentItem(None); self.scene.removeItem(child)

    def parse_point(self, text: str):
        s = text.strip().replace('(', '').replace(')', '').replace(' ', '');
        if not s or ',' not in s: return None
        try: x, y = map(float, s.split(',', 1)); return self.clamp_point(QPointF(x, y))
        except ValueError: return None

    def apply_route_from_inputs(self):
        waypoints = [p for p in [self.parse_point(le.text()) for le in [self.le1, self.le2, self.le3]] if p]
        if not waypoints:
            QMessageBox.warning(self, "입력 오류", "최소 1개의 웨이포인트를 입력하세요."); return

        self.snapped_waypoints = [self.find_nearest_free_cell_from_point(p) for p in waypoints]
        segments = []; prev = self.ENTRANCE
        for goal in self.snapped_waypoints:
            c = self.astar(prev, goal)
            if not c: QMessageBox.warning(self, "경로 실패", f"{prev} → {goal} 경로를 찾을 수 없습니다."); return
            segments.append(c); prev = goal

        whole = [];
        for i, seg in enumerate(segments): whole.extend(seg if i == 0 else seg[1:])
        
        self.full_path_points = [self.cell_to_pt_center(c) for c in self.simplify_cells(whole)]
        if not self.full_path_points: return

        self.full_path_points[0] = self.ENTRANCE; self.full_path_points[-1] = self.snapped_waypoints[-1]
        
        self.clear_path_layer()
        self.draw_smooth_path(self.full_path_points)
        for i, p in enumerate(self.snapped_waypoints, start=1):
            t = QGraphicsSimpleTextItem(f"W{i}"); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setPos(p.x()-6, p.y()+10); t.setBrush(QColor(30,30,30)); t.setParentItem(self.layer_path)

        # 경로 생성 후 상태 초기화
        self.current_path_segment_index = 0
        self.car.setPos(self.ENTRANCE)
        self.car.show()
        self.update_hud_from_car_position(self.ENTRANCE)
        self.btn_apply.setText("경로 재설정")

    def _update_current_segment(self, car_pos):
        """차량의 위치를 기반으로 현재 주행 중인 경로의 구간을 업데이트합니다."""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return

        # 차량이 마지막 구간을 넘어가지 않도록 반복 범위를 제한합니다.
        while self.current_path_segment_index < len(self.full_path_points) - 2:
            p1 = self.full_path_points[self.current_path_segment_index]
            p2 = self.full_path_points[self.current_path_segment_index + 1]

            v = p2 - p1
            if v.x() == 0 and v.y() == 0:
                self.current_path_segment_index += 1
                continue

            w = car_pos - p1
            dot_product = QPointF.dotProduct(w, v)
            length_sq = v.x()**2 + v.y()**2
            t = dot_product / length_sq

            if t > 1:
                # 투영된 위치가 현재 구간의 끝점을 넘었으므로 다음 구간으로 이동합니다.
                self.current_path_segment_index += 1
            else:
                # 차량이 현재 구간 내에 있으므로 루프를 중단합니다.
                break

    def update_hud_from_car_position(self, car_pos):
        """차량의 위치가 변경될 때마다 호출되어 HUD를 업데이트합니다."""
        if not self.full_path_points:
            return

        # 1. 차량의 현재 주행 구간을 갱신합니다.
        self._update_current_segment(car_pos)

        # 2. 현재 위치부터 남은 경로 노드들을 가져옵니다.
        remaining_turn_points = self.full_path_points[self.current_path_segment_index + 1:]
        
        # 3. HUD 안내 생성을 위해 경로의 시작점으로 현재 차량 위치를 추가합니다.
        path_for_hud = [car_pos] + remaining_turn_points
        
        if len(path_for_hud) < 2:
            # 목적지 도착
            self.hud.update_navigation_info([("목적지 도착", 0)], 
                                           current_speed=0, 
                                           route_progress=100)
            return
            
        # 4. 생성된 경로를 기반으로 HUD 안내를 생성합니다.
        instructions = self.generate_hud_instructions(path_for_hud)
        
        # 5. 진행률과 속도 계산
        progress = self.calculate_route_progress(car_pos)
        
        # 속도는 임의로 설정 (실제로는 이동 거리/시간으로 계산 가능)
        speed = min(60, int(progress * 0.6 + 10))  # 10~70 km/h 범위
        
        # 6. 고급 HUD 업데이트
        self.hud.update_navigation_info(instructions, 
                                       current_speed=speed, 
                                       route_progress=progress)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = ParkingLotUI()
    ui.show()
    sys.exit(app.exec_())
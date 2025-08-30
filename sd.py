import sys
from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QLineEdit, QLabel, QMessageBox, QGraphicsItemGroup, QFrame, QGraphicsObject
)
from PyQt5.QtGui import (
    QBrush, QPainter, QPen, QColor, QPainterPath, QFont, QPolygonF,
    QLinearGradient, QRadialGradient, QConicalGradient
)
from PyQt5.QtCore import (
    Qt, QPointF, QRectF, pyqtSignal, QPropertyAnimation, QEasingCurve,
    pyqtProperty, QObject
)

# ===================================================================
# 현대차 스타일 컬러 팔레트
# ===================================================================
HYUNDAI_COLORS = {
    'primary': '#002C5F',
    'secondary': '#007FA3',
    'accent': '#00AAD2',
    'glow': '#00DFFF',
    'success': '#00C851',
    'warning': '#FFB300',
    'background': '#0A0E1A',
    'surface': '#1A1E2E',
    'text_primary': '#FFFFFF',
    'text_secondary': '#B0BEC5',
    'glass': 'rgba(26, 30, 46, 0.7)'
}

# ===================================================================
# 애니메이션 상태 관리를 위한 QObject
# ===================================================================
class HudAnimationState(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._distance = 0.0
        self._rotation = 0.0
        self._progress = 0.0
        self._speed = 0.0
        self._color_factor = 0.0

    @pyqtProperty(float)
    def distance(self): return self._distance
    @distance.setter
    def distance(self, value): self._distance = value; self.parent().update()

    @pyqtProperty(float)
    def rotation(self): return self._rotation
    @rotation.setter
    def rotation(self, value): self._rotation = value; self.parent().update()

    @pyqtProperty(float)
    def progress(self): return self._progress
    @progress.setter
    def progress(self, value): self._progress = value; self.parent().update()

    @pyqtProperty(float)
    def speed(self): return self._speed
    @speed.setter
    def speed(self, value): self._speed = value; self.parent().update()

    @pyqtProperty(float)
    def color_factor(self): return self._color_factor
    @color_factor.setter
    def color_factor(self, value): self._color_factor = value; self.parent().update()

# ===================================================================
# 고급 HUD 위젯: 현대차 스타일 네비게이션 (애니메이션 적용)
# ===================================================================
class AdvancedHudWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumSize(400, 600)
        self.setStyleSheet("background-color: transparent; border: none;")

        self.anim_state = HudAnimationState(self)
        self.setup_animations()

        self.current_direction_type = "straight"
        self.current_direction_text = "경로를 생성하세요"
        self.next_direction_text = ""
        self.target_distance = 0.0
        self.arrow_base_rotation = 0.0

    def setup_animations(self):
        self.dist_anim = QPropertyAnimation(self.anim_state, b'distance', self)
        self.dist_anim.setDuration(500)
        self.dist_anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.rot_anim = QPropertyAnimation(self.anim_state, b'rotation', self)
        self.rot_anim.setDuration(700)
        self.rot_anim.setEasingCurve(QEasingCurve.InOutBack)
        self.rot_anim.finished.connect(self.update_base_rotation)

        self.prog_anim = QPropertyAnimation(self.anim_state, b'progress', self)
        self.prog_anim.setDuration(500)
        self.prog_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.speed_anim = QPropertyAnimation(self.anim_state, b'speed', self)
        self.speed_anim.setDuration(500)
        self.speed_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.color_anim = QPropertyAnimation(self.anim_state, b'color_factor', self)
        self.color_anim.setDuration(400)
        self.color_anim.setEasingCurve(QEasingCurve.InOutQuad)

    def update_base_rotation(self):
        self.arrow_base_rotation = self.anim_state.rotation

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        center_x = rect.width() / 2

        self.draw_background(painter, rect)
        self.draw_direction_arrow(painter, center_x, 120)
        self.draw_distance_info(painter, center_x, 280)
        self.draw_speed_and_progress(painter, center_x, 420)
        self.draw_next_instruction(painter, center_x, 520)

    def draw_background(self, painter, rect):
        painter.save()
        bg_gradient = QLinearGradient(0, 0, 0, rect.height())
        bg_gradient.setColorAt(0, QColor(HYUNDAI_COLORS['surface']))
        bg_gradient.setColorAt(1, QColor(HYUNDAI_COLORS['background']))
        painter.setBrush(bg_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 20, 20)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['accent']).lighter(120), 2))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 20, 20)
        painter.restore()

    def get_arrow_path(self, direction_type):
        path = QPainterPath()
        if direction_type == "left":
            path.moveTo(-35, 0); path.lineTo(-10, -25); path.lineTo(-10, -12)
            path.lineTo(25, -12); path.lineTo(25, 12); path.lineTo(-10, 12)
            path.lineTo(-10, 25); path.closeSubpath()
        elif direction_type == "right":
            path.moveTo(35, 0); path.lineTo(10, -25); path.lineTo(10, -12)
            path.lineTo(-25, -12); path.lineTo(-25, 12); path.lineTo(10, 12)
            path.lineTo(10, 25); path.closeSubpath()
        elif direction_type == "dest":
            path.addRect(-2, -30, 4, 60)
            path.moveTo(-2, -30)
            path.cubicTo(15, -25, 15, -10, -2, -5)
        else: # straight
            path.moveTo(0, -35); path.lineTo(-18, -12); path.lineTo(-10, -12)
            path.lineTo(-10, 25); path.lineTo(10, 25); path.lineTo(10, -12)
            path.lineTo(18, -12); path.closeSubpath()
        return path

    def draw_direction_arrow(self, painter, center_x, y):
        painter.save()
        painter.translate(center_x, y)
        painter.rotate(self.anim_state.rotation)

        f = self.anim_state.color_factor
        c1 = QColor.fromRgbF(
            (1-f)*QColor(HYUNDAI_COLORS['accent']).redF() + f*QColor(HYUNDAI_COLORS['warning']).redF(),
            (1-f)*QColor(HYUNDAI_COLORS['accent']).greenF() + f*QColor(HYUNDAI_COLORS['warning']).greenF(),
            (1-f)*QColor(HYUNDAI_COLORS['accent']).blueF() + f*QColor(HYUNDAI_COLORS['warning']).blueF()
        )
        c2 = c1.darker(250)

        radius = 70
        gradient = QRadialGradient(0, 0, radius)
        gradient.setColorAt(0, c1.lighter(120)); gradient.setColorAt(0.8, c1); gradient.setColorAt(1, c2)
        painter.setBrush(gradient)
        painter.setPen(QPen(c1.lighter(150), 2))
        painter.drawEllipse(QPointF(0, 0), radius, radius)

        arrow_path = self.get_arrow_path(self.current_direction_type)
        painter.setPen(Qt.NoPen); painter.setBrush(Qt.white)
        painter.drawPath(arrow_path)
        painter.restore()

    def draw_distance_info(self, painter, center_x, y):
        painter.save()
        dist = self.anim_state.distance
        distance_text = f"{dist:.0f}m" if dist < 1000 else f"{dist/1000:.1f}km"
        
        painter.setFont(QFont("Malgun Gothic", 50, QFont.Bold))
        painter.setPen(QColor(HYUNDAI_COLORS['text_primary']))
        painter.drawText(QRectF(0, y - 40, self.width(), 60), Qt.AlignCenter, distance_text)

        painter.setFont(QFont("Malgun Gothic", 16, QFont.Normal))
        painter.setPen(QColor(HYUNDAI_COLORS['text_secondary']))
        painter.drawText(QRectF(0, y + 20, self.width(), 30), Qt.AlignCenter, self.current_direction_text)
        painter.restore()

    def draw_speed_and_progress(self, painter, center_x, y):
        painter.save()
        gauge_radius, pen_width = 55, 8
        
        # Speed Gauge
        painter.translate(center_x - 100, y)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['surface']), pen_width, cap=Qt.RoundCap))
        painter.drawArc(QRectF(-gauge_radius, -gauge_radius, gauge_radius*2, gauge_radius*2), -45 * 16, 270 * 16)
        
        speed_angle = self.anim_state.speed / 100 * 270
        gradient = QConicalGradient(0, 0, -90)
        gradient.setColorAt(0, QColor(HYUNDAI_COLORS['accent'])); gradient.setColorAt(0.75, QColor(HYUNDAI_COLORS['glow']))
        painter.setPen(QPen(QBrush(gradient), pen_width, cap=Qt.RoundCap))
        painter.drawArc(QRectF(-gauge_radius, -gauge_radius, gauge_radius*2, gauge_radius*2), 135 * 16, -int(speed_angle * 16))
        
        painter.setPen(QColor(HYUNDAI_COLORS['text_primary']))
        painter.setFont(QFont("Malgun Gothic", 24, QFont.Bold))
        painter.drawText(QRectF(-gauge_radius, -gauge_radius, gauge_radius*2, gauge_radius*2), Qt.AlignCenter, f"{self.anim_state.speed:.0f}")
        painter.setFont(QFont("Malgun Gothic", 12))
        painter.setPen(QColor(HYUNDAI_COLORS['text_secondary']))
        painter.drawText(QRectF(-gauge_radius, 20, gauge_radius*2, 20), Qt.AlignCenter, "km/h")
        
        # Progress Gauge
        painter.resetTransform()
        painter.translate(center_x + 100, y)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['surface']), pen_width, cap=Qt.RoundCap))
        painter.drawArc(QRectF(-gauge_radius, -gauge_radius, gauge_radius*2, gauge_radius*2), 0, 360 * 16)
        
        progress_angle = self.anim_state.progress / 100 * 360
        gradient2 = QConicalGradient(0, 0, -90)
        gradient2.setColorAt(0, QColor(HYUNDAI_COLORS['success'])); gradient2.setColorAt(0.5, QColor(HYUNDAI_COLORS['success']).lighter(120))
        painter.setPen(QPen(QBrush(gradient2), pen_width, cap=Qt.RoundCap))
        painter.drawArc(QRectF(-gauge_radius, -gauge_radius, gauge_radius*2, gauge_radius*2), 90 * 16, -int(progress_angle * 16))

        painter.setPen(QColor(HYUNDAI_COLORS['text_primary']))
        painter.setFont(QFont("Malgun Gothic", 24, QFont.Bold))
        painter.drawText(QRectF(-gauge_radius, -gauge_radius, gauge_radius*2, gauge_radius*2), Qt.AlignCenter, f"{self.anim_state.progress:.0f}%")
        painter.setFont(QFont("Malgun Gothic", 12))
        painter.setPen(QColor(HYUNDAI_COLORS['text_secondary']))
        painter.drawText(QRectF(-gauge_radius, 20, gauge_radius*2, 20), Qt.AlignCenter, "완료")
        
        painter.restore()

    def draw_next_instruction(self, painter, center_x, y):
        if not self.next_direction_text: return
        painter.save()
        bg_rect = QRectF(center_x - 180, y, 360, 60)
        painter.setBrush(QColor(HYUNDAI_COLORS['glass']))
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['accent']).darker(150), 1))
        painter.drawRoundedRect(bg_rect, 15, 15)
        painter.setFont(QFont("Malgun Gothic", 14, QFont.Bold))
        painter.setPen(QColor(HYUNDAI_COLORS['text_secondary']))
        painter.drawText(bg_rect, Qt.AlignCenter, f"다음: {self.next_direction_text}")
        painter.restore()

    def update_navigation_info(self, instructions, current_speed=0, route_progress=0):
        if not instructions:
            direction_text, distance, new_direction_type, next_direction_text = "경로를 생성하세요", 0, "straight", ""
        else:
            direction_text, distance = instructions[0]
            if "좌회전" in direction_text: new_direction_type = "left"
            elif "우회전" in direction_text: new_direction_type = "right"
            elif "목적지" in direction_text: new_direction_type = "dest"
            else: new_direction_type = "straight"
            
            next_direction_text = instructions[1][0] if len(instructions) > 1 else "목적지"

        self.target_distance = distance
        self.current_direction_text = direction_text
        self.next_direction_text = next_direction_text

        if self.current_direction_type != new_direction_type:
            self.current_direction_type = new_direction_type
            target_rotation = self.arrow_base_rotation
            if new_direction_type == "left": target_rotation -= 90
            elif new_direction_type == "right": target_rotation += 90
            
            self.rot_anim.setStartValue(self.anim_state.rotation)
            self.rot_anim.setEndValue(target_rotation)
            self.rot_anim.start()

        self.dist_anim.setStartValue(self.anim_state.distance); self.dist_anim.setEndValue(self.target_distance); self.dist_anim.start()
        self.prog_anim.setStartValue(self.anim_state.progress); self.prog_anim.setEndValue(route_progress); self.prog_anim.start()
        self.speed_anim.setStartValue(self.anim_state.speed); self.speed_anim.setEndValue(current_speed); self.speed_anim.start()
        
        is_warning = self.target_distance <= 10 and self.current_direction_type in ["left", "right", "dest"]
        self.color_anim.setStartValue(self.anim_state.color_factor); self.color_anim.setEndValue(1.0 if is_warning else 0.0); self.color_anim.start()

# ===================================================================
# 자동차 아이템
# ===================================================================
class CarItem(QGraphicsObject):
    positionChanged = pyqtSignal(QPointF)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.car_shape = QPolygonF([QPointF(-15, -8), QPointF(15, -8), QPointF(15, 8), QPointF(10, 12), QPointF(-10, 12), QPointF(-15, 8)])
        gradient = QLinearGradient(-15, -8, 15, 12)
        gradient.setColorAt(0, QColor(HYUNDAI_COLORS['accent'])); gradient.setColorAt(1, QColor(HYUNDAI_COLORS['primary']))
        self._brush = QBrush(gradient)
        self._pen = QPen(QColor(255, 255, 255), 3)
        self.setFlag(QGraphicsItem.ItemIsMovable); self.setFlag(QGraphicsItem.ItemSendsGeometryChanges); self.setZValue(100)
    def boundingRect(self): return self.car_shape.boundingRect()
    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing); painter.setBrush(self._brush); painter.setPen(self._pen); painter.drawPolygon(self.car_shape)
        painter.setPen(QPen(QColor(255, 255, 255), 2)); painter.drawLine(QPointF(0, -5), QPointF(0, 5)); painter.drawLine(QPointF(0, -5), QPointF(-3, -2)); painter.drawLine(QPointF(0, -5), QPointF(3, -2))
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged: self.positionChanged.emit(value)
        return super().itemChange(change, value)

# ===================================================================
# 메인 UI (UI 간소화 및 외부 제어 함수 추가)
# ===================================================================
class ParkingLotUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH = 30, 10, 8
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HYUNDAI SmartParking Navigation System")
        self.setGeometry(50, 50, 1700, 900)
        self.setStyleSheet(f"""
            QWidget {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HYUNDAI_COLORS['background']}, stop:1 {HYUNDAI_COLORS['surface']}); color: {HYUNDAI_COLORS['text_primary']}; font-family: 'Malgun Gothic'; }}
            QGraphicsView {{ border: 3px solid {HYUNDAI_COLORS['accent']}; border-radius: 15px; background: {HYUNDAI_COLORS['background']}; }}
        """)
        main_layout = QHBoxLayout(self)
        
        # 지도 뷰만 포함하는 왼쪽 패널
        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.scale(0.5, 0.5)
        self.view.scale(1, -1)
        self.view.translate(0, -self.SCENE_H)
        
        self.hud = AdvancedHudWidget()
        
        main_layout.addWidget(self.view, 3)
        main_layout.addWidget(self.hud, 1)

        self.layer_static = QGraphicsItemGroup(); self.layer_path = QGraphicsItemGroup()
        self.scene.addItem(self.layer_static); self.scene.addItem(self.layer_path)

        self.full_path_points = []; self.snapped_waypoints = []; self.current_path_segment_index = 0
        
        self.car = CarItem(); self.car.positionChanged.connect(self.update_hud_from_car_position); self.scene.addItem(self.car); self.car.hide()
        
        self.build_static_layout(); self.build_occupancy()
        s
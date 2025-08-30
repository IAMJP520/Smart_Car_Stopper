import sys
import socket
import json
import threading
from heapq import heappush, heappop
from math import sqrt, atan2, degrees, sin, cos, radians
import random
from datetime import datetime
from typing import List, Tuple, Optional

from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QLineEdit, QLabel, QMessageBox, QGraphicsItemGroup, QFrame, QGraphicsObject
)
from PyQt5.QtGui import (
    QBrush, QPainter, QPen, QColor, QPainterPath, QFont, QPolygonF,
    QLinearGradient, QRadialGradient, QTransform, QFontMetrics
)
from PyQt5.QtCore import (
    Qt, QPointF, QRectF, pyqtSignal, QTimer, QPropertyAnimation,
    pyqtProperty, QEasingCurve, QParallelAnimationGroup
)

# ===================================================================
# WiFi 통신 모듈 (WaypointReceiver)
# ===================================================================
class WaypointReceiver:
    """라즈베리파이로부터 waypoint를 수신하는 클래스"""

    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.waypoint_callback = None
        print(f"📡 Waypoint 수신기 초기화됨. 수신 대기 주소: {self.host}:{self.port}")

    def set_waypoint_callback(self, callback_function):
        """새 waypoint 수신 시 호출될 콜백 함수 설정"""
        self.waypoint_callback = callback_function

    def start_receiver(self):
        """waypoint 수신 서버 시작 (별도 스레드)"""
        def server_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind((self.host, self.port))
                self.server_socket.listen(5)
                print(f"✅ 서버가 {self.host}:{self.port}에서 대기 중...")
                self.running = True

                while self.running:
                    try:
                        client_socket, addr = self.server_socket.accept()
                        print(f"🔗 클라이언트 연결됨: {addr}")
                        self.handle_connection(client_socket)
                    except Exception as e:
                        if self.running:
                            print(f"❌ 연결 오류: {e}")
                        break
            except Exception as e:
                print(f"❌ 서버 시작 오류: {e}")

        threading.Thread(target=server_thread, daemon=True).start()

    def handle_connection(self, client_socket):
        """클라이언트 연결 처리"""
        try:
            while self.running:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                try:
                    message = json.loads(data)
                    self.process_waypoint_data(message)
                    response = {"status": "received", "timestamp": datetime.now().isoformat()}
                    client_socket.send(json.dumps(response).encode('utf--8'))
                except json.JSONDecodeError:
                    print(f"❌ 잘못된 JSON 데이터: {data}")
        except Exception as e:
            print(f"❌ 데이터 수신 오류: {e}")
        finally:
            client_socket.close()
            print("📱 클라이언트 연결 종료")

    def process_waypoint_data(self, data):
        """수신된 waypoint 데이터 처리"""
        if data.get('type') == 'waypoint_assignment':
            waypoints = data.get('waypoints', [])
            print(f"\n🎯 새로운 waypoint 수신: {waypoints}")
            if self.waypoint_callback:
                self.waypoint_callback(waypoints)
            print("=" * 50)

    def stop(self):
        """수신 서버 중지"""
        print("🛑 Waypoint 수신기를 종료합니다...")
        self.running = False
        if self.server_socket:
            try:
                # 소켓을 즉시 닫기 위해 shutdown 사용
                self.server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.server_socket.close()

# ===================================================================
# 현대차 스타일 컬러 팔레트 및 폰트
# ===================================================================
HYUNDAI_COLORS = {
    'primary': '#002C5F', 'secondary': "#0991B6", 'accent': '#00AAD2',
    'success': '#00C851', 'warning': '#FFB300', 'danger': '#FF4444',
    'background': '#0A0E1A', 'surface': '#1A1E2E', 'text_primary': '#FFFFFF',
    'text_secondary': '#B0BEC5', 'glass': 'rgba(255, 255, 255, 0.1)'
}
FONT_SIZES = {
    'hud_distance': 42, 'hud_direction': 12, 'hud_speed': 28, 'hud_speed_unit': 10,
    'hud_progress': 14, 'hud_next_label': 10, 'hud_next_direction': 14,
    'map_label': 10, 'map_io_label': 12, 'map_waypoint_label': 12,
    'controls_title': 16, 'controls_info': 12, 'controls_button': 16, 'msgbox_button': 10
}

# ===================================================================
# 애니메이션 HUD 위젯: 현대차 프리미엄 스타일 (기존 코드와 동일)
# ===================================================================
class PremiumHudWidget(QFrame):
    # ... (이전 코드의 PremiumHudWidget 클래스 내용 전체를 여기에 붙여넣으세요) ...
    # ... 내용이 길어 생략합니다. 제공된 원본 코드의 클래스를 그대로 사용하면 됩니다.
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumSize(450, 700)
        self.setStyleSheet(f"""
            PremiumHudWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {HYUNDAI_COLORS['background']},
                    stop:0.3 rgba(26, 30, 46, 240),
                    stop:0.7 rgba(10, 14, 26, 240),
                    stop:1 {HYUNDAI_COLORS['background']});
                border: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {HYUNDAI_COLORS['accent']},
                    stop:0.5 {HYUNDAI_COLORS['secondary']},
                    stop:1 {HYUNDAI_COLORS['accent']});
                border-radius: 25px;
            }}
        """)

        # 현재 지시사항 정보
        self.current_direction = "경로 설정 대기"
        self.current_distance = 0.0
        self.next_direction = ""
        self.speed = 0  # km/h
        self.progress = 0  # 0-100%

        # 애니메이션 변수들
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)  # 20 FPS

        self.rotation_angle = 0
        self.pulse_scale = 1.0
        self.pulse_growing = True
        self.glow_opacity = 0.3
        self.glow_increasing = True
        self.particle_positions = []
        self.init_particles()

        self.direction_transition = 0.0
        self.target_direction = "직진"
        self.previous_direction = "직진"

    def init_particles(self):
        """배경 파티클 초기화"""
        self.particle_positions = []
        for _ in range(15):
            self.particle_positions.append({
                'x': random.randint(0, 450),
                'y': random.randint(0, 700),
                'speed': random.uniform(0.5, 2.0),
                'size': random.randint(2, 4),
                'opacity': random.uniform(0.1, 0.3)
            })

    def update_animation(self):
        """애니메이션 업데이트"""
        self.rotation_angle = (self.rotation_angle + 2) % 360

        if self.pulse_growing:
            self.pulse_scale += 0.02
            if self.pulse_scale >= 1.2: self.pulse_growing = False
        else:
            self.pulse_scale -= 0.02
            if self.pulse_scale <= 1.0: self.pulse_growing = True

        if self.glow_increasing:
            self.glow_opacity += 0.03
            if self.glow_opacity >= 0.8: self.glow_increasing = False
        else:
            self.glow_opacity -= 0.03
            if self.glow_opacity <= 0.3: self.glow_increasing = True

        for particle in self.particle_positions:
            particle['y'] -= particle['speed']
            if particle['y'] < 0:
                particle['y'] = 700
                particle['x'] = random.randint(0, 450)

        if self.direction_transition < 1.0:
            self.direction_transition = min(1.0, self.direction_transition + 0.1)

        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = self.rect()
        center_x = rect.width() // 2

        self.draw_background_effects(painter, rect)
        self.draw_3d_direction_display(painter, center_x, 120)
        self.draw_distance_panel(painter, center_x, 280)
        self.draw_speed_gauge(painter, center_x, 400)
        self.draw_progress_bar(painter, center_x, 500)
        self.draw_next_instruction_card(painter, center_x, 580)
        self.draw_decorative_elements(painter, rect)

    def draw_background_effects(self, painter, rect):
        """프리미엄 배경 효과"""
        painter.save()
        for particle in self.particle_positions:
            color = QColor(0, 170, 210)
            color.setAlphaF(particle['opacity'])
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(particle['x'], particle['y']), particle['size'], particle['size'])

        painter.setPen(QPen(QColor(0, 170, 210, 15), 1))
        for x in range(0, rect.width(), 30): painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), 30): painter.drawLine(0, y, rect.width(), y)

        for corner_x, corner_y in [(0, 0), (rect.width(), 0), (0, rect.height()), (rect.width(), rect.height())]:
            gradient = QRadialGradient(corner_x, corner_y, 150)
            gradient.setColorAt(0, QColor(0, 170, 210, int(50 * self.glow_opacity)))
            gradient.setColorAt(1, QColor(0, 170, 210, 0))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(corner_x, corner_y), 150, 150)
        painter.restore()

    def draw_3d_direction_display(self, painter, center_x, y):
        """3D 스타일 방향 표시"""
        painter.save()
        painter.translate(center_x, y)
        painter.rotate(self.rotation_angle)

        gradient = QRadialGradient(0, 0, 90)
        gradient.setColorAt(0, QColor(0, 170, 210, 0))
        gradient.setColorAt(0.7, QColor(0, 170, 210, 50))
        gradient.setColorAt(1, QColor(0, 170, 210, 100))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(0, 200, 255, 150), 2))
        painter.drawEllipse(QPointF(0, 0), 85, 85)

        painter.rotate(-self.rotation_angle)
        painter.scale(self.pulse_scale, self.pulse_scale)

        is_warning = self.current_distance <= 5 and ("좌회전" in self.current_direction or "우회전" in self.current_direction or "목적지" in self.current_direction)
        if is_warning:
            gradient = QRadialGradient(0, 0, 70)
            gradient.setColorAt(0, QColor(255, 180, 0, 200))
            gradient.setColorAt(0.5, QColor(255, 140, 0, 150))
            gradient.setColorAt(1, QColor(255, 100, 0, 100))
            glow_color = QColor(255, 200, 50)
        else:
            gradient = QRadialGradient(0, 0, 70)
            gradient.setColorAt(0, QColor(0, 170, 210, 200))
            gradient.setColorAt(0.5, QColor(0, 127, 163, 150))
            gradient.setColorAt(1, QColor(0, 44, 95, 100))
            glow_color = QColor(0, 200, 255)

        painter.setPen(QPen(glow_color, 6))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPointF(0, 0), 65, 65)

        gradient_inner = QRadialGradient(0, 0, 45)
        gradient_inner.setColorAt(0, QColor(255, 255, 255, 40))
        gradient_inner.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(gradient_inner))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0, 0), 45, 45)

        painter.scale(1 / self.pulse_scale, 1 / self.pulse_scale)
        self.draw_3d_direction_icon(painter)
        painter.restore()

    def draw_3d_direction_icon(self, painter):
        """3D 스타일 방향 아이콘"""
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 80)))

        if self.current_distance <= 5:
            if "좌회전" in self.current_direction:
                painter.translate(3, 3)
                self.draw_3d_left_arrow(painter, 0, 0)
                painter.translate(-3, -3)
                gradient = QLinearGradient(-30, -20, 30, 20)
                gradient.setColorAt(0, QColor(255, 255, 255))
                gradient.setColorAt(1, QColor(200, 200, 200))
                painter.setBrush(QBrush(gradient))
                painter.setPen(QPen(QColor(255, 255, 255), 3))
                self.draw_3d_left_arrow(painter, 0, 0)
            elif "우회전" in self.current_direction:
                painter.translate(3, 3)
                self.draw_3d_right_arrow(painter, 0, 0)
                painter.translate(-3, -3)
                gradient = QLinearGradient(-30, -20, 30, 20)
                gradient.setColorAt(0, QColor(255, 255, 255))
                gradient.setColorAt(1, QColor(200, 200, 200))
                painter.setBrush(QBrush(gradient))
                painter.setPen(QPen(QColor(255, 255, 255), 3))
                self.draw_3d_right_arrow(painter, 0, 0)
            elif "목적지" in self.current_direction:
                self.draw_3d_destination_icon(painter, 0, 0)
            else:
                self.draw_3d_straight_arrow(painter, 0, 0)
        else:
            self.draw_3d_straight_arrow(painter, 0, 0)
        painter.restore()

    def draw_3d_left_arrow(self, painter, x, y):
        arrow = QPolygonF([QPointF(x - 35, y), QPointF(x - 15, y - 20), QPointF(x - 15, y - 10), QPointF(x + 20, y - 10), QPointF(x + 20, y + 10), QPointF(x - 15, y + 10), QPointF(x - 15, y + 20)])
        painter.drawPolygon(arrow)

    def draw_3d_right_arrow(self, painter, x, y):
        arrow = QPolygonF([QPointF(x + 35, y), QPointF(x + 15, y - 20), QPointF(x + 15, y - 10), QPointF(x - 20, y - 10), QPointF(x - 20, y + 10), QPointF(x + 15, y + 10), QPointF(x + 15, y + 20)])
        painter.drawPolygon(arrow)

    def draw_3d_straight_arrow(self, painter, x, y):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
        shadow = QPolygonF([QPointF(x + 3, y - 32), QPointF(x - 15, y - 7), QPointF(x - 7, y - 7), QPointF(x - 7, y + 28), QPointF(x + 13, y + 28), QPointF(x + 13, y - 7), QPointF(x + 21, y - 7)])
        painter.drawPolygon(shadow)
        gradient = QLinearGradient(x - 20, y - 35, x + 20, y + 25)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(0.5, QColor(240, 240, 240))
        gradient.setColorAt(1, QColor(200, 200, 200))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        arrow = QPolygonF([QPointF(x, y - 35), QPointF(x - 18, y - 10), QPointF(x - 10, y - 10), QPointF(x - 10, y + 25), QPointF(x + 10, y + 25), QPointF(x + 10, y - 10), QPointF(x + 18, y - 10)])
        painter.drawPolygon(arrow)

    def draw_3d_destination_icon(self, painter, x, y):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
        painter.drawEllipse(QPointF(x + 3, y + 3), 25, 25)
        gradient = QRadialGradient(x, y, 25)
        gradient.setColorAt(0, QColor(255, 100, 100))
        gradient.setColorAt(1, QColor(200, 50, 50))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255), 3))
        painter.drawEllipse(QPointF(x, y), 25, 25)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(x, y), 10, 10)
        painter.setPen(QPen(QColor(50, 200, 50), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(x - 8, y, x - 3, y + 5)
        painter.drawLine(x - 3, y + 5, x + 8, y - 6)

    def draw_distance_panel(self, painter, center_x, y):
        painter.save()
        panel_rect = QRectF(center_x - 150, y - 50, 300, 100)
        gradient = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomRight())
        gradient.setColorAt(0, QColor(26, 30, 46, 200))
        gradient.setColorAt(0.5, QColor(20, 24, 36, 180))
        gradient.setColorAt(1, QColor(10, 14, 26, 160))
        painter.setBrush(QBrush(gradient))
        pen_gradient = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomRight())
        pen_gradient.setColorAt(0, QColor(0, 170, 210, 150))
        pen_gradient.setColorAt(0.5, QColor(0, 200, 255, 200))
        pen_gradient.setColorAt(1, QColor(0, 170, 210, 150))
        painter.setPen(QPen(QBrush(pen_gradient), 2))
        painter.drawRoundedRect(panel_rect, 20, 20)

        distance_text = f"{self.current_distance:.0f}m"
        if self.current_distance >= 1000:
            distance_text = f"{self.current_distance/1000:.1f}km"

        font = QFont()
        font.setFamily("Segoe UI")
        font.setWeight(QFont.Bold)
        font.setPointSize(FONT_SIZES['hud_distance'])
        painter.setFont(font)

        if self.current_distance <= 5: text_color = QColor(255, 180, 0)
        elif self.current_distance <= 20: text_color = QColor(0, 255, 150)
        else: text_color = QColor(0, 200, 255)

        fm = painter.fontMetrics()
        text_width = fm.width(distance_text)
        painter.setPen(QPen(text_color))
        painter.drawText(center_x - text_width // 2, y + 15, distance_text)

        font.setFamily("Malgun Gothic")
        font.setWeight(QFont.Normal)
        font.setPointSize(FONT_SIZES['hud_direction'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(180, 190, 200)))
        direction_text = self.current_direction
        if len(direction_text) > 20: direction_text = direction_text[:20] + "..."
        fm2 = painter.fontMetrics()
        text_width2 = fm2.width(direction_text)
        painter.drawText(center_x - text_width2 // 2, y + 40, direction_text)
        painter.restore()

    def draw_speed_gauge(self, painter, center_x, y):
        painter.save()
        gauge_rect = QRectF(center_x - 80, y - 40, 160, 80)
        painter.setPen(QPen(QColor(0, 44, 95, 100), 8))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(gauge_rect, 0, 180 * 16)
        speed_angle = min(180, (self.speed / 100) * 180)
        gradient = QLinearGradient(gauge_rect.topLeft(), gauge_rect.topRight())
        gradient.setColorAt(0, QColor(0, 200, 255))
        gradient.setColorAt(0.5, QColor(0, 170, 210))
        gradient.setColorAt(1, QColor(0, 127, 163))
        painter.setPen(QPen(QBrush(gradient), 6))
        painter.drawArc(gauge_rect, 0, int(speed_angle * 16))

        font = QFont()
        font.setFamily("Segoe UI")
        font.setWeight(QFont.Bold)
        font.setPointSize(FONT_SIZES['hud_speed'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        speed_text = f"{self.speed}"
        fm = painter.fontMetrics()
        text_width = fm.width(speed_text)
        painter.drawText(center_x - text_width // 2, y + 10, speed_text)

        font.setFamily("Malgun Gothic")
        font.setPointSize(FONT_SIZES['hud_speed_unit'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(180, 190, 200)))
        painter.drawText(center_x - 15, y + 30, "km/h")
        painter.restore()

    def draw_progress_bar(self, painter, center_x, y):
        painter.save()
        bar_width, bar_height = 350, 12
        bar_rect = QRectF(center_x - bar_width // 2, y - bar_height // 2, bar_width, bar_height)
        painter.setBrush(QBrush(QColor(0, 44, 95, 100)))
        painter.setPen(QPen(QColor(0, 170, 210, 50), 1))
        painter.drawRoundedRect(bar_rect, 6, 6)

        if self.progress > 0:
            progress_width = (self.progress / 100) * bar_width
            progress_rect = QRectF(center_x - bar_width // 2, y - bar_height // 2, progress_width, bar_height)
            gradient = QLinearGradient(progress_rect.topLeft(), progress_rect.topRight())
            gradient.setColorAt(0, QColor(0, 200, 255))
            gradient.setColorAt(0.5, QColor(0, 170, 210))
            gradient.setColorAt(1, QColor(0, 255, 200))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(progress_rect, 6, 6)

        font = QFont()
        font.setFamily("Segoe UI")
        font.setWeight(QFont.Bold)
        font.setPointSize(FONT_SIZES['hud_progress'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        percent_text = f"{self.progress:.0f}%"
        fm = painter.fontMetrics()
        text_width = fm.width(percent_text)
        painter.drawText(center_x - text_width // 2, y + 35, percent_text)
        painter.restore()

    def draw_next_instruction_card(self, painter, center_x, y):
        if not self.next_direction: return
        painter.save()
        card_rect = QRectF(center_x - 200, y - 40, 400, 80)
        gradient = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
        gradient.setColorAt(0, QColor(26, 30, 46, 180))
        gradient.setColorAt(1, QColor(10, 14, 26, 140))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(0, 170, 210, 100), 2))
        painter.drawRoundedRect(card_rect, 20, 20)

        font = QFont()
        font.setFamily("Malgun Gothic")
        font.setWeight(QFont.Bold)
        font.setPointSize(FONT_SIZES['hud_next_label'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(0, 200, 255)))
        painter.drawText(center_x - 190, y - 15, "다음")

        icon_x, icon_y = center_x - 140, y + 10
        gradient_icon = QRadialGradient(icon_x, icon_y, 25)
        gradient_icon.setColorAt(0, QColor(0, 170, 210, 150))
        gradient_icon.setColorAt(1, QColor(0, 44, 95, 100))
        painter.setBrush(QBrush(gradient_icon))
        painter.setPen(QPen(QColor(0, 200, 255), 2))
        painter.drawEllipse(QPointF(icon_x, icon_y), 25, 25)
        painter.setPen(QPen(QColor(255, 255, 255), 3))
        painter.setBrush(QBrush(QColor(255, 255, 255)))

        if "좌회전" in self.next_direction: self.draw_mini_left_arrow(painter, icon_x, icon_y)
        elif "우회전" in self.next_direction: self.draw_mini_right_arrow(painter, icon_x, icon_y)
        elif "목적지" in self.next_direction or "도착" in self.next_direction: self.draw_mini_destination(painter, icon_x, icon_y)
        else: self.draw_mini_straight(painter, icon_x, icon_y)

        font.setPointSize(FONT_SIZES['hud_next_direction'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(220, 230, 240)))
        text = self.next_direction
        if len(text) > 20: text = text[:20] + "..."
        painter.drawText(icon_x + 50, icon_y + 5, text)
        painter.restore()

    def draw_mini_left_arrow(self, painter, x, y):
        arrow = QPolygonF([QPointF(x - 12, y), QPointF(x - 5, y - 7), QPointF(x - 5, y - 3), QPointF(x + 8, y - 3), QPointF(x + 8, y + 3), QPointF(x - 5, y + 3), QPointF(x - 5, y + 7)])
        painter.drawPolygon(arrow)

    def draw_mini_right_arrow(self, painter, x, y):
        arrow = QPolygonF([QPointF(x + 12, y), QPointF(x + 5, y - 7), QPointF(x + 5, y - 3), QPointF(x - 8, y - 3), QPointF(x - 8, y + 3), QPointF(x + 5, y + 3), QPointF(x + 5, y + 7)])
        painter.drawPolygon(arrow)

    def draw_mini_straight(self, painter, x, y):
        arrow = QPolygonF([QPointF(x, y - 12), QPointF(x - 6, y - 4), QPointF(x - 3, y - 4), QPointF(x - 3, y + 8), QPointF(x + 3, y + 8), QPointF(x + 3, y - 4), QPointF(x + 6, y - 4)])
        painter.drawPolygon(arrow)

    def draw_mini_destination(self, painter, x, y):
        painter.drawEllipse(QPointF(x, y), 8, 8)
        painter.setPen(QPen(QColor(50, 200, 50), 3))
        painter.drawLine(x - 5, y, x - 2, y + 3)
        painter.drawLine(x - 2, y + 3, x + 5, y - 4)

    def draw_decorative_elements(self, painter, rect):
        painter.save()
        gradient = QLinearGradient(0, 20, rect.width(), 20)
        gradient.setColorAt(0, QColor(0, 170, 210, 0))
        gradient.setColorAt(0.2, QColor(0, 170, 210, 100))
        gradient.setColorAt(0.5, QColor(0, 200, 255, 200))
        gradient.setColorAt(0.8, QColor(0, 170, 210, 100))
        gradient.setColorAt(1, QColor(0, 170, 210, 0))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 20, rect.width(), 4)
        painter.drawRect(0, rect.height() - 24, rect.width(), 4)
        corner_size = 30
        painter.setPen(QPen(QColor(0, 200, 255), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(15, 15, corner_size, corner_size, 90 * 16, 90 * 16)
        painter.drawArc(rect.width() - 45, 15, corner_size, corner_size, 0 * 16, 90 * 16)
        painter.drawArc(15, rect.height() - 45, corner_size, corner_size, 180 * 16, 90 * 16)
        painter.drawArc(rect.width() - 45, rect.height() - 45, corner_size, corner_size, 270 * 16, 90 * 16)
        painter.restore()

    def update_navigation_info(self, instructions, current_speed=0, route_progress=0):
        self.speed = current_speed
        self.progress = route_progress
        if not instructions:
            self.current_direction = "경로를 생성하세요"
            self.current_distance = 0.0
            self.next_direction = ""
            self.update()
            return

        direction, distance = instructions[0]
        new_direction = "직진" if distance > 5 else direction
        if new_direction != self.target_direction:
            self.previous_direction = self.target_direction
            self.target_direction = new_direction
            self.direction_transition = 0.0

        if distance > 5:
            self.current_direction = "직진"
            self.current_distance = distance
            self.next_direction = direction if ("좌회전" in direction or "우회전" in direction or "목적지" in direction) and distance <= 50 else ""
        else:
            self.current_direction = direction
            self.current_distance = distance
            if len(instructions) > 1:
                next_dir, next_dist = instructions[1]
                self.next_direction = f"직진 {int(round(next_dist))}m 후 도착" if "목적지" in next_dir else f"직진 {int(round(next_dist))}m"
            else:
                self.next_direction = ""
        self.update()
# ===================================================================
# 자동차 아이템: 현대차 스타일 (기존 코드와 동일)
# ===================================================================
class CarItem(QGraphicsObject):
    # ... (이전 코드의 CarItem 클래스 내용 전체를 여기에 붙여넣으세요) ...
    positionChanged = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.car_shape = QPolygonF([QPointF(-15, -8), QPointF(15, -8), QPointF(15, 8), QPointF(10, 12), QPointF(-10, 12), QPointF(-15, 8)])
        gradient = QLinearGradient(-15, -8, 15, 12)
        gradient.setColorAt(0, QColor(0, 170, 210))
        gradient.setColorAt(1, QColor(0, 44, 95))
        self._brush = QBrush(gradient)
        self._pen = QPen(QColor(255, 255, 255), 3)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(100)

    def boundingRect(self):
        return self.car_shape.boundingRect()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawPolygon(self.car_shape)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(QPointF(0, -5), QPointF(0, 5))
        painter.drawLine(QPointF(0, -5), QPointF(-3, -2))
        painter.drawLine(QPointF(0, -5), QPointF(3, -2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)
        return super().itemChange(change, value)
# ===================================================================
# 메인 UI: 현대차 스타일 주차장 지도 (WiFi 통합)
# ===================================================================
class ParkingLotUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH = 30, 10, 8
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)
    
    # WiFi 스레드 -> UI 스레드 통신을 위한 시그널
    newWaypointsReceived = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HYUNDAI SmartParking Navigation System (WiFi Ver.)")
        self.initial_fit = False
        self.received_waypoints = [] # 수신된 웨이포인트를 저장할 변수

        self.setup_styles()
        self.init_ui()
        self.init_map()
        self.init_wifi()

    def setup_styles(self):
        self.setStyleSheet(f"""
            QWidget {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HYUNDAI_COLORS['background']}, stop:1 {HYUNDAI_COLORS['surface']}); color: {HYUNDAI_COLORS['text_primary']}; font-family: 'Malgun Gothic'; }}
            QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HYUNDAI_COLORS['primary']}, stop:1 {HYUNDAI_COLORS['secondary']}); border: none; border-radius: 15px; color: white; font-size: {FONT_SIZES['controls_button']}pt; font-weight: bold; padding: 15px 30px; min-height: 20px; }}
            QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HYUNDAI_COLORS['accent']}, stop:1 {HYUNDAI_COLORS['secondary']}); }}
            QPushButton:disabled {{ background: {HYUNDAI_COLORS['surface']}; color: {HYUNDAI_COLORS['text_secondary']}; }}
            QLabel {{ color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold; margin: 10px; }}
            QGraphicsView {{ border: 3px solid {HYUNDAI_COLORS['accent']}; border-radius: 15px; background: {HYUNDAI_COLORS['background']}; }}
        """)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        left_panel = QWidget()
        left_panel.setStyleSheet("background: transparent; margin: 0px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(20)
        left_layout.setContentsMargins(10, 10, 10, 10)

        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.scale(1, -1)
        self.view.translate(0, -self.SCENE_H)

        controls_frame = QWidget()
        controls_frame.setStyleSheet(f"background: rgba(0,0,0,0.2); border: 1px solid {HYUNDAI_COLORS['accent']}; border-radius: 15px; padding: 15px;")
        controls_layout = QVBoxLayout(controls_frame)
        
        dest_info = QLabel("수신된 목적지:")
        dest_info.setStyleSheet(f"color: {HYUNDAI_COLORS['accent']}; font-size: {FONT_SIZES['controls_title']}pt;")
        self.main_dest_label = QLabel("주 목적지: 수신 대기 중...")
        self.main_dest_label.setStyleSheet(f"color: {HYUNDAI_COLORS['text_primary']}; font-size: {FONT_SIZES['controls_info']}pt;")
        self.waypoint1_label = QLabel("경유지 1: -")
        self.waypoint1_label.setStyleSheet(f"color: {HYUNDAI_COLORS['text_secondary']}; font-size: {FONT_SIZES['controls_info']-2}pt;")
        self.waypoint2_label = QLabel("경유지 2: -")
        self.waypoint2_label.setStyleSheet(f"color: {HYUNDAI_COLORS['text_secondary']}; font-size: {FONT_SIZES['controls_info']-2}pt;")
        
        self.btn_reset_route = QPushButton("경로 수신 대기 중")
        self.btn_reset_route.clicked.connect(self.calculate_and_display_route)
        self.btn_reset_route.setEnabled(False)
        
        controls_layout.addWidget(dest_info)
        controls_layout.addWidget(self.main_dest_label)
        controls_layout.addWidget(self.waypoint1_label)
        controls_layout.addWidget(self.waypoint2_label)
        controls_layout.addWidget(self.btn_reset_route)
        controls_layout.addStretch()

        left_layout.addWidget(self.view, 3)
        left_layout.addWidget(controls_frame, 1)

        self.hud = PremiumHudWidget()
        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(self.hud, 1)

    def init_map(self):
        self.layer_static = QGraphicsItemGroup()
        self.layer_path = QGraphicsItemGroup()
        self.scene.addItem(self.layer_static)
        self.scene.addItem(self.layer_path)

        self.full_path_points = []
        self.snapped_waypoints = []
        self.current_path_segment_index = 0
        
        self.car = CarItem()
        self.car.positionChanged.connect(self.update_hud_from_car_position)
        self.scene.addItem(self.car)
        self.car.hide()

        self.build_static_layout()
        self.build_occupancy()
        self.hud.update_navigation_info([])

    def init_wifi(self):
        self.newWaypointsReceived.connect(self.update_ui_with_waypoints)
        self.waypoint_receiver = WaypointReceiver()
        self.waypoint_receiver.set_waypoint_callback(self.handle_new_waypoints_from_thread)
        self.waypoint_receiver.start_receiver()
        QMessageBox.information(self, "WiFi 수신기", f"서버가 {self.waypoint_receiver.host}:{self.waypoint_receiver.port}에서 시작되었습니다.\n관제 시스템의 연결을 기다립니다.")

    def handle_new_waypoints_from_thread(self, waypoints):
        """(백그라운드 스레드에서 실행) UI 업데이트를 위해 메인 스레드로 시그널 전송"""
        self.newWaypointsReceived.emit(waypoints)

    def update_ui_with_waypoints(self, waypoints):
        """(메인 UI 스레드에서 실행) 수신된 데이터로 UI 업데이트 및 경로 생성"""
        if not waypoints or not isinstance(waypoints, list):
            QMessageBox.warning(self, "수신 오류", "잘못된 형식의 웨이포인트 데이터가 수신되었습니다.")
            return

        self.received_waypoints = waypoints
        QMessageBox.information(self, "경로 자동 설정", f"새로운 경로가 수신되었습니다:\n{waypoints}\n\n자동으로 경로 안내를 시작합니다.")

        # UI 라벨 업데이트
        self.main_dest_label.setText(f"주 목적지: {waypoints[-1]}")
        self.waypoint1_label.setText(f"경유지 1: {waypoints[0] if len(waypoints) > 1 else '-'}")
        self.waypoint2_label.setText(f"경유지 2: {waypoints[1] if len(waypoints) > 2 else '-'}")

        self.calculate_and_display_route()

        # 버튼 활성화 및 텍스트 변경
        self.btn_reset_route.setText("경로 재설정")
        self.btn_reset_route.setEnabled(True)

    def calculate_and_display_route(self):
        """저장된 웨이포인트를 기반으로 경로를 계산하고 지도에 표시"""
        if not self.received_waypoints:
            QMessageBox.warning(self, "경로 오류", "경로를 계산할 웨이포인트가 없습니다."); return

        waypoints_qpoints = [self.clamp_point(QPointF(p[0], p[1])) for p in self.received_waypoints]
        
        self.snapped_waypoints = [self.find_nearest_free_cell_from_point(p) for p in waypoints_qpoints]
        segments, prev = [], self.ENTRANCE
        for goal in self.snapped_waypoints:
            c = self.astar(prev, goal)
            if not c: QMessageBox.warning(self, "경로 실패", f"{prev} → {goal} 경로를 찾을 수 없습니다."); return
            segments.append(c); prev = goal
        
        whole = [c for i, seg in enumerate(segments) for c in (seg if i == 0 else seg[1:])]
        self.full_path_points = [self.cell_to_pt_center(c) for c in self.simplify_cells(whole)]
        if not self.full_path_points: return

        self.full_path_points[0], self.full_path_points[-1] = self.ENTRANCE, self.snapped_waypoints[-1]
        
        self.clear_path_layer()
        self.draw_straight_path(self.full_path_points)
        
        self.current_path_segment_index = 0
        self.car.setPos(self.ENTRANCE); self.car.show()
        self.update_hud_from_car_position(self.ENTRANCE)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.initial_fit:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.initial_fit = True
            
    def closeEvent(self, event):
        """어플리케이션 종료 시 WiFi 수신기 스레드를 정리"""
        self.waypoint_receiver.stop()
        super().closeEvent(event)

    # ... (add_block, build_static_layout, astar 등 나머지 헬퍼 함수들은 여기에 그대로 붙여넣으세요) ...
    # ... 내용이 길어 생략합니다. 제공된 원본 코드의 함수들을 그대로 사용하면 됩니다.
    def add_block(self, x, y, w, h, color, label=""):
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        if "장애인" in label:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(255, 180, 0, 200))
            gradient.setColorAt(1, QColor(255, 140, 0, 150))
            r.setBrush(QBrush(gradient))
        elif "전기차" in label:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(0, 200, 130, 200))
            gradient.setColorAt(1, QColor(0, 150, 100, 150))
            r.setBrush(QBrush(gradient))
        elif "일반" in label:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(0, 170, 210, 200))
            gradient.setColorAt(1, QColor(0, 44, 95, 150))
            r.setBrush(QBrush(gradient))
        else:
            r.setBrush(QBrush(color))
        r.setPen(QPen(QColor(255, 255, 255, 100), 2))
        r.setParentItem(self.layer_static)
        
        if label:
            t = QGraphicsSimpleTextItem(label)
            t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setBrush(QColor(255, 255, 255))
            font = QFont()
            font.setFamily("Malgun Gothic")
            font.setWeight(QFont.Bold)
            font.setPointSize(FONT_SIZES['map_label'])
            t.setFont(font)
            t.setPos(x + 5, y + h - 25)
            t.setParentItem(self.layer_static)

    def add_hatched(self, x, y, w, h, edge=QColor("black"), fill=QColor(220, 20, 60, 90)):
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        b = QBrush(fill)
        b.setStyle(Qt.BDiagPattern)
        r.setBrush(b)
        r.setPen(QPen(edge, 3))
        r.setParentItem(self.layer_static)
        
        t = QGraphicsSimpleTextItem("통행 불가")
        t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        t.setBrush(QColor(255, 100, 100))
        font = QFont()
        font.setFamily("Malgun Gothic")
        font.setWeight(QFont.Bold)
        font.setPointSize(FONT_SIZES['map_label'])
        t.setFont(font)
        t.setPos(x + 10, y + h - 30)
        t.setParentItem(self.layer_static)

    def add_dot_label_static(self, p: QPointF, text: str, color=QColor("blue")):
        d = QGraphicsEllipseItem(p.x() - 8, p.y() - 8, 16, 16)
        gradient = QLinearGradient(p.x() - 8, p.y() - 8, p.x() + 8, p.y() + 8)
        gradient.setColorAt(0, QColor(0, 170, 210))
        gradient.setColorAt(1, QColor(0, 44, 95))
        d.setBrush(QBrush(gradient))
        d.setPen(QPen(QColor(255, 255, 255), 3))
        d.setParentItem(self.layer_static)
        
        t = QGraphicsSimpleTextItem(text)
        t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        t.setBrush(QColor(0, 200, 255))
        font = QFont()
        font.setFamily("Malgun Gothic")
        font.setWeight(QFont.Bold)
        font.setPointSize(FONT_SIZES['map_io_label'])
        t.setFont(font)
        t.setPos(p.x() - 20, p.y() + 25)
        t.setParentItem(self.layer_static)

    def build_static_layout(self):
        c_dis, c_ele, c_gen, c_obs, c_emp, c_io = QColor(255, 179, 0), QColor(0, 200, 130), QColor(0, 170, 210), QColor(108, 117, 125), QColor(206, 212, 218), QColor(231, 111, 81)
        border = QGraphicsRectItem(0, 0, self.SCENE_W, self.SCENE_H)
        border.setPen(QPen(QColor(0, 170, 210), 12))
        border.setBrush(QBrush(Qt.NoBrush))
        border.setParentItem(self.layer_static)
        base = [(0, 1600, 300, 400, c_dis, "장애인"), (300, 1600, 300, 400, c_dis, "장애인"), (600, 1600, 200, 400, c_gen, "일반"), (800, 1600, 200, 400, c_gen, "일반"), (1000, 1600, 200, 400, c_gen, "일반"), (1200, 1600, 200, 400, c_ele, "전기차"), (1400, 1600, 200, 400, c_ele, "전기차"), (1600, 1600, 400, 400, c_emp, "빈기둥"), (550, 1050, 800, 300, c_obs, "장애물"), (1600, 400, 400, 400, c_emp, "빈기둥"), (0, 0, 400, 400, c_io, "입출차")]
        for x, y, w, h, c, l in base: self.add_block(x, y, w, h, c, l)
        for i in range(6): self.add_block(400 + i * 200, 400, 200, 400, c_gen, "일반")
        for i in range(4): self.add_block(1600, 800 + i * 200, 400, 200, c_gen, "일반")
        self.add_hatched(400, 0, 1600, 400)
        self.add_dot_label_static(self.ENTRANCE, "입구", QColor(0, 170, 210))

    def build_occupancy(self):
        W, H, C = self.SCENE_W, self.SCENE_H, self.CELL
        gx, gy = (W + C - 1) // C, (H + C - 1) // C
        self.grid_w, self.grid_h = gx, gy
        self.occ = bytearray(gx * gy)
        def idx(cx, cy): return cy * gx + cx
        def block_rect(x, y, w, h):
            x0, y0 = max(0, x - self.MARGIN), max(0, y - self.MARGIN)
            x1, y1 = min(W, x + w + self.MARGIN), min(H, y + h + self.MARGIN)
            cx0, cy0 = int(x0 // C), int(y0 // C)
            cx1, cy1 = int((x1 - 1) // C), int((y1 - 1) // C)
            for cy in range(cy0, cy1 + 1):
                for cx in range(cx0, cx1 + 1):
                    if 0 <= cx < gx and 0 <= cy < gy: self.occ[cy * gx + cx] = 1
        block_rect(550, 1050, 800, 300)
        block_rect(400, 0, 1600, 400)
        block_rect(1600, 400, 400, 400)
        block_rect(1600, 1600, 400, 400)
        block_rect(0, 1600, 300, 400)
        block_rect(300, 1600, 300, 400)
        for i in range(6): block_rect(400 + i * 200, 400, 200, 400)
        for i in range(4): block_rect(1600, 800 + i * 200, 400, 200)
        block_rect(600, 1600, 200, 400)
        block_rect(800, 1600, 200, 400)
        block_rect(1000, 1600, 200, 400)
        block_rect(1200, 1600, 200, 400)
        block_rect(1400, 1600, 200, 400)
        self._occ_idx = idx

    def clamp_point(self, p: QPointF):
        return QPointF(min(self.SCENE_W - 1.0, max(0.0, p.x())), min(self.SCENE_H - 1.0, max(0.0, p.y())))
    def pt_to_cell(self, p: QPointF):
        return int(p.x() // self.CELL), int(p.y() // self.CELL)
    def cell_to_pt_center(self, c):
        return QPointF(c[0] * self.CELL + self.CELL / 2.0, c[1] * self.CELL + self.CELL / 2.0)
    def is_cell_free(self, cx, cy):
        return 0 <= cx < self.grid_w and 0 <= cy < self.grid_h and self.occ[self._occ_idx(cx, cy)] == 0
    
    def find_nearest_free_cell_from_point(self, p: QPointF, max_radius_cells=30):
        sx, sy = self.pt_to_cell(p)
        if self.is_cell_free(sx, sy): return self.cell_to_pt_center((sx, sy))
        for r in range(1, max_radius_cells + 1):
            for dx in range(-r, r + 1):
                for dy in [-r, r]:
                    if self.is_cell_free(sx + dx, sy + dy): return self.cell_to_pt_center((sx + dx, sy + dy))
            for dy in range(-r + 1, r):
                for dx in [-r, r]:
                    if self.is_cell_free(sx + dx, sy + dy): return self.cell_to_pt_center((sx + dx, sy + dy))
        return self.cell_to_pt_center((sx, sy))

    def astar(self, start_pt: QPointF, goal_pt: QPointF):
        sx, sy = self.pt_to_cell(start_pt)
        gx, gy = self.pt_to_cell(goal_pt)
        W, H = self.grid_w, self.grid_h
        occ, idx = self.occ, self._occ_idx
        if not (0 <= sx < W and 0 <= sy < H and 0 <= gx < W and 0 <= gy < H) or occ[idx(sx, sy)] or occ[idx(gx, gy)]: return None
        openh = [(abs(sx - gx) + abs(sy - gy), 0, (sx, sy))]
        came, g = {}, {(sx, sy): 0}
        while openh:
            _, gc, (x, y) = heappop(openh)
            if (x, y) == (gx, gy):
                path = []
                curr = (x, y)
                while curr in came: path.append(curr); curr = came[curr]
                path.append((sx, sy)); path.reverse()
                return path
            for dx, dy, cst in [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)]:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < W and 0 <= ny < H) or occ[idx(nx, ny)]: continue
                ng = gc + cst
                if (nx, ny) not in g or ng < g[(nx, ny)]:
                    g[(nx, ny)] = ng; came[(nx, ny)] = (x, y); heappush(openh, (ng + abs(nx - gx) + abs(ny - gy), ng, (nx, ny)))
        return None

    def simplify_cells(self, cells):
        if not cells: return []
        simp = [cells[0]]
        norm = lambda vx, vy: ((0 if vx == 0 else (1 if vx > 0 else -1)), (0 if vy == 0 else (1 if vy > 0 else -1)))
        for i in range(1, len(cells) - 1):
            if norm(cells[i][0] - simp[-1][0], cells[i][1] - simp[-1][1]) == norm(cells[i + 1][0] - cells[i][0], cells[i + 1][1] - cells[i][1]): continue
            simp.append(cells[i])
        if len(cells) > 1 and cells[-1] != simp[-1]: simp.append(cells[-1])
        return simp

    def draw_straight_path(self, pts):
        """웨이포인트 간 직선으로 경로를 그립니다."""
        if len(pts) < 2: return
        
        # 글로우 효과를 위한 외곽선
        for i in range(len(pts) - 1):
            start, end = pts[i], pts[i + 1]
            
            # 가장 큰 글로우
            glow_pen = QPen(QColor(0, 170, 210, 60), self.PATH_WIDTH + 12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            glow_line = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), glow_pen)
            glow_line.setParentItem(self.layer_path)
            
            # 중간 글로우
            mid_glow_pen = QPen(QColor(0, 200, 255, 100), self.PATH_WIDTH + 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            mid_glow_line = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), mid_glow_pen)
            mid_glow_line.setParentItem(self.layer_path)
            
            # 메인 경로선
            main_pen = QPen(QColor(0, 200, 255), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            main_line = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), main_pen)
            main_line.setParentItem(self.layer_path)
            
            # 중앙 가이드선
            center_pen = QPen(QColor(255, 255, 255, 150), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            center_line = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), center_pen)
            center_line.setParentItem(self.layer_path)

    def generate_hud_instructions(self, pts):
        if len(pts) < 2: return []
        instructions, total_distance = [], 0
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i + 1]
            dist_meters = sqrt((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2) / self.PIXELS_PER_METER
            total_distance += dist_meters
            if i < len(pts) - 2:
                p3 = pts[i + 2]
                turn_angle = (degrees(atan2(p3.y() - p2.y(), p3.x() - p2.x())) - degrees(atan2(p2.y() - p1.y(), p2.x() - p1.x())) + 180) % 360 - 180
                direction = "좌회전" if turn_angle > 45 else ("우회전" if turn_angle < -45 else "")
                if direction: instructions.append((direction, total_distance)); total_distance = 0
        instructions.append(("목적지 도착", total_distance))
        return instructions

    def calculate_route_progress(self, car_pos):
        if not self.full_path_points or len(self.full_path_points) < 2: return 0
        total_length = sum(sqrt((self.full_path_points[i+1].x() - p.x())**2 + (self.full_path_points[i+1].y() - p.y())**2) for i, p in enumerate(self.full_path_points[:-1]))
        if total_length == 0: return 0
        min_dist, closest_segment, projection_ratio = float('inf'), 0, 0
        for i, p1 in enumerate(self.full_path_points[:-1]):
            p2 = self.full_path_points[i + 1]
            segment_vec, car_vec = p2 - p1, car_pos - p1
            segment_length_sq = QPointF.dotProduct(segment_vec, segment_vec)
            if segment_length_sq == 0: continue
            t = max(0, min(1, QPointF.dotProduct(car_vec, segment_vec) / segment_length_sq))
            projection = p1 + t * segment_vec
            dist = sqrt((car_pos.x() - projection.x())**2 + (car_pos.y() - projection.y())**2)
            if dist < min_dist: min_dist, closest_segment, projection_ratio = dist, i, t
        traveled_length = sum(sqrt((self.full_path_points[i+1].x() - p.x())**2 + (self.full_path_points[i+1].y() - p.y())**2) for i, p in enumerate(self.full_path_points[:closest_segment]))
        if closest_segment < len(self.full_path_points) - 1:
            p1, p2 = self.full_path_points[closest_segment], self.full_path_points[closest_segment + 1]
            traveled_length += sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2) * projection_ratio
        return min(100, (traveled_length / total_length) * 100)

    def clear_path_layer(self):
        for child in self.layer_path.childItems():
            self.scene.removeItem(child)

    def _update_current_segment(self, car_pos):
        """차량의 위치를 기반으로 현재 주행 중인 경로의 구간을 업데이트합니다. (로직 개선)"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return

        # 차량이 마지막 구간을 넘어가지 않도록 반복 범위를 제한합니다.
        while self.current_path_segment_index < len(self.full_path_points) - 2:
            p_current = self.full_path_points[self.current_path_segment_index]
            p_next = self.full_path_points[self.current_path_segment_index + 1]
            p_future = self.full_path_points[self.current_path_segment_index + 2]

            # 현재 구간 벡터와 차량 위치 벡터
            v_segment = p_next - p_current
            v_car = car_pos - p_current
            
            if v_segment.x() == 0 and v_segment.y() == 0:
                self.current_path_segment_index += 1
                continue

            # 현재 구간에 대한 차량의 투영 비율 계산
            projection_ratio = QPointF.dotProduct(v_car, v_segment) / QPointF.dotProduct(v_segment, v_segment)

            # 차량과 다음 구간 시작점까지의 거리
            dist_to_next_start = sqrt((car_pos.x() - p_next.x())**2 + (car_pos.y() - p_next.y())**2)
            
            # 차량과 다음 구간의 다음 점까지의 거리
            dist_to_future_start = sqrt((car_pos.x() - p_future.x())**2 + (car_pos.y() - p_future.y())**2)

            # 다음 구간으로 넘어갈 조건:
            # 1. 차량이 현재 구간의 끝점을 지났거나 (projection_ratio > 1)
            # 2. 차량이 다음 구간의 시작점(p_next)보다 그 다음 점(p_future)에 더 가까워졌을 때
            if projection_ratio > 1 or dist_to_future_start < dist_to_next_start:
                self.current_path_segment_index += 1
            else:
                break

    def update_hud_from_car_position(self, car_pos):
        if not self.full_path_points: return
        self._update_current_segment(car_pos)
        
        # 현재 위치부터 남은 경로 노드들을 가져옵니다.
        # 주의: 현재 인덱스가 아니라 그 다음 인덱스부터가 남은 경로입니다.
        remaining_turn_points = self.full_path_points[self.current_path_segment_index + 1:]
        
        path_for_hud = [car_pos] + remaining_turn_points
        if len(path_for_hud) < 2:
            self.hud.update_navigation_info([("목적지 도착", 0)], current_speed=0, route_progress=100)
            return
        instructions = self.generate_hud_instructions(path_for_hud)
        progress = self.calculate_route_progress(car_pos)
        speed = min(60, int(progress * 0.6 + 10))
        self.hud.update_navigation_info(instructions, current_speed=speed, route_progress=progress)

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    font = QFont("Malgun Gothic")
    font.setPointSize(10)
    app.setFont(font)

    app.setStyleSheet(f"""
        QApplication {{ background-color: {HYUNDAI_COLORS['background']}; }}
        QMessageBox {{ background: {HYUNDAI_COLORS['surface']}; color: {HYUNDAI_COLORS['text_primary']}; border: 1px solid {HYUNDAI_COLORS['accent']}; border-radius: 10px; }}
        QMessageBox QPushButton {{ background: {HYUNDAI_COLORS['primary']}; border: 1px solid {HYUNDAI_COLORS['secondary']}; border-radius: 5px; color: white; padding: 8px 16px; min-width: 60px; font-size: {FONT_SIZES['msgbox_button']}pt; }}
    """)
    
    ui = ParkingLotUI()
    ui.showMaximized()
    sys.exit(app.exec_())
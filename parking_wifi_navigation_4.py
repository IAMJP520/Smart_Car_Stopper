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
    """라즈베리파이로부터 waypoint 및 실시간 위치를 수신하는 클래스"""

    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.waypoint_callback = None
        self.position_callback = None
        print(f"📡 Waypoint 및 위치 수신기 초기화됨. 수신 대기 주소: {self.host}:{self.port}")

    def set_waypoint_callback(self, callback_function):
        """새 waypoint 수신 시 호출될 콜백 함수 설정"""
        self.waypoint_callback = callback_function

    def set_position_callback(self, callback_function):
        """실시간 위치 수신 시 호출될 콜백 함수 설정"""
        self.position_callback = callback_function

    def start_receiver(self):
        """수신 서버 시작 (별도 스레드)"""
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
                    for chunk in data.strip().split('}{'):
                        if not chunk.startswith('{'): chunk = '{' + chunk
                        if not chunk.endswith('}'): chunk = chunk + '}'
                       
                        message = json.loads(chunk)
                        self.process_waypoint_data(message)
                        response = {"status": "received", "timestamp": datetime.now().isoformat()}
                        client_socket.send(json.dumps(response).encode('utf-8'))

                except json.JSONDecodeError:
                    print(f"❌ 잘못된 JSON 데이터: {data}")
        except Exception as e:
            print(f"❌ 데이터 수신 오류: {e}")
        finally:
            client_socket.close()
            print("📱 클라이언트 연결 종료")

    def process_waypoint_data(self, data):
        """수신된 데이터 처리 (경로 또는 위치)"""
        msg_type = data.get('type')
       
        # 경로 할당 메시지 처리
        if msg_type == 'waypoint_assignment':
            waypoints = data.get('waypoints', [])
            print(f"\n🎯 새로운 waypoint 수신: {waypoints}")
            if self.waypoint_callback:
                self.waypoint_callback(waypoints)
            print("=" * 50)
           
        # [수정] 실시간 위치 메시지 처리 - 송신 코드의 형식에 맞춤
        elif msg_type == 'real_time_position':
            x = data.get('x')
            y = data.get('y')
            tag_id = data.get('tag_id')
           
            print(f"📍 실시간 위치 수신 - Tag {tag_id}: ({x}, {y})")
           
            if x is not None and y is not None:
                position = [float(x), float(y)]
                if self.position_callback:
                    self.position_callback(position)
            else:
                print(f"❌ 잘못된 위치 데이터: x={x}, y={y}")

    def stop(self):
        """수신 서버 중지"""
        print("🛑 Waypoint 수신기를 종료합니다...")
        self.running = False
        if self.server_socket:
            try:
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
# 애니메이션 HUD 위젯: 현대차 프리미엄 스타일
# ===================================================================
class PremiumHudWidget(QFrame):
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
        self.current_direction = "경로 설정 대기"
        self.current_distance = 0.0
        self.next_direction = ""
        self.speed = 0
        self.progress = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(50)
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
        self.particle_positions = []
        for _ in range(15):
            self.particle_positions.append({
                'x': random.randint(0, 450), 'y': random.randint(0, 700),
                'speed': random.uniform(0.5, 2.0), 'size': random.randint(2, 4),
                'opacity': random.uniform(0.1, 0.3)
            })

    def update_animation(self):
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
        rect, center_x = self.rect(), self.rect().width() // 2
        self.draw_background_effects(painter, rect)
        self.draw_3d_direction_display(painter, center_x, 120)
        self.draw_distance_panel(painter, center_x, 280)
        self.draw_speed_gauge(painter, center_x, 400)
        self.draw_progress_bar(painter, center_x, 500)
        self.draw_next_instruction_card(painter, center_x, 580)
        self.draw_decorative_elements(painter, rect)

    def draw_background_effects(self, painter, rect):
        painter.save()
        for particle in self.particle_positions:
            color = QColor(0, 170, 210)
            color.setAlphaF(particle['opacity'])
            painter.setBrush(QBrush(color)); painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(particle['x'], particle['y']), particle['size'], particle['size'])
        painter.setPen(QPen(QColor(0, 170, 210, 15), 1))
        for x in range(0, rect.width(), 30): painter.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), 30): painter.drawLine(0, y, rect.width(), y)
        for corner_x, corner_y in [(0, 0), (rect.width(), 0), (0, rect.height()), (rect.width(), rect.height())]:
            gradient = QRadialGradient(corner_x, corner_y, 150)
            gradient.setColorAt(0, QColor(0, 170, 210, int(50 * self.glow_opacity)))
            gradient.setColorAt(1, QColor(0, 170, 210, 0))
            painter.setBrush(QBrush(gradient)); painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(corner_x, corner_y), 150, 150)
        painter.restore()

    def draw_3d_direction_display(self, painter, center_x, y):
        painter.save(); painter.translate(center_x, y); painter.rotate(self.rotation_angle)
        gradient = QRadialGradient(0, 0, 90)
        gradient.setColorAt(0, QColor(0, 170, 210, 0)); gradient.setColorAt(0.7, QColor(0, 170, 210, 50)); gradient.setColorAt(1, QColor(0, 170, 210, 100))
        painter.setBrush(QBrush(gradient)); painter.setPen(QPen(QColor(0, 200, 255, 150), 2)); painter.drawEllipse(QPointF(0, 0), 85, 85)
        painter.rotate(-self.rotation_angle); painter.scale(self.pulse_scale, self.pulse_scale)
        is_warning = self.current_distance <= 0 and ("좌회전" in self.current_direction or "우회전" in self.current_direction or "목적지" in self.current_direction)
        gradient, glow_color = (QRadialGradient(0, 0, 70), QColor(255, 200, 50)) if is_warning else (QRadialGradient(0, 0, 70), QColor(0, 200, 255))
        gradient.setColorAt(0, QColor(255, 180, 0, 200) if is_warning else QColor(0, 170, 210, 200))
        gradient.setColorAt(0.5, QColor(255, 140, 0, 150) if is_warning else QColor(0, 127, 163, 150))
        gradient.setColorAt(1, QColor(255, 100, 0, 100) if is_warning else QColor(0, 44, 95, 100))
        painter.setPen(QPen(glow_color, 6)); painter.setBrush(QBrush(gradient)); painter.drawEllipse(QPointF(0, 0), 65, 65)
        gradient_inner = QRadialGradient(0, 0, 45); gradient_inner.setColorAt(0, QColor(255, 255, 255, 40)); gradient_inner.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(gradient_inner)); painter.setPen(Qt.NoPen); painter.drawEllipse(QPointF(0, 0), 45, 45)
        painter.scale(1 / self.pulse_scale, 1 / self.pulse_scale); self.draw_3d_direction_icon(painter); painter.restore()

    def draw_3d_direction_icon(self, painter):
        painter.save(); painter.setPen(Qt.NoPen); painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
        action = None
        if self.current_distance <= 0:
            if "좌회전" in self.current_direction: action = self.draw_3d_left_arrow
            elif "우회전" in self.current_direction: action = self.draw_3d_right_arrow
            elif "목적지" in self.current_direction: action = self.draw_3d_destination_icon
        if action:
            painter.translate(3, 3); action(painter, 0, 0, shadow=True)
            painter.translate(-3, -3)
            gradient = QLinearGradient(-30, -20, 30, 20); gradient.setColorAt(0, QColor(255, 255, 255)); gradient.setColorAt(1, QColor(200, 200, 200))
            painter.setBrush(QBrush(gradient)); painter.setPen(QPen(QColor(255, 255, 255), 3)); action(painter, 0, 0)
        else: self.draw_3d_straight_arrow(painter, 0, 0)
        painter.restore()

    def draw_3d_left_arrow(self, painter, x, y, shadow=False):
        if not shadow: painter.drawPolygon(QPolygonF([QPointF(x-35,y),QPointF(x-15,y-20),QPointF(x-15,y-10),QPointF(x+20,y-10),QPointF(x+20,y+10),QPointF(x-15,y+10),QPointF(x-15,y+20)]))
        else: painter.drawPolygon(QPolygonF([QPointF(x-35,y),QPointF(x-15,y-20),QPointF(x-15,y-10),QPointF(x+20,y-10),QPointF(x+20,y+10),QPointF(x-15,y+10),QPointF(x-15,y+20)]))

    def draw_3d_right_arrow(self, painter, x, y, shadow=False):
        if not shadow: painter.drawPolygon(QPolygonF([QPointF(x+35,y),QPointF(x+15,y-20),QPointF(x+15,y-10),QPointF(x-20,y-10),QPointF(x-20,y+10),QPointF(x+15,y+10),QPointF(x+15,y+20)]))
        else: painter.drawPolygon(QPolygonF([QPointF(x+35,y),QPointF(x+15,y-20),QPointF(x+15,y-10),QPointF(x-20,y-10),QPointF(x-20,y+10),QPointF(x+15,y+10),QPointF(x+15,y+20)]))

    def draw_3d_straight_arrow(self, painter, x, y):
        painter.setPen(Qt.NoPen); painter.setBrush(QBrush(QColor(0,0,0,80)))
        painter.drawPolygon(QPolygonF([QPointF(x+3,y-32),QPointF(x-15,y-7),QPointF(x-7,y-7),QPointF(x-7,y+28),QPointF(x+13,y+28),QPointF(x+13,y-7),QPointF(x+21,y-7)]))
        gradient = QLinearGradient(x-20,y-35,x+20,y+25); gradient.setColorAt(0,QColor(255,255,255)); gradient.setColorAt(0.5,QColor(240,240,240)); gradient.setColorAt(1,QColor(200,200,200))
        painter.setBrush(QBrush(gradient)); painter.setPen(QPen(QColor(255,255,255),2))
        painter.drawPolygon(QPolygonF([QPointF(x,y-35),QPointF(x-18,y-10),QPointF(x-10,y-10),QPointF(x-10,y+25),QPointF(x+10,y+25),QPointF(x+10,y-10),QPointF(x+18,y-10)]))

    def draw_3d_destination_icon(self, painter, x, y, shadow=False):
        if shadow: painter.drawEllipse(QPointF(x, y), 25, 25)
        else:
            gradient = QRadialGradient(x, y, 25); gradient.setColorAt(0, QColor(255, 100, 100)); gradient.setColorAt(1, QColor(200, 50, 50))
            painter.setBrush(QBrush(gradient)); painter.setPen(QPen(QColor(255, 255, 255), 3)); painter.drawEllipse(QPointF(x, y), 25, 25)
            painter.setBrush(QBrush(QColor(255, 255, 255))); painter.setPen(Qt.NoPen); painter.drawEllipse(QPointF(x, y), 10, 10)
            painter.setPen(QPen(QColor(50, 200, 50), 4, Qt.SolidLine, Qt.RoundCap)); painter.drawLine(x-8,y,x-3,y+5); painter.drawLine(x-3,y+5,x+8,y-6)

    def draw_distance_panel(self, painter, center_x, y):
        painter.save()
        panel_rect = QRectF(center_x - 150, y - 50, 300, 100)
        gradient = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomRight()); gradient.setColorAt(0, QColor(26, 30, 46, 200)); gradient.setColorAt(0.5, QColor(20, 24, 36, 180)); gradient.setColorAt(1, QColor(10, 14, 26, 160)); painter.setBrush(QBrush(gradient))
        pen_gradient = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomRight()); pen_gradient.setColorAt(0, QColor(0, 170, 210, 150)); pen_gradient.setColorAt(0.5, QColor(0, 200, 255, 200)); pen_gradient.setColorAt(1, QColor(0, 170, 210, 150)); painter.setPen(QPen(QBrush(pen_gradient), 2)); painter.drawRoundedRect(panel_rect, 20, 20)
        distance_text = f"{self.current_distance:.0f}m" if self.current_distance < 1000 else f"{self.current_distance/1000:.1f}km"
        font = QFont("Segoe UI", FONT_SIZES['hud_distance'], QFont.Bold); painter.setFont(font)
        text_color = QColor(255,180,0) if self.current_distance<=5 else (QColor(0,255,150) if self.current_distance<=20 else QColor(0,200,255))
        painter.setPen(QPen(text_color)); painter.drawText(QRectF(center_x-150, y-30, 300, 60), Qt.AlignCenter, distance_text)
        font = QFont("Malgun Gothic", FONT_SIZES['hud_direction']); painter.setFont(font); painter.setPen(QPen(QColor(180,190,200)))
        direction_text = self.current_direction[:20] + "..." if len(self.current_direction)>20 else self.current_direction
        painter.drawText(QRectF(center_x-150, y+10, 300, 40), Qt.AlignCenter, direction_text); painter.restore()

    def draw_speed_gauge(self, painter, center_x, y):
        painter.save()
        gauge_rect = QRectF(center_x - 80, y - 40, 160, 80)
        painter.setPen(QPen(QColor(0, 44, 95, 100), 8)); painter.setBrush(Qt.NoBrush); painter.drawArc(gauge_rect, 0, 180 * 16)
        speed_angle = min(180, (self.speed / 100) * 180)
        gradient = QLinearGradient(gauge_rect.topLeft(), gauge_rect.topRight()); gradient.setColorAt(0, QColor(0, 200, 255)); gradient.setColorAt(0.5, QColor(0, 170, 210)); gradient.setColorAt(1, QColor(0, 127, 163))
        painter.setPen(QPen(QBrush(gradient), 6)); painter.drawArc(gauge_rect, 0, int(speed_angle * 16))
        font = QFont("Segoe UI", FONT_SIZES['hud_speed'], QFont.Bold); painter.setFont(font); painter.setPen(QPen(QColor(255, 255, 255))); painter.drawText(QRectF(center_x-80, y-20, 160, 40), Qt.AlignCenter, f"{self.speed}")
        font = QFont("Malgun Gothic", FONT_SIZES['hud_speed_unit']); painter.setFont(font); painter.setPen(QPen(QColor(180,190,200))); painter.drawText(QRectF(center_x-80, y+10, 160, 20), Qt.AlignCenter, "km/h"); painter.restore()

    def draw_progress_bar(self, painter, center_x, y):
        painter.save()
        bar_width, bar_height = 350, 12
        bar_rect = QRectF(center_x - bar_width / 2, y - bar_height / 2, bar_width, bar_height)
        painter.setBrush(QBrush(QColor(0, 44, 95, 100))); painter.setPen(QPen(QColor(0, 170, 210, 50), 1)); painter.drawRoundedRect(bar_rect, 6, 6)
        if self.progress > 0:
            progress_rect = QRectF(bar_rect.x(), bar_rect.y(), (self.progress / 100) * bar_width, bar_height)
            gradient = QLinearGradient(progress_rect.topLeft(), progress_rect.topRight()); gradient.setColorAt(0, QColor(0, 200, 255)); gradient.setColorAt(0.5, QColor(0, 170, 210)); gradient.setColorAt(1, QColor(0, 255, 200))
            painter.setBrush(QBrush(gradient)); painter.setPen(Qt.NoPen); painter.drawRoundedRect(progress_rect, 6, 6)
        font = QFont("Segoe UI", FONT_SIZES['hud_progress'], QFont.Bold); painter.setFont(font); painter.setPen(QPen(QColor(255,255,255))); painter.drawText(QRectF(center_x-175, y+10, 350, 30), Qt.AlignCenter, f"{self.progress:.0f}%"); painter.restore()

    def draw_next_instruction_card(self, painter, center_x, y):
        if not self.next_direction: return
        painter.save(); card_rect = QRectF(center_x-200, y-40, 400, 80)
        gradient = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight()); gradient.setColorAt(0, QColor(26,30,46,180)); gradient.setColorAt(1, QColor(10,14,26,140))
        painter.setBrush(QBrush(gradient)); painter.setPen(QPen(QColor(0,170,210,100), 2)); painter.drawRoundedRect(card_rect, 20, 20)
        font = QFont("Malgun Gothic", FONT_SIZES['hud_next_label'], QFont.Bold); painter.setFont(font); painter.setPen(QPen(QColor(0,200,255))); painter.drawText(QPointF(center_x-190, y-15), "다음")
        icon_x, icon_y = center_x - 140, y + 10
        gradient_icon = QRadialGradient(icon_x, icon_y, 25); gradient_icon.setColorAt(0, QColor(0,170,210,150)); gradient.setColorAt(1, QColor(0,44,95,100))
        painter.setBrush(QBrush(gradient_icon)); painter.setPen(QPen(QColor(0,200,255), 2)); painter.drawEllipse(QPointF(icon_x, icon_y), 25, 25)
        painter.setPen(QPen(QColor(255,255,255), 3)); painter.setBrush(QBrush(QColor(255,255,255)))
        if "좌회전" in self.next_direction: self.draw_mini_left_arrow(painter, icon_x, icon_y)
        elif "우회전" in self.next_direction: self.draw_mini_right_arrow(painter, icon_x, icon_y)
        elif "목적지" in self.next_direction or "도착" in self.next_direction: self.draw_mini_destination(painter, icon_x, icon_y)
        else: self.draw_mini_straight(painter, icon_x, icon_y)
        font.setPointSize(FONT_SIZES['hud_next_direction']); painter.setFont(font); painter.setPen(QPen(QColor(220,230,240)))
        painter.drawText(QRectF(icon_x+30, y-20, 200, 60), Qt.AlignVCenter, self.next_direction[:20]+"..." if len(self.next_direction)>20 else self.next_direction); painter.restore()

    def draw_mini_left_arrow(self, painter, x, y): painter.drawPolygon(QPolygonF([QPointF(x-12,y),QPointF(x-5,y-7),QPointF(x-5,y-3),QPointF(x+8,y-3),QPointF(x+8,y+3),QPointF(x-5,y+3),QPointF(x-5,y+7)]))
    def draw_mini_right_arrow(self, painter, x, y): painter.drawPolygon(QPolygonF([QPointF(x+12,y),QPointF(x+5,y-7),QPointF(x+5,y-3),QPointF(x-8,y-3),QPointF(x-8,y+3),QPointF(x+5,y+3),QPointF(x+5,y+7)]))
    def draw_mini_straight(self, painter, x, y): painter.drawPolygon(QPolygonF([QPointF(x,y-12),QPointF(x-6,y-4),QPointF(x-3,y-4),QPointF(x-3,y+8),QPointF(x+3,y+8),QPointF(x+3,y-4),QPointF(x+6,y-4)]))
    def draw_mini_destination(self, painter, x, y):
        painter.drawEllipse(QPointF(x,y), 8, 8); painter.setPen(QPen(QColor(50,200,50),3)); painter.drawLine(x-5,y,x-2,y+3); painter.drawLine(x-2,y+3,x+5,y-4)

    def draw_decorative_elements(self, painter, rect):
        painter.save()
        gradient = QLinearGradient(0,20,rect.width(),20); gradient.setColorAt(0,QColor(0,170,210,0)); gradient.setColorAt(0.2,QColor(0,170,210,100)); gradient.setColorAt(0.5,QColor(0,200,255,200)); gradient.setColorAt(0.8,QColor(0,170,210,100)); gradient.setColorAt(1,QColor(0,170,210,0))
        painter.setBrush(QBrush(gradient)); painter.setPen(Qt.NoPen); painter.drawRect(0,20,rect.width(),4); painter.drawRect(0,rect.height()-24,rect.width(),4)
        corner_size=30; painter.setPen(QPen(QColor(0,200,255),3)); painter.setBrush(Qt.NoBrush)
        painter.drawArc(15,15,corner_size,corner_size,90*16,90*16); painter.drawArc(rect.width()-45,15,corner_size,corner_size,0*16,90*16)
        painter.drawArc(15,rect.height()-45,corner_size,corner_size,180*16,90*16); painter.drawArc(rect.width()-45,rect.height()-45,corner_size,corner_size,270*16,90*16)
        painter.restore()

    def update_navigation_info(self, instructions, current_speed=0, route_progress=0):
        self.speed, self.progress = current_speed, route_progress
        if not instructions: self.current_direction, self.current_distance, self.next_direction = "경로를 생성하세요", 0.0, ""; self.update(); return
        direction, distance = instructions[0]
        new_direction = "직진" if distance > 0 else direction
        if new_direction != self.target_direction: self.previous_direction, self.target_direction, self.direction_transition = self.target_direction, new_direction, 0.0
        if distance > 0:
            self.current_direction, self.current_distance = "직진", distance
            self.next_direction = direction if ("좌회전" in direction or "우회전" in direction or "목적지" in direction) and distance<=50 else ""
        else:
            self.current_direction, self.current_distance = direction, distance
            self.next_direction = (f"직진 {int(round(instructions[1][1]))}m 후 도착" if "목적지" in instructions[1][0] else f"직진 {int(round(instructions[1][1]))}m") if len(instructions) > 1 else ""
        self.update()

# ===================================================================
# 자동차 아이템: 현대차 스타일
# ===================================================================
# ===================================================================
# 자동차 아이템: 제공된 이미지의 파란색 차량 스타일
# ===================================================================
# ===================================================================
# 자동차 아이템: 간단한 자동차 정면 모양 스타일 (상하반전)
# ===================================================================
class CarItem(QGraphicsObject):
    positionChanged = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        # [수정] 모든 도형의 y 좌표를 반전시켜 상하반전된 모양으로 정의
        
        # 차량 본체 (위쪽이 넓은 사다리꼴 모양)
        self.car_body = QPolygonF([
            QPointF(-45, -45), QPointF(45, -45), QPointF(40, 15), QPointF(-40, 15)
        ])
        
        # 차량 지붕 및 유리창 (아래쪽이 좁은 사다리꼴 모양)
        self.car_cabin = QPolygonF([
            QPointF(-30, 15), QPointF(30, 15), QPointF(25, 45), QPointF(-25, 45)
        ])
        
        # 헤드라이트 (좌/우) - y 좌표 반전
        self.headlight_left = QRectF(-35, -10, 15, 10)
        self.headlight_right = QRectF(20, -10, 15, 10)

        # 전면 그릴 - y 좌표 반전
        self.grille = QRectF(-15, -15, 30, 10)
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(100)
        self.setRotation(0)

    def boundingRect(self):
        # 경계 사각형 계산은 동일
        return self.car_body.boundingRect().united(self.car_cabin.boundingRect()).adjusted(-5, -5, 5, 5)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # 그림자 효과
        painter.save()
        painter.translate(4, 4)
        painter.setBrush(QBrush(QColor(0, 0, 0, 70)))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(self.car_body)
        painter.drawPolygon(self.car_cabin)
        painter.restore()

        # [수정] 차량 본체 그라데이션 방향 반전
        body_gradient = QLinearGradient(0, 15, 0, -45)
        body_gradient.setColorAt(0, QColor(HYUNDAI_COLORS['accent']))
        body_gradient.setColorAt(1, QColor(HYUNDAI_COLORS['primary']))
        painter.setBrush(QBrush(body_gradient))
        painter.setPen(QPen(QColor(200, 220, 255, 150), 2))
        painter.drawPolygon(self.car_body)

        # [수정] 차량 지붕 및 유리창 그라데이션 방향 반전
        cabin_gradient = QLinearGradient(0, 45, 0, 15)
        cabin_gradient.setColorAt(0, QColor(50, 60, 80))
        cabin_gradient.setColorAt(1, QColor(20, 30, 50))
        painter.setBrush(QBrush(cabin_gradient))
        painter.setPen(QPen(QColor(150, 180, 200, 100), 1))
        painter.drawPolygon(self.car_cabin)

        # 헤드라이트 그리기 (위치만 변경됨)
        headlight_gradient = QRadialGradient(0, 0, 15)
        headlight_gradient.setColorAt(0, QColor(255, 255, 220))
        headlight_gradient.setColorAt(1, QColor(200, 200, 150, 100))
        
        painter.save()
        painter.translate(self.headlight_left.center())
        painter.setBrush(QBrush(headlight_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(-7.5, -5, 15, 10))
        painter.restore()

        painter.save()
        painter.translate(self.headlight_right.center())
        painter.setBrush(QBrush(headlight_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(-7.5, -5, 15, 10))
        painter.restore()

        # 그릴 그리기 (위치만 변경됨)
        painter.setBrush(QBrush(QColor(50, 60, 70)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.grille, 3, 3)
        painter.setPen(QPen(QColor(100, 110, 120), 1.5))
        painter.drawLine(self.grille.left(), self.grille.center().y(), self.grille.right(), self.grille.center().y())


    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)
        return super().itemChange(change, value)

# ===================================================================
# 메인 UI: 현대차 스타일 주차장 지도 (WiFi 통합)
# ===================================================================
# ===================================================================
# 메인 UI: 현대차 스타일 주차장 지도 (WiFi 통합)
# ===================================================================
class ParkingLotUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH = 30, 10, 50
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)
    
    newWaypointsReceived = pyqtSignal(list)
    carPositionReceived = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HYUNDAI SmartParking Navigation System (WiFi Ver.)")
        self.initial_fit = False
        self.received_waypoints = []
        self.setup_styles()
        self.init_ui()
        self.init_map()
        self.init_wifi()

    def setup_styles(self):
        self.setStyleSheet(f"""
            QWidget {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HYUNDAI_COLORS['background']}, stop:1 {HYUNDAI_COLORS['surface']}); color: {HYUNDAI_COLORS['text_primary']}; font-family: 'Malgun Gothic'; }}
            QGraphicsView {{ border: 3px solid {HYUNDAI_COLORS['accent']}; border-radius: 15px; background: '#303030'; }}
        """)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.scale(1, -1)
        self.view.translate(0, -self.SCENE_H)
        self.hud = PremiumHudWidget()
        main_layout.addWidget(self.view, 3)
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
        self.carPositionReceived.connect(self.update_car_position_from_wifi)
        self.waypoint_receiver = WaypointReceiver()
        self.waypoint_receiver.set_waypoint_callback(self.handle_new_waypoints_from_thread)
        self.waypoint_receiver.set_position_callback(self.handle_new_position_from_thread)
        self.waypoint_receiver.start_receiver()
        QMessageBox.information(self, "WiFi 수신기", f"서버가 {self.waypoint_receiver.host}:{self.waypoint_receiver.port}에서 시작되었습니다.\n관제 시스템의 연결을 기다립니다.")

    def handle_new_waypoints_from_thread(self, waypoints):
        self.newWaypointsReceived.emit(waypoints)

    def handle_new_position_from_thread(self, position):
        self.carPositionReceived.emit(position)

    def update_ui_with_waypoints(self, waypoints):
        if not waypoints or not isinstance(waypoints, list):
            QMessageBox.warning(self, "수신 오류", "잘못된 형식의 웨이포인트 데이터가 수신되었습니다.")
            return
        self.received_waypoints = waypoints
        QMessageBox.information(self, "경로 자동 설정", f"새로운 경로가 수신되었습니다:\n{waypoints}\n\n자동으로 경로 안내를 시작합니다.")
        self.calculate_and_display_route()

    def update_car_position_from_wifi(self, position: List[float]):
        if not (isinstance(position, list) and len(position) == 2):
            return
        new_pos = QPointF(position[0], position[1])
        self.car.setPos(new_pos)

    def calculate_and_display_route(self):
        if not self.received_waypoints:
            QMessageBox.warning(self, "경로 오류", "경로를 계산할 웨이포인트가 없습니다."); return
        start_point = self.car.pos() if self.car.isVisible() else self.ENTRANCE
        waypoints_qpoints = [self.clamp_point(QPointF(p[0], p[1])) for p in self.received_waypoints]
        self.snapped_waypoints = [self.find_nearest_free_cell_from_point(p) for p in waypoints_qpoints]
        segments, prev = [], start_point
        for goal in self.snapped_waypoints:
            c = self.astar(prev, goal)
            if not c: QMessageBox.warning(self, "경로 실패", f"경로를 찾을 수 없습니다: {prev.x():.0f},{prev.y():.0f} -> {goal.x():.0f},{goal.y():.0f}"); return
            segments.append(c); prev = goal
        whole = [c for i, seg in enumerate(segments) for c in (seg if i == 0 else seg[1:])]
        self.full_path_points = [self.cell_to_pt_center(c) for c in self.simplify_cells(whole)]
        if not self.full_path_points: return
        self.full_path_points[0], self.full_path_points[-1] = start_point, self.snapped_waypoints[-1]
        self.clear_path_layer()
        self.draw_straight_path(self.full_path_points)
        self.current_path_segment_index = 0
        if not self.car.isVisible():
            self.car.setPos(start_point)
            self.car.show()
        self.update_hud_from_car_position(self.car.pos())

    def showEvent(self, event):
        super().showEvent(event)
        if not self.initial_fit:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.initial_fit = True
            
    def closeEvent(self, event):
        self.waypoint_receiver.stop()
        super().closeEvent(event)

    # ★ 변경점 1: add_block 함수에서 테두리 그리기(setPen) 제거
    def add_block(self, x, y, w, h, color, label=""):
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        if "장애인" in label: gradient = QLinearGradient(x,y,x+w,y+h); gradient.setColorAt(0,QColor(135, 206, 250, 200)); gradient.setColorAt(1,QColor(70, 130, 180,150)); r.setBrush(QBrush(gradient))
        elif "전기차" in label: gradient = QLinearGradient(x,y,x+w,y+h); gradient.setColorAt(0,QColor(0,200,130,200)); gradient.setColorAt(1,QColor(0,150,100,150)); r.setBrush(QBrush(gradient))
        elif "일반" in label: gradient = QLinearGradient(x,y,x+w,y+h); gradient.setColorAt(0,QColor("#303030")); gradient.setColorAt(1,QColor("#303030")); r.setBrush(QBrush(gradient))
        else: r.setBrush(QBrush(color))
        r.setPen(Qt.NoPen) # ★ 테두리를 그리지 않음
        r.setParentItem(self.layer_static)
        if label:
            t = QGraphicsSimpleTextItem(label); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setBrush(QColor(255,255,255))
            font = QFont("Malgun Gothic", FONT_SIZES['map_label'], QFont.Bold); t.setFont(font); t.setPos(x+5,y+h-25); t.setParentItem(self.layer_static)

    def add_hatched(self, x, y, w, h, edge=QColor("black"), fill=QColor(220, 20, 60, 90)):
        r = QGraphicsRectItem(QRectF(x,y,w,h)); b = QBrush(fill); b.setStyle(Qt.BDiagPattern); r.setBrush(b); r.setPen(QPen(edge,3)); r.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem("통행 불가"); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setBrush(QColor(255,100,100))
        font = QFont("Malgun Gothic", FONT_SIZES['map_label'], QFont.Bold); t.setFont(font); t.setPos(x+10,y+h-30); t.setParentItem(self.layer_static)

    def add_dot_label_static(self, p: QPointF, text: str, color=QColor("blue")):
        d = QGraphicsEllipseItem(p.x()-8,p.y()-8,16,16); gradient = QLinearGradient(p.x()-8,p.y()-8,p.x()+8,p.y()+8); gradient.setColorAt(0,QColor(0,170,210)); gradient.setColorAt(1,QColor(0,44,95)); d.setBrush(QBrush(gradient)); d.setPen(QPen(QColor(255,255,255),3)); d.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem(text); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setBrush(QColor(0,200,255))
        font = QFont("Malgun Gothic", FONT_SIZES['map_io_label'], QFont.Bold); t.setFont(font); t.setPos(p.x()-20,p.y()+25); t.setParentItem(self.layer_static)

    # ★ 변경점 2: build_static_layout 함수에서 모든 주차선을 한 번에 그림
    def build_static_layout(self):
        c_dis, c_ele, c_gen, c_obs, c_emp, c_io = QColor(135, 206, 250), QColor(0, 200, 130), QColor("#303030"), QColor(108, 117, 125), QColor(206, 212, 218), QColor("#303030")
        
        # 1. 모든 블록의 배경색과 라벨을 먼저 그림
        base = [(0, 1600, 300, 400, c_dis, "장애인"), (300, 1600, 300, 400, c_dis, "장애인"), (600, 1600, 200, 400, c_gen, "일반"), (800, 1600, 200, 400, c_gen, "일반"), (1000, 1600, 200, 400, c_gen, "일반"), (1200, 1600, 200, 400, c_ele, "전기차"), (1400, 1600, 200, 400, c_ele, "전기차"), (1600, 1600, 400, 400, c_emp, "101"), (550, 1050, 800, 300, c_obs, "장애물"), (1600, 400, 400, 400, c_emp, "102"), (0, 0, 400, 400, c_io, "입출차")]
        for x, y, w, h, c, l in base: self.add_block(x, y, w, h, c, l)
        for i in range(6): self.add_block(400 + i * 200, 400, 200, 400, c_gen, "일반")
        for i in range(4): self.add_block(1600, 800 + i * 200, 400, 200, c_gen, "일반")
        
        # 2. 모든 주차선을 QPainterPath를 이용해 하나의 객체로 묶어 그림
        parking_lines_path = QPainterPath()

        # 상단 주차 구역 라인 (y=1600~2000)
        parking_lines_path.addRect(QRectF(0, 1600, 1600, 400)) # 바깥 테두리
        for x_div in [300, 600, 800, 1000, 1200, 1400]: # 내부 세로선
            parking_lines_path.moveTo(x_div, 1600)
            parking_lines_path.lineTo(x_div, 2000)

        # 중간 주차 구역 라인 (y=400~800)
        parking_lines_path.addRect(QRectF(400, 400, 1200, 400)) # 바깥 테두리
        for i in range(1, 6): # 내부 세로선
            x_div = 400 + i * 200
            parking_lines_path.moveTo(x_div, 400)
            parking_lines_path.lineTo(x_div, 800)
            
        # 우측 주차 구역 라인 (x=1600~2000)
        parking_lines_path.addRect(QRectF(1600, 800, 400, 800)) # 바깥 테두리
        for i in range(1, 4): # 내부 가로선
            y_div = 800 + i * 200
            parking_lines_path.moveTo(1600, y_div)
            parking_lines_path.lineTo(2000, y_div)
            
        # QPainterPath를 씬에 추가
        from PyQt5.QtWidgets import QGraphicsPathItem
        lines_item = QGraphicsPathItem(parking_lines_path)
        pen = QPen(QColor(255, 255, 255, 200), 10) # 10픽셀 두께의 흰색 선
        pen.setJoinStyle(Qt.MiterJoin) # 모서리를 각지게 처리
        lines_item.setPen(pen)
        lines_item.setParentItem(self.layer_static)

        # 3. 기타 요소들
        self.add_hatched(400, 0, 1600, 400)
        self.add_dot_label_static(self.ENTRANCE, "입구", QColor(0, 170, 210))

    # (이하 나머지 모든 함수는 이전과 동일)
    # ...

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
   
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
   
    font = QFont("Malgun Gothic"); font.setPointSize(10); app.setFont(font)

    app.setStyleSheet(f"""
        QApplication {{ background-color: '#303030'; }}
        QMessageBox {{ background: {HYUNDAI_COLORS['surface']}; color: {HYUNDAI_COLORS['text_primary']}; border: 1px solid {HYUNDAI_COLORS['accent']}; border-radius: 10px; }}
        QMessageBox QPushButton {{ background: {HYUNDAI_COLORS['primary']}; border: 1px solid {HYUNDAI_COLORS['secondary']}; border-radius: 5px; color: white; padding: 8px 16px; min-width: 60px; font-size: {FONT_SIZES['msgbox_button']}pt; }}
    """)
   
    ui = ParkingLotUI()
    ui.showMaximized()
    sys.exit(app.exec_())
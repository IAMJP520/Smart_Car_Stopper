import sys
import random
import datetime
import subprocess
import os
import socket
import json
import threading
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QDialog, QFrame,
                             QStackedWidget, QGridLayout, QProgressBar, QGraphicsOpacityEffect,
                             QButtonGroup)
from PyQt5.QtGui import (QPixmap, QFont, QPainter, QPainterPath, QLinearGradient,
                         QColor, QIcon, QBrush, QPen, QPolygonF)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPointF, QSequentialAnimationGroup

# ===================================================================
# Wi-Fi 통신 설정
# ===================================================================
WIFI_CONFIG = {
    'target_ip': '192.168.111.1',  # ❗️ 데이터를 받을 ESP32 또는 라즈베리파이의 IP 주소
    'port': 6666
}

# ===================================================================
# 심플 & 모노톤 컬러 팔레트
# ===================================================================
SIMPLE_COLORS = {
    'background': '#121212',   # Black
    'surface': '#1E1E1E',      # Dark Gray
    'primary': '#FFFFFF',      # White
    'secondary': '#E0E0E0',    # Light Gray
    'tertiary': '#333333',     # Medium Gray for borders
    'text_primary': '#FFFFFF', # White Text
    'text_secondary': '#A9A9A9', # Gray Text
    'warning': '#FFD60A',      # A touch of yellow for warnings
}


# --- 해상도 독립적인 폰트 크기 (단위: pt) ---
FONT_SIZES = {
    'status_bar_location': 12,
    'status_bar_date': 11,
    'status_bar_time': 28,
    'status_bar_weather': 12,
    'status_bar_radio': 11,
    'main_title': 36,
    'main_subtitle': 16,
    'button': 15,
    'toggle_button': 15, # [수정] 14 -> 15
    'scenario_title': 28,
    'scenario_subtitle': 16,
    'scenario_info': 14,
    'scanner_text': 18,
    'timer': 14,
    'transition_text': 28,
}

# ===================================================================
# Wi-Fi 데이터 전송 클래스
# ===================================================================
class WifiSender:
    """선택된 주차 정보를 다른 기기로 전송하는 클라이언트 클래스"""
    def __init__(self, host, port):
        self.host = host
        self.port = port
        print(f"📡 WifiSender 초기화 -> 대상: {self.host}:{self.port}")

    def send_data(self, data):
        """데이터를 JSON 형식으로 인코딩하여 전송합니다."""
        thread = threading.Thread(target=self._send_in_background, args=(data,))
        thread.daemon = True
        thread.start()

    def _send_in_background(self, data):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                print(f"연결 시도 중... -> {self.host}:{self.port}")
                s.connect((self.host, self.port))
                data['timestamp'] = datetime.datetime.now().isoformat()
                message = json.dumps(data)
                s.sendall(message.encode('utf-8'))
                print(f"🚀 데이터 전송 성공: {message}")
                response = s.recv(1024)
                print(f"📬 서버 응답: {response.decode('utf-8')}")
        except socket.timeout:
            print(f"❌ 전송 실패: 연결 시간 초과. {self.host} 기기가 켜져 있고 같은 네트워크에 있는지 확인하세요.")
        except ConnectionRefusedError:
            print(f"❌ 전송 실패: 연결이 거부되었습니다. 대상 기기에서 수신 프로그램이 실행 중인지 확인하세요.")
        except Exception as e:
            print(f"❌ 전송 중 알 수 없는 오류 발생: {e}")


class HyundaiBackground(QWidget):
    """심플한 배경 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(SIMPLE_COLORS['background']))
        gradient.setColorAt(1, QColor(SIMPLE_COLORS['surface']))
        painter.fillRect(self.rect(), QBrush(gradient))
        
        painter.setPen(QPen(QColor(SIMPLE_COLORS['tertiary']), 0.5))
        for i in range(0, self.width(), 80): painter.drawLine(i, 0, i, self.height())
        for i in range(0, self.height(), 80): painter.drawLine(0, i, self.width(), i)

class StatusBar(QWidget):
    """상단 상태 바"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(30, 15, 30, 15)
        
        location_layout = QHBoxLayout()
        location_icon = QLabel("📍")
        location_icon.setStyleSheet(f"font-size: {FONT_SIZES['status_bar_location']}pt; color: white;")
        self.location_label = QLabel("Seocho-gu, Seoul")
        self.location_label.setStyleSheet(f"color: {SIMPLE_COLORS['text_primary']}; font-size: {FONT_SIZES['status_bar_location']}pt; font-weight: bold;")
        location_layout.addWidget(location_icon)
        location_layout.addWidget(self.location_label)
        location_layout.addStretch()

        time_layout = QVBoxLayout()
        time_layout.setSpacing(0)
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet(f"color: {SIMPLE_COLORS['text_secondary']}; font-size: {FONT_SIZES['status_bar_date']}pt;")
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet(f"color: {SIMPLE_COLORS['text_primary']}; font-size: {FONT_SIZES['status_bar_time']}pt; font-weight: bold;")
        time_layout.addWidget(self.date_label)
        time_layout.addWidget(self.time_label)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)
        weather_layout = QHBoxLayout()
        weather_layout.addStretch()
        temp_label = QLabel("26°C")
        temp_label.setStyleSheet(f"color: {SIMPLE_COLORS['text_primary']}; font-size: {FONT_SIZES['status_bar_weather']}pt; font-weight: bold;")
        weather_icon = QLabel("🌙")
        weather_icon.setStyleSheet(f"font-size: {FONT_SIZES['status_bar_weather']}pt;")
        weather_layout.addWidget(temp_label)
        weather_layout.addWidget(weather_icon)
        
        radio_layout = QHBoxLayout()
        radio_layout.addStretch()
        radio_label = QLabel("FM 87.5")
        radio_label.setStyleSheet(f"color: {SIMPLE_COLORS['text_secondary']}; font-size: {FONT_SIZES['status_bar_radio']}pt;")
        radio_layout.addWidget(radio_label)
        
        right_layout.addLayout(weather_layout)
        right_layout.addLayout(radio_layout)

        layout.addLayout(location_layout, 1)
        layout.addLayout(time_layout, 2)
        layout.addLayout(right_layout, 1)
        self.setLayout(layout)
        self.setStyleSheet(f"background: {SIMPLE_COLORS['surface']}; border-bottom: 1px solid {SIMPLE_COLORS['tertiary']};")

    def update_time(self):
        now = datetime.datetime.now()
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        date_str = f"{now.month}월 {now.day}일 ({weekdays[now.weekday()]})"
        self.date_label.setText(date_str)
        time_str = now.strftime("%H:%M")
        self.time_label.setText(time_str)

class AnimatedButton(QPushButton):
    """심플 스타일 버튼"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        # [수정] 버튼 크기 조정
        self.setMinimumHeight(65)
        self.setMaximumWidth(500)
        self.setCursor(Qt.PointingHandCursor)
        
        self.default_style = f"""
            QPushButton {{
                background-color: {SIMPLE_COLORS['surface']};
                color: {SIMPLE_COLORS['text_primary']};
                border: 1px solid {SIMPLE_COLORS['tertiary']};
                border-radius: 12px;
                font-size: {FONT_SIZES['button']}pt;
                font-weight: bold;
                padding: 15px 30px;
            }}
            QPushButton:disabled {{
                background-color: {SIMPLE_COLORS['tertiary']};
                color: {SIMPLE_COLORS['text_secondary']};
                border: 1px solid {SIMPLE_COLORS['tertiary']};
            }}
        """
        self.hover_style = f"""
            QPushButton {{
                background-color: {SIMPLE_COLORS['tertiary']};
                color: {SIMPLE_COLORS['primary']};
                border: 1px solid {SIMPLE_COLORS['secondary']};
                border-radius: 12px;
                font-size: {FONT_SIZES['button']}pt;
                font-weight: bold;
                padding: 15px 30px;
            }}
        """
        self.setStyleSheet(self.default_style)

    def enterEvent(self, event):
        if self.isEnabled():
            self.setStyleSheet(self.hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.default_style)
        super().leaveEvent(event)

class ToggleButton(QPushButton):
    """심플 스타일 토글 버튼"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        # [수정] 버튼 크기 조정
        self.setMinimumHeight(55)
        self.setMaximumWidth(350)
        self.setCursor(Qt.PointingHandCursor)
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {SIMPLE_COLORS['text_secondary']};
                border: 1px solid {SIMPLE_COLORS['tertiary']};
                border-radius: 10px;
                font-size: {FONT_SIZES['toggle_button']}pt;
                font-weight: bold;
                padding: 12px 25px; /* [수정] 패딩 조정 */
            }}
            QPushButton:hover {{
                background: {SIMPLE_COLORS['tertiary']};
                color: {SIMPLE_COLORS['text_primary']};
            }}
            QPushButton:checked {{
                background: {SIMPLE_COLORS['primary']};
                color: {SIMPLE_COLORS['background']};
                border: 1px solid {SIMPLE_COLORS['primary']};
            }}
        """)


class BaseScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.background = HyundaiBackground(self)
        self.main_widget = QWidget(self)
        self.main_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.main_widget)
        self.content_layout.setSpacing(25)
        self.content_layout.setContentsMargins(80, 40, 80, 40)
        full_layout = QVBoxLayout(self)
        full_layout.setContentsMargins(0, 0, 0, 0)
        full_layout.addWidget(self.main_widget)
        self.setLayout(full_layout)

    def resizeEvent(self, event):
        self.background.resize(event.size())
        super().resizeEvent(event)

class SimulationSetupScreen(BaseScreen):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vehicle_type = None
        self.is_handicapped = None
        self.initUI()

    def initUI(self):
        title = QLabel("Smart Parking System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: {FONT_SIZES['main_title']}pt; font-weight: bold; color: {SIMPLE_COLORS['text_primary']};")

        subtitle = QLabel("Please select your vehicle options")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"font-size: {FONT_SIZES['main_subtitle']}pt; color: {SIMPLE_COLORS['text_secondary']};")

        vehicle_label = QLabel("Vehicle Type")
        vehicle_label.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {SIMPLE_COLORS['text_primary']}; margin-top: 15px; margin-bottom: 5px; text-align: center;")
        vehicle_label.setAlignment(Qt.AlignCenter)
        
        self.vehicle_btn_group = QButtonGroup(self)
        self.vehicle_btn_group.setExclusive(True)
        
        vehicle_buttons_layout = QHBoxLayout()
        vehicle_buttons_layout.setSpacing(20)
        self.regular_car_btn = ToggleButton("🚗 Regular")
        self.ev_car_btn = ToggleButton("🔋 Electric")
        self.vehicle_btn_group.addButton(self.regular_car_btn)
        self.vehicle_btn_group.addButton(self.ev_car_btn)
        vehicle_buttons_layout.addStretch(1)
        vehicle_buttons_layout.addWidget(self.regular_car_btn)
        vehicle_buttons_layout.addWidget(self.ev_car_btn)
        vehicle_buttons_layout.addStretch(1)
        
        handicap_label = QLabel("Disabled Parking")
        handicap_label.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {SIMPLE_COLORS['text_primary']}; margin-top: 15px; margin-bottom: 5px;")
        handicap_label.setAlignment(Qt.AlignCenter)

        self.handicap_btn_group = QButtonGroup(self)
        self.handicap_btn_group.setExclusive(True)

        handicap_buttons_layout = QHBoxLayout()
        handicap_buttons_layout.setSpacing(20)
        self.handicapped_btn = ToggleButton("♿ Yes")
        self.non_handicapped_btn = ToggleButton("🅿️ No")
        self.handicap_btn_group.addButton(self.handicapped_btn)
        self.handicap_btn_group.addButton(self.non_handicapped_btn)
        handicap_buttons_layout.addStretch(1)
        handicap_buttons_layout.addWidget(self.handicapped_btn)
        handicap_buttons_layout.addWidget(self.non_handicapped_btn)
        handicap_buttons_layout.addStretch(1)

        self.start_btn = AnimatedButton("Start Simulation")
        self.start_btn.clicked.connect(self.start_simulation)
        self.start_btn.setEnabled(False)

        self.vehicle_btn_group.buttonClicked.connect(self.check_selections)
        self.handicap_btn_group.buttonClicked.connect(self.check_selections)

        start_btn_layout = QHBoxLayout()
        start_btn_layout.addStretch()
        start_btn_layout.addWidget(self.start_btn)
        start_btn_layout.addStretch()

        self.content_layout.addStretch(2)
        self.content_layout.addWidget(title)
        self.content_layout.addWidget(subtitle)
        self.content_layout.addSpacing(40)
        self.content_layout.addWidget(vehicle_label)
        self.content_layout.addLayout(vehicle_buttons_layout)
        self.content_layout.addSpacing(30)
        self.content_layout.addWidget(handicap_label)
        self.content_layout.addLayout(handicap_buttons_layout)
        self.content_layout.addStretch(3)
        self.content_layout.addLayout(start_btn_layout)
        self.content_layout.addStretch(1)

    def check_selections(self):
        if self.vehicle_btn_group.checkedButton() and self.handicap_btn_group.checkedButton():
            self.start_btn.setEnabled(True)
        else:
            self.start_btn.setEnabled(False)

    def start_simulation(self):
        self.vehicle_type = 'regular' if self.regular_car_btn.isChecked() else 'electric'
        self.is_handicapped = True if self.handicapped_btn.isChecked() else False
        if hasattr(self.parent_window, 'show_transition'):
            self.parent_window.show_transition(self.vehicle_type, self.is_handicapped)

class TransitionScreen(BaseScreen):
    def __init__(self, vehicle_type, is_handicapped, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.is_handicapped = is_handicapped
        self.initUI()
        self.start_animation()

    def initUI(self):
        self.message_label = QLabel("Starting Simulation")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet(f"font-size: {FONT_SIZES['transition_text']}pt; font-weight: bold; color: {SIMPLE_COLORS['text_primary']};")
        self.content_layout.addStretch(1)
        self.content_layout.addWidget(self.message_label)
        self.content_layout.addStretch(1)
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.message_label.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

    def start_animation(self):
        fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_in.setDuration(1000); fade_in.setStartValue(0.0); fade_in.setEndValue(1.0)
        fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_out.setDuration(1000); fade_out.setStartValue(1.0); fade_out.setEndValue(0.0)
        self.anim_group = QSequentialAnimationGroup(self)
        self.anim_group.addAnimation(fade_in)
        self.anim_group.addPause(1000)
        self.anim_group.addAnimation(fade_out)
        self.anim_group.finished.connect(self.on_animation_finished)
        self.anim_group.start()

    def on_animation_finished(self):
        if hasattr(self.parent_window, 'show_scenario'):
            self.parent_window.show_scenario(self.vehicle_type, self.is_handicapped)

class FingerprintAuthentication(BaseScreen):
    def __init__(self, vehicle_type, is_handicapped, fallback_scenario, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.is_handicapped = is_handicapped
        self.fallback_scenario = fallback_scenario
        self.authentication_timer = None
        self.initUI()
        self.start_authentication()

    def initUI(self):
        message = QLabel("Disabled Parking Area"); message.setAlignment(Qt.AlignCenter); message.setStyleSheet(f"font-size: {FONT_SIZES['scenario_title']}pt; color: {SIMPLE_COLORS['text_primary']}; font-weight: bold;")
        fingerprint_info = QLabel("Please proceed with fingerprint authentication"); fingerprint_info.setAlignment(Qt.AlignCenter); fingerprint_info.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {SIMPLE_COLORS['text_secondary']};")
        self.timer_label = QLabel("Automatic assignment to a regular spot in 5 seconds"); self.timer_label.setAlignment(Qt.AlignCenter); self.timer_label.setStyleSheet(f"font-size: {FONT_SIZES['timer']}pt; color: {SIMPLE_COLORS['warning']};")
        
        fingerprint_scanner = QFrame(); fingerprint_scanner.setMinimumHeight(160); fingerprint_scanner.setMaximumWidth(450);
        fingerprint_scanner.setStyleSheet(f"border: 1px solid {SIMPLE_COLORS['tertiary']}; border-radius: 20px; background: {SIMPLE_COLORS['surface']}; margin: 20px;")
        scanner_layout = QVBoxLayout(); scanner_text = QLabel("👆\nPlace your finger on the scanner"); scanner_text.setAlignment(Qt.AlignCenter); scanner_text.setStyleSheet(f"font-size: {FONT_SIZES['scanner_text']}pt; color: {SIMPLE_COLORS['text_secondary']}; font-weight: bold; border: none; background: transparent;"); scanner_layout.addWidget(scanner_text); fingerprint_scanner.setLayout(scanner_layout)

        button_layout = QHBoxLayout(); button_layout.setSpacing(20); success_btn = AnimatedButton("Authentication Success"); success_btn.clicked.connect(self.authentication_success); fallback_btn = AnimatedButton("Use Regular Spot"); fallback_btn.clicked.connect(self.authentication_timeout);
        button_layout.addStretch(); button_layout.addWidget(success_btn); button_layout.addWidget(fallback_btn); button_layout.addStretch()

        self.content_layout.addStretch(1); self.content_layout.addWidget(message); self.content_layout.addWidget(fingerprint_info); self.content_layout.addSpacing(30); self.content_layout.addWidget(fingerprint_scanner, 0, Qt.AlignCenter); self.content_layout.addWidget(self.timer_label); self.content_layout.addLayout(button_layout); self.content_layout.addStretch(1)

    def start_authentication(self):
        self.remaining_time = 5
        self.authentication_timer = QTimer(self)
        self.authentication_timer.timeout.connect(self.update_timer)
        self.authentication_timer.start(1000)

    def update_timer(self):
        self.remaining_time -= 1
        if self.remaining_time > 0:
            self.timer_label.setText(f"Automatic assignment to a regular spot in {self.remaining_time} seconds")
        else:
            self.authentication_timer.stop()
            self.authentication_timeout()

    def authentication_success(self):
        if self.authentication_timer: self.authentication_timer.stop()
        self.send_choice_and_launch('disabled')

    def authentication_timeout(self):
        if self.authentication_timer: self.authentication_timer.stop()
        self.send_choice_and_launch(self.fallback_scenario)

    def send_choice_and_launch(self, parking_spot_type):
        data = {'vehicle_type': self.vehicle_type, 'is_handicapped': self.is_handicapped, 'parking_spot_type': parking_spot_type}
        if hasattr(self.parent_window, 'send_parking_choice'):
            self.parent_window.send_parking_choice(data)
        self.launch_parking_ui()

    def launch_parking_ui(self):
        try:
            script_name = 'parking_ui_testing_5.py'
            subprocess.Popen([sys.executable, script_name])
            QApplication.quit()
        except Exception as e:
            print(f"Error launching parking UI: {e}"); self.go_back_to_home()

    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'): self.parent_window.show_home()

class ElectricVehicleOptions(BaseScreen):
    def __init__(self, vehicle_type, is_handicapped, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.is_handicapped = is_handicapped
        self.initUI()

    def initUI(self):
        message = QLabel("EV Charging Options"); message.setAlignment(Qt.AlignCenter); message.setStyleSheet(f"font-size: {FONT_SIZES['scenario_title']}pt; color: {SIMPLE_COLORS['text_primary']}; font-weight: bold;")
        option_info = QLabel("Please select your desired parking spot"); option_info.setAlignment(Qt.AlignCenter); option_info.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {SIMPLE_COLORS['text_secondary']};")
        
        button_layout = QVBoxLayout(); button_layout.setSpacing(15); button_layout.setAlignment(Qt.AlignCenter)
        normal_btn = AnimatedButton("🅿️ Regular Spot"); normal_btn.clicked.connect(self.select_normal_parking); button_layout.addWidget(normal_btn)
        charging_btn = AnimatedButton("⚡ EV Charging Spot"); charging_btn.clicked.connect(self.select_charging); button_layout.addWidget(charging_btn)

        if self.is_handicapped:
            handicapped_btn = AnimatedButton("♿ Disabled Spot"); handicapped_btn.clicked.connect(self.select_handicapped_parking); button_layout.addWidget(handicapped_btn)

        self.content_layout.addStretch(1); self.content_layout.addWidget(message); self.content_layout.addWidget(option_info); self.content_layout.addSpacing(30); self.content_layout.addLayout(button_layout); self.content_layout.addStretch(1)

    def select_charging(self): self.send_choice_and_launch('electric')
    def select_normal_parking(self): self.send_choice_and_launch('regular')
    def select_handicapped_parking(self):
        if hasattr(self.parent_window, 'show_fingerprint_auth'):
            self.parent_window.show_fingerprint_auth(self.vehicle_type, self.is_handicapped, 'regular')

    def send_choice_and_launch(self, parking_spot_type):
        data = {'vehicle_type': self.vehicle_type, 'is_handicapped': self.is_handicapped, 'parking_spot_type': parking_spot_type}
        if hasattr(self.parent_window, 'send_parking_choice'):
            self.parent_window.send_parking_choice(data)
        self.launch_parking_ui()
    
    def launch_parking_ui(self):
        try:
            script_name = 'parking_ui_testing_5.py'
            subprocess.Popen([sys.executable, script_name])
            QApplication.quit()
        except Exception as e:
            print(f"Error launching parking UI: {e}"); self.go_back_to_home()
            
    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'): self.parent_window.show_home()

class RegularVehicleResult(BaseScreen):
    def __init__(self, vehicle_type, is_handicapped, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.is_handicapped = is_handicapped
        self.initUI()

    def initUI(self):
        message = QLabel("Regular Spot Assigned"); message.setAlignment(Qt.AlignCenter); message.setStyleSheet(f"font-size: {FONT_SIZES['scenario_title']}pt; color: {SIMPLE_COLORS['text_primary']}; font-weight: bold;")
        info = QLabel("The parking gate will open shortly"); info.setAlignment(Qt.AlignCenter); info.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {SIMPLE_COLORS['text_secondary']};")
        
        confirm_btn = AnimatedButton("Confirm"); confirm_btn.clicked.connect(self.confirm_and_launch)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(confirm_btn)
        btn_layout.addStretch()

        self.content_layout.addStretch(1); self.content_layout.addWidget(message); self.content_layout.addWidget(info); self.content_layout.addSpacing(30); self.content_layout.addLayout(btn_layout); self.content_layout.addStretch(1)

    def confirm_and_launch(self):
        data = {'vehicle_type': self.vehicle_type, 'is_handicapped': self.is_handicapped, 'parking_spot_type': 'regular'}
        if hasattr(self.parent_window, 'send_parking_choice'):
            self.parent_window.send_parking_choice(data)
        self.launch_parking_ui()

    def launch_parking_ui(self):
        try:
            script_name = 'parking_ui_testing_5.py'
            subprocess.Popen([sys.executable, script_name])
            QApplication.quit()
        except Exception as e:
            print(f"Error launching parking UI: {e}"); self.go_back_to_home()

    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'): self.parent_window.show_home()

class HyundaiStyleUI(QWidget):
    def __init__(self):
        super().__init__()
        self.wifi_sender = WifiSender(WIFI_CONFIG['target_ip'], WIFI_CONFIG['port'])
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SmartParking System')
        self.resize(1280, 800)
        self.setMinimumSize(1000, 700)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)
        self.stacked_widget = QStackedWidget()
        self.home_screen = SimulationSetupScreen(self)
        self.stacked_widget.addWidget(self.home_screen)
        main_layout.addWidget(self.stacked_widget)
        self.setLayout(main_layout)
        self.setStyleSheet(f"background-color: {SIMPLE_COLORS['background']};")
        self.showMaximized()

    def send_parking_choice(self, choice_data):
        self.wifi_sender.send_data(choice_data)

    def show_transition(self, vehicle_type, is_handicapped):
        transition_screen = TransitionScreen(vehicle_type, is_handicapped, self)
        self.switch_screen(transition_screen)

    def show_scenario(self, vehicle_type, is_handicapped):
        if vehicle_type == 'regular':
            if is_handicapped:
                self.show_fingerprint_auth(vehicle_type, is_handicapped, 'regular')
            else:
                self.show_regular_result(vehicle_type, is_handicapped)
        elif vehicle_type == 'electric':
            self.show_electric_options(vehicle_type, is_handicapped)

    def show_fingerprint_auth(self, vehicle_type, is_handicapped, fallback_scenario):
        fingerprint_screen = FingerprintAuthentication(vehicle_type, is_handicapped, fallback_scenario, self)
        self.switch_screen(fingerprint_screen)

    def show_electric_options(self, vehicle_type, is_handicapped):
        electric_screen = ElectricVehicleOptions(vehicle_type, is_handicapped, self)
        self.switch_screen(electric_screen)

    def show_regular_result(self, vehicle_type, is_handicapped):
        result_screen = RegularVehicleResult(vehicle_type, is_handicapped, self)
        self.switch_screen(result_screen)

    def switch_screen(self, new_screen):
        if self.stacked_widget.currentWidget():
            self.stacked_widget.currentWidget().hide()
        
        while self.stacked_widget.count() > 1:
            widget = self.stacked_widget.widget(1)
            self.stacked_widget.removeWidget(widget)
            widget.deleteLater()
        
        self.stacked_widget.addWidget(new_screen)
        self.stacked_widget.setCurrentWidget(new_screen)

    def show_home(self):
        while self.stacked_widget.count() > 1:
            widget_to_remove = self.stacked_widget.widget(1)
            self.stacked_widget.removeWidget(widget_to_remove)
            widget_to_remove.deleteLater()
        self.stacked_widget.setCurrentIndex(0)

if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    app = QApplication(sys.argv)
    
    font = QFont("Malgun Gothic")
    font.setPointSize(11)
    app.setFont(font)
    app.setStyle('Fusion')

    ex = HyundaiStyleUI()
    sys.exit(app.exec_())

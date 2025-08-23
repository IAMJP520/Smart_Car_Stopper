# 파일명: RSSI_ask.py
# (제공해주신 전체 코드에 아래 send_data_to_rpi 함수와 각 클래스의 함수 호출 부분을 수정한 것입니다.)

import sys
import random
import datetime
import subprocess
import os
import bluetooth # 블루투스 모듈 임포트
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QDialog, QFrame,
                             QStackedWidget, QGridLayout, QProgressBar, QGraphicsOpacityEffect,
                             QButtonGroup)
from PyQt5.QtGui import (QPixmap, QFont, QPainter, QPainterPath, QLinearGradient,
                         QColor, QIcon, QBrush, QPen, QPolygonF)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPointF, QSequentialAnimationGroup

# --- 블루투스 데이터 전송 함수 (새로 추가) ---
def send_data_to_rpi(message):
    """ 주어진 메시지를 라즈베리파이로 전송합니다. """
    # TODO: 여기에 실제 라즈베리파이의 블루투스 MAC 주소를 입력하세요.
    RPI_MAC_ADDRESS = "XX:XX:XX:XX:XX:XX"  
    PORT = 1
    
    print(f"라즈베리파이({RPI_MAC_ADDRESS})로 데이터 전송 시도: '{message}'")
    
    try:
        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        sock.connect((RPI_MAC_ADDRESS, PORT))
        sock.send(message.encode('utf-8'))
        sock.close()
        print("데이터 전송 성공.")
        return True
    except Exception as e:
        print(f"블루투스 통신 오류: {e}")
        # 실제 앱에서는 사용자에게 오류 팝업을 보여줄 수 있습니다.
        return False

# --- 1. 현대차 스타일 컬러 팔레트 및 기본 스타일 (기존 코드와 동일) ---
HYUNDAI_COLORS = {
    'primary': '#002C5F',      # 현대차 딥 블루
    'secondary': '#007FA3',    # 현대차 라이트 블루
    'accent': '#00AAD2',      # 현대차 시안
    'success': '#00C851',      # 그린
    'warning': '#FFB300',      # 앰버
    'background': '#0A0E1A',   # 다크 배경
    'surface': '#1A1E2E',      # 다크 서피스
    'text_primary': '#FFFFFF', # 화이트 텍스트
    'text_secondary': '#B0BEC5', # 라이트 그레이
    'glass': 'rgba(255, 255, 255, 0.1)' # 글래스모피즘
}
FONT_SIZES = {
    'status_bar_location': 12, 'status_bar_date': 11, 'status_bar_time': 28,
    'status_bar_weather': 12, 'status_bar_radio': 11, 'main_title': 32,
    'main_subtitle': 16, 'button': 16, 'toggle_button': 14, 'scenario_title': 26,
    'scenario_subtitle': 16, 'scenario_info': 14, 'scanner_text': 18, 'timer': 14,
    'progress_bar': 12, 'transition_text': 28,
}
# ... (HyundaiBackground, StatusBar, AnimatedButton, ToggleButton, BaseScreen 클래스는 제공해주신 코드와 동일) ...
# ... (코드가 매우 길어 생략합니다. 제공해주신 코드를 그대로 사용하시면 됩니다.) ...


# --- FingerprintAuthentication 클래스 수정 ---
class FingerprintAuthentication(BaseScreen):
    """지문 인식 화면"""
    def __init__(self, vehicle_type, fallback_scenario, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.fallback_scenario = fallback_scenario
        self.authentication_timer = None
        self.initUI()
        self.start_authentication()

    def initUI(self):
        # ... (기존 UI 코드와 동일) ...
        fingerprint_label = QLabel("👆"); fingerprint_label.setAlignment(Qt.AlignCenter); fingerprint_label.setStyleSheet("font-size: 100pt; margin-bottom: 20px;")
        message = QLabel("장애인 주차구역 이용 안내"); message.setAlignment(Qt.AlignCenter); message.setStyleSheet(f"font-size: {FONT_SIZES['scenario_title']}pt; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold;")
        fingerprint_info = QLabel("본인 확인을 위해 지문 인식을 진행해주세요"); fingerprint_info.setAlignment(Qt.AlignCenter); fingerprint_info.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {HYUNDAI_COLORS['text_secondary']};")
        self.timer_label = QLabel("5초 후 일반 구역으로 자동 배정됩니다"); self.timer_label.setAlignment(Qt.AlignCenter); self.timer_label.setStyleSheet(f"font-size: {FONT_SIZES['timer']}pt; color: {HYUNDAI_COLORS['warning']};")
        fingerprint_scanner = QFrame(); fingerprint_scanner.setMinimumHeight(140); fingerprint_scanner.setStyleSheet("border: 3px solid rgba(0, 170, 210, 0.6); border-radius: 25px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(26, 30, 46, 0.9), stop:1 rgba(10, 14, 26, 0.7)); margin: 20px; backdrop-filter: blur(10px);")
        scanner_layout = QVBoxLayout(); scanner_text = QLabel("지문을 스캐너에 올려주세요"); scanner_text.setAlignment(Qt.AlignCenter); scanner_text.setStyleSheet(f"font-size: {FONT_SIZES['scanner_text']}pt; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold;"); scanner_layout.addWidget(scanner_text); fingerprint_scanner.setLayout(scanner_layout)
        button_layout = QHBoxLayout(); button_layout.setSpacing(20); success_btn = AnimatedButton("인증 성공"); success_btn.clicked.connect(self.authentication_success); fallback_btn = AnimatedButton("일반 구역으로"); fallback_btn.clicked.connect(self.authentication_fallback); button_layout.addWidget(success_btn); button_layout.addWidget(fallback_btn)
        self.content_layout.addStretch(1); self.content_layout.addWidget(fingerprint_label); self.content_layout.addWidget(message); self.content_layout.addWidget(fingerprint_info); self.content_layout.addWidget(self.timer_label); self.content_layout.addWidget(fingerprint_scanner); self.content_layout.addLayout(button_layout); self.content_layout.addStretch(1)


    def start_authentication(self):
        self.remaining_time = 5
        self.authentication_timer = QTimer(self)
        self.authentication_timer.timeout.connect(self.update_timer)
        self.authentication_timer.start(1000)

    def update_timer(self):
        self.remaining_time -= 1
        if self.remaining_time > 0:
            self.timer_label.setText(f"{self.remaining_time}초 후 일반 구역으로 자동 배정됩니다")
        else:
            self.authentication_timer.stop()
            self.authentication_fallback() # 시간 초과 시 fallback 실행

    def authentication_success(self):
        if self.authentication_timer: self.authentication_timer.stop()
        message = f"{self.vehicle_type}_handicapped" # "regular_handicapped" 또는 "electric_handicapped"
        send_data_to_rpi(message) # <<< 데이터 전송
        self.launch_external_app()

    def authentication_fallback(self): # timeout을 fallback으로 이름 변경
        if self.authentication_timer: self.authentication_timer.stop()
        message = f"{self.vehicle_type}_normal" # "regular_normal" 또는 "electric_normal"
        send_data_to_rpi(message) # <<< 데이터 전송
        self.launch_external_app()

    def launch_external_app(self):
        # 외부 앱 실행 및 종료 로직 공통화
        try:
            # parking_ui_testing_5.py 가 없으므로, 이 예제에서는 단순히 앱을 종료합니다.
            print("선택 완료. 앱을 종료합니다.")
            QApplication.quit()
        except Exception as e:
            print(f"앱 종료 중 오류 발생: {e}")
            self.go_back_to_home()
            
    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'):
            self.parent_window.show_home()


# --- ElectricVehicleOptions 클래스 수정 ---
class ElectricVehicleOptions(BaseScreen):
    """전기차 옵션 선택 화면"""
    def __init__(self, is_handicapped, parent=None):
        super().__init__(parent)
        self.is_handicapped = is_handicapped
        self.initUI()

    def initUI(self):
        # ... (기존 UI 코드와 동일) ...
        icon_label = QLabel("🔋"); icon_label.setAlignment(Qt.AlignCenter); icon_label.setStyleSheet("font-size: 80pt; margin-bottom: 20px;")
        message = QLabel("전기차 옵션 선택"); message.setAlignment(Qt.AlignCenter); message.setStyleSheet(f"font-size: {FONT_SIZES['scenario_title']}pt; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold;")
        option_info = QLabel("원하시는 주차구역을 선택해주세요"); option_info.setAlignment(Qt.AlignCenter); option_info.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {HYUNDAI_COLORS['text_secondary']};")
        button_layout = QVBoxLayout(); button_layout.setSpacing(20)
        normal_btn = AnimatedButton("🅿️ 일반 주차구역"); normal_btn.clicked.connect(self.select_normal_parking); button_layout.addWidget(normal_btn)
        charging_btn = AnimatedButton("⚡ 전기차 충전구역"); charging_btn.clicked.connect(self.select_charging); button_layout.addWidget(charging_btn)
        if self.is_handicapped:
            handicapped_btn = AnimatedButton("♿ 장애인 전용 주차구역"); handicapped_btn.clicked.connect(self.select_handicapped_parking); button_layout.addWidget(handicapped_btn)
        self.content_layout.addStretch(1); self.content_layout.addWidget(icon_label); self.content_layout.addWidget(message); self.content_layout.addWidget(option_info); self.content_layout.addSpacing(30); self.content_layout.addLayout(button_layout); self.content_layout.addStretch(1)

    def select_charging(self):
        send_data_to_rpi("electric_charging") # <<< 데이터 전송
        self.launch_external_app()
    
    def select_handicapped_parking(self):
        # 지문 인식 화면으로 전환, 데이터는 지문 인식 화면에서 전송됨
        if hasattr(self.parent_window, 'show_fingerprint_auth'):
            self.parent_window.show_fingerprint_auth('electric', 'normal')
            
    def select_normal_parking(self):
        send_data_to_rpi("electric_normal") # <<< 데이터 전송
        self.launch_external_app()
    
    def launch_external_app(self):
        try:
            print("선택 완료. 앱을 종료합니다.")
            QApplication.quit()
        except Exception as e:
            print(f"앱 종료 중 오류 발생: {e}")
            self.go_back_to_home()
            
    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'):
            self.parent_window.show_home()


# --- RegularVehicleResult 클래스 수정 ---
class RegularVehicleResult(BaseScreen):
    """일반 차량 결과 화면"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        # 이 화면이 표시되는 즉시 데이터 전송
        send_data_to_rpi("regular_normal") # <<< 데이터 전송

    def initUI(self):
        # ... (기존 UI 코드와 동일) ...
        success_label = QLabel("✅"); success_label.setAlignment(Qt.AlignCenter); success_label.setStyleSheet("font-size: 80pt; margin-bottom: 20px;")
        message = QLabel("일반 주차구역 배정 완료"); message.setAlignment(Qt.AlignCenter); message.setStyleSheet(f"font-size: {FONT_SIZES['scenario_title']}pt; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold;")
        info = QLabel("주차장 입구가 곧 열립니다"); info.setAlignment(Qt.AlignCenter); info.setStyleSheet(f"font-size: {FONT_SIZES['scenario_subtitle']}pt; color: {HYUNDAI_COLORS['text_secondary']};")
        confirm_btn = AnimatedButton("확인"); confirm_btn.clicked.connect(self.confirm_and_exit) # 함수 이름 변경
        self.content_layout.addStretch(1); self.content_layout.addWidget(success_label); self.content_layout.addWidget(message); self.content_layout.addWidget(info); self.content_layout.addSpacing(30); self.content_layout.addWidget(confirm_btn); self.content_layout.addStretch(1)

    def confirm_and_exit(self):
        print("확인 완료. 앱을 종료합니다.")
        QApplication.quit()

# --- 메인 윈도우 및 실행 코드 (제공해주신 코드와 대부분 동일) ---
# ... (HyundaiStyleUI, TransitionScreen, SimulationSetupScreen 등 나머지 클래스들은 수정 없이 그대로 사용) ...

if __name__ == '__main__':
    if "XX:XX:XX:XX:XX:XX" in send_data_to_rpi.__doc__:
         print("오류: 코드 상단의 'send_data_to_rpi' 함수 내 'RPI_MAC_ADDRESS'를 실제 라즈베리파이 MAC 주소로 변경해주세요.")
    else:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        
        app = QApplication(sys.argv)
        
        font = QFont("Malgun Gothic")
        font.setPointSize(11)
        app.setFont(font)
        app.setStyle('Fusion')

        ex = HyundaiStyleUI()
        sys.exit(app.exec_())
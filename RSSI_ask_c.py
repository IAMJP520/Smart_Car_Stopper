import sys
import random
import datetime
import subprocess
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QDialog, QFrame,
                             QStackedWidget, QGridLayout, QProgressBar)
from PyQt5.QtGui import (QPixmap, QFont, QPainter, QPainterPath, QLinearGradient,
                         QColor, QIcon, QBrush, QPen, QPolygonF)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPointF

# --- 1. 현대차 스타일 컬러 팔레트 및 기본 스타일 ---

HYUNDAI_COLORS = {
    'primary': '#002C5F',      # 현대차 딥 블루
    'secondary': '#007FA3',    # 현대차 라이트 블루
    'accent': '#00AAD2',       # 현대차 시안
    'success': '#00C851',      # 그린
    'warning': '#FFB300',      # 앰버
    'background': '#0A0E1A',   # 다크 배경
    'surface': '#1A1E2E',      # 다크 서피스
    'text_primary': '#FFFFFF', # 화이트 텍스트
    'text_secondary': '#B0BEC5', # 라이트 그레이
    'glass': 'rgba(255, 255, 255, 0.1)' # 글래스모피즘
}

# --- 해상도 독립적인 폰트 크기 (단위: pt) ---
FONT_SIZES = {
    'status_bar_location': 12,
    'status_bar_date': 11,
    'status_bar_time': 28,
    'status_bar_weather': 12,
    'status_bar_radio': 11,
    'main_title': 32,
    'main_subtitle': 16,
    'button': 16,
    'scenario_title': 26,
    'scenario_subtitle': 16,
    'scenario_info': 14,
    'scanner_text': 18,
    'timer': 14,
    'progress_bar': 12,
}


class HyundaiBackground(QWidget):
    """현대차 스타일 배경 위젯 (크기 조절에 반응하도록 수정)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 위젯이 부모 크기에 맞춰 자동으로 조절되도록 설정
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        # 1. 기본 다크 배경
        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0, QColor('#0A0E1A'))
        gradient.setColorAt(0.5, QColor('#1A1E2E'))
        gradient.setColorAt(1, QColor('#0F1419'))
        painter.fillRect(self.rect(), QBrush(gradient))

        # 2. 기하학적 라인 패턴
        painter.setPen(QPen(QColor(0, 170, 210, 30), 1))
        for i in range(0, w, 50):
            painter.drawLine(i, 0, i, h)
        for i in range(0, h, 50):
            painter.drawLine(0, i, w, i)

        # 3. 좌상단 타원형 디자인 (창 크기에 비례하도록 수정)
        painter.setPen(QPen(QColor(0, 170, 210, 80), 2))
        painter.setBrush(QBrush(QColor(0, 170, 210, 20)))
        painter.drawEllipse(QPointF(w * 0.15, h * 0.15), w * 0.12, h * 0.1)
        painter.drawEllipse(QPointF(w * 0.27, h * 0.25), w * 0.1, h * 0.08)

        # 4. 우하단 곡선 디자인 (창 크기에 비례하도록 수정)
        path = QPainterPath()
        path.moveTo(w * 0.7, h)
        path.quadTo(w * 0.9, h * 0.7, w, h * 0.85)
        path.lineTo(w, h)
        path.closeSubpath()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 123, 163, 40)))
        painter.drawPath(path)

class StatusBar(QWidget):
    """상단 상태 바 (시간, 날씨, 라디오 등)"""
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

        # 왼쪽: 위치 정보
        location_layout = QHBoxLayout()
        location_icon = QLabel("📍")
        location_icon.setStyleSheet(f"font-size: {FONT_SIZES['status_bar_location']}pt; color: white;")

        self.location_label = QLabel("Seocho-gu, Seoul")
        self.location_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_primary']};
                font-size: {FONT_SIZES['status_bar_location']}pt;
                font-weight: bold;
            }}
        """)
        location_layout.addWidget(location_icon)
        location_layout.addWidget(self.location_label)
        location_layout.addStretch()

        # 중앙: 시간
        time_layout = QVBoxLayout()
        time_layout.setSpacing(0)
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_secondary']};
                font-size: {FONT_SIZES['status_bar_date']}pt;
            }}
        """)
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_primary']};
                font-size: {FONT_SIZES['status_bar_time']}pt;
                font-weight: bold;
            }}
        """)
        time_layout.addWidget(self.date_label)
        time_layout.addWidget(self.time_label)

        # 오른쪽: 날씨와 라디오
        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)
        weather_layout = QHBoxLayout()
        weather_layout.addStretch()
        temp_label = QLabel("26°C")
        temp_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_primary']};
                font-size: {FONT_SIZES['status_bar_weather']}pt;
                font-weight: bold;
            }}
        """)
        weather_icon = QLabel("🌙")
        weather_icon.setStyleSheet(f"font-size: {FONT_SIZES['status_bar_weather']}pt;")
        weather_layout.addWidget(temp_label)
        weather_layout.addWidget(weather_icon)

        radio_layout = QHBoxLayout()
        radio_layout.addStretch()
        radio_label = QLabel("FM 87.5")
        radio_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_secondary']};
                font-size: {FONT_SIZES['status_bar_radio']}pt;
            }}
        """)
        radio_layout.addWidget(radio_label)
        right_layout.addLayout(weather_layout)
        right_layout.addLayout(radio_layout)

        # 메인 레이아웃에 추가
        layout.addLayout(location_layout, 1)
        layout.addLayout(time_layout, 2)
        layout.addLayout(right_layout, 1)

        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 rgba(26, 30, 46, 0.9),
                                stop:1 rgba(10, 14, 26, 0.7));
                border-bottom: 1px solid rgba(0, 170, 210, 0.3);
            }
        """)

    def update_time(self):
        now = datetime.datetime.now()
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        date_str = f"{now.month}월 {now.day}일 ({weekdays[now.weekday()]})"
        self.date_label.setText(date_str)
        time_str = now.strftime("%H:%M")
        self.time_label.setText(time_str)

class AnimatedButton(QPushButton):
    """애니메이션 효과가 있는 현대차 스타일 버튼"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(70)
        self.setCursor(Qt.PointingHandCursor)
        self.default_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 44, 95, 0.8),
                    stop:1 rgba(0, 127, 163, 0.8));
                color: white;
                border: 2px solid rgba(0, 170, 210, 0.5);
                border-radius: 25px;
                font-size: {FONT_SIZES['button']}pt;
                font-weight: bold;
                padding: 15px 30px;
                backdrop-filter: blur(10px);
            }}
        """
        self.hover_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(0, 170, 210, 0.9),
                    stop:1 rgba(0, 127, 163, 0.9));
                color: white;
                border: 2px solid rgba(0, 170, 210, 0.8);
                border-radius: 25px;
                font-size: {FONT_SIZES['button']}pt;
                font-weight: bold;
                padding: 15px 30px;
                backdrop-filter: blur(10px);
            }}
        """
        self.setStyleSheet(self.default_style)

    def enterEvent(self, event):
        self.setStyleSheet(self.hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.default_style)
        super().leaveEvent(event)

# --- 공통 화면 레이아웃 클래스 ---
class BaseScreen(QWidget):
    """화면들의 공통적인 배경과 레이아웃 구조를 정의하는 기본 클래스"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

        # 전체 화면을 덮는 배경 위젯
        self.background = HyundaiBackground(self)

        # 컨텐츠를 담을 메인 위젯 (투명)
        self.main_widget = QWidget(self)
        self.main_widget.setStyleSheet("background: transparent;")

        # 메인 위젯의 레이아웃
        self.content_layout = QVBoxLayout(self.main_widget)
        self.content_layout.setSpacing(30)
        self.content_layout.setContentsMargins(80, 80, 80, 80)

        # 전체 레이아웃 설정
        full_layout = QVBoxLayout(self)
        full_layout.setContentsMargins(0, 0, 0, 0)
        full_layout.addWidget(self.main_widget)
        self.setLayout(full_layout)

    def resizeEvent(self, event):
        # 창 크기가 변경될 때 배경 위젯의 크기도 함께 조절
        self.background.resize(event.size())
        super().resizeEvent(event)

# --- 2. 1단계: 차량 타입 선택 화면 ---
class VehicleTypeSelector(BaseScreen):
    """1단계: 차량 타입을 선택하는 화면 (일반/전기차)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        title = QLabel("SmartParking System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['main_title']}pt;
                font-weight: bold;
                color: {HYUNDAI_COLORS['text_primary']};
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }}
        """)

        subtitle = QLabel("차량 유형을 선택해주세요")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['main_subtitle']}pt;
                color: {HYUNDAI_COLORS['text_secondary']};
                margin-bottom: 20px;
            }}
        """)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(25)
        regular_btn = AnimatedButton("🚗 일반 차량")
        regular_btn.clicked.connect(lambda: self.select_vehicle_type('regular'))
        ev_btn = AnimatedButton("🔋 전기차")
        ev_btn.clicked.connect(lambda: self.select_vehicle_type('electric'))
        button_layout.addWidget(regular_btn)
        button_layout.addWidget(ev_btn)

        self.content_layout.addStretch(2)
        self.content_layout.addWidget(title)
        self.content_layout.addWidget(subtitle)
        self.content_layout.addLayout(button_layout)
        self.content_layout.addStretch(3)

    def select_vehicle_type(self, vehicle_type):
        if hasattr(self.parent_window, 'show_accessibility_selector'):
            self.parent_window.show_accessibility_selector(vehicle_type)

# --- 3. 2단계: 장애 유무 선택 화면 ---
class AccessibilitySelector(BaseScreen):
    """2단계: 장애 유무를 선택하는 화면"""
    def __init__(self, vehicle_type, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.initUI()

    def initUI(self):
        vehicle_icon = "🚗" if self.vehicle_type == 'regular' else "🔋"
        vehicle_name = "일반 차량" if self.vehicle_type == 'regular' else "전기차"
        title = QLabel(f"{vehicle_icon} {vehicle_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_title']}pt;
                font-weight: bold;
                color: {HYUNDAI_COLORS['text_primary']};
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }}
        """)

        subtitle = QLabel("장애인 주차구역 이용 여부를 선택해주세요")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_subtitle']}pt;
                color: {HYUNDAI_COLORS['text_secondary']};
                margin-bottom: 20px;
            }}
        """)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(25)
        handicapped_btn = AnimatedButton("♿ 장애인 전용 주차구역 이용")
        handicapped_btn.clicked.connect(lambda: self.select_accessibility(True))
        regular_btn = AnimatedButton("🅿️ 일반 주차구역 이용")
        regular_btn.clicked.connect(lambda: self.select_accessibility(False))
        button_layout.addWidget(handicapped_btn)
        button_layout.addWidget(regular_btn)

        back_btn = AnimatedButton("← 뒤로가기")
        back_btn.setMinimumHeight(50)
        back_btn.clicked.connect(self.go_back)

        self.content_layout.addStretch(2)
        self.content_layout.addWidget(title)
        self.content_layout.addWidget(subtitle)
        self.content_layout.addLayout(button_layout)
        self.content_layout.addSpacing(40)
        self.content_layout.addWidget(back_btn)
        self.content_layout.addStretch(3)

    def select_accessibility(self, is_handicapped):
        if hasattr(self.parent_window, 'show_scenario'):
            self.parent_window.show_scenario(self.vehicle_type, is_handicapped)

    def go_back(self):
        if hasattr(self.parent_window, 'show_home'):
            self.parent_window.show_home()

# --- 4. 시나리오별 화면들 ---
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
        fingerprint_label = QLabel("👆")
        fingerprint_label.setAlignment(Qt.AlignCenter)
        fingerprint_label.setStyleSheet("font-size: 100pt; margin-bottom: 20px;")

        message = QLabel("장애인 주차구역 이용 안내")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_title']}pt;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
            }}
        """)

        fingerprint_info = QLabel("본인 확인을 위해 지문 인식을 진행해주세요")
        fingerprint_info.setAlignment(Qt.AlignCenter)
        fingerprint_info.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_subtitle']}pt;
                color: {HYUNDAI_COLORS['text_secondary']};
            }}
        """)

        self.timer_label = QLabel("5초 후 일반 구역으로 자동 배정됩니다")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet(f"font-size: {FONT_SIZES['timer']}pt; color: {HYUNDAI_COLORS['warning']};")

        fingerprint_scanner = QFrame()
        fingerprint_scanner.setMinimumHeight(140)
        fingerprint_scanner.setStyleSheet(f"""
            QFrame {{
                border: 3px solid rgba(0, 170, 210, 0.6);
                border-radius: 25px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(26, 30, 46, 0.9), stop:1 rgba(10, 14, 26, 0.7));
                margin: 20px;
                backdrop-filter: blur(10px);
            }}
        """)
        scanner_layout = QVBoxLayout()
        scanner_text = QLabel("지문을 스캐너에 올려주세요")
        scanner_text.setAlignment(Qt.AlignCenter)
        scanner_text.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scanner_text']}pt;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
            }}
        """)
        scanner_layout.addWidget(scanner_text)
        fingerprint_scanner.setLayout(scanner_layout)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        success_btn = AnimatedButton("인증 성공")
        success_btn.clicked.connect(self.authentication_success)
        fallback_btn = AnimatedButton("일반 구역으로")
        fallback_btn.clicked.connect(self.authentication_timeout)
        button_layout.addWidget(success_btn)
        button_layout.addWidget(fallback_btn)

        self.content_layout.addStretch(1)
        self.content_layout.addWidget(fingerprint_label)
        self.content_layout.addWidget(message)
        self.content_layout.addWidget(fingerprint_info)
        self.content_layout.addWidget(self.timer_label)
        self.content_layout.addWidget(fingerprint_scanner)
        self.content_layout.addLayout(button_layout)
        self.content_layout.addStretch(1)

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
            self.authentication_timeout()

    def authentication_success(self):
        if self.authentication_timer:
            self.authentication_timer.stop()
        self.launch_parking_ui()

    def authentication_timeout(self):
        if self.authentication_timer:
            self.authentication_timer.stop()
        self.launch_parking_ui()

    def launch_parking_ui(self):
        try:
            subprocess.Popen([sys.executable, 'parking_ui_testing_darkblue.py'])
            QApplication.quit()
        except FileNotFoundError:
            print("parking_ui_testing_darkblue.py 파일을 찾을 수 없습니다.")
            self.go_back_to_home()
        except Exception as e:
            print(f"parking_ui_testing_darkblue.py 실행 중 오류 발생: {e}")
            self.go_back_to_home()

    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'):
            self.parent_window.show_home()

class ElectricVehicleOptions(BaseScreen):
    """전기차 옵션 선택 화면"""
    def __init__(self, is_handicapped, parent=None):
        super().__init__(parent)
        self.is_handicapped = is_handicapped
        self.battery_level = random.randint(20, 95)
        self.initUI()

    def initUI(self):
        battery_label = QLabel("🔋")
        battery_label.setAlignment(Qt.AlignCenter)
        battery_label.setStyleSheet("font-size: 80pt; margin-bottom: 20px;")

        message = QLabel(f"현재 배터리 용량: {self.battery_level}%")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_title']}pt;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
            }}
        """)

        option_info_text = "원하시는 주차구역을 선택해주세요" if self.is_handicapped else "충전이 필요하신가요?"
        option_info = QLabel(option_info_text)
        option_info.setAlignment(Qt.AlignCenter)
        option_info.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_subtitle']}pt;
                color: {HYUNDAI_COLORS['text_secondary']};
            }}
        """)

        battery_bar = QProgressBar()
        battery_bar.setRange(0, 100)
        battery_bar.setValue(self.battery_level)
        battery_bar.setTextVisible(False)
        battery_bar.setMinimumHeight(30)
        battery_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {HYUNDAI_COLORS['surface']};
                border-radius: 15px;
                background: rgba(26, 30, 46, 0.8);
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00C851, stop:1 #69F0AE);
                border-radius: 14px;
            }}
        """)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(20)
        charging_btn = AnimatedButton("⚡ 전기차 충전구역")
        charging_btn.clicked.connect(self.select_charging)
        button_layout.addWidget(charging_btn)

        if self.is_handicapped:
            handicapped_btn = AnimatedButton("♿ 장애인 전용 주차구역")
            handicapped_btn.clicked.connect(self.select_handicapped_parking)
            button_layout.addWidget(handicapped_btn)
        else:
            normal_btn = AnimatedButton("🅿️ 일반 주차구역")
            normal_btn.clicked.connect(self.select_normal_parking)
            button_layout.addWidget(normal_btn)

        self.content_layout.addStretch(1)
        self.content_layout.addWidget(battery_label)
        self.content_layout.addWidget(message)
        self.content_layout.addWidget(option_info)
        self.content_layout.addWidget(battery_bar)
        self.content_layout.addSpacing(20)
        self.content_layout.addLayout(button_layout)
        self.content_layout.addStretch(1)

    def select_charging(self):
        self.launch_parking_ui()

    def select_handicapped_parking(self):
        if hasattr(self.parent_window, 'show_fingerprint_auth'):
            self.parent_window.show_fingerprint_auth('electric', 'normal')

    def select_normal_parking(self):
        self.launch_parking_ui()

    def launch_parking_ui(self):
        try:
            subprocess.Popen([sys.executable, 'parking_ui_testing_darkblue.py'])
            QApplication.quit()
        except FileNotFoundError:
            print("parking_ui_testing_darkblue.py 파일을 찾을 수 없습니다.")
            self.go_back_to_home()
        except Exception as e:
            print(f"parking_ui_testing_darkblue.py 실행 중 오류 발생: {e}")
            self.go_back_to_home()

    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'):
            self.parent_window.show_home()

class RegularVehicleResult(BaseScreen):
    """일반 차량 결과 화면"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        success_label = QLabel("✅")
        success_label.setAlignment(Qt.AlignCenter)
        success_label.setStyleSheet("font-size: 80pt; margin-bottom: 20px;")

        message = QLabel("일반 주차구역 배정 완료")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_title']}pt;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
            }}
        """)

        info = QLabel("주차장 입구가 곧 열립니다")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet(f"""
            QLabel {{
                font-size: {FONT_SIZES['scenario_subtitle']}pt;
                color: {HYUNDAI_COLORS['text_secondary']};
            }}
        """)

        confirm_btn = AnimatedButton("확인")
        confirm_btn.clicked.connect(self.launch_parking_ui)

        self.content_layout.addStretch(1)
        self.content_layout.addWidget(success_label)
        self.content_layout.addWidget(message)
        self.content_layout.addWidget(info)
        self.content_layout.addSpacing(30)
        self.content_layout.addWidget(confirm_btn)
        self.content_layout.addStretch(1)

    def launch_parking_ui(self):
        try:
            subprocess.Popen([sys.executable, 'parking_ui_testing_darkblue.py'])
            QApplication.quit()
        except FileNotFoundError:
            print("parking_ui_testing_darkblue.py 파일을 찾을 수 없습니다.")
            self.go_back_to_home()
        except Exception as e:
            print(f"parking_ui_testing_darkblue.py 실행 중 오류 발생: {e}")
            self.go_back_to_home()

    def go_back_to_home(self):
        if hasattr(self.parent_window, 'show_home'):
            self.parent_window.show_home()

# --- 5. 메인 윈도우 ---
class HyundaiStyleUI(QWidget):
    """현대차 스타일의 메인 UI"""
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('HYUNDAI SmartParking System')
        # 고정 크기 대신 초기 크기와 최소 크기 설정
        self.resize(1280, 800)
        self.setMinimumSize(1000, 700)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.status_bar = StatusBar()
        # 상태바의 고정 높이를 제거하여 내용에 맞게 자동 조절되도록 수정
        main_layout.addWidget(self.status_bar)

        self.stacked_widget = QStackedWidget()
        self.home_screen = VehicleTypeSelector(self)
        self.stacked_widget.addWidget(self.home_screen)
        main_layout.addWidget(self.stacked_widget)

        self.setLayout(main_layout)
        self.setStyleSheet(f"background-color: {HYUNDAI_COLORS['background']};")
        self.showMaximized()

    def show_accessibility_selector(self, vehicle_type):
        accessibility_screen = AccessibilitySelector(vehicle_type, self)
        self.switch_screen(accessibility_screen)

    def show_scenario(self, vehicle_type, is_handicapped):
        if vehicle_type == 'regular':
            if is_handicapped:
                # 시나리오 1: 일반차량/장애O - 지문인식
                self.show_fingerprint_auth('regular', 'normal')
            else:
                # 시나리오 2: 일반차량/장애X - 바로 일반구역
                self.show_regular_result()
        elif vehicle_type == 'electric':
            # 시나리오 3 & 4: 전기차 - 옵션 선택
            self.show_electric_options(is_handicapped)

    def show_fingerprint_auth(self, vehicle_type, fallback_scenario):
        fingerprint_screen = FingerprintAuthentication(vehicle_type, fallback_scenario, self)
        self.switch_screen(fingerprint_screen)

    def show_electric_options(self, is_handicapped):
        electric_screen = ElectricVehicleOptions(is_handicapped, self)
        self.switch_screen(electric_screen)

    def show_regular_result(self):
        result_screen = RegularVehicleResult(self)
        self.switch_screen(result_screen)

    def switch_screen(self, new_screen):
        """새로운 화면으로 전환하는 헬퍼 함수"""
        # 이전 화면을 제거하여 메모리 누수를 방지
        if self.stacked_widget.count() > 1:
            old_widget = self.stacked_widget.widget(1)
            self.stacked_widget.removeWidget(old_widget)
            old_widget.deleteLater()
        
        self.stacked_widget.addWidget(new_screen)
        self.stacked_widget.setCurrentWidget(new_screen)

    def show_home(self):
        """홈 화면으로 돌아가기"""
        # 현재 화면을 제거하고 홈으로 전환
        if self.stacked_widget.currentIndex() != 0:
            current_widget = self.stacked_widget.currentWidget()
            self.stacked_widget.removeWidget(current_widget)
            current_widget.deleteLater()
        self.stacked_widget.setCurrentIndex(0)

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # --- 고해상도(HiDPI) 디스플레이 지원 설정 ---
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # 애플리케이션 전체 폰트 설정 (한국어 지원 폰트)
    font = QFont("Malgun Gothic")
    font.setPointSize(11) # 기본 포인트 크기 설정
    app.setFont(font)

    # 다크 테마 설정
    app.setStyle('Fusion')

    ex = HyundaiStyleUI()
    sys.exit(app.exec_())

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

class HyundaiBackground(QWidget):
    """현대차 스타일 배경 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(1000, 700)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. 기본 다크 배경
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor('#0A0E1A'))
        gradient.setColorAt(0.5, QColor('#1A1E2E'))
        gradient.setColorAt(1, QColor('#0F1419'))
        painter.fillRect(self.rect(), QBrush(gradient))
        
        # 2. 기하학적 라인 패턴 (현대차 스타일)
        painter.setPen(QPen(QColor(0, 170, 210, 30), 1))
        
        # 격자 패턴
        for i in range(0, self.width(), 50):
            painter.drawLine(i, 0, i, self.height())
        for i in range(0, self.height(), 50):
            painter.drawLine(0, i, self.width(), i)
            
        # 3. 현대차 로고 영역 표현 (좌상단)
        painter.setPen(QPen(QColor(0, 170, 210, 80), 2))
        painter.setBrush(QBrush(QColor(0, 170, 210, 20)))
        
        # 타원형 디자인 요소들
        painter.drawEllipse(50, 50, 200, 100)
        painter.drawEllipse(200, 150, 150, 75)
        
        # 4. 우하단 곡선 디자인
        path = QPainterPath()
        path.moveTo(self.width() - 300, self.height())
        path.quadTo(self.width() - 100, self.height() - 200, self.width(), self.height() - 100)
        path.lineTo(self.width(), self.height())
        path.closeSubpath()
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 123, 163, 40)))
        painter.drawPath(path)

class StatusBar(QWidget):
    """상단 상태 바 (시간, 날씨, 라디오 등)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
        # 1초마다 시간 업데이트
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        
    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(30, 15, 30, 15)
        
        # 왼쪽: 위치 정보
        location_layout = QHBoxLayout()
        location_icon = QLabel("📍")
        location_icon.setStyleSheet("font-size: 16px; color: white;")
        
        self.location_label = QLabel("Seocho-gu, Seoul")
        self.location_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        
        location_layout.addWidget(location_icon)
        location_layout.addWidget(self.location_label)
        location_layout.addStretch()
        
        # 중앙: 시간
        time_layout = QVBoxLayout()
        time_layout.setSpacing(0)
        
        # 날짜
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_secondary']};
                font-size: 12px;
            }}
        """)
        
        # 시간
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_primary']};
                font-size: 32px;
                font-weight: bold;
            }}
        """)
        
        time_layout.addWidget(self.date_label)
        time_layout.addWidget(self.time_label)
        
        # 오른쪽: 날씨와 라디오
        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)
        
        # 날씨
        weather_layout = QHBoxLayout()
        weather_layout.addStretch()
        
        temp_label = QLabel("26°C")
        temp_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_primary']};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        
        weather_icon = QLabel("🌙")
        weather_icon.setStyleSheet("font-size: 16px;")
        
        weather_layout.addWidget(temp_label)
        weather_layout.addWidget(weather_icon)
        
        # 라디오
        radio_layout = QHBoxLayout()
        radio_layout.addStretch()
        
        radio_label = QLabel("FM 87.5")
        radio_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_COLORS['text_secondary']};
                font-size: 12px;
            }}
        """)
        
        radio_layout.addWidget(radio_label)
        
        right_layout.addLayout(weather_layout)
        right_layout.addLayout(radio_layout)
        
        # 메인 레이아웃에 추가
        layout.addLayout(location_layout)
        layout.addStretch()
        layout.addLayout(time_layout)
        layout.addStretch()
        layout.addLayout(right_layout)
        
        self.setLayout(layout)
        self.update_time()
        
        # 스타일 설정
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(26, 30, 46, 0.9),
                    stop:1 rgba(10, 14, 26, 0.7));
                border-bottom: 1px solid rgba(0, 170, 210, 0.3);
            }}
        """)
        
    def update_time(self):
        """시간 업데이트"""
        now = datetime.datetime.now()
        
        # 날짜 (한국어)
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        date_str = f"{now.month}월 {now.day}일 ({weekdays[now.weekday()]})"
        self.date_label.setText(date_str)
        
        # 시간
        time_str = now.strftime("%H:%M")
        am_pm = "AM" if now.hour < 12 else "PM"
        self.time_label.setText(f"{time_str} {am_pm}")

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
                font-size: 18px;
                font-weight: bold;
                padding: 20px 40px;
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
                font-size: 18px;
                font-weight: bold;
                padding: 20px 40px;
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

# --- 2. 차량 타입 선택 화면 ---

class VehicleTypeSelector(QWidget):
    """차량 타입을 선택하는 초기 화면"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.initUI()
        
    def initUI(self):
        # 배경 설정
        background = HyundaiBackground(self)
        
        # 메인 컨텐츠
        main_widget = QWidget()
        main_widget.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout()
        layout.setSpacing(40)
        layout.setContentsMargins(80, 120, 80, 80)
        
        # 타이틀
        title = QLabel("SmartParking System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 36px;
                font-weight: bold;
                color: {HYUNDAI_COLORS['text_primary']};
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }}
        """)
        
        # 서브타이틀
        subtitle = QLabel("차량 유형을 선택해주세요")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                color: {HYUNDAI_COLORS['text_secondary']};
                margin-bottom: 40px;
            }}
        """)
        
        # 차량 타입 버튼들
        button_layout = QVBoxLayout()
        button_layout.setSpacing(25)
        
        # 일반 차량 버튼
        regular_btn = AnimatedButton("🚗 일반 차량")
        regular_btn.clicked.connect(lambda: self.select_vehicle_type('regular'))
        
        # 전기차 버튼
        ev_btn = AnimatedButton("🔋 전기차")
        ev_btn.clicked.connect(lambda: self.select_vehicle_type('electric'))
        
        # 장애인 차량 버튼
        handicapped_btn = AnimatedButton("♿ 장애인 차량")
        handicapped_btn.clicked.connect(lambda: self.select_vehicle_type('handicapped'))
        
        button_layout.addWidget(regular_btn)
        button_layout.addWidget(ev_btn)
        button_layout.addWidget(handicapped_btn)
        
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(button_layout)
        layout.addStretch(1)
        
        main_widget.setLayout(layout)
        
        # 전체 레이아웃
        final_layout = QVBoxLayout()
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(main_widget)
        
        self.setLayout(final_layout)
        
    def select_vehicle_type(self, vehicle_type):
        """차량 타입 선택 후 메인 프로세스로 이동"""
        if hasattr(self.parent_window, 'show_main_process'):
            self.parent_window.show_main_process(vehicle_type)

# --- 3. 메인 프로세스 화면들 ---

class ProcessingScreen(QWidget):
    """차량 처리 중 화면"""
    def __init__(self, vehicle_type, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.parent_window = parent
        self.initUI()
        self.start_processing()
        
    def initUI(self):
        # 배경 설정
        background = HyundaiBackground(self)
        
        main_widget = QWidget()
        main_widget.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout()
        layout.setSpacing(50)
        layout.setContentsMargins(100, 120, 100, 100)
        
        # 차량 아이콘
        icon_label = QLabel()
        icon_text = "🚗" if self.vehicle_type == 'regular' else "🔋" if self.vehicle_type == 'electric' else "♿"
        icon_label.setText(icon_text)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                font-size: 100px;
                margin-bottom: 30px;
            }
        """)
        
        # 처리 중 메시지
        self.status_label = QLabel("차량 정보를 확인하고 있습니다...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 26px;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
                margin-bottom: 40px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }}
        """)
        
        # 진행률 표시바 (현대차 스타일)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMinimumHeight(35)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 17px;
                background: rgba(26, 30, 46, 0.8);
                color: white;
                text-align: center;
                font-size: 16px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {HYUNDAI_COLORS['accent']}, 
                    stop:1 {HYUNDAI_COLORS['secondary']});
                border-radius: 17px;
                margin: 2px;
            }}
        """)
        
        layout.addStretch(1)
        layout.addWidget(icon_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch(1)
        
        main_widget.setLayout(layout)
        
        final_layout = QVBoxLayout()
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(main_widget)
        
        self.setLayout(final_layout)
        
    def start_processing(self):
        """처리 시뮬레이션 시작"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.progress = 0
        self.timer.start(60)  # 60ms마다 업데이트
        
    def update_progress(self):
        """진행률 업데이트"""
        self.progress += 2
        self.progress_bar.setValue(self.progress)
        
        if self.progress >= 100:
            self.timer.stop()
            # 차량 타입에 따른 결과 화면으로 이동
            QTimer.singleShot(500, self.show_result)
            
    def show_result(self):
        """결과 화면 표시"""
        if hasattr(self.parent_window, 'show_result_screen'):
            self.parent_window.show_result_screen(self.vehicle_type)

class ResultScreen(QWidget):
    """결과 표시 화면"""
    def __init__(self, vehicle_type, parent=None):
        super().__init__(parent)
        self.vehicle_type = vehicle_type
        self.parent_window = parent
        self.initUI()
        
    def initUI(self):
        # 배경 설정
        background = HyundaiBackground(self)
        
        main_widget = QWidget()
        main_widget.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout()
        layout.setSpacing(40)
        layout.setContentsMargins(80, 120, 80, 80)
        
        # 결과에 따른 컨텐츠 생성
        if self.vehicle_type == 'regular':
            self.create_regular_result(layout)
        elif self.vehicle_type == 'electric':
            self.create_electric_result(layout)
        elif self.vehicle_type == 'handicapped':
            self.create_handicapped_result(layout)
            
        main_widget.setLayout(layout)
        
        final_layout = QVBoxLayout()
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(main_widget)
        
        self.setLayout(final_layout)
        
    def create_regular_result(self, layout):
        """일반 차량 결과"""
        # 성공 아이콘
        success_label = QLabel("✅")
        success_label.setAlignment(Qt.AlignCenter)
        success_label.setStyleSheet("font-size: 80px; margin-bottom: 30px;")
        
        # 메시지
        message = QLabel("차량 확인이 완료되었습니다")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"""
            QLabel {{
                font-size: 28px;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }}
        """)
        
        # 상세 정보
        info = QLabel("주차장 입구가 곧 열립니다")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                color: {HYUNDAI_COLORS['text_secondary']};
            }}
        """)
        
        # 확인 버튼
        confirm_btn = AnimatedButton("확인")
        confirm_btn.clicked.connect(self.launch_parking_ui)
        
        layout.addStretch(1)
        layout.addWidget(success_label)
        layout.addWidget(message)
        layout.addWidget(info)
        layout.addWidget(confirm_btn)
        layout.addStretch(1)
        
    def launch_parking_ui(self):
        """parking_ui_testing_2.py 실행 후 현재 창 종료"""
        try:
            # parking_ui_testing_2.py 실행
            subprocess.Popen([sys.executable, 'parking_ui_testing_2.py'])
            # 현재 애플리케이션 종료
            QApplication.quit()
        except FileNotFoundError:
            print("parking_ui_testing_2.py 파일을 찾을 수 없습니다.")
            # 파일이 없으면 기본 동작 (홈으로 돌아가기)
            self.go_back_to_home()
        except Exception as e:
            print(f"parking_ui_testing_2.py 실행 중 오류 발생: {e}")
            self.go_back_to_home()
        
    def create_electric_result(self, layout):
        """전기차 결과"""
        # 배터리 아이콘
        battery_label = QLabel("🔋")
        battery_label.setAlignment(Qt.AlignCenter)
        battery_label.setStyleSheet("font-size: 80px; margin-bottom: 30px;")
        
        # 배터리 정보
        battery_level = random.randint(20, 95)
        message = QLabel(f"현재 배터리 용량: {battery_level}%")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"""
            QLabel {{
                font-size: 28px;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }}
        """)
        
        # 충전소 안내
        charging_info = QLabel("전기차 충전구역으로 안내해드립니다")
        charging_info.setAlignment(Qt.AlignCenter)
        charging_info.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                color: {HYUNDAI_COLORS['text_secondary']};
                margin-bottom: 30px;
            }}
        """)
        
        # 배터리 시각적 표시
        battery_bar = QProgressBar()
        battery_bar.setRange(0, 100)
        battery_bar.setValue(battery_level)
        battery_bar.setMinimumHeight(30)
        battery_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 15px;
                background: rgba(26, 30, 46, 0.8);
                color: white;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00C851, stop:1 #69F0AE);
                border-radius: 15px;
                margin: 2px;
            }}
        """)
        
        # 버튼들
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        normal_parking_btn = AnimatedButton("일반 주차")
        charging_parking_btn = AnimatedButton("충전 주차")
        
        normal_parking_btn.clicked.connect(self.launch_parking_ui)
        charging_parking_btn.clicked.connect(self.launch_parking_ui)
        
        button_layout.addWidget(normal_parking_btn)
        button_layout.addWidget(charging_parking_btn)
        
        layout.addStretch(1)
        layout.addWidget(battery_label)
        layout.addWidget(message)
        layout.addWidget(charging_info)
        layout.addWidget(battery_bar)
        layout.addLayout(button_layout)
        layout.addStretch(1)
        
    def create_handicapped_result(self, layout):
        """장애인 차량 결과"""
        # 지문 인식 아이콘
        fingerprint_label = QLabel("👆")
        fingerprint_label.setAlignment(Qt.AlignCenter)
        fingerprint_label.setStyleSheet("font-size: 80px; margin-bottom: 30px;")
        
        # 안내 메시지
        message = QLabel("장애인 주차구역 이용 안내")
        message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"""
            QLabel {{
                font-size: 28px;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }}
        """)
        
        # 지문 인식 안내
        fingerprint_info = QLabel("본인 확인을 위해 지문 인식을 진행해주세요")
        fingerprint_info.setAlignment(Qt.AlignCenter)
        fingerprint_info.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                color: {HYUNDAI_COLORS['text_secondary']};
                margin-bottom: 30px;
            }}
        """)
        
        # 지문 인식기 UI
        fingerprint_scanner = QFrame()
        fingerprint_scanner.setMinimumHeight(140)
        fingerprint_scanner.setStyleSheet(f"""
            QFrame {{
                border: 3px solid rgba(0, 170, 210, 0.6);
                border-radius: 25px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(26, 30, 46, 0.9), 
                    stop:1 rgba(10, 14, 26, 0.7));
                margin: 20px;
                backdrop-filter: blur(10px);
            }}
        """)
        
        scanner_layout = QVBoxLayout()
        scanner_text = QLabel("지문을 스캐너에 올려주세요")
        scanner_text.setAlignment(Qt.AlignCenter)
        scanner_text.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                color: {HYUNDAI_COLORS['text_primary']};
                font-weight: bold;
            }}
        """)
        scanner_layout.addWidget(scanner_text)
        fingerprint_scanner.setLayout(scanner_layout)
        
        # 확인 버튼
        confirm_btn = AnimatedButton("인증 완료")
        confirm_btn.clicked.connect(self.launch_parking_ui)
        
        layout.addStretch(1)
        layout.addWidget(fingerprint_label)
        layout.addWidget(message)
        layout.addWidget(fingerprint_info)
        layout.addWidget(fingerprint_scanner)
        layout.addWidget(confirm_btn)
        layout.addStretch(1)
        
    def launch_parking_ui(self):
        """parking_ui_testing_2.py 실행 후 현재 창 종료"""
        try:
            # parking_ui_testing_2.py 실행
            subprocess.Popen([sys.executable, 'parking_ui_testing_darkblue.py'])
            # 현재 애플리케이션 종료
            QApplication.quit()
        except FileNotFoundError:
            print("parking_ui_testing_darkblue.py 파일을 찾을 수 없습니다.")
            # 파일이 없으면 기본 동작 (홈으로 돌아가기)
            self.go_back_to_home()
        except Exception as e:
            print(f"parking_ui_testing_darkblue.py 실행 중 오류 발생: {e}")
            self.go_back_to_home()
        
    def go_back_to_home(self):
        """홈으로 돌아가기"""
        if hasattr(self.parent_window, 'show_home'):
            self.parent_window.show_home()

# --- 4. 메인 윈도우 ---

class HyundaiStyleUI(QWidget):
    """현대차 스타일의 메인 UI"""
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('HYUNDAI SmartParking System')
        self.setGeometry(150, 150, 1000, 700)
        self.setFixedSize(1000, 700)  # 고정 크기
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 상단 상태 바
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)
        
        # 스택 위젯으로 화면 전환 관리
        self.stacked_widget = QStackedWidget()
        
        # 홈 화면 (차량 타입 선택)
        self.home_screen = VehicleTypeSelector(self)
        self.stacked_widget.addWidget(self.home_screen)
        
        main_layout.addWidget(self.stacked_widget)
        
        self.setLayout(main_layout)
        
        # 전체 윈도우 스타일
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {HYUNDAI_COLORS['background']};
            }}
        """)
        
        self.show()
        
    def show_main_process(self, vehicle_type):
        """메인 프로세스 시작"""
        processing_screen = ProcessingScreen(vehicle_type, self)
        self.stacked_widget.addWidget(processing_screen)
        self.stacked_widget.setCurrentWidget(processing_screen)
        
    def show_result_screen(self, vehicle_type):
        """결과 화면 표시"""
        result_screen = ResultScreen(vehicle_type, self)
        self.stacked_widget.addWidget(result_screen)
        self.stacked_widget.setCurrentWidget(result_screen)
        
    def show_home(self):
        """홈 화면으로 돌아가기"""
        # 기존 화면들 제거 (메모리 절약)
        while self.stacked_widget.count() > 1:
            widget = self.stacked_widget.widget(1)
            self.stacked_widget.removeWidget(widget)
            widget.deleteLater()
            
        self.stacked_widget.setCurrentWidget(self.home_screen)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 애플리케이션 전체 폰트 설정
    font = QFont("Malgun Gothic", 12)  # 한국어 지원 폰트
    app.setFont(font)
    
    # 다크 테마 설정
    app.setStyle('Fusion')
    
    ex = HyundaiStyleUI()
    sys.exit(app.exec_())
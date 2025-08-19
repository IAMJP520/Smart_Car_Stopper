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

# --- 2. 주차 구역 선택 화면 ---

class ParkingTypeSelector(QWidget):
    """주차 구역 타입을 선택하는 초기 화면"""
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
        subtitle = QLabel("원하시는 주차 구역을 선택해주세요")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                color: {HYUNDAI_COLORS['text_secondary']};
                margin-bottom: 40px;
            }}
        """)
        
        # 주차 구역 버튼들
        button_layout = QVBoxLayout()
        button_layout.setSpacing(25)
        
        # 일반 주차 버튼
        regular_btn = AnimatedButton("🚗 일반 주차")
        regular_btn.clicked.connect(lambda: self.select_parking_type('regular'))
        
        # 전기차 충전 버튼
        ev_btn = AnimatedButton("🔋 전기차 충전")
        ev_btn.clicked.connect(lambda: self.select_parking_type('electric'))
        
        # 장애인 주차 버튼
        handicapped_btn = AnimatedButton("♿ 장애인 주차")
        handicapped_btn.clicked.connect(lambda: self.select_parking_type('handicapped'))
        
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
        
    def select_parking_type(self, parking_type):
        """주차 타입 선택 후 메인 프로세스로 이동"""
        if hasattr(self.parent_window, 'show_main_process'):
            self.parent_window.show_main_process(parking_type)

# --- 3. 메인 프로세스 화면들 ---

class ProcessingScreen(QWidget):
    """처리 중 화면"""
    def __init__(self, parking_type, parent=None):
        super().__init__(parent)
        self.parking_type = parking_type
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
        
        # 아이콘
        icon_label = QLabel()
        icon_text = "🚗" if self.parking_type == 'regular' else "🔋" if self.parking_type == 'electric' else "♿"
        icon_label.setText(icon_text)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("QLabel { font-size: 100px; margin-bottom: 30px; }")
        
        # 처리 중 메시지
        status_text = {
            'regular': "일반 주차구역을 찾고 있습니다...",
            'electric': "전기차 충전구역을 찾고 있습니다...",
            'handicapped': "장애인 전용구역 정보를 확인합니다..."
        }
        self.status_label = QLabel(status_text.get(self.parking_type, "확인 중..."))
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
        
        # 진행률 표시바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMinimumHeight(35)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 17px; background: rgba(26, 30, 46, 0.8);
                color: white; text-align: center; font-size: 16px; font-weight: bold;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {HYUNDAI_COLORS['accent']}, stop:1 {HYUNDAI_COLORS['secondary']});
                border-radius: 17px; margin: 2px;
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
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.progress = 0
        self.timer.start(60)
        
    def update_progress(self):
        self.progress += 2
        self.progress_bar.setValue(self.progress)
        
        if self.progress >= 100:
            self.timer.stop()
            QTimer.singleShot(500, self.show_result)
            
    def show_result(self):
        if hasattr(self.parent_window, 'show_result_screen'):
            self.parent_window.show_result_screen(self.parking_type)

class ResultScreen(QWidget):
    """결과 표시 화면"""
    def __init__(self, parking_type, parent=None):
        super().__init__(parent)
        self.parking_type = parking_type
        self.parent_window = parent
        self.initUI()
        
    def initUI(self):
        background = HyundaiBackground(self)
        main_widget = QWidget(self)
        main_widget.setStyleSheet("background: transparent;")
        
        self.layout = QVBoxLayout(main_widget) # layout을 self 멤버로 만듭니다.
        self.layout.setSpacing(40)
        self.layout.setContentsMargins(80, 120, 80, 80)
        
        # 결과에 따른 컨텐츠 생성
        if self.parking_type == 'regular':
            self.create_regular_result(self.layout)
        elif self.parking_type == 'electric':
            self.create_electric_result(self.layout)
        elif self.parking_type == 'handicapped':
            # 장애인 주차의 경우, 인증 UI를 먼저 표시합니다.
            self.show_authentication_ui()
            
        final_layout = QVBoxLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(main_widget)
        
    def create_regular_result(self, layout):
        success_label = QLabel("✅"); success_label.setAlignment(Qt.AlignCenter); success_label.setStyleSheet("font-size: 80px; margin-bottom: 30px;")
        message = QLabel("일반 주차구역으로 안내합니다"); message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"font-size: 28px; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold; margin-bottom: 20px;")
        info = QLabel("주차장 입구가 곧 열립니다"); info.setAlignment(Qt.AlignCenter); info.setStyleSheet(f"font-size: 18px; color: {HYUNDAI_COLORS['text_secondary']};")
        confirm_btn = AnimatedButton("확인"); confirm_btn.clicked.connect(self.launch_parking_ui)
        
        layout.addStretch(1); layout.addWidget(success_label); layout.addWidget(message); layout.addWidget(info); layout.addWidget(confirm_btn); layout.addStretch(1)
        
    def create_electric_result(self, layout):
        battery_label = QLabel("🔋"); battery_label.setAlignment(Qt.AlignCenter); battery_label.setStyleSheet("font-size: 80px; margin-bottom: 30px;")
        message = QLabel("전기차 충전구역으로 안내합니다"); message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"font-size: 28px; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold; margin-bottom: 20px;")
        info = QLabel("주차장 입구가 곧 열립니다"); info.setAlignment(Qt.AlignCenter); info.setStyleSheet(f"font-size: 18px; color: {HYUNDAI_COLORS['text_secondary']};")
        confirm_btn = AnimatedButton("확인"); confirm_btn.clicked.connect(self.launch_parking_ui)
        
        layout.addStretch(1); layout.addWidget(battery_label); layout.addWidget(message); layout.addWidget(info); layout.addWidget(confirm_btn); layout.addStretch(1)

    def show_authentication_ui(self):
        """장애인 차량 인증 UI를 표시합니다."""
        # 기존 위젯들을 모두 제거합니다.
        self.clear_layout()

        fingerprint_label = QLabel("👆"); fingerprint_label.setAlignment(Qt.AlignCenter); fingerprint_label.setStyleSheet("font-size: 80px; margin-bottom: 30px;")
        message = QLabel("장애인 차량 인증"); message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"font-size: 28px; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold; margin-bottom: 20px;")
        info = QLabel("본인 확인을 위해 지문 인식을 진행해주세요"); info.setAlignment(Qt.AlignCenter); info.setStyleSheet(f"font-size: 18px; color: {HYUNDAI_COLORS['text_secondary']}; margin-bottom: 30px;")
        
        auth_btn = AnimatedButton("지문 인증하기")
        auth_btn.clicked.connect(self.show_parking_options_ui)

        self.layout.addStretch(1); self.layout.addWidget(fingerprint_label); self.layout.addWidget(message); self.layout.addWidget(info); self.layout.addWidget(auth_btn); self.layout.addStretch(1)

    def show_parking_options_ui(self):
        """인증 완료 후 주차 옵션 선택 UI를 표시합니다."""
        self.clear_layout()

        success_label = QLabel("✅"); success_label.setAlignment(Qt.AlignCenter); success_label.setStyleSheet("font-size: 80px; margin-bottom: 30px;")
        message = QLabel("인증이 완료되었습니다"); message.setAlignment(Qt.AlignCenter)
        message.setStyleSheet(f"font-size: 28px; color: {HYUNDAI_COLORS['text_primary']}; font-weight: bold; margin-bottom: 20px;")
        info = QLabel("주차 옵션을 선택해주세요"); info.setAlignment(Qt.AlignCenter); info.setStyleSheet(f"font-size: 18px; color: {HYUNDAI_COLORS['text_secondary']}; margin-bottom: 30px;")

        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        normal_parking_btn = AnimatedButton("일반 주차 (장애인 구역)")
        charging_parking_btn = AnimatedButton("충전 주차 (장애인 구역)")
        normal_parking_btn.clicked.connect(self.launch_parking_ui)
        charging_parking_btn.clicked.connect(self.launch_parking_ui)
        button_layout.addWidget(normal_parking_btn)
        button_layout.addWidget(charging_parking_btn)
        
        self.layout.addStretch(1); self.layout.addWidget(success_label); self.layout.addWidget(message); self.layout.addWidget(info); self.layout.addLayout(button_layout); self.layout.addStretch(1)
    
    def clear_layout(self):
        """레이아웃의 모든 위젯을 제거하는 헬퍼 함수"""
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                layout = item.layout()
                if layout is not None:
                    # 재귀적으로 하위 레이아웃의 위젯도 삭제
                    while layout.count():
                        sub_item = layout.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget:
                            sub_widget.deleteLater()

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

# --- 4. 메인 윈도우 ---

class HyundaiStyleUI(QWidget):
    """현대차 스타일의 메인 UI"""
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('HYUNDAI SmartParking System')
        self.setGeometry(150, 150, 1000, 700)
        self.setFixedSize(1000, 700)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)
        
        self.stacked_widget = QStackedWidget()
        
        # 클래스 이름을 ParkingTypeSelector로 변경
        self.home_screen = ParkingTypeSelector(self)
        self.stacked_widget.addWidget(self.home_screen)
        
        main_layout.addWidget(self.stacked_widget)
        self.setLayout(main_layout)
        
        self.setStyleSheet(f"QWidget {{ background-color: {HYUNDAI_COLORS['background']}; }}")
        self.show()
        
    def show_main_process(self, parking_type):
        processing_screen = ProcessingScreen(parking_type, self)
        self.stacked_widget.addWidget(processing_screen)
        self.stacked_widget.setCurrentWidget(processing_screen)
        
    def show_result_screen(self, parking_type):
        result_screen = ResultScreen(parking_type, self)
        self.stacked_widget.addWidget(result_screen)
        self.stacked_widget.setCurrentWidget(result_screen)
        
    def show_home(self):
        while self.stacked_widget.count() > 1:
            widget = self.stacked_widget.widget(1)
            self.stacked_widget.removeWidget(widget)
            widget.deleteLater()
        self.stacked_widget.setCurrentWidget(self.home_screen)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    font = QFont("Malgun Gothic", 12)
    app.setFont(font)
    app.setStyle('Fusion')
    ex = HyundaiStyleUI()
    sys.exit(app.exec_())

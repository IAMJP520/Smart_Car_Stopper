import sys
import socket
import json
import threading
from heapq import heappush, heappop
from math import sqrt, atan2, degrees, sin, cos, radians
import random
from datetime import datetime
from typing import List, Tuple, Optional
import pyttsx3
from gtts import gTTS
import pygame
import tempfile
import os

from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem, QGraphicsPolygonItem,
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
# TTS 음성 안내 모듈 (한국어 최적화)
# ===================================================================
class VoiceGuide:
    """음성 경로 안내를 담당하는 클래스 (Google TTS 사용)"""
    
    def __init__(self):
        self.last_instruction = None  # 마지막 안내 내용 저장
        self.temp_files = []  # 임시 파일 관리
        self.init_tts()
    
    def init_tts(self):
        """TTS 엔진 초기화 (Google TTS 사용)"""
        try:
            # pygame 초기화 (오디오 재생용)
            pygame.mixer.init()
            print("🔊 Google TTS 엔진 초기화 완료")
            
        except Exception as e:
            print(f"❌ TTS 초기화 실패: {e}")
            self.engine = None
    
    def speak_instruction(self, instruction_text):
        """음성 안내 재생"""
        if not instruction_text:
            return
        
        # 같은 안내가 반복되지 않도록 체크
        if self.last_instruction == instruction_text:
            return
        
        self.last_instruction = instruction_text
        
        try:
            # 별도 스레드에서 음성 재생 (UI 블로킹 방지)
            threading.Thread(
                target=self._speak_thread,
                args=(instruction_text,),
                daemon=True,
                name="VoiceGuide"
            ).start()
            
        except Exception as e:
            print(f"❌ 음성 안내 재생 실패: {e}")
    
    def speak_instruction_force(self, instruction_text):
        """음성 안내 강제 재생 (중복 체크 무시)"""
        if not instruction_text:
            return
        
        print(f"🔊 강제 TTS 재생: {instruction_text}")
        
        try:
            # 별도 스레드에서 음성 재생 (UI 블로킹 방지)
            threading.Thread(
                target=self._speak_thread,
                args=(instruction_text,),
                daemon=True,
                name="VoiceGuideForce"
            ).start()
            
        except Exception as e:
            print(f"❌ 강제 음성 안내 재생 실패: {e}")
    
    def _speak_thread(self, text):
        """음성 재생 스레드 (Google TTS 사용)"""
        try:
            print(f"🎵 TTS 스레드 시작: {text}")
            
            # Google TTS로 한국어 음성 생성
            tts = gTTS(text=text, lang='ko', slow=False)
            print(f"✅ TTS 음성 생성 완료")
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_path = temp_file.name
                tts.save(temp_path)
                self.temp_files.append(temp_path)
                print(f"💾 임시 파일 생성: {temp_path}")
            
            # pygame으로 음성 재생
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            print(f"▶️ 음성 재생 시작")
            
            # 재생 완료까지 대기
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            
            print(f"✅ 음성 재생 완료: {text}")
            
            # 임시 파일 정리
            try:
                os.unlink(temp_path)
                if temp_path in self.temp_files:
                    self.temp_files.remove(temp_path)
                print(f"🗑️ 임시 파일 정리 완료")
            except Exception as cleanup_error:
                print(f"⚠️ 임시 파일 정리 실패: {cleanup_error}")
            
        except Exception as e:
            print(f"❌ 음성 재생 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """TTS 엔진 정리"""
        try:
            # pygame 정리
            pygame.mixer.quit()
            
            # 임시 파일들 정리
            for temp_file in self.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
            self.temp_files.clear()
            
            print("🔇 TTS 엔진 정리 완료")
        except Exception as e:
            print(f"❌ TTS 정리 중 오류: {e}")

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
        """수신 서버 시작 (별도 스레드) - 개선된 연결 안정성"""
        def server_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Keep-alive 추가
                self.server_socket.settimeout(1.0)  # 타임아웃 설정
                self.server_socket.bind((self.host, self.port))
                self.server_socket.listen(5)
                print(f"✅ 서버가 {self.host}:{self.port}에서 대기 중...")
                self.running = True

                while self.running:
                    try:
                        client_socket, addr = self.server_socket.accept()
                        print(f"🔗 클라이언트 연결됨: {addr}")
                        
                        # 연결별로 별도 스레드에서 처리 (동시 연결 지원)
                        threading.Thread(
                            target=self.handle_connection, 
                            args=(client_socket,), 
                            daemon=True,
                            name=f"ClientHandler-{addr[0]}:{addr[1]}"
                        ).start()
                        
                    except socket.timeout:
                        # 타임아웃은 정상적인 상황, 계속 대기
                        continue
                    except Exception as e:
                        if self.running:
                            print(f"❌ 연결 오류: {e}")
                        break
            except Exception as e:
                print(f"❌ 서버 시작 오류: {e}")
            finally:
                if self.server_socket:
                    try:
                        self.server_socket.close()
                    except:
                        pass

        threading.Thread(target=server_thread, daemon=True, name="WaypointReceiver").start()

    def handle_connection(self, client_socket):
        """클라이언트 연결 처리 - 개선된 JSON 파싱"""
        try:
            buffer = ""
            while self.running:
                data = client_socket.recv(4096).decode('utf-8')  # 버퍼 크기 증가
                if not data:
                    break
                
                buffer += data
                print(f"📥 수신된 데이터 (길이: {len(data)}): {data[:100]}...")  # 디버깅용
                
                # 완전한 JSON 메시지들을 처리
                while buffer:
                    try:
                        # JSON 객체의 시작과 끝 찾기
                        start = buffer.find('{')
                        if start == -1:
                            buffer = ""
                            break
                        
                        # 중괄호 카운팅으로 완전한 JSON 찾기
                        brace_count = 0
                        end = -1
                        for i, char in enumerate(buffer[start:], start):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end = i
                                    break
                        
                        if end == -1:
                            # 완전한 JSON이 없음, 더 많은 데이터 대기
                            print("⏳ 완전한 JSON을 기다리는 중...")
                            break
                        
                        # 완전한 JSON 추출
                        json_str = buffer[start:end+1]
                        buffer = buffer[end+1:]
                        
                        print(f"🔍 파싱할 JSON: {json_str}")
                        message = json.loads(json_str)
                        self.process_waypoint_data(message)
                        
                        response = {"status": "received", "timestamp": datetime.now().isoformat()}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        print("✅ JSON 처리 완료 및 응답 전송")
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON 파싱 오류: {e}")
                        print(f"   문제가 된 데이터: {json_str}")
                        # 잘못된 JSON은 버리고 계속 진행
                        buffer = buffer[end+1:] if end != -1 else ""
                        break
                    except Exception as e:
                        print(f"❌ 메시지 처리 오류: {e}")
                        break
                        
        except Exception as e:
            print(f"❌ 데이터 수신 오류: {e}")
        finally:
            client_socket.close()
            print("📱 클라이언트 연결 종료")

    def process_waypoint_data(self, data):
        """수신된 데이터 처리 (경로 또는 위치) - 개선된 로깅"""
        print(f"📥 수신된 원본 데이터: {data}")  # 디버깅용
        
        if not isinstance(data, dict):
            print(f"❌ 잘못된 데이터 형식: {type(data)}")
            return
            
        msg_type = data.get('type')
        
        # 경로 할당 메시지 처리
        if msg_type == 'waypoint_assignment':
            waypoints = data.get('waypoints', [])
            print(f"\n🎯 새로운 waypoint 수신: {waypoints}")
            print(f"📊 웨이포인트 개수: {len(waypoints)}")
            
            # 웨이포인트 유효성 검사
            if not isinstance(waypoints, list):
                print(f"❌ 웨이포인트가 리스트가 아님: {type(waypoints)}")
                return
                
            if len(waypoints) == 0:
                print("⚠️ 빈 웨이포인트 리스트 수신")
                return
                
            # 각 웨이포인트 유효성 검사
            for i, wp in enumerate(waypoints):
                if not isinstance(wp, list) or len(wp) != 2:
                    print(f"❌ 잘못된 웨이포인트 형식 [{i}]: {wp}")
                    return
                try:
                    float(wp[0])
                    float(wp[1])
                except (ValueError, TypeError):
                    print(f"❌ 웨이포인트 좌표가 숫자가 아님 [{i}]: {wp}")
                    return
            
            if self.waypoint_callback:
                self.waypoint_callback(waypoints)
                print("✅ 웨이포인트 콜백 호출 완료")
            else:
                print("❌ waypoint_callback이 설정되지 않음")
            print("=" * 50)
            
        # 실시간 위치 메시지 처리
        elif msg_type == 'real_time_position':
            x = data.get('x')
            y = data.get('y')
            tag_id = data.get('tag_id')
            
            print(f"📍 실시간 위치 수신 - Tag {tag_id}: ({x}, {y})")
            
            # 좌표 유효성 검사
            try:
                if x is not None and y is not None:
                    x_float = float(x)
                    y_float = float(y)
                    position = [x_float, y_float]
                    
                    if self.position_callback:
                        self.position_callback(position)
                        print("✅ 위치 콜백 호출 완료")
                    else:
                        print("❌ position_callback이 설정되지 않음")
                else:
                    print(f"❌ 잘못된 위치 데이터: x={x}, y={y}")
            except (ValueError, TypeError) as e:
                print(f"❌ 좌표 변환 오류: {e}, x={x}, y={y}")
                
        else:
            print(f"⚠️ 알 수 없는 메시지 타입: {msg_type}")
            print(f"   지원되는 타입: 'waypoint_assignment', 'real_time_position'")

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
# 개선된 현대차 스타일 컬러 팔레트 - 더 심플하고 세련된 느낌
# ===================================================================
HYUNDAI_COLORS = {
    'primary': '#1a1a1a',        # 진한 차콜 그레이
    'secondary': "#2d2d2d",      # 미디엄 그레이  
    'accent': '#4a9eff',         # 부드러운 블루 (기존보다 연하고 세련됨)
    'success': '#00d084',        # 민트 그린
    'warning': '#ffa726',        # 소프트 오렌지
    'danger': '#ef5350',         # 소프트 레드
    'background': '#0f0f0f',     # 더 깊은 블랙
    'surface': '#1e1e1e',        # 다크 서페이스
    'text_primary': '#ffffff',   # 순백
    'text_secondary': '#9e9e9e', # 쿨 그레이
    'glass': 'rgba(255, 255, 255, 0.08)',  # 더 은은한 글래스 효과
    'blue_soft': '#6bb6ff',      # 소프트 블루
    'blue_muted': '#4285f4',     # 뮤트 블루
    'white_soft': '#f5f5f5',     # 소프트 화이트
    'gray_light': '#757575',     # 라이트 그레이
    'gray_medium': '#424242'     # 미디엄 그레이
}

FONT_SIZES = {
    'hud_distance': 42, 'hud_direction': 12, 'hud_speed': 28, 'hud_speed_unit': 10,
    'hud_progress': 14, 'hud_next_label': 10, 'hud_next_direction': 14,
    'map_label': 10, 'map_io_label': 12, 'map_waypoint_label': 12,
    'controls_title': 16, 'controls_info': 12, 'controls_button': 16, 'msgbox_button': 10
}

# ===================================================================
# 애니메이션 HUD 위젯: 개선된 현대차 프리미엄 스타일
# ===================================================================
class PremiumHudWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumSize(450, 700)
        self.setStyleSheet(f"""
            PremiumHudWidget {{
                /* 더 심플한 다크 그라데이션 */
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {HYUNDAI_COLORS['primary']}, 
                    stop:1 {HYUNDAI_COLORS['background']});
                
                /* 더 은은한 테두리 */
                border: 2px solid {HYUNDAI_COLORS['gray_medium']};
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
        
        # TTS 음성 안내 초기화
        self.voice_guide = VoiceGuide()
        
        # TTS 지연 출력을 위한 타이머와 변수들
        self.tts_delay_timer = QTimer(self)
        self.tts_delay_timer.setSingleShot(True)
        self.tts_delay_timer.timeout.connect(self.execute_delayed_tts)
        self.pending_direction = None
        self.pending_distance = 0
        
        # 출차 시나리오 버튼 추가
        self.exit_scenario_button = QPushButton("출차 시나리오 시작", self)
        self.exit_scenario_button.setGeometry(50, 650, 350, 40)
        self.exit_scenario_button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {HYUNDAI_COLORS['accent']}, 
                    stop:1 {HYUNDAI_COLORS['blue_muted']});
                color: {HYUNDAI_COLORS['text_primary']};
                border: 2px solid {HYUNDAI_COLORS['blue_soft']};
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
                font-family: 'Malgun Gothic';
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {HYUNDAI_COLORS['blue_soft']}, 
                    stop:1 {HYUNDAI_COLORS['accent']});
                border: 2px solid {HYUNDAI_COLORS['text_primary']};
            }}
            QPushButton:pressed {{
                background: {HYUNDAI_COLORS['blue_muted']};
                border: 2px solid {HYUNDAI_COLORS['warning']};
            }}
        """)
        self.exit_scenario_button.clicked.connect(self.start_exit_scenario)

    def start_exit_scenario(self):
        """출차 시나리오 시작"""
        # 부모 위젯(ParkingLotUI)의 출차 시나리오 메서드 호출
        if hasattr(self.parent(), 'start_exit_scenario'):
            self.parent().start_exit_scenario()

    def init_particles(self):
        self.particle_positions = []
        for _ in range(8):  # 파티클 수 줄임
            self.particle_positions.append({
                'x': random.randint(0, 450), 'y': random.randint(0, 700),
                'speed': random.uniform(0.3, 1.0), 'size': random.randint(1, 3),  # 크기와 속도 줄임
                'opacity': random.uniform(0.05, 0.15)  # 더 은은하게
            })

    def update_animation(self):
        self.rotation_angle = (self.rotation_angle + 1) % 360  # 회전 속도 줄임
        if self.pulse_growing:
            self.pulse_scale += 0.01  # 펄스 변화량 줄임
            if self.pulse_scale >= 1.05: self.pulse_growing = False  # 펄스 범위 줄임
        else:
            self.pulse_scale -= 0.01
            if self.pulse_scale <= 1.0: self.pulse_growing = True
        if self.glow_increasing:
            self.glow_opacity += 0.02  # 글로우 변화량 줄임
            if self.glow_opacity >= 0.4: self.glow_increasing = False  # 글로우 범위 줄임
        else:
            self.glow_opacity -= 0.02
            if self.glow_opacity <= 0.2: self.glow_increasing = True
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
        # 더 은은한 파티클
        for particle in self.particle_positions:
            color = QColor(HYUNDAI_COLORS['blue_soft'])
            color.setAlphaF(particle['opacity'])
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(particle['x'], particle['y']), particle['size'], particle['size'])
        
        # 그리드 제거 (더 심플하게)
        
        painter.restore()

    def draw_3d_direction_display(self, painter, center_x, y):
        painter.save()
        painter.translate(center_x, y)
        
        # 회전하는 외부 링 (더 은은하게)
        painter.rotate(self.rotation_angle)
        gradient = QRadialGradient(0, 0, 90)
        gradient.setColorAt(0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.8, QColor(HYUNDAI_COLORS['gray_light']).darker(200))
        gradient.setColorAt(1, QColor(HYUNDAI_COLORS['gray_medium']))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['gray_medium']), 1))
        painter.drawEllipse(QPointF(0, 0), 85, 85)
        painter.rotate(-self.rotation_angle)
        
        # 메인 원형 배경 (더 심플하게)
        painter.scale(self.pulse_scale, self.pulse_scale)
        is_warning = self.current_distance <= 0 and ("좌회전" in self.current_direction or "우회전" in self.current_direction)
        is_exit_complete = "출차 완료" in self.current_direction
        is_destination_arrival = "목적지 도착" in self.current_direction
        
        if is_warning or is_exit_complete or is_destination_arrival:
            # 경고 색상, 출차 완료 색상, 목적지 도착 색상 (소프트 오렌지)
            main_color = QColor(HYUNDAI_COLORS['warning'])
            bg_color = main_color.darker(150)
        else:
            # 일반 색상 (소프트 블루)
            main_color = QColor(HYUNDAI_COLORS['blue_soft'])
            bg_color = main_color.darker(150)
        
        # 단순한 원형 배경
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(main_color.lighter(120), 3))
        painter.drawEllipse(QPointF(0, 0), 65, 65)
        
        # 중앙 하이라이트 (더 은은하게)
        inner_gradient = QRadialGradient(0, 0, 30)
        inner_gradient.setColorAt(0, QColor(255, 255, 255, 20))
        inner_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(inner_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0, 0), 30, 30)
        
        painter.scale(1 / self.pulse_scale, 1 / self.pulse_scale)
        self.draw_3d_direction_icon(painter)
        painter.restore()

    def draw_3d_direction_icon(self, painter):
        painter.save()
        painter.setPen(Qt.NoPen)
        
        # 그림자 효과 (더 은은하게)
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        action = None

        if "좌회전" in self.current_direction:
            action = self.draw_3d_left_arrow
        elif "우회전" in self.current_direction:
            action = self.draw_3d_right_arrow
        elif "목적지" in self.current_direction:
            action = self.draw_3d_destination_icon
        elif "출차 완료" in self.current_direction:
            action = self.draw_3d_exit_complete_icon

        if action:
            painter.translate(2, 2)  # 그림자 오프셋 줄임
            action(painter, 0, 0, shadow=True)
            painter.translate(-2, -2)
            # 더 심플한 아이콘 색상
            painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['white_soft'])))
            painter.setPen(QPen(QColor(HYUNDAI_COLORS['white_soft']), 2))
            action(painter, 0, 0)
        else:
            self.draw_3d_straight_arrow(painter, 0, 0)
        painter.restore()

    def draw_3d_left_arrow(self, painter, x, y, shadow=False):
        if not shadow: painter.drawPolygon(QPolygonF([QPointF(x-35,y),QPointF(x-15,y-20),QPointF(x-15,y-10),QPointF(x+20,y-10),QPointF(x+20,y+10),QPointF(x-15,y+10),QPointF(x-15,y+20)]))
        else: painter.drawPolygon(QPolygonF([QPointF(x-35,y),QPointF(x-15,y-20),QPointF(x-15,y-10),QPointF(x+20,y-10),QPointF(x+20,y+10),QPointF(x-15,y+10),QPointF(x-15,y+20)]))

    def draw_3d_right_arrow(self, painter, x, y, shadow=False):
        if not shadow: painter.drawPolygon(QPolygonF([QPointF(x+35,y),QPointF(x+15,y-20),QPointF(x+15,y-10),QPointF(x-20,y-10),QPointF(x-20,y+10),QPointF(x+15,y+10),QPointF(x+15,y+20)]))
        else: painter.drawPolygon(QPolygonF([QPointF(x+35,y),QPointF(x+15,y-20),QPointF(x+15,y-10),QPointF(x-20,y-10),QPointF(x-20,y+10),QPointF(x+15,y+10),QPointF(x+15,y+20)]))

    def draw_3d_straight_arrow(self, painter, x, y):
        # 그림자
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0,0,0,30)))
        painter.drawPolygon(QPolygonF([QPointF(x+2,y-32),QPointF(x-15,y-7),QPointF(x-7,y-7),QPointF(x-7,y+28),QPointF(x+13,y+28),QPointF(x+13,y-7),QPointF(x+21,y-7)]))
        
        # 메인 화살표 (더 심플한 색상)
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['white_soft'])))
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['white_soft']), 2))
        painter.drawPolygon(QPolygonF([QPointF(x,y-35),QPointF(x-18,y-10),QPointF(x-10,y-10),QPointF(x-10,y+25),QPointF(x+10,y+25),QPointF(x+10,y-10),QPointF(x+18,y-10)]))

    def draw_3d_destination_icon(self, painter, x, y, shadow=False):
        if shadow:
            painter.drawEllipse(QPointF(x, y), 25, 25)
        else:
            # 목적지 도착 아이콘 (주황색 원)
            painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['warning'])))
            painter.setPen(QPen(QColor(HYUNDAI_COLORS['white_soft']), 2))
            painter.drawEllipse(QPointF(x, y), 25, 25)
            painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['white_soft'])))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x, y), 8, 8)

    def draw_3d_exit_complete_icon(self, painter, x, y, shadow=False):
        if shadow:
            painter.drawEllipse(QPointF(x, y), 25, 25)
        else:
            # 출차 완료 아이콘 (주황색 원)
            painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['warning'])))
            painter.setPen(QPen(QColor(HYUNDAI_COLORS['white_soft']), 2))
            painter.drawEllipse(QPointF(x, y), 25, 25)
            # 중앙에 체크마크 그리기
            painter.setPen(QPen(QColor(HYUNDAI_COLORS['white_soft']), 3))
            painter.drawLine(QPointF(x-8, y), QPointF(x-2, y+6))
            painter.drawLine(QPointF(x-2, y+6), QPointF(x+8, y-6))

    def draw_distance_panel(self, painter, center_x, y):
        painter.save()
        panel_rect = QRectF(center_x - 150, y - 50, 300, 100)
        
        # 더 심플한 패널 배경
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['surface'])))
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['gray_medium']), 1))
        painter.drawRoundedRect(panel_rect, 20, 20)
        
        # 거리 텍스트
        distance_text = f"{self.current_distance:.0f}m" if self.current_distance < 1000 else f"{self.current_distance/1000:.1f}km"
        font = QFont("Segoe UI", FONT_SIZES['hud_distance'], QFont.Bold)
        painter.setFont(font)
        
        # 더 세련된 색상 선택
        if self.current_distance <= 5:
            text_color = QColor(HYUNDAI_COLORS['warning'])
        elif self.current_distance <= 20:
            text_color = QColor(HYUNDAI_COLORS['success'])
        elif "출차 완료" in self.current_direction or "목적지 도착" in self.current_direction:
            text_color = QColor(HYUNDAI_COLORS['warning'])
        else:
            text_color = QColor(HYUNDAI_COLORS['blue_soft'])
            
        painter.setPen(QPen(text_color))
        painter.drawText(QRectF(center_x-150, y-30, 300, 60), Qt.AlignCenter, distance_text)
        
        # 방향 텍스트
        font = QFont("Malgun Gothic", FONT_SIZES['hud_direction'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['text_secondary'])))
        direction_text = self.current_direction[:20] + "..." if len(self.current_direction)>20 else self.current_direction
        painter.drawText(QRectF(center_x-150, y+10, 300, 40), Qt.AlignCenter, direction_text)
        painter.restore()

    def draw_speed_gauge(self, painter, center_x, y):
        painter.save()
        gauge_rect = QRectF(center_x - 80, y - 40, 160, 80)
        
        # 배경 아크 (더 은은하게)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['gray_medium']), 6))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(gauge_rect, 0, 180 * 16)
        
        # 진행 아크 (더 심플한 색상)
        speed_angle = min(180, (self.speed / 100) * 180)
        # 출차 완료 또는 목적지 도착 시 주황색으로 변경
        if "출차 완료" in self.current_direction or "목적지 도착" in self.current_direction:
            painter.setPen(QPen(QColor(HYUNDAI_COLORS['warning']), 6))
        else:
            painter.setPen(QPen(QColor(HYUNDAI_COLORS['blue_soft']), 6))
        painter.drawArc(gauge_rect, 0, int(speed_angle * 16))
        
        # 속도 텍스트
        font = QFont("Segoe UI", FONT_SIZES['hud_speed'], QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['text_primary'])))
        painter.drawText(QRectF(center_x-80, y-20, 160, 40), Qt.AlignCenter, f"{self.speed}")
        
        # 단위 텍스트
        font = QFont("Malgun Gothic", FONT_SIZES['hud_speed_unit'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['text_secondary'])))
        painter.drawText(QRectF(center_x-80, y+10, 160, 20), Qt.AlignCenter, "km/h")
        painter.restore()

    def draw_progress_bar(self, painter, center_x, y):
        painter.save()
        bar_width, bar_height = 350, 12
        bar_rect = QRectF(center_x - bar_width / 2, y - bar_height / 2, bar_width, bar_height)
        
        # 배경 바 (더 심플하게)
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['gray_medium'])))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bar_rect, 6, 6)
        
        # 진행 바
        if self.progress > 0:
            progress_rect = QRectF(bar_rect.x(), bar_rect.y(), (self.progress / 100) * bar_width, bar_height)
            # 출차 완료 또는 목적지 도착 시 주황색으로 변경
            if "출차 완료" in self.current_direction or "목적지 도착" in self.current_direction:
                painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['warning'])))
            else:
                painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['blue_soft'])))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(progress_rect, 6, 6)
        
        # 진행률 텍스트
        font = QFont("Segoe UI", FONT_SIZES['hud_progress'], QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['text_primary'])))
        painter.drawText(QRectF(center_x-175, y+10, 350, 30), Qt.AlignCenter, f"{self.progress:.0f}%")
        painter.restore()

    def draw_next_instruction_card(self, painter, center_x, y):
        if not self.next_direction: return
        painter.save()
        card_rect = QRectF(center_x-200, y-40, 400, 80)
        
        # 카드 배경 (더 심플하게)
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['surface'])))
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['gray_medium']), 1))
        painter.drawRoundedRect(card_rect, 20, 20)
        
        # "다음" 라벨
        font = QFont("Malgun Gothic", FONT_SIZES['hud_next_label'], QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['blue_soft'])))
        painter.drawText(QPointF(center_x-190, y-15), "다음")
        
        # 아이콘 배경
        icon_x, icon_y = center_x - 140, y + 10
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['gray_medium'])))
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['blue_soft']), 1))
        painter.drawEllipse(QPointF(icon_x, icon_y), 25, 25)
        
        # 아이콘 그리기
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['white_soft']), 2))
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['white_soft'])))
        if "좌회전" in self.next_direction:
            self.draw_mini_left_arrow(painter, icon_x, icon_y)
        elif "우회전" in self.next_direction:
            self.draw_mini_right_arrow(painter, icon_x, icon_y)
        elif "목적지" in self.next_direction or "도착" in self.next_direction:
            self.draw_mini_destination(painter, icon_x, icon_y)
        elif "출차 완료" in self.next_direction:
            self.draw_mini_exit_complete(painter, icon_x, icon_y)
        else:
            self.draw_mini_straight(painter, icon_x, icon_y)
        
        # 지시 텍스트
        font.setPointSize(FONT_SIZES['hud_next_direction'])
        painter.setFont(font)
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['text_secondary'])))
        painter.drawText(QRectF(icon_x+30, y-20, 200, 60), Qt.AlignVCenter, 
                        self.next_direction[:20]+"..." if len(self.next_direction)>20 else self.next_direction)
        painter.restore()

    def draw_mini_left_arrow(self, painter, x, y): 
        painter.drawPolygon(QPolygonF([QPointF(x-12,y),QPointF(x-5,y-7),QPointF(x-5,y-3),QPointF(x+8,y-3),QPointF(x+8,y+3),QPointF(x-5,y+3),QPointF(x-5,y+7)]))
    def draw_mini_right_arrow(self, painter, x, y): 
        painter.drawPolygon(QPolygonF([QPointF(x+12,y),QPointF(x+5,y-7),QPointF(x+5,y-3),QPointF(x-8,y-3),QPointF(x-8,y+3),QPointF(x+5,y+3),QPointF(x+5,y+7)]))
    def draw_mini_straight(self, painter, x, y): 
        painter.drawPolygon(QPolygonF([QPointF(x,y-12),QPointF(x-6,y-4),QPointF(x-3,y-4),QPointF(x-3,y+8),QPointF(x+3,y+8),QPointF(x+3,y-4),QPointF(x+6,y-4)]))
    def draw_mini_destination(self, painter, x, y):
        # 목적지 도착 시 주황색으로 변경
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['warning'])))
        painter.drawEllipse(QPointF(x,y), 8, 8)
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['white_soft'])))
        painter.drawEllipse(QPointF(x,y), 3, 3)

    def draw_mini_exit_complete(self, painter, x, y):
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['warning'])))
        painter.drawEllipse(QPointF(x,y), 8, 8)
        # 중앙에 작은 체크마크 그리기
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['white_soft']), 2))
        painter.drawLine(QPointF(x-3, y), QPointF(x-1, y+2))
        painter.drawLine(QPointF(x-1, y+2), QPointF(x+3, y-2))

    def draw_decorative_elements(self, painter, rect):
        painter.save()
        # 더 은은한 상하단 라인
        painter.setBrush(QBrush(QColor(HYUNDAI_COLORS['gray_medium'])))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 20, rect.width(), 2)
        painter.drawRect(0, rect.height()-22, rect.width(), 2)
        
        # 더 심플한 코너 라인
        corner_size = 20
        painter.setPen(QPen(QColor(HYUNDAI_COLORS['blue_soft']), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(15, 15, corner_size, corner_size, 90*16, 90*16)
        painter.drawArc(rect.width()-35, 15, corner_size, corner_size, 0*16, 90*16)
        painter.drawArc(15, rect.height()-35, corner_size, corner_size, 180*16, 90*16)
        painter.drawArc(rect.width()-35, rect.height()-35, corner_size, corner_size, 270*16, 90*16)
        painter.restore()

    def update_navigation_info(self, instructions, current_speed=0, route_progress=0):
        self.speed, self.progress = current_speed, route_progress
        if not instructions:
            self.current_direction, self.current_distance, self.next_direction = "경로를 생성하세요", 0.0, ""
            self.update()
            return

        direction, distance = instructions[0]
        is_turn_complete = ("좌회전" in direction or "우회전" in direction) and distance <= 1

        if is_turn_complete and len(instructions) > 1:
            next_dir, next_dist = instructions[1]
            if "목적지" in next_dir and next_dist > 5:
                self.current_direction = "직진"
                self.current_distance = next_dist
                self.next_direction = next_dir
            else:
                self.current_direction = next_dir
                self.current_distance = next_dist
                if len(instructions) > 2:
                    self.next_direction = instructions[2][0]
                else:
                    self.next_direction = ""
        else:
            if distance > 5:
                self.current_direction = "직진"
                self.current_distance = distance
                self.next_direction = direction
            else:
                self.current_direction = direction
                self.current_distance = distance
                if len(instructions) > 1:
                    next_dir, next_dist = instructions[1]
                    if "목적지" in next_dir and next_dist <= 5:
                        self.next_direction = next_dir
                    else:
                        self.next_direction = "직진"
                else:
                    self.next_direction = ""

        new_direction = self.current_direction
        if new_direction != self.target_direction:
            self.previous_direction, self.target_direction, self.direction_transition = self.target_direction, new_direction, 0.0
            
            # 기존 타이머가 실행 중이면 중지
            if self.tts_delay_timer.isActive():
                self.tts_delay_timer.stop()
                print(f"🔄 이전 TTS 타이머 취소: {self.pending_direction}")
            
            # 새로운 방향과 거리를 저장하고 0.1초 후 실행하도록 타이머 시작
            self.pending_direction = new_direction
            self.pending_distance = self.current_distance
            self.tts_delay_timer.start(100)  # 0.1초 지연
            print(f"⏰ TTS 타이머 시작: {new_direction}, 거리: {self.current_distance}")

        self.update()
    
    def execute_delayed_tts(self):
        """지연된 TTS 음성 안내 실행"""
        if self.pending_direction and self.pending_distance is not None:
            print(f"🔊 지연된 TTS 실행: {self.pending_direction}, 거리: {self.pending_distance}")
            self.play_voice_guidance(self.pending_direction, self.pending_distance)
            self.pending_direction = None
            self.pending_distance = 0
    
    def play_voice_guidance(self, direction, distance):
        """음성 안내 메시지 생성 및 재생"""
        if not direction or direction == "경로 설정 대기":
            return
        
        # 거리와 방향에 따른 음성 안내 메시지 생성
        voice_message = self.generate_voice_message(direction, distance)
        
        if voice_message:
            self.voice_guide.speak_instruction(voice_message)
    
    def generate_voice_message(self, direction, distance):
        """방향과 거리에 따른 음성 안내 메시지 생성 (한국어)"""
        # 거리 반올림 (소수점 제거)
        distance_int = int(round(distance))
        
        # 방향별 메시지 생성 (한국어)
        if "좌회전" in direction:
            if distance_int <= 0:
                return "지금 좌회전하세요"
            else:
                return f"{distance_int}미터 후 좌회전입니다"
        elif "우회전" in direction:
            if distance_int <= 0:
                return "지금 우회전하세요"
            else:
                return f"{distance_int}미터 후 우회전입니다"
        elif "직진" in direction:
            if distance_int <= 0:
                return "지금 직진하세요"
            else:
                return f"{distance_int}미터 직진입니다"
        elif "목적지 도착" in direction:
            return "목적지에 도착했습니다"
        elif "출차 완료" in direction:
            return "출차가 완료되었습니다"
        elif "출차" in direction:
            if "좌회전" in direction:
                if distance_int <= 0:
                    return "지금 출차 좌회전하세요"
                else:
                    return f"{distance_int}미터 후 출차 좌회전입니다"
            elif "우회전" in direction:
                if distance_int <= 0:
                    return "지금 출차 우회전하세요"
                else:
                    return f"{distance_int}미터 후 출차 우회전입니다"
            else:
                if distance_int <= 0:
                    return "지금 출차 직진하세요"
                else:
                    return f"{distance_int}미터 출차 직진입니다"
        else:
            # 기타 방향의 경우
            if distance_int <= 0:
                return f"지금 {direction}하세요"
            else:
                return f"{distance_int}미터 후 {direction}입니다"

# ===================================================================
# 자동차 아이템: 간단한 자동차 정면 모양 스타일 (상하반전)
# ===================================================================
class CarItem(QGraphicsObject):
    positionChanged = pyqtSignal(QPointF)

    def __init__(self, parent=None, car_color="red"):
        super().__init__(parent)
        self.car_color = car_color
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

        # 차량 본체 그라데이션을 색상에 따라 변경
        body_gradient = QLinearGradient(0, 15, 0, -45)
        
        if self.car_color == "red":
            body_gradient.setColorAt(0, QColor(220, 30, 30))  # 밝은 빨강
            body_gradient.setColorAt(1, QColor(150, 20, 20))  # 어두운 빨강
            pen_color = QColor(255, 200, 200, 150)
        elif self.car_color == "blue":
            body_gradient.setColorAt(0, QColor(30, 30, 220))  # 밝은 파랑
            body_gradient.setColorAt(1, QColor(20, 20, 150))  # 어두운 파랑
            pen_color = QColor(200, 200, 255, 150)
        elif self.car_color == "green":
            body_gradient.setColorAt(0, QColor(30, 220, 30))  # 밝은 초록
            body_gradient.setColorAt(1, QColor(20, 150, 20))  # 어두운 초록
            pen_color = QColor(200, 255, 200, 150)
        elif self.car_color == "yellow":
            body_gradient.setColorAt(0, QColor(220, 220, 30))  # 밝은 노랑
            body_gradient.setColorAt(1, QColor(150, 150, 20))  # 어두운 노랑
            pen_color = QColor(255, 255, 200, 150)
        else:  # 기본값은 빨간색
            body_gradient.setColorAt(0, QColor(220, 30, 30))
            body_gradient.setColorAt(1, QColor(150, 20, 20))
            pen_color = QColor(255, 200, 200, 150)
            
        painter.setBrush(QBrush(body_gradient))
        painter.setPen(QPen(pen_color, 2))
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
        painter.drawLine(int(self.grille.left()), int(self.grille.center().y()), int(self.grille.right()), int(self.grille.center().y()))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)
        return super().itemChange(change, value)

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
        self.setWindowTitle("SmartParking Navigation System")
        self.initial_fit = False
        self.received_waypoints = []
        
        # 경로 이탈 감지 관련 변수들
        self.route_deviation_timer = QTimer(self)
        self.route_deviation_timer.timeout.connect(self.check_route_deviation)
        self.deviation_start_time = None
        self.is_deviating = False
        self.deviation_threshold = 2.0  # 2초
        self.route_tolerance = 50  # 픽셀 단위 허용 오차
        
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
        self.is_exit_scenario = False  # 출차 시나리오 상태 추적
        self.car = CarItem()
        self.car.positionChanged.connect(self.update_hud_from_car_position)
        self.scene.addItem(self.car)
        self.car.hide()
        
        # 점유된 주차구역에 고정된 차량들 추가
        self.parked_cars = {}  # 주차구역 번호 -> CarItem 매핑
        
        # 주차구역별 좌표와 색상 정의 (이동된 위치)
        parked_car_positions = {
            2: (QPointF(550, 1800), "blue"),    # 2번 주차구역 - 파란색 (위로 325픽셀 이동)
            3: (QPointF(850, 1800), "green"),  # 3번 주차구역 - 초록색 (위로 325픽셀 이동)
            7: (QPointF(1800, 1000), "yellow"), # 7번 주차구역 - 노란색 (우로 325픽셀 이동)
            9: (QPointF(1150, 600), "red")     # 9번 주차구역 - 빨간색 (아래로 325픽셀 이동)
        }
        
        # 각 점유된 주차구역에 차량 배치
        for spot_num, (position, color) in parked_car_positions.items():
            parked_car = CarItem(car_color=color)
            parked_car.setPos(position)
            parked_car.setZValue(50)  # 주차구역 위에 표시
            self.scene.addItem(parked_car)
            self.parked_cars[spot_num] = parked_car
            print(f"🚗 주차구역 {spot_num}번에 {color}색 차량 배치: ({position.x()}, {position.y()})")
        
        # 주차구역 블록들을 저장할 딕셔너리 추가
        self.parking_spots = {}  # 주차구역 번호 -> QGraphicsRectItem 매핑
        self.current_parking_spot = None  # 현재 주차된 구역 번호 추적
        
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
        """[x, y] 좌표를 받아 차량의 위치를 업데이트합니다."""
        if not (isinstance(position, list) and len(position) == 2):
            return
        
        x, y = position[0], position[1]
        
        # (9000, 9000) 좌표는 출차 신호로 처리
        if x == 9000 and y == 9000:
            print("🚗 출차 신호 감지: (9000, 9000) 좌표 수신")
            self.handle_car_exit()
            return
        
        new_pos = QPointF(x, y)
        self.car.setPos(new_pos)

    def handle_car_exit(self):
        """차량 출차 처리 - 차량 제거 및 상태 초기화"""
        print("🚗 차량 출차 처리 시작")
        
        # 차량을 UI에서 숨김
        if self.car.isVisible():
            self.car.hide()
            print("✅ 차량을 UI에서 제거했습니다")
        
        # 현재 주차구역이 있다면 색상 복원
        if hasattr(self, 'current_parking_spot') and self.current_parking_spot:
            self.restore_parking_spot_color(self.current_parking_spot)
            print(f"✅ 주차구역 {self.current_parking_spot}번 색상을 복원했습니다")
            self.current_parking_spot = None
        
        # 경로 초기화
        self.clear_path_layer()
        self.full_path_points = []
        self.current_path_segment_index = 0
        self.is_exit_scenario = False
        
        # 경로 이탈 감지 타이머 중지
        self.route_deviation_timer.stop()
        self.is_deviating = False
        self.deviation_start_time = None
        
        # HUD 초기화
        self.hud.update_navigation_info([])
        
        # 웨이포인트 초기화
        self.received_waypoints = []
        
        print("✅ 차량 출차 처리 완료 - 모든 상태가 초기화되었습니다")

    def detect_parking_spot_from_waypoint(self, waypoint):
        """웨이포인트 좌표를 기반으로 주차구역 번호 감지"""
        x, y = waypoint[0], waypoint[1]
        
        # sender.py의 주차구역별 waypoint 좌표와 동일
        parking_waypoints = {
            # 주차구역 1-5 (상단, 왼쪽→오른쪽)
            1: [200, 1475], 2: [550, 1475], 3: [850, 1475], 4: [1150, 1475],
            5: [1450, 1475],
            # 주차구역 6-7 (우측, 위→아래)  
            6: [1475, 1400], 7: [1475, 1000],
            # 주차구역 8-11 (하단, 오른쪽→왼쪽)
            8: [1475, 925], 9: [1150, 925], 10: [850, 925], 11: [550, 925]
        }
        
        # 허용 범위 내에서 매칭 (각각 ±50픽셀 허용)
        tolerance = 50
        for spot_num, coord in parking_waypoints.items():
            if abs(x - coord[0]) <= tolerance and abs(y - coord[1]) <= tolerance:
                return spot_num
        
        return None

    def change_parking_spot_color(self, parking_spot_num, color):
        """특정 주차구역의 색상을 변경합니다."""
        if parking_spot_num in self.parking_spots:
            rect_item = self.parking_spots[parking_spot_num]
            
            # 주황색 그라데이션 생성
            if color == "orange":
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(255, 165, 0, 250))  # 밝은 주황색
                gradient.setColorAt(1, QColor(255, 140, 0, 200))  # 어두운 주황색
                rect_item.setBrush(QBrush(gradient))
                
                # 테두리는 하얀색으로 유지
                rect_item.setPen(QPen(QColor("white"), 20))
                print(f"🎯 주차구역 {parking_spot_num}번 색상을 주황색으로 변경 (테두리는 흰색 유지)")
            else:
                # 원래 색상으로 복원
                self.restore_parking_spot_color(parking_spot_num)

    def restore_parking_spot_color(self, parking_spot_num):
        """주차구역 색상을 원래 색상으로 복원합니다."""
        if parking_spot_num in self.parking_spots:
            rect_item = self.parking_spots[parking_spot_num]
            
            # 2번, 3번, 7번, 9번은 항상 주황색 유지 (점유된 상태)
            if parking_spot_num in [2, 3, 7, 9]:
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(255, 165, 0, 250))  # 밝은 주황색
                gradient.setColorAt(1, QColor(255, 140, 0, 200))  # 어두운 주황색
                rect_item.setBrush(QBrush(gradient))
                rect_item.setPen(QPen(QColor("white"), 20))
                print(f"🎯 주차구역 {parking_spot_num}번은 점유된 상태로 주황색 유지")
                return
            
            # 원래 색상 복원 (일반/장애인/전기차 구역별)
            if parking_spot_num in [1, 7]:  # 장애인 구역
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(135, 206, 250, 200))
                gradient.setColorAt(1, QColor(70, 130, 180, 150))
                rect_item.setBrush(QBrush(gradient))
            elif parking_spot_num in [4, 5, 10, 11]:  # 전기차 구역
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(0, 200, 130, 200))
                gradient.setColorAt(1, QColor(0, 150, 100, 150))
                rect_item.setBrush(QBrush(gradient))
            else:  # 일반 구역
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor("#303030"))
                gradient.setColorAt(1, QColor("#303030"))
                rect_item.setBrush(QBrush(gradient))
            
            # 테두리 원래 색상으로 복원
            rect_item.setPen(QPen(QColor("white"), 20))
            print(f"🎯 주차구역 {parking_spot_num}번 색상을 원래 색상으로 복원")

    def calculate_and_display_route(self):
        """받은 웨이포인트들을 직선으로 연결하여 경로를 표시합니다."""
        if not self.received_waypoints:
            QMessageBox.warning(self, "경로 오류", "경로를 계산할 웨이포인트가 없습니다.")
            return

        print(f"🗺️ 웨이포인트 경로 생성: {self.received_waypoints}")
        
        # 시작점은 항상 입구 (200, 200)
        start_point = QPointF(200, 200)
        
        # 받은 웨이포인트들을 QPointF로 변환
        waypoints_qpoints = [QPointF(p[0], p[1]) for p in self.received_waypoints]
        
        # 전체 경로: 시작점 + 웨이포인트들
        self.full_path_points = [start_point] + waypoints_qpoints
        
        # 마지막 웨이포인트가 주차구역인지 확인하고 색상 변경
        if self.received_waypoints:
            last_waypoint = self.received_waypoints[-1]
            destination_parking_spot = self.detect_parking_spot_from_waypoint(last_waypoint)
            
            if destination_parking_spot:
                print(f"🎯 마지막 웨이포인트는 주차구역 {destination_parking_spot}번 입니다. 색상을 주황색으로 변경합니다.")
                self.change_parking_spot_color(destination_parking_spot, "orange")
                self.current_parking_spot = destination_parking_spot  # 현재 주차구역 추적
            else:
                print(f"📍 마지막 웨이포인트 ({last_waypoint})는 주차구역이 아닙니다.")
        
        print(f"✅ 최종 경로: {len(self.full_path_points)}개 포인트")
        for i, point in enumerate(self.full_path_points):
            print(f"  {i+1}. ({point.x():.1f}, {point.y():.1f})")
        
        # 기존 경로 클리어 후 새 경로 그리기
        self.clear_path_layer()
        self.draw_straight_path(self.full_path_points)
        
        # 차량 위치 설정
        self.current_path_segment_index = 0
        self.is_exit_scenario = False  # 일반 주차 시나리오로 설정
        
        if not self.car.isVisible():
            self.car.setPos(start_point)
            self.car.show()
        
        # 경로 이탈 감지 타이머 시작 (1초마다 체크)
        self.route_deviation_timer.start(1000)
        
        self.update_hud_from_car_position(self.car.pos())

    def check_route_deviation(self):
        """경로 이탈 상태를 주기적으로 체크"""
        if not self.full_path_points or not self.car.isVisible():
            return
        
        car_pos = self.car.pos()
        
        # 주차 칸 박스 안에 있는지 확인 (예외 처리)
        if self.is_in_parking_spot(car_pos):
            # 주차 칸 안에 있으면 이탈 상태 초기화
            if self.is_deviating:
                self.is_deviating = False
                self.deviation_start_time = None
                print("🅿️ 주차 칸 내부로 복귀 - 경로 이탈 상태 해제")
            return
        
        # 경로에서의 거리 계산
        distance_to_route = self.calculate_distance_to_route(car_pos)
        
        if distance_to_route > self.route_tolerance:
            # 경로에서 벗어남
            if not self.is_deviating:
                self.is_deviating = True
                self.deviation_start_time = datetime.now()
                print(f"⚠️ 경로 이탈 감지 - 거리: {distance_to_route:.1f}픽셀")
            else:
                # 이미 이탈 상태인 경우 시간 체크
                if self.deviation_start_time:
                    deviation_duration = (datetime.now() - self.deviation_start_time).total_seconds()
                    if deviation_duration >= self.deviation_threshold:
                        self.show_route_recalculation_popup()
                        # 팝업 표시 후 이탈 상태 초기화 (중복 방지)
                        self.is_deviating = False
                        self.deviation_start_time = None
        else:
            # 경로에 복귀
            if self.is_deviating:
                self.is_deviating = False
                self.deviation_start_time = None
                print("✅ 경로에 복귀 - 이탈 상태 해제")

    def is_in_parking_spot(self, car_pos):
        """차량이 주차 칸 박스 안에 있는지 확인"""
        x, y = car_pos.x(), car_pos.y()
        
        # 주차구역별 좌표 범위 정의
        parking_spots = {
            # 1~5번 주차구역 (상단 주차구역)
            1: (0, 1600, 400, 400),      # 장애인 구역
            2: (400, 1600, 300, 400),    # 일반 구역
            3: (700, 1600, 300, 400),     # 일반 구역
            4: (1000, 1600, 300, 400),   # 전기차 구역
            5: (1300, 1600, 300, 400),   # 전기차 구역
            
            # 6~7번 주차구역 (우측 주차구역)
            6: (1600, 1200, 400, 400),   # 장애인 구역
            7: (1600, 800, 400, 400),    # 장애인 구역
            
            # 8~11번 주차구역 (하단 주차구역)
            8: (1300, 400, 300, 400),    # 일반 구역
            9: (1000, 400, 300, 400),     # 일반 구역
            10: (700, 400, 300, 400),     # 전기차 구역
            11: (400, 400, 300, 400),     # 전기차 구역
        }
        
        for spot_num, (spot_x, spot_y, spot_w, spot_h) in parking_spots.items():
            if spot_x <= x <= spot_x + spot_w and spot_y <= y <= spot_y + spot_h:
                return True
        
        return False

    def calculate_distance_to_route(self, car_pos):
        """차량 위치에서 가장 가까운 경로까지의 거리 계산"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return float('inf')
        
        min_distance = float('inf')
        
        # 각 경로 세그먼트에 대해 거리 계산
        for i in range(len(self.full_path_points) - 1):
            p1 = self.full_path_points[i]
            p2 = self.full_path_points[i + 1]
            
            # 점과 선분 사이의 최단 거리 계산
            distance = self.point_to_line_distance(car_pos, p1, p2)
            min_distance = min(min_distance, distance)
        
        return min_distance

    def point_to_line_distance(self, point, line_start, line_end):
        """점과 선분 사이의 최단 거리 계산"""
        # 선분의 벡터
        line_vec = line_end - line_start
        point_vec = point - line_start
        
        # 선분의 길이의 제곱
        line_len_sq = QPointF.dotProduct(line_vec, line_vec)
        
        if line_len_sq == 0:
            # 선분이 점인 경우
            return sqrt((point.x() - line_start.x())**2 + (point.y() - line_start.y())**2)
        
        # 점을 선분에 투영한 매개변수 t
        t = QPointF.dotProduct(point_vec, line_vec) / line_len_sq
        
        # t를 [0, 1] 범위로 제한
        t = max(0, min(1, t))
        
        # 선분 위의 가장 가까운 점
        closest_point = line_start + t * line_vec
        
        # 거리 계산
        return sqrt((point.x() - closest_point.x())**2 + (point.y() - closest_point.y())**2)

    def show_route_recalculation_popup(self):
        """경로 재탐색 팝업 표시"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("경로 이탈 감지")
        msg_box.setText("차량이 설정된 경로에서 벗어났습니다.")
        msg_box.setInformativeText("경로를 재탐색합니다.\n잠시만 기다려주세요.")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        # 팝업 스타일 설정
        msg_box.setStyleSheet(f"""
            QMessageBox {{
                background: {HYUNDAI_COLORS['surface']};
                color: {HYUNDAI_COLORS['text_primary']};
                border: 2px solid {HYUNDAI_COLORS['warning']};
                border-radius: 15px;
                font-family: 'Malgun Gothic';
                font-size: 14pt;
            }}
            QMessageBox QPushButton {{
                background: {HYUNDAI_COLORS['warning']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 12pt;
                font-weight: bold;
                min-width: 80px;
            }}
            QMessageBox QPushButton:hover {{
                background: {HYUNDAI_COLORS['danger']};
            }}
        """)
        
        print("🔄 경로 재탐색 팝업 표시")
        
        # TTS 음성 안내 추가 (강제 재생)
        if hasattr(self.hud, 'voice_guide'):
            self.hud.voice_guide.speak_instruction_force("경로를 재탐색합니다. 잠시만 기다려주세요.")
        
        msg_box.exec_()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.initial_fit:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.initial_fit = True
            
    def closeEvent(self, event):
        self.waypoint_receiver.stop()
        # 경로 이탈 감지 타이머 중지
        self.route_deviation_timer.stop()
        # TTS 엔진 정리
        if hasattr(self.hud, 'voice_guide'):
            self.hud.voice_guide.stop()
        super().closeEvent(event)

    def add_block(self, x, y, w, h, color, label=""):
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        
        # 브러시(채우기) 설정
        if "장애인" in label:
            gradient = QLinearGradient(x,y,x+w,y+h)
            gradient.setColorAt(0,QColor(135, 206, 250, 200))
            gradient.setColorAt(1,QColor(70, 130, 180,150))
            r.setBrush(QBrush(gradient))
        elif "전기차" in label:
            gradient = QLinearGradient(x,y,x+w,y+h)
            gradient.setColorAt(0,QColor(0,200,130,200))
            gradient.setColorAt(1,QColor(0,150,100,150))
            r.setBrush(QBrush(gradient))
        elif "일반" in label:
            gradient = QLinearGradient(x,y,x+w,y+h)
            gradient.setColorAt(0,QColor("#303030"))
            gradient.setColorAt(1,QColor("#303030"))
            r.setBrush(QBrush(gradient))
        else:
            r.setBrush(QBrush(color))
            
        # 펜(테두리) 설정 - 요청사항 반영
        if "장애인" in label or "전기" in label or "일반" in label:
            # 주차 구역에 해당하는 경우: 흰색, 20픽셀 테두리
            pen = QPen(QColor("white"), 20)
            r.setPen(pen)
        elif label in ["백화점 본관 입구", "영화관 입구", "문화시설 입구"]:
            # 백화점 본관 입구, 영화관 입구, 문화시설 입구: 노랑색 테두리로 통일
            pen = QPen(QColor(255, 255, 0), 20)  # 노랑색
            r.setPen(pen)
        elif "입출차" in label:
            # 입출차 구역은 테두리 없음
            r.setPen(QPen(Qt.NoPen))
        else:
            # 그 외의 블록(장애물, 입출차 구역 등)은 기존 테두리 유지
            r.setPen(QPen(QColor(255,255,255,100), 2))

        r.setParentItem(self.layer_static)

        # 라벨 설정
        if label:
            t = QGraphicsSimpleTextItem(label)
            t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setBrush(QColor(255,255,255))
            # 백화점 본관 입구, 영화관 입구, 문화시설 입구는 폰트 크기를 2.25배로 설정 (1.5 * 1.5)
            if label in ["백화점 본관 입구", "영화관 입구", "문화시설 입구"]:
                font = QFont("Malgun Gothic", int(FONT_SIZES['map_label'] * 2.25), QFont.Bold)
                # 목적지 라벨 위치를 주차구역 좌우에 배치
                if label == "백화점 본관 입구":
                    # 백화점: 블록(-400,1600,400,400) 왼쪽으로 310픽셀 이동한 위치에 라벨 배치
                    t.setPos(x+w//2-50-310, y-20)  # 기존 위치에서 왼쪽으로 310픽셀 이동
                elif label == "영화관 입구":
                    # 영화관: 오른쪽 주차구역 아래에 배치
                    t.setPos(x+w+20, y+h-40)
                elif label == "문화시설 입구":
                    # 문화시설: 우측 주차구역 옆에 배치
                    t.setPos(x+w+20, y+h-60)
            # 주차구역은 폰트 크기를 1.5배로 설정
            elif label in ["장애인", "전기", "일반"]:
                font = QFont("Malgun Gothic", int(FONT_SIZES['map_label'] * 1.5), QFont.Bold)
                t.setPos(x+5,y+h-25)
            else:
                font = QFont("Malgun Gothic", FONT_SIZES['map_label'], QFont.Bold)
                t.setPos(x+5,y+h-25)
            t.setFont(font)
            t.setParentItem(self.layer_static)
        
        return r  # QGraphicsRectItem 반환

    def add_hatched(self, x, y, w, h, edge=QColor("black"), fill=QColor(220, 20, 60, 90)):
        r = QGraphicsRectItem(QRectF(x,y,w,h)); b = QBrush(fill); b.setStyle(Qt.BDiagPattern); r.setBrush(b); r.setPen(QPen(edge,3)); r.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem("통행 불가"); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setBrush(QColor(255,100,100))
        font = QFont("Malgun Gothic", int(FONT_SIZES['map_label'] * 1.5), QFont.Bold); t.setFont(font); t.setPos(x+10,y+h-30); t.setParentItem(self.layer_static)

    def add_dot_label_static(self, p: QPointF, text: str, color=QColor("blue")):
        # 점(원형) 제거 - 텍스트만 표시
        t = QGraphicsSimpleTextItem(text); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setBrush(QColor(0,200,255))
        font = QFont("Malgun Gothic", FONT_SIZES['map_io_label'], QFont.Bold); t.setFont(font); t.setPos(p.x()-20,p.y()+25); t.setParentItem(self.layer_static)

    def build_static_layout(self):
        c_dis, c_ele, c_gen, c_obs, c_emp, c_io = QColor(135, 206, 250), QColor(0, 200, 130), QColor("#303030"), QColor(108, 117, 125), QColor(206, 212, 218), QColor("#303030")
        border = QGraphicsRectItem(0, 0, self.SCENE_W, self.SCENE_H); border.setPen(QPen(QColor(0, 170, 210), 12)); border.setBrush(QBrush(Qt.NoBrush)); border.setParentItem(self.layer_static)
        
        # 통행불가 구역을 가장 먼저 추가 (맨 뒤로 보내기 위해)
        self.add_hatched(400, 0, 1600, 400)
        
        # 입출차 구역 추가
        self.add_block(0, 0, 400, 400, c_io, "입출차")
        
        # 목적지 블록들 (입출차 제외) - 문화시설 입구 제외
        base = [
            (-400, 1600, 400, 400, c_emp, "백화점 본관 입구"),  # 백화점 본관 입구
            (1600, 1600, 400, 400, c_emp, "영화관 입구"),    # 영화관 입구
            (550, 1050, 800, 300, c_obs, "장애물")    # 금지구역
        ]
        
        # 새로운 주차구역들 (1~11번) - 7번, 8번 제외
        parking_spots = [
            # 1~5번 주차구역 (상단 주차구역)
            (0, 1600, 400, 400, c_dis, "장애인"),      # 장애인 구역
            (400, 1600, 300, 400, c_gen, "일반"),    # 일반 구역 (2번 - 점유됨)
            (700, 1600, 300, 400, c_gen, "일반"),    # 일반 구역 (3번 - 점유됨)
            (1000, 1600, 300, 400, c_ele, "전기"),   # 전기차 구역
            (1300, 1600, 300, 400, c_ele, "전기"),   # 전기차 구역 (5번)
            
            # 6번 주차구역 (우측 주차구역)
            (1600, 1200, 400, 400, c_dis, "장애인"),   # 장애인 구역 (6번 - 점유됨)
            
            # 9~11번 주차구역 (하단 주차구역) - 7번, 8번 제외
            (1000, 400, 300, 400, c_gen, "일반"),     # 일반 구역 (9번 - 점유됨)
            (700, 400, 300, 400, c_ele, "전기"),    # 전기차 구역
            (400, 400, 300, 400, c_ele, "전기")      # 전기차 구역
        ]
        
        for x, y, w, h, c, l in base: self.add_block(x, y, w, h, c, l)
        
        self.add_dot_label_static(self.ENTRANCE, "입구", QColor(0, 170, 210))
        
        # 주차구역을 추가하고 딕셔너리에 저장
        spot_numbers = [1, 2, 3, 4, 5, 6, 9, 10, 11]  # parking_spots 리스트와 매칭
        for i, (x, y, w, h, c, l) in enumerate(parking_spots):
            rect_item = self.add_block(x, y, w, h, c, l)
            if rect_item:  # add_block이 QGraphicsRectItem을 반환한다고 가정
                self.parking_spots[spot_numbers[i]] = rect_item
        
        # 2번, 3번, 9번 주차구역을 주황색으로 설정 (점유된 상태로 표시)
        self.change_parking_spot_color(2, "orange")
        self.change_parking_spot_color(3, "orange")
        self.change_parking_spot_color(9, "orange")
        
        # 문화시설 입구 추가
        self.add_block(1600, 400, 400, 400, c_emp, "문화시설 입구")
        
        # 7번 주차구역 추가
        rect_item = self.add_block(1600, 800, 400, 400, c_dis, "장애인")
        self.parking_spots[7] = rect_item
        
        # 8번 주차구역을 가장 마지막에 추가하여 가장 위에 표시되도록 함
        rect_item = self.add_block(1300, 400, 300, 400, c_gen, "일반")
        self.parking_spots[8] = rect_item
        
        # 7번 주차구역을 주황색으로 설정 (점유된 상태로 표시)
        self.change_parking_spot_color(7, "orange")

    def build_occupancy(self):
        W, H, C = self.SCENE_W, self.SCENE_H, self.CELL; gx, gy = (W + C - 1) // C, (H + C - 1) // C
        self.grid_w, self.grid_h = gx, gy; self.occ = bytearray(gx * gy)
        def idx(cx, cy): return cy * gx + cx
        def block_rect(x, y, w, h):
            x0,y0,x1,y1 = max(0,x-self.MARGIN), max(0,y-self.MARGIN), min(W,x+w+self.MARGIN), min(H,y+h+self.MARGIN)
            cx0,cy0,cx1,cy1 = int(x0//C), int(y0//C), int((x1-1)//C), int((y1-1)//C)
            for cy in range(cy0,cy1+1):
                for cx in range(cx0,cx1+1):
                    if 0<=cx<gx and 0<=cy<gy: self.occ[cy*gx+cx] = 1
        
        # 목적지 및 장애물 블록들
        for x,y,w,h,c,l in [
            (550,1050,800,300,0,""),      # 금지구역
            (400,0,1600,400,0,""),        # 하단 통행금지구역
            (1600,400,400,400,0,""),      # 문화시설 입구
            (1600,1600,400,400,0,""),     # 영화관 입구
            (-400,1600,400,400,0,""),     # 백화점 본관 입구
            (0,0,400,400,0,"")            # 입출차
        ]: 
            block_rect(x,y,w,h)
        
        # 새로운 주차구역들 (1~11번)
        parking_blocks = [
            # 1~5번 주차구역 (상단 주차구역)
            (0, 1600, 400, 400, 0, ""),      # 1번
            (400, 1600, 300, 400, 0, ""),    # 2번
            (700, 1600, 300, 400, 0, ""),    # 3번
            (1000, 1600, 300, 400, 0, ""),   # 4번
            (1300, 1600, 300, 400, 0, ""),   # 5번
            
            # 6~7번 주차구역 (우측 주차구역)
            (1600, 1200, 400, 400, 0, ""),   # 6번
            (1600, 800, 400, 400, 0, ""),    # 7번
            
            # 8~11번 주차구역 (하단 주차구역)
            (1300, 400, 300, 400, 0, ""),    # 8번
            (1000, 400, 300, 400, 0, ""),    # 9번
            (700, 400, 300, 400, 0, ""),     # 10번
            (400, 400, 300, 400, 0, "")      # 11번
        ]
        
        for x,y,w,h,c,l in parking_blocks: 
            block_rect(x,y,w,h)
        
        self._occ_idx = idx

    def clamp_point(self, p: QPointF): return QPointF(min(self.SCENE_W-1.,max(0.,p.x())), min(self.SCENE_H-1.,max(0.,p.y())))
    def pt_to_cell(self, p: QPointF): return int(p.x()//self.CELL), int(p.y()//self.CELL)
    def cell_to_pt_center(self, c): return QPointF(c[0]*self.CELL+self.CELL/2., c[1]*self.CELL+self.CELL/2.)
    def is_cell_free(self, cx, cy): return 0<=cx<self.grid_w and 0<=cy<self.grid_h and self.occ[self._occ_idx(cx,cy)]==0
    
    def find_nearest_free_cell_from_point(self, p: QPointF, max_radius_cells=100):
        """주어진 점에서 가장 가까운 자유 셀을 찾습니다."""
        sx, sy = self.pt_to_cell(p)
        print(f"🔍 자유 셀 검색: 원본 좌표 ({p.x():.1f}, {p.y():.1f}) -> 셀 ({sx}, {sy})")
        
        # 원본 셀이 자유하면 바로 반환
        if self.is_cell_free(sx, sy): 
            result = self.cell_to_pt_center((sx, sy))
            print(f"✅ 원본 셀이 자유함: {result}")
            return result
            
        # 주변에서 자유 셀 검색
        for r in range(1, max_radius_cells + 1):
            for dx in range(-r, r+1):
                for dy in [-r, r]:
                    if self.is_cell_free(sx+dx, sy+dy): 
                        result = self.cell_to_pt_center((sx+dx, sy+dy))
                        print(f"✅ 자유 셀 발견 (반경 {r}): ({sx+dx}, {sy+dy}) -> {result}")
                        return result
            for dy in range(-r+1, r):
                for dx in [-r, r]:
                    if self.is_cell_free(sx+dx, sy+dy): 
                        result = self.cell_to_pt_center((sx+dx, sy+dy))
                        print(f"✅ 자유 셀 발견 (반경 {r}): ({sx+dx}, {sy+dy}) -> {result}")
                        return result
        
        # 자유 셀을 찾지 못한 경우 원본 셀 반환 (강제)
        result = self.cell_to_pt_center((sx, sy))
        print(f"⚠️ 자유 셀을 찾지 못함, 원본 셀 반환: {result}")
        return result

    def astar(self, start_pt: QPointF, goal_pt: QPointF):
        """A* 알고리즘으로 경로를 찾습니다."""
        sx, sy = self.pt_to_cell(start_pt)
        gx, gy = self.pt_to_cell(goal_pt)
        W, H = self.grid_w, self.grid_h
        occ, idx = self.occ, self._occ_idx
        
        print(f"🗺️ A* 경로 검색: ({start_pt.x():.1f}, {start_pt.y():.1f}) -> ({goal_pt.x():.1f}, {goal_pt.y():.1f})")
        print(f"   셀 좌표: ({sx}, {sy}) -> ({gx}, {gy})")
        
        # 경계 체크
        if not (0 <= sx < W and 0 <= sy < H and 0 <= gx < W and 0 <= gy < H):
            print(f"❌ 경계 밖 좌표: 시작({sx}, {sy}) 목적지({gx}, {gy}), 그리드 크기({W}, {H})")
            return None
        
        # 시작점이나 목적지가 점유된 경우 가장 가까운 자유 셀로 이동
        if occ[idx(sx, sy)]:
            print(f"⚠️ 시작점 ({sx}, {sy})이 점유됨, 자유 셀 검색 중...")
            free_start = self.find_nearest_free_cell_from_point(start_pt)
            sx, sy = self.pt_to_cell(free_start)
            print(f"   새로운 시작점: ({sx}, {sy})")
            
        if occ[idx(gx, gy)]:
            print(f"⚠️ 목적지 ({gx}, {gy})이 점유됨, 자유 셀 검색 중...")
            free_goal = self.find_nearest_free_cell_from_point(goal_pt)
            gx, gy = self.pt_to_cell(free_goal)
            print(f"   새로운 목적지: ({gx}, {gy})")
        
        # 여전히 점유된 경우 경로 찾기 불가
        if occ[idx(sx, sy)] or occ[idx(gx, gy)]:
            print(f"❌ 시작점 또는 목적지가 여전히 점유됨: 시작({sx}, {sy})={occ[idx(sx, sy)]}, 목적지({gx}, {gy})={occ[idx(gx, gy)]}")
            return None
        
        openh = [(abs(sx - gx) + abs(sy - gy), 0, (sx, sy))]
        came, g = {}, {(sx, sy): 0}
        iterations = 0
        max_iterations = 10000  # 무한 루프 방지
        
        while openh and iterations < max_iterations:
            iterations += 1
            _, gc, (x, y) = heappop(openh)
            
            if (x, y) == (gx, gy):
                path = []
                curr = (x, y)
                while curr in came:
                    path.append(curr)
                    curr = came[curr]
                path.append((sx, sy))
                path.reverse()
                print(f"✅ 경로 발견! {len(path)}개 셀, {iterations}회 반복")
                return path
            
            for dx, dy, cst in [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)]:
                nx, ny = x + dx, y + dy
                
                if not (0 <= nx < W and 0 <= ny < H) or occ[idx(nx, ny)]:
                    continue
                
                ng = gc + cst
                
                if (nx, ny) not in g or ng < g[(nx, ny)]:
                    g[(nx, ny)] = ng
                    came[(nx, ny)] = (x, y)
                    heappush(openh, (ng + abs(nx - gx) + abs(ny - gy), ng, (nx, ny)))
        
        if iterations >= max_iterations:
            print(f"❌ 최대 반복 횟수 초과: {max_iterations}회")
        else:
            print(f"❌ 경로를 찾을 수 없음: {iterations}회 반복 후 종료")
        return None

    def simplify_cells(self, cells):
        if not cells: return []
        simp = [cells[0]]
        norm = lambda vx,vy: ((0 if vx==0 else (1 if vx>0 else -1)), (0 if vy==0 else (1 if vy>0 else -1)))
        for i in range(1, len(cells)-1):
            if norm(cells[i][0]-simp[-1][0], cells[i][1]-simp[-1][1]) != norm(cells[i+1][0]-cells[i][0], cells[i+1][1]-cells[i][1]): simp.append(cells[i])
        if len(cells)>1 and cells[-1]!=simp[-1]: simp.append(cells[-1])
        return simp

    def draw_straight_path(self, pts):
        if len(pts) < 2: return
        
        # 웨이포인트들을 순서대로 직선으로 연결
        for i in range(len(pts) - 1):
            start = pts[i]
            end = pts[i + 1]
            
            # 글로우 효과
            for width, alpha in [(self.PATH_WIDTH + 12, 60), (self.PATH_WIDTH + 6, 100)]:
                glow_pen = QPen(QColor(0,170,210,alpha), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                self.scene.addLine(start.x(), start.y(), end.x(), end.y(), glow_pen).setParentItem(self.layer_path)
            
            # 메인 경로
            main_pen = QPen(QColor(0,200,255), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self.scene.addLine(start.x(), start.y(), end.x(), end.y(), main_pen).setParentItem(self.layer_path)
            
            # 중앙 라인
            center_pen = QPen(QColor(255,255,255,150), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self.scene.addLine(start.x(), start.y(), end.x(), end.y(), center_pen).setParentItem(self.layer_path)

    def generate_hud_instructions(self, pts, is_exit_scenario=False):
        if len(pts) < 2: return []
        instructions, total_dist = [], 0
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i+1]
            dist_m = sqrt((p2.x()-p1.x())**2 + (p2.y()-p1.y())**2) / self.PIXELS_PER_METER
            total_dist += dist_m
            if i < len(pts) - 2:
                p3 = pts[i+2]
                angle = (degrees(atan2(p3.y()-p2.y(),p3.x()-p2.x()))-degrees(atan2(p2.y()-p1.y(),p2.x()-p1.x()))+180)%360-180
                direction = "좌회전" if angle>45 else ("우회전" if angle<-45 else "")
                if direction: 
                    if is_exit_scenario:
                        direction = f"출차 {direction}"
                    instructions.append((direction, total_dist)); total_dist = 0
        
        if is_exit_scenario:
            instructions.append(("출차 완료", total_dist))
        else:
            instructions.append(("목적지 도착", total_dist))
        return instructions

    def calculate_route_progress(self, car_pos):
        if not self.full_path_points or len(self.full_path_points)<2: return 0
        total_len = sum(sqrt((self.full_path_points[i+1].x()-p.x())**2 + (self.full_path_points[i+1].y()-p.y())**2) for i,p in enumerate(self.full_path_points[:-1]))
        if total_len==0: return 0
        min_dist, closest_seg, proj_ratio = float('inf'), 0, 0
        for i,p1 in enumerate(self.full_path_points[:-1]):
            p2 = self.full_path_points[i+1]; seg_vec, car_vec = p2-p1, car_pos-p1
            seg_len_sq = QPointF.dotProduct(seg_vec, seg_vec)
            if seg_len_sq==0: continue
            t = max(0, min(1, QPointF.dotProduct(car_vec, seg_vec)/seg_len_sq))
            proj = p1 + t * seg_vec
            dist = sqrt((car_pos.x()-proj.x())**2 + (car_pos.y()-proj.y())**2)
            if dist < min_dist: min_dist, closest_seg, proj_ratio = dist, i, t
        traveled = sum(sqrt((self.full_path_points[i+1].x()-p.x())**2+(self.full_path_points[i+1].y()-p.y())**2) for i,p in enumerate(self.full_path_points[:closest_seg]))
        if closest_seg < len(self.full_path_points)-1:
            p1, p2 = self.full_path_points[closest_seg], self.full_path_points[closest_seg+1]
            traveled += sqrt((p2.x()-p1.x())**2+(p2.y()-p1.y())**2) * proj_ratio
        return min(100, (traveled / total_len) * 100)

    def clear_path_layer(self):
        for child in self.layer_path.childItems(): self.scene.removeItem(child)

    def _update_current_segment(self, car_pos):
        if not self.full_path_points or len(self.full_path_points) < 2:
            return
            
        while self.current_path_segment_index < len(self.full_path_points) - 1:
            p_curr = self.full_path_points[self.current_path_segment_index]
            p_next = self.full_path_points[self.current_path_segment_index + 1]

            dist_to_next = sqrt((car_pos.x() - p_next.x())**2 + (car_pos.y() - p_next.y())**2)

            v_seg = p_next - p_curr
            v_car = car_pos - p_curr
            seg_len_sq = QPointF.dotProduct(v_seg, v_seg)
            proj_ratio = 1.0
            if seg_len_sq > 0:
                proj_ratio = QPointF.dotProduct(v_car, v_seg) / seg_len_sq

            if dist_to_next < 50 or proj_ratio > 1.0:
                self.current_path_segment_index += 1
            else:
                break

    def update_hud_from_car_position(self, car_pos):
        if not self.full_path_points: return
        self._update_current_segment(car_pos)
        remaining_pts = self.full_path_points[self.current_path_segment_index+1:]
        path_for_hud = [car_pos] + remaining_pts
        if len(path_for_hud) < 2:
            if self.is_exit_scenario:
                self.hud.update_navigation_info([("출차 완료", 0)], current_speed=0, route_progress=100)
            else:
                self.hud.update_navigation_info([("목적지 도착", 0)], current_speed=0, route_progress=100)
            return
        instructions = self.generate_hud_instructions(path_for_hud, self.is_exit_scenario)
        progress = self.calculate_route_progress(car_pos)
        speed = self.calculate_realistic_speed(instructions, progress, car_pos)
        self.hud.update_navigation_info(instructions, current_speed=speed, route_progress=progress)

    def calculate_realistic_speed(self, instructions, progress, car_pos):
        """현재 상황에 맞는 현실적인 속도 계산 (0-30km/h 범위)"""
        if not instructions:
            return 0
        
        direction, distance = instructions[0]
        
        # 기본 속도 설정
        base_speed = 20  # 기본 20km/h
        
        # 거리에 따른 속도 조절
        if distance <= 5:
            # 목적지가 가까우면 감속 (5-15km/h)
            speed = 5 + (distance / 5) * 10
        elif distance <= 20:
            # 중간 거리면 적당한 속도 (15-25km/h)
            speed = 15 + (distance / 20) * 10
        else:
            # 먼 거리면 정상 속도 (20-30km/h)
            speed = 20 + min(10, (distance - 20) / 50 * 10)
        
        # 방향에 따른 속도 조절
        if "좌회전" in direction or "우회전" in direction:
            # 회전 시 감속 (5-15km/h)
            speed = min(speed, 15)
        elif "목적지" in direction or "도착" in direction:
            # 목적지 근처에서 감속 (5-15km/h)
            speed = min(speed, 15)
        elif "출차" in direction:
            # 출차 시 조심스럽게 (10-20km/h)
            speed = min(speed, 20)
        
        # 진행률에 따른 미세 조절
        if progress < 20:
            # 시작 구간에서는 조금 더 신중하게
            speed *= 0.8
        elif progress > 80:
            # 마지막 구간에서는 더 조심스럽게
            speed *= 0.7
        
        # 출차 시나리오에서는 더 조심스럽게
        if self.is_exit_scenario:
            speed *= 0.75
        
        # 최종 속도 범위 제한 (0-30km/h)
        speed = max(0, min(30, int(speed)))
        
        return speed

    def start_exit_scenario(self):
        """출차 시나리오 시작 - 시계방향으로 출차 경로 생성"""
        if not self.car.isVisible():
            QMessageBox.warning(self, "출차 오류", "차량이 지도에 표시되지 않았습니다. 먼저 경로를 설정해주세요.")
            return
        
        car_pos = self.car.pos()
        parking_spot = self.detect_parking_spot(car_pos)
        
        if parking_spot is None:
            QMessageBox.warning(self, "출차 오류", "현재 위치에서 주차 구역을 찾을 수 없습니다.")
            return
        
        exit_waypoints = self.generate_exit_waypoints(parking_spot)
        if not exit_waypoints:
            QMessageBox.warning(self, "출차 오류", "출차 경로를 생성할 수 없습니다.")
            return
        
        # 출차 시나리오 상태 설정
        self.is_exit_scenario = True
        
        # 기존 경로 클리어
        self.clear_path_layer()
        
        # 출차 경로 계산 및 표시
        self.calculate_and_display_exit_route(exit_waypoints, parking_spot)
        
        QMessageBox.information(self, "출차 시나리오", f"주차 구역 {parking_spot}번에서 출차 경로를 시작합니다.\n입차 경로의 역순으로 안전하게 출차하세요.")

    def detect_parking_spot(self, car_pos):
        """차량 위치를 기반으로 주차 구역 번호 감지"""
        x, y = car_pos.x(), car_pos.y()
        
        # 새로운 주차 구역별 좌표 범위 정의 (1~11번)
        parking_spots = {
            # 1~5번 주차구역 (상단 주차구역)
            1: (0, 1600, 400, 400),      # 장애인 구역
            2: (400, 1600, 300, 400),    # 일반 구역
            3: (700, 1600, 300, 400),    # 일반 구역
            4: (1000, 1600, 300, 400),   # 전기차 구역
            5: (1300, 1600, 300, 400),   # 전기차 구역
            
            # 6~7번 주차구역 (우측 주차구역)
            6: (1600, 1200, 400, 400),   # 장애인 구역
            7: (1600, 800, 400, 400),     # 장애인 구역
            
            # 8~11번 주차구역 (하단 주차구역)
            8: (1300, 400, 300, 400),    # 일반 구역
            9: (1000, 400, 300, 400),     # 일반 구역
            10: (700, 400, 300, 400),     # 전기차 구역
            11: (400, 400, 300, 400),     # 전기차 구역
        }
        
        for spot_num, (spot_x, spot_y, spot_w, spot_h) in parking_spots.items():
            if spot_x <= x <= spot_x + spot_w and spot_y <= y <= spot_y + spot_h:
                return spot_num
        
        return None

    def generate_exit_waypoints(self, parking_spot):
        """sender.py의 입차 로직을 역으로 사용하여 출차 웨이포인트 생성"""
        # sender.py의 MANDATORY_WAYPOINT와 동일
        MANDATORY_WAYPOINT = [200, 925]
        
        # sender.py의 주차구역별 waypoint 좌표와 동일
        parking_waypoints = {
            # 주차구역 1-5 (상단, 왼쪽→오른쪽)
            1: [200, 1475], 2: [550, 1475], 3: [850, 1475], 4: [1150, 1475],
            5: [1450, 1475],
            # 주차구역 6-7 (우측, 위→아래)  
            6: [1475, 1400], 7: [1475, 1000],
            # 주차구역 8-11 (하단, 오른쪽→왼쪽)
            8: [1475, 925], 9: [1150, 925], 10: [850, 925], 11: [550, 925]
        }
        
        current_waypoint = parking_waypoints.get(parking_spot)
        if not current_waypoint:
            return None
        
        # 출차 최종 목적지는 무조건 (200, 200)으로 설정
        FINAL_DESTINATION = [200, 200]  # 최종 목적지 (입구)
        exit_waypoints = []
        
        if parking_spot == 1:  # 1번: (200,1475) -> (200,925) -> (200,200)
            exit_waypoints.append(MANDATORY_WAYPOINT)
            exit_waypoints.append(FINAL_DESTINATION)
        elif parking_spot in [2, 3, 4, 5]:  # 2~5번: 현재위치 -> (200, 1475) -> (200, 925) -> (200,200)
            exit_waypoints.append([200, 1475])
            exit_waypoints.append(MANDATORY_WAYPOINT)
            exit_waypoints.append(FINAL_DESTINATION)
        elif parking_spot == 6:  # 6번: (1475, 1400) -> (1475, 1475) -> (200, 1475) -> (200, 925) -> (200,200)
            exit_waypoints.append([1475, 1475])
            exit_waypoints.append([200, 1475])
            exit_waypoints.append(MANDATORY_WAYPOINT)
            exit_waypoints.append(FINAL_DESTINATION)
        elif parking_spot == 7:  # 7번: (1475, 1000) -> (1475, 925) -> (200, 925) -> (200,200)
            exit_waypoints.append([1475, 925])
            exit_waypoints.append(MANDATORY_WAYPOINT)
            exit_waypoints.append(FINAL_DESTINATION)
        elif parking_spot in [8, 9, 10, 11]:  # 8~11번: 현재위치 -> (200, 925) -> (200,200)
            exit_waypoints.append(MANDATORY_WAYPOINT)
            exit_waypoints.append(FINAL_DESTINATION)
        
        print(f"🚗 출차 경로 생성 - 주차구역 {parking_spot}번")
        print(f"   최종 목적지: {FINAL_DESTINATION}")
        print(f"   경로 포인트: {exit_waypoints}")
        
        return exit_waypoints

    def get_parking_spot_start_waypoint(self, parking_spot):
        """주차구역별 시작 웨이포인트 반환 - sender.py의 좌표와 동일하게 설정"""
        # sender.py의 주차구역별 waypoint 좌표와 동일
        parking_waypoints = {
            # 주차구역 1-5 (상단, 왼쪽→오른쪽)
            1: [200, 1475], 2: [550, 1475], 3: [850, 1475], 4: [1150, 1475],
            5: [1450, 1475],
            # 주차구역 6-7 (우측, 위→아래)  
            6: [1475, 1400], 7: [1475, 1000],
            # 주차구역 8-11 (하단, 오른쪽→왼쪽)
            8: [1475, 925], 9: [1150, 925], 10: [850, 925], 11: [550, 925]
        }
        
        if parking_spot in parking_waypoints:
            return parking_waypoints[parking_spot]
        
        return None

    def calculate_and_display_exit_route(self, exit_waypoints, parking_spot):
        """출차 경로 계산 및 표시 - 각 주차구역 핀포인트부터 시작"""
        # 주차구역별 핀포인트에서 시작
        assigned_waypoint = self.get_parking_spot_start_waypoint(parking_spot)
        if not assigned_waypoint:
            QMessageBox.warning(self, "출차 경로 실패", "배정 웨이포인트를 찾을 수 없습니다.")
            return
        
        start_point = QPointF(assigned_waypoint[0], assigned_waypoint[1])
        
        # 전체 경로 구성: 핀포인트 → 웨이포인트들 (직선 연결)
        waypoints_qpoints = [QPointF(p[0], p[1]) for p in exit_waypoints]
        self.full_path_points = [start_point] + waypoints_qpoints
        
        print(f"✅ 출차 경로: {len(self.full_path_points)}개 포인트")
        for i, point in enumerate(self.full_path_points):
            print(f"  {i+1}. ({point.x():.1f}, {point.y():.1f})")
        
        # 기존 경로 클리어 후 출차 경로 그리기
        self.clear_path_layer()
        self.draw_exit_path(self.full_path_points)
        
        # 차량은 현재 위치에 그대로 두고 경로만 표시
        self.car.show()
        
        # 경로 이탈 감지 타이머 시작 (1초마다 체크)
        self.route_deviation_timer.start(1000)
        
        self.current_path_segment_index = 0
        self.update_hud_from_car_position(self.car.pos())

    def draw_exit_path(self, pts):
        """출차 경로 그리기 (시계방향 표시)"""
        if len(pts) < 2: 
            print(f"출차 경로 포인트가 부족합니다: {len(pts)}개")
            return
        
        print(f"출차 경로 그리기 시작: {len(pts)}개 포인트")
        
        # 시계방향 화살표를 포함한 경로 그리기
        for i in range(len(pts) - 1):
            start, end = pts[i], pts[i + 1]
            print(f"경로 구간 {i+1}: ({start.x():.0f}, {start.y():.0f}) -> ({end.x():.0f}, {end.y():.0f})")
            
            # 글로우 효과
            for width, alpha in [(self.PATH_WIDTH + 12, 60), (self.PATH_WIDTH + 6, 100)]:
                glow_pen = QPen(QColor(255, 165, 0, alpha), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)  # 오렌지색 글로우
                line_item = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), glow_pen)
                line_item.setParentItem(self.layer_path)
            
            # 메인 경로 (오렌지색)
            main_pen = QPen(QColor(255, 140, 0), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            line_item = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), main_pen)
            line_item.setParentItem(self.layer_path)
            
            # 중앙 라인 (흰색)
            center_pen = QPen(QColor(255, 255, 255, 150), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            line_item = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), center_pen)
            line_item.setParentItem(self.layer_path)
            
            # 시계방향 화살표 그리기
            self.draw_clockwise_arrow(start, end)
        
        print("출차 경로 그리기 완료")

    def draw_clockwise_arrow(self, start, end):
        """시계방향 화살표 그리기"""
        # 선분의 중점 계산
        mid_x = (start.x() + end.x()) / 2
        mid_y = (start.y() + end.y()) / 2
        
        # 선분의 방향 벡터 계산
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
        
        # 정규화된 방향 벡터
        nx = dx / length
        ny = dy / length
        
        # 시계방향 화살표 크기
        arrow_size = 20
        
        # 화살표의 세 점 계산 (시계방향)
        # 화살표 머리 부분
        arrow_head_x = mid_x + nx * arrow_size
        arrow_head_y = mid_y + ny * arrow_size
        
        # 화살표 왼쪽 날개 (시계방향으로 30도 회전)
        angle = radians(30)
        cos_angle = cos(angle)
        sin_angle = sin(angle)
        
        left_wing_x = mid_x + (nx * cos_angle - ny * sin_angle) * arrow_size * 0.6
        left_wing_y = mid_y + (nx * sin_angle + ny * cos_angle) * arrow_size * 0.6
        
        # 화살표 오른쪽 날개 (시계방향으로 -30도 회전)
        right_wing_x = mid_x + (nx * cos_angle + ny * sin_angle) * arrow_size * 0.6
        right_wing_y = mid_y + (-nx * sin_angle + ny * cos_angle) * arrow_size * 0.6
        
        # 화살표 그리기
        arrow_points = [
            QPointF(arrow_head_x, arrow_head_y),
            QPointF(left_wing_x, left_wing_y),
            QPointF(right_wing_x, right_wing_y)
        ]
        
        # 화살표 폴리곤 생성
        arrow_polygon = QPolygonF(arrow_points)
        
        # 화살표 그리기 (오렌지색)
        arrow_item = QGraphicsPolygonItem(arrow_polygon)
        arrow_item.setBrush(QBrush(QColor(255, 140, 0)))
        arrow_item.setPen(QPen(QColor(255, 255, 255), 2))
        arrow_item.setParentItem(self.layer_path)
        self.scene.addItem(arrow_item)

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
import sys
import os

# 중요: OpenCV import 전에 Qt 플러그인 경로를 설정해야 함
# OpenCV의 Qt 플러그인 충돌을 완전히 방지하기 위해 PyQt5 경로를 먼저 설정

# PyQt5의 플러그인 경로를 동적으로 찾아서 설정
try:
    # 방법 1: PyQt5.QtCore를 사용하여 실제 플러그인 경로 확인
    # (하지만 PyQt5를 import하면 OpenCV보다 먼저 로드되어야 함)
    # 따라서 시스템 경로를 직접 확인
    
    # 시스템 Qt 플러그인 경로 시도 (우선순위 1)
    system_qt_paths = [
        '/usr/lib/x86_64-linux-gnu/qt5/plugins',
        '/usr/lib/qt5/plugins',
        '/usr/lib/qt/plugins'
    ]
    
    qt_plugin_path = None
    for path in system_qt_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, 'platforms')):
            qt_plugin_path = path
            break
    
    # 방법 2: PyQt5 패키지에서 플러그인 경로 찾기
    if not qt_plugin_path:
        try:
            import PyQt5
            pyqt5_path = os.path.dirname(PyQt5.__file__)
            possible_paths = [
                os.path.join(pyqt5_path, 'Qt5', 'plugins'),
                os.path.join(os.path.dirname(pyqt5_path), 'PyQt5', 'Qt5', 'plugins')
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    qt_plugin_path = path
                    break
        except:
            pass
    
    # 플러그인 경로 설정
    if qt_plugin_path:
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugin_path
        print(f"✅ Qt 플러그인 경로 설정: {qt_plugin_path}")
    else:
        print("⚠️ PyQt5 플러그인 경로를 찾을 수 없습니다.")
except Exception as e:
    print(f"⚠️ PyQt5 플러그인 경로 설정 실패: {e}")

# OpenCV가 Qt 백엔드를 사용하지 않도록 환경 변수 설정
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'

# OpenCV import
import cv2

# OpenCV import 후에도 올바른 플러그인 경로가 설정되어 있는지 확인
# OpenCV가 환경 변수를 덮어쓸 수 있으므로 재확인
if 'QT_QPA_PLATFORM_PLUGIN_PATH' in os.environ:
    current_path = os.environ['QT_QPA_PLATFORM_PLUGIN_PATH']
    # OpenCV의 플러그인 경로라면 무시하고 시스템 경로로 재설정
    if 'cv2' in current_path or 'opencv' in current_path.lower():
        print(f"⚠️ OpenCV가 Qt 플러그인 경로를 덮어씀: {current_path}")
        # 시스템 경로로 재설정
        system_qt_paths = [
            '/usr/lib/x86_64-linux-gnu/qt5/plugins',
            '/usr/lib/qt5/plugins',
            '/usr/lib/qt/plugins'
        ]
        for path in system_qt_paths:
            if os.path.exists(path) and os.path.exists(os.path.join(path, 'platforms')):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = path
                print(f"✅ Qt 플러그인 경로 재설정: {path}")
                break

# OpenCV의 Qt 플러그인 디렉토리 경로 확인 (정보용)
try:
    cv2_plugin_path = os.path.join(os.path.dirname(cv2.__file__), 'qt', 'plugins')
    if os.path.exists(cv2_plugin_path):
        print(f"ℹ️ OpenCV Qt 플러그인 발견: {cv2_plugin_path} (사용 안 함)")
except:
    pass

from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import time

ESP32_CAM_URL = "http://192.168.0.29:81/stream"

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    connection_status_signal = pyqtSignal(str)  # 연결 상태 신호 추가
    error_signal = pyqtSignal(str)  # 에러 신호 추가
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self._run_flag = True
        self.cap = None
        self.reconnect_delay = 2.0  # 재연결 대기 시간 (초)
        self.max_reconnect_attempts = 10  # 최대 재연결 시도 횟수
        self.reconnect_count = 0
        self.frame_timeout = 5.0  # 프레임 수신 타임아웃 (초)
        self.last_frame_time = None
        self.fps_target = 30  # 목표 FPS
        self.frame_interval = 1.0 / self.fps_target
        self.last_frame_received = time.time()
        
    def _initialize_capture(self):
        """비디오 캡처 객체 초기화"""
        try:
            if self.cap:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(self.url)
            
            # 캡처 설정 최적화
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 버퍼 크기 최소화 (지연 감소)
            # 해상도 설정 (ESP32-CAM 기본 해상도에 맞춤, 필요시 조정)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # 자동 노출 비활성화 (안정성 향상)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            # FPS 제한 (네트워크 부하 감소)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # 연결 타임아웃 설정
            # 참고: OpenCV VideoCapture는 타임아웃을 직접 지원하지 않으므로
            # read() 호출 시 타임아웃을 구현해야 함
            
            if self.cap.isOpened():
                self.connection_status_signal.emit("연결됨")
                self.reconnect_count = 0
                print(f"✅ ESP32 카메라 연결 성공: {self.url}")
                return True
            else:
                self.connection_status_signal.emit("연결 실패")
                print(f"❌ ESP32 카메라 연결 실패: {self.url}")
                return False
                
        except Exception as e:
            self.connection_status_signal.emit("연결 오류")
            self.error_signal.emit(f"초기화 오류: {str(e)}")
            print(f"❌ 비디오 캡처 초기화 오류: {e}")
            return False
    
    def run(self):
        """메인 스레드 루프"""
        while self._run_flag:
            # 캡처 객체가 없거나 닫혀있으면 초기화 시도
            if self.cap is None or not self.cap.isOpened():
                if not self._try_reconnect():
                    # 재연결 실패 시 대기 후 재시도
                    self.msleep(int(self.reconnect_delay * 1000))
                    continue
            
            try:
                # 버퍼에 쌓인 오래된 프레임들을 버리기 위해 여러 번 읽기
                # (지연 최소화를 위해 최신 프레임만 사용)
                ret, frame = None, None
                for _ in range(2):  # 최대 2번까지 읽어서 최신 프레임 확보
                    temp_ret, temp_frame = self.cap.read()
                    if temp_ret and temp_frame is not None:
                        ret, frame = temp_ret, temp_frame
                    else:
                        # 더 이상 프레임이 없으면 중단
                        break
                
                # 최신 프레임 처리
                if ret and frame is not None:
                    # 성공적으로 프레임 수신
                    self.last_frame_time = time.time()
                    self.last_frame_received = time.time()
                    self.reconnect_count = 0  # 성공 시 재연결 카운터 리셋
                    
                    # BGR을 RGB로 변환
                    try:
                        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_image.shape
                        bytes_per_line = ch * w
                        
                        # QImage로 변환 (데이터 복사)
                        qt_image = QImage(rgb_image.copy(), w, h, bytes_per_line, QImage.Format_RGB888)
                        self.change_pixmap_signal.emit(qt_image)
                        
                    except Exception as e:
                        print(f"⚠️ 이미지 변환 오류: {e}")
                        self.msleep(10)
                        
                else:
                    # 프레임 읽기 실패
                    self._handle_frame_read_error()
                    
            except Exception as e:
                # 예외 처리
                print(f"❌ 프레임 읽기 오류: {e}")
                self.error_signal.emit(f"프레임 읽기 오류: {str(e)}")
                self.cap = None  # 캡처 객체 리셋
                self.msleep(int(self.reconnect_delay * 1000))
            
            # FPS 제어를 위한 대기
            current_time = time.time()
            elapsed = current_time - self.last_frame_received if self.last_frame_received else 0
            sleep_time = max(0, (self.frame_interval - elapsed) * 1000)
            if sleep_time > 0:
                self.msleep(int(sleep_time))
            self.last_frame_received = time.time()
        
        # 정리
        self._cleanup()
    
    def _try_reconnect(self):
        """재연결 시도"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            self.connection_status_signal.emit("재연결 실패")
            self.error_signal.emit(f"최대 재연결 시도 횟수({self.max_reconnect_attempts}) 초과")
            print(f"❌ 최대 재연결 시도 횟수 초과: {self.max_reconnect_attempts}")
            return False
        
        self.reconnect_count += 1
        self.connection_status_signal.emit(f"재연결 시도 중... ({self.reconnect_count}/{self.max_reconnect_attempts})")
        print(f"🔄 재연결 시도 {self.reconnect_count}/{self.max_reconnect_attempts}...")
        
        return self._initialize_capture()
    
    def _handle_frame_read_error(self):
        """프레임 읽기 오류 처리"""
        # 타임아웃 체크
        if self.last_frame_time:
            time_since_last_frame = time.time() - self.last_frame_time
            if time_since_last_frame > self.frame_timeout:
                print(f"⚠️ 프레임 수신 타임아웃 ({time_since_last_frame:.1f}초)")
                self.cap = None  # 캡처 객체 리셋하여 재연결 유도
                return
        
        # 짧은 대기 후 재시도
        self.msleep(100)
    
    def _cleanup(self):
        """리소스 정리"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
            print("🧹 비디오 캡처 리소스 정리 완료")
        except Exception as e:
            print(f"⚠️ 정리 중 오류: {e}")
    
    def stop(self):
        """스레드 종료"""
        self._run_flag = False
        self.wait()
    
    def update_url(self, new_url):
        """URL 업데이트 (재연결 트리거)"""
        self.url = new_url
        if self.cap:
            self.cap.release()
            self.cap = None
        print(f"🔄 URL 업데이트: {new_url}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESP32-CAM Stream")
        self.setGeometry(100, 100, 800, 600)
        
        # 메인 레이아웃
        from PyQt5.QtWidgets import QVBoxLayout, QWidget, QStatusBar
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 이미지 라벨 생성
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("ESP32 카메라 연결 중...")
        self.image_label.setStyleSheet("color: white; font-size: 18px; background-color: #1a1a1a;")
        layout.addWidget(self.image_label)
        
        # 상태바 생성
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("color: white; background-color: #2d2d2d;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("초기화 중...")
        
        # 비디오 쓰레드 시작
        self.thread = VideoThread(ESP32_CAM_URL)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.connection_status_signal.connect(self.update_connection_status)
        self.thread.error_signal.connect(self.handle_error)
        self.thread.start()
        
        # FPS 계산용 변수
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_status = "초기화 중..."
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)  # 1초마다 FPS 업데이트
    
    def update_image(self, qt_image):
        """이미지 업데이트"""
        try:
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.image_label.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            
            # FPS 카운트
            self.frame_count += 1
        except Exception as e:
            print(f"⚠️ 이미지 업데이트 오류: {e}")
    
    def update_connection_status(self, status):
        """연결 상태 업데이트"""
        self.current_status = status
        status_message = f"상태: {status}"
        if self.frame_count > 0:
            elapsed = time.time() - self.fps_start_time
            if elapsed > 0:
                fps = self.frame_count / elapsed
                status_message = f"FPS: {fps:.1f} | {status_message}"
        
        self.status_bar.showMessage(status_message)
        if status == "연결됨":
            self.status_bar.setStyleSheet("color: #00ff00; background-color: #2d2d2d;")
        elif "재연결" in status:
            self.status_bar.setStyleSheet("color: #ffa500; background-color: #2d2d2d;")
        else:
            self.status_bar.setStyleSheet("color: #ff0000; background-color: #2d2d2d;")
    
    def handle_error(self, error_message):
        """에러 처리"""
        print(f"❌ 에러: {error_message}")
        self.status_bar.showMessage(f"오류: {error_message}")
        self.status_bar.setStyleSheet("color: #ff0000; background-color: #2d2d2d;")
    
    def update_fps(self):
        """FPS 계산 및 표시"""
        elapsed = time.time() - self.fps_start_time
        if elapsed > 0:
            fps = self.frame_count / elapsed if self.frame_count > 0 else 0.0
            status_message = f"FPS: {fps:.1f} | 상태: {self.current_status}"
            self.status_bar.showMessage(status_message)
            self.frame_count = 0
            self.fps_start_time = time.time()
    
    def closeEvent(self, event):
        """창 닫기 이벤트"""
        if self.fps_timer:
            self.fps_timer.stop()
        if self.thread:
            self.thread.stop()
        event.accept()

if __name__ == "__main__":
    # Qt 플러그인 경로 확인 및 출력
    if 'QT_QPA_PLATFORM_PLUGIN_PATH' in os.environ:
        print(f"🔧 사용 중인 Qt 플러그인 경로: {os.environ['QT_QPA_PLATFORM_PLUGIN_PATH']}")
    else:
        print("⚠️ QT_QPA_PLATFORM_PLUGIN_PATH가 설정되지 않았습니다.")
    
    # QApplication 생성
    app = QApplication(sys.argv)
    
    # OpenCV가 Qt 백엔드를 사용하지 않도록 설정
    app.setAttribute(Qt.AA_ShareOpenGLContexts, False)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
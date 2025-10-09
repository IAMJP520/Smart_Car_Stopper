# 파일 이름: main_launcher_sy.py
# main_launcher_sy.py - gui_app.py - UI_testing.py
import sys
import socket
import json
import threading
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

# gui_app.py 파일에서 HyundaiStyleUI 클래스를 가져옵니다.
from gui_app import HyundaiStyleUI 

# --- ESP32 트리거 수신을 위한 클래스 ---
class TriggerReceiver(QObject):
    """ESP32로부터 GUI 시작 트리거와 차량 IP 주소를 수신하는 클래스"""
    
    # [수정] 시그널이 차량의 IP 주소(str)를 전달하도록 변경
    start_gui_signal = pyqtSignal(str)

    def __init__(self, host='0.0.0.0', port=7777):
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        print(f"📡 트리거 수신기 초기화. PC IP: {self.get_local_ip()}:{self.port}")

    def get_local_ip(self):
        """현재 PC의 로컬 IP 주소를 찾아 반환합니다."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def start(self):
        """수신 서버를 별도의 스레드에서 시작합니다."""
        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()

    def _run_server(self):
        """서버 메인 루프"""
        try:
            
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            print(f"✅ ESP32의 시작 신호를 {self.host}:{self.port}에서 대기 중...")

            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    print(f"🔗 클라이언트 연결됨: {addr}")
                    self.handle_connection(client_socket)
                except Exception as e:
                    if self.running:
                        print(f"❌ 연결 수락 중 오류: {e}")
                    break
        except Exception as e:
            print(f"❌ 서버 시작 오류: {e}")

    def handle_connection(self, client_socket):
        """클라이언트로부터 데이터를 수신하고 처리합니다."""
        try:
            data = client_socket.recv(1024).decode('utf-8')
            if data:
                print(f"📬 수신 데이터: {data}")
                message = json.loads(data)
                
                if message.get('command') == 'start_simulation':
                    # [수정] ESP32가 보낸 vehicle_ip 추출
                    vehicle_ip = message.get('vehicle_ip')
                    
                    if vehicle_ip:
                        print(f"🚀 'start_simulation' 트리거 수신! 차량 IP: {vehicle_ip}. GUI를 시작합니다.")
                        # [수정] 시그널에 IP 주소를 담아 보냄
                        self.start_gui_signal.emit(vehicle_ip)
                        response = {"status": "GUI started"}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        self.stop()
                    else:
                        print("❌ 오류: 트리거는 수신했으나 차량 IP 주소가 없습니다.")
        except json.JSONDecodeError:
            print("❌ 잘못된 JSON 형식의 데이터 수신")
        except Exception as e:
            print(f"❌ 데이터 처리 중 오류: {e}")
        finally:
            client_socket.close()

    def stop(self):
        """수신 서버를 중지합니다."""
        if self.running:
            print("🛑 트리거 수신기를 종료합니다.")
            self.running = False
            if self.server_socket:
                self.server_socket.close()


# --- 애플리케이션 전체를 관리하는 컨트롤러 ---
class AppController(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.window = None
        self.receiver = TriggerReceiver()
        self.receiver.start_gui_signal.connect(self.show_gui)

    def run(self):
        """애플리케이션 시작: 수신기 실행"""
        self.receiver.start()

    # [수정] show_gui 함수가 vehicle_ip를 인자로 받도록 변경
    def show_gui(self, vehicle_ip):
        """GUI를 생성하고 화면에 표시하는 슬롯 함수"""
        if not self.window:
            print(f"🖥️  HyundaiStyleUI 인스턴스 생성 (대상 차량 IP: {vehicle_ip})")
            # [수정] HyundaiStyleUI 생성자에 vehicle_ip를 전달
            self.window = HyundaiStyleUI(vehicle_ip=vehicle_ip)
        else:
            print("🖥️  이미 UI가 실행 중입니다.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    font = QFont("Malgun Gothic")
    font.setPointSize(11)
    app.setFont(font)
    app.setStyle('Fusion')

    controller = AppController(app)
    controller.run()

    print("⏳ PyQt 애플리케이션 이벤트 루프 시작. GUI는 트리거를 기다립니다...")
    sys.exit(app.exec_())
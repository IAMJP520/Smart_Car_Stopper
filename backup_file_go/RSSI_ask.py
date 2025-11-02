# 파일명: RSSI_ask.py
# 역할: 사용자에게 차량 정보를 선택받는 GUI를 띄우고, 선택된 정보를 블루투스로 전송합니다.
# 변경사항: PyBluez-CE 의존 제거 → 표준 라이브러리 socket(AF_BLUETOOTH, BTPROTO_RFCOMM) 사용

import sys
import socket  # ★ 표준 라이브러리
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QMessageBox)
from PyQt5.QtCore import Qt

# --- (1/3) 블루투스 데이터 전송 함수 ---
def send_data_to_rpi(message: str) -> bool:
    """
    주어진 메시지를 라즈베리파이로 전송합니다. (RFCOMM / SPP)
    라즈베리파이 측은 RFCOMM 서버(channel 1)를 열어두어야 합니다.
    """
    RPI_MAC_ADDRESS = "2C:CF:67:47:BF:50"  # ← 실제 Pi MAC
    CHANNEL = 1  # Pi 서버와 동일 채널

    if len(RPI_MAC_ADDRESS.split(":")) != 6:
        _alert("블루투스 설정 오류", "라즈베리파이 MAC 주소 형식이 올바르지 않습니다.")
        return False

    print(f"라즈베리파이({RPI_MAC_ADDRESS})로 데이터 전송 시도: '{message}'")

    # Linux 이외 환경/커널에서 AF_BLUETOOTH가 없을 수 있으므로 방어
    if not hasattr(socket, "AF_BLUETOOTH") or not hasattr(socket, "BTPROTO_RFCOMM"):
        _alert("환경 불일치", "이 시스템은 RFCOMM 블루투스 소켓을 지원하지 않습니다.")
        return False

    try:
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        sock.connect((RPI_MAC_ADDRESS, CHANNEL))
        sock.sendall(message.encode("utf-8"))
        # (선택) 응답 대기
        try:
            sock.settimeout(2.0)
            resp = sock.recv(1024)
            if resp:
                print("<<< 응답:", resp.decode(errors="ignore").strip())
        except Exception:
            pass
        finally:
            sock.close()

        print(">>> 데이터 전송 성공.")
        return True

    except PermissionError as e:
        # 일부 Linux는 블루투스 소켓에 CAP_NET_ADMIN/RAW 권한 필요
        _alert("권한 오류", f"블루투스 소켓 권한이 부족합니다.\n(관리자 권한 또는 블루투스 활성화 필요)\n\n{e}")
        return False
    except OSError as e:
        _alert("블루투스 통신 실패",
               f"라즈베리파이와 연결할 수 없습니다.\n"
               f"- Pi가 RFCOMM 서버(channel 1)를 열었는지\n"
               f"- 두 장치가 bluetoothctl로 pair/trust/connect 되었는지\n"
               f"- MAC 주소가 맞는지\n을 확인하세요.\n\n에러: {e}")
        return False
    except Exception as e:
        _alert("블루투스 통신 실패", f"예상치 못한 오류가 발생했습니다.\n\n{e}")
        return False


def _alert(title: str, text: str):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(title)
    msg.setText(title)
    msg.setInformativeText(text)
    msg.exec_()

# --- (2/3) 사용자 선택 GUI 클래스 ---
class SelectionUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("차량 정보 선택")
        self.setGeometry(300, 300, 500, 350)

        # 스타일
        self.setStyleSheet("""
            QWidget {
                background-color: #0A0E1A;
                color: #FFFFFF;
                font-family: 'Malgun Gothic';
            }
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #00AAD2;
            }
            QPushButton {
                background-color: #002C5F;
                border: 2px solid #007FA3;
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
                padding: 20px;
            }
            QPushButton:hover {
                background-color: #007FA3;
                border: 2px solid #00AAD2;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("주차 유형을 선택하세요", self)
        title.setAlignment(Qt.AlignCenter)

        b1 = QPushButton("🅿️ 일반 차량 (일반 구역)", self)
        b2 = QPushButton("♿ 일반 차량 (장애인 구역)", self)
        b3 = QPushButton("⚡ 전기차 (충전 구역)", self)
        b4 = QPushButton("♿ 전기차 (장애인 구역)", self)

        b1.clicked.connect(lambda: self.on_selection("regular_normal"))
        b2.clicked.connect(lambda: self.on_selection("regular_handicapped"))
        b3.clicked.connect(lambda: self.on_selection("electric_charging"))
        b4.clicked.connect(lambda: self.on_selection("electric_handicapped"))

        layout.addWidget(title)
        layout.addWidget(b1)
        layout.addWidget(b2)
        layout.addWidget(b3)
        layout.addWidget(b4)
        self.setLayout(layout)
        self.show()

    def on_selection(self, selection_message: str):
        print(f"선택됨: {selection_message}")
        success = send_data_to_rpi(selection_message)
        if success:
            QMessageBox.information(self, "전송 완료", "차량 정보가 관제 서버로 전송되었습니다.")
        QApplication.instance().quit()

# --- (3/3) 프로그램 실행 ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = SelectionUI()
    sys.exit(app.exec_())

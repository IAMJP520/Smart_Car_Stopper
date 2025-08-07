# main.py
import sys, os
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QTimer, QUrl


class NavigationUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Navigation UI")
        self.resize(900, 600)

        # 중앙 위젯과 레이아웃
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 상단 정보 표시
        self.info_label = QLabel("목적지: 경복궁 | 거리: 1.2km | ETA: 5분")
        layout.addWidget(self.info_label)

        # QWebEngineView로 지도 로드
        self.web_view = QWebEngineView()
        map_path = os.path.abspath("map.html")
        self.web_view.load(QUrl.fromLocalFile(map_path))
        layout.addWidget(self.web_view)

        # HTML 로드 완료 후 위치 업데이트 시작
        self.web_view.loadFinished.connect(self.start_updates)

    def start_updates(self, ok):
        if not ok:
            print("❌ HTML 로드 실패")
            return
        print("✅ HTML 로드 완료, JS 함수 확인 중...")

        # updatePosition 함수 존재 여부 체크
        self.web_view.page().runJavaScript("typeof updatePosition", self.debug_js_function)

        # 테스트: 2초마다 마커 이동
        self.lat, self.lon = 37.5665, 126.9780
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(2000)

    def debug_js_function(self, result):
        print(f"JS typeof updatePosition → {result}")
        if result != "function":
            print("⚠️ updatePosition 함수가 HTML에서 정의되지 않았습니다.")

    def update_position(self):
        self.lat += 0.0005
        self.lon += 0.0003
        js_code = f"updatePosition({self.lat}, {self.lon});"
        self.web_view.page().runJavaScript(js_code)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NavigationUI()
    window.show()
    sys.exit(app.exec_())

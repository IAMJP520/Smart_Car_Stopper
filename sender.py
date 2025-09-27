import socket
import json
import time
import sys
import math

# ====== 플랫폼별 키보드 입력 유틸 ======
class KeyboardReader:
    """
    Cross-platform non-blocking keyboard reader.
    - Windows: msvcrt
    - Unix (Linux/macOS): termios + tty + select
    """
    def __init__(self):
        self.platform = sys.platform
        self._entered_raw = False
        if self.platform == "win32":
            import msvcrt
            self.msvcrt = msvcrt
        else:
            import tty, termios, select
            self.tty = tty
            self.termios = termios
            self.select = select
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)

    def __enter__(self):
        if self.platform != "win32":
            # raw mode
            self.tty.setcbreak(self.fd)
            self._entered_raw = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.platform != "win32" and self._entered_raw:
            self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.old_settings)

    def read_key(self):
        """
        Returns a single logical key string or None when no key available.
        Logical keys:
          'UP','DOWN','LEFT','RIGHT','w','a','s','d','+','-','q'
        """
        if self.platform == "win32":
            if not self.msvcrt.kbhit():
                return None
            ch = self.msvcrt.getwch()
            # Arrow keys come as prefix (0 or \xe0) + code
            if ch in ('\x00', '\xe0'):
                code = self.msvcrt.getwch()
                mapping = {'H': 'UP', 'P': 'DOWN', 'K': 'LEFT', 'M': 'RIGHT'}
                return mapping.get(code, None)
            # Normalize
            ch = ch.lower()
            if ch in ('w','a','s','d','+','-','q'):
                return ch
            return None
        else:
            # Unix: non-block poll
            r, _, _ = self.select.select([sys.stdin], [], [], 0)
            if not r:
                return None
            ch1 = sys.stdin.read(1)
            if ch1 == '\x1b':  # escape
                # possible arrow: \x1b [ A/B/C/D
                r, _, _ = self.select.select([sys.stdin], [], [], 0.0005)
                if not r:
                    return None
                ch2 = sys.stdin.read(1)
                if ch2 != '[':
                    return None
                r, _, _ = self.select.select([sys.stdin], [], [], 0.0005)
                if not r:
                    return None
                ch3 = sys.stdin.read(1)
                mapping = {'A': 'UP', 'B': 'DOWN', 'C': 'RIGHT', 'D': 'LEFT'}
                return mapping.get(ch3, None)
            ch1 = ch1.lower()
            if ch1 in ('w','a','s','d','+','-','q'):
                return ch1
            return None


class DummyCarClient:
    """
    주차 내비게이션 UI(서버)에 가상의 경로 및 실시간 위치 데이터를 전송하는 클라이언트.
    - 경로(waypoints)는 자동으로 전송
    - 실시간 위치는 키보드(화살표/WASD)로 수동 조종
    """

    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.client_socket = None
        print(f"🚗 더미 클라이언트 초기화. 서버 주소: {self.host}:{self.port}")

    # ====== 네트워킹 ======
    def connect_to_server(self):
        """서버에 연결을 시도합니다."""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            print(f"✅ 서버에 성공적으로 연결되었습니다.")
            return True
        except ConnectionRefusedError:
            print(f"❌ 연결 실패: 서버가 실행 중인지 확인하세요.")
            return False
        except Exception as e:
            print(f"❌ 연결 중 오류 발생: {e}")
            return False

    def send_json(self, data):
        """JSON 데이터를 서버로 전송합니다."""
        if not self.client_socket:
            print("❌ 소켓이 연결되지 않았습니다.")
            return
        try:
            message = json.dumps(data)
            self.client_socket.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"❌ 데이터 전송 오류: {e}")

    def close_connection(self):
        """서버와의 연결을 종료합니다."""
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
            print("🔗 서버 연결이 종료되었습니다.")

    # ====== 기능: 경로 전송 ======
    def send_waypoints(self, waypoints):
        """지정된 웨이포인트 경로를 서버에 전송합니다."""
        print("\n" + "="*50)
        print(f"🗺️  웨이포인트 경로를 전송합니다: {waypoints}")
        waypoint_data = {"type": "waypoint_assignment", "waypoints": waypoints}
        self.send_json(waypoint_data)
        print("="*50 + "\n")
        time.sleep(1)  # UI가 경로를 그릴 시간

    # ====== 기능: 키보드 수동 조종 ======
    def control_with_keyboard(self, start_pos, step=25, send_interval=0.02, tag_id="dummy_car_01"):
        """
        키보드 입력(화살표/WASD)으로 실시간 위치를 조종합니다.
        - step: 키 1회당 이동 픽셀
        - send_interval: 전송 간 최소 간격(초)
        조작키:
          ↑/W: 위로, ↓/S: 아래로, ←/A: 왼쪽, →/D: 오른쪽
          +/-: step 증감(최소 1)
          Q: 종료
        """
        x, y = start_pos
        last_send = 0.0

        def send_pos(px, py):
            data = {"type": "real_time_position", "tag_id": tag_id, "x": px, "y": py}
            self.send_json(data)

        print("🎮 수동 조종 모드 시작")
        print("   ↑/↓/←/→ 또는 W/A/S/D 로 이동,  + / - 로 스텝 조절,  Q 로 종료")
        print(f"   현재 스텝: {step}px")
        with KeyboardReader() as kr:
            try:
                while True:
                    key = kr.read_key()
                    moved = False

                    if key in ('UP','s'):
                        y -= step
                        moved = True
                    elif key in ('DOWN','w'):
                        y += step
                        moved = True
                    elif key in ('LEFT','a'):
                        x -= step
                        moved = True
                    elif key in ('RIGHT','d'):
                        x += step
                        moved = True
                    elif key == '+':
                        step = max(1, step + 5)
                        print(f"   ➕ 스텝 증가: {step}px")
                    elif key == '-':
                        step = max(1, step - 5)
                        print(f"   ➖ 스텝 감소: {step}px")
                    elif key == 'q':
                        print("🛑 수동 조종 종료")
                        break

                    # 이동 시 즉시 전송(전송 스로틀 적용)
                    now = time.time()
                    if moved and (now - last_send) >= send_interval:
                        send_pos(x, y)
                        last_send = now

                    # CPU 점유 억제
                    time.sleep(0.005)
            except KeyboardInterrupt:
                print("\n🛑 (Ctrl+C) 수동 조종 종료")

        # 마지막 위치 한 번 더 전송(선택)
        send_pos(x, y)
        print(f"✅ 마지막 위치 전송 완료: ({x:.1f}, {y:.1f})")

    # ====== (기존) 자동 이동 시뮬레이션도 보존 ======
    def simulate_movement(self, waypoints, speed=300):
        """
        경로를 따라 이동하는 것처럼 실시간 위치를 시뮬레이션하여 전송합니다.
        - speed: 초당 이동하는 픽셀 단위 속도
        """
        print("🛰️  실시간 위치 시뮬레이션을 시작합니다...")
        for i in range(len(waypoints) - 1):
            start_point = waypoints[i]
            end_point = waypoints[i+1]
            print(f"  - 경로 구간 이동: {start_point} -> {end_point}")

            dx = end_point[0] - start_point[0]
            dy = end_point[1] - start_point[1]
            distance = math.sqrt(dx**2 + dy**2)
            if distance == 0:
                continue

            duration = distance / speed
            num_steps = max(1, int(duration * 20))

            for step in range(num_steps + 1):
                ratio = step / num_steps
                current_pos_x = start_point[0] + dx * ratio
                current_pos_y = start_point[1] + dy * ratio
                position_data = {
                    "type": "real_time_position",
                    "tag_id": "dummy_car_01",
                    "x": current_pos_x,
                    "y": current_pos_y
                }
                self.send_json(position_data)
                time.sleep(0.05)

        print("✅ 시뮬레이션 완료: 최종 목적지에 도달했습니다.")

    # ====== 주차구역 좌표 정의 ======
    def get_parking_coordinates(self):
        """주차구역 1~11번의 중심 좌표를 반환합니다."""
        return {
            1: [200, 1800],    # 장애인 구역 (상단)
            2: [550, 1800],    # 일반 구역 (상단)
            3: [850, 1800],    # 일반 구역 (상단)
            4: [1150, 1800],   # 전기차 구역 (상단)
            5: [1450, 1800],   # 전기차 구역 (상단)
            6: [1800, 1400],   # 장애인 구역 (우측)
            7: [1800, 1000],   # 장애인 구역 (우측)
            8: [1450, 600],    # 일반 구역 (하단)
            9: [1150, 600],    # 일반 구역 (하단)
            10: [850, 600],    # 전기차 구역 (하단)
            11: [550, 600]     # 전기차 구역 (하단)
        }

    def show_parking_menu(self):
        """주차구역 선택 메뉴를 표시합니다."""
        coords = self.get_parking_coordinates()
        print("\n" + "="*60)
        print("🏢 주차구역 선택 메뉴")
        print("="*60)
        print("상단 주차구역:")
        for i in range(1, 6):
            spot_type = "장애인" if i == 1 else ("일반" if i in [2,3] else "전기차")
            print(f"  {i}번: {spot_type} 구역 - 좌표: {coords[i]}")
        
        print("\n우측 주차구역:")
        for i in range(6, 8):
            print(f"  {i}번: 장애인 구역 - 좌표: {coords[i]}")
        
        print("\n하단 주차구역:")
        for i in range(8, 12):
            spot_type = "일반" if i in [8,9] else "전기차"
            print(f"  {i}번: {spot_type} 구역 - 좌표: {coords[i]}")
        
        print("="*60)
        return coords

    def select_parking_spot(self):
        """사용자가 주차구역을 선택할 수 있도록 합니다."""
        coords = self.show_parking_menu()
        
        while True:
            try:
                choice = input("\n🎯 주차구역 번호를 선택하세요 (1~11, 또는 'q'로 종료): ").strip()
                
                if choice.lower() == 'q':
                    print("👋 프로그램을 종료합니다.")
                    return None
                
                spot_num = int(choice)
                if 1 <= spot_num <= 11:
                    selected_coords = coords[spot_num]
                    spot_type = "장애인" if spot_num in [1,6,7] else ("일반" if spot_num in [2,3,8,9] else "전기차")
                    print(f"✅ {spot_num}번 {spot_type} 구역이 선택되었습니다: {selected_coords}")
                    return spot_num, selected_coords
                else:
                    print("❌ 1~11번 중에서 선택해주세요.")
            except ValueError:
                print("❌ 숫자를 입력해주세요.")
            except KeyboardInterrupt:
                print("\n👋 프로그램을 종료합니다.")
                return None

    def generate_route_to_parking(self, parking_spot_num, parking_coords):
        """ROS2 노드의 calculate_waypoints 로직을 기반으로 주차구역으로의 경로를 생성합니다."""
        # ROS2 노드의 MANDATORY_WAYPOINT와 동일
        MANDATORY_WAYPOINT = [200, 925]
        
        # ROS2 노드의 주차구역별 waypoint 좌표와 동일하게 설정
        parking_waypoints = {
            # 주차구역 1-5 (상단, 왼쪽→오른쪽)
            1: [200, 1475], 2: [550, 1475], 3: [850, 1475], 4: [1150, 1475],
            5: [1450, 1475],
            # 주차구역 6-7 (우측, 위→아래)  
            6: [1475, 1400], 7: [1475, 1000],
            # 주차구역 8-11 (하단, 오른쪽→왼쪽)
            8: [1475, 925], 9: [1150, 925], 10: [850, 925], 11: [550, 925]
        }
        
        target_waypoint = parking_waypoints.get(parking_spot_num, parking_coords)
        waypoints = [MANDATORY_WAYPOINT]  # 필수 시작점 (200, 925)
        
        # ROS2 노드와 동일한 경로 생성 로직
        if parking_spot_num == 1:  # 1번: (200, 925) -> (200,1475)
            waypoints.append(target_waypoint)
        elif parking_spot_num in [2, 3, 4, 5]:  # 2~5번: (200, 925) -> (200, 1475) -> 최종 주차구역
            waypoints.append([200, 1475])
            waypoints.append(target_waypoint)
        elif parking_spot_num == 6:  # 6번: (200, 925) -> (200, 1475) -> (1475, 1475) -> (1475, 1400)
            waypoints.append([200, 1475])
            waypoints.append([1475, 1475])
            waypoints.append(target_waypoint)
        elif parking_spot_num == 7:  # 7번: (200, 925) -> (1475, 925) -> (1475, 1000)
            waypoints.append([1475, 925])
            waypoints.append(target_waypoint)
        elif parking_spot_num in [8, 9, 10, 11]:  # 8~11번: (200, 925) -> 최종 주차구역
            waypoints.append(target_waypoint)
        
        return waypoints

    # ====== 시나리오 ======
    def run_scenario(self, manual=True):
        """
        시나리오 실행:
          1) 서버 연결
          2) 주차구역 선택
          3) 경로(목적지들) 자동 전송
          4) (manual=True) 수동 조종 모드로 실시간 위치 전송
             (manual=False) 자동 이동 시뮬레이션
        """
        if not self.connect_to_server():
            return

        # 주차구역 선택
        selection = self.select_parking_spot()
        if selection is None:
            self.close_connection()
            return
        
        parking_spot_num, parking_coords = selection
        
        # 선택된 주차구역으로의 경로 생성
        waypoints_to_send = self.generate_route_to_parking(parking_spot_num, parking_coords)
        
        print(f"\n🗺️  {parking_spot_num}번 주차구역으로의 경로를 전송합니다:")
        for i, waypoint in enumerate(waypoints_to_send):
            print(f"  {i+1}. {waypoint}")
        
        self.send_waypoints(waypoints_to_send)

        # 서버와 동일한 '입구' 시작점
        ENTRANCE = [200, 200]

        if manual:
            print("⏳ 3초 후 키보드 수동 조종을 시작합니다...")
            time.sleep(3)
            self.control_with_keyboard(start_pos=tuple(ENTRANCE), step=25, send_interval=0.02)
        else:
            # 자동 시뮬레이션은 '입구'부터 시작하도록 경로 재구성
            simulation_path = [ENTRANCE] + waypoints_to_send
            print("⏳ 3초 후 자동 이동 시뮬레이션을 시작합니다...")
            time.sleep(3)
            self.simulate_movement(simulation_path, speed=300)

        self.close_connection()


if __name__ == "__main__":
    client = DummyCarClient()
    # manual=True: 키보드 수동 조종 / manual=False: 자동 이동
    client.run_scenario(manual=True)

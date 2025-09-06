import socket
import json
import time
import math

class DummyCarClient:
    """
    주차 내비게이션 UI(서버)에 가상의 경로 및 실시간 위치 데이터를 전송하는 클라이언트 클래스.
    """

    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.client_socket = None
        print(f"🚗 더미 클라이언트 초기화. 서버 주소: {self.host}:{self.port}")

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

    def send_waypoints(self, waypoints):
        """지정된 웨이포인트 경로를 서버에 전송합니다."""
        print("\n" + "="*50)
        print(f"🗺️  웨이포인트 경로를 전송합니다: {waypoints}")
        
        waypoint_data = {
            "type": "waypoint_assignment",
            "waypoints": waypoints
        }
        self.send_json(waypoint_data)
        print("="*50 + "\n")
        time.sleep(1) # UI가 경로를 그릴 시간을 줍니다.

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
            num_steps = int(duration * 20)
            if num_steps == 0: num_steps = 1

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

    def close_connection(self):
        """서버와의 연결을 종료합니다."""
        if self.client_socket:
            self.client_socket.close()
            print("🔗 서버 연결이 종료되었습니다.")

    def run_scenario(self):
        """정의된 시나리오(경로 전송 -> 이동 시뮬레이션)를 실행합니다."""
        if self.connect_to_server():
            # ★ 변경점 1: 서버와 동일한 '입구' 시작점 정의
            ENTRANCE = [200, 200]

            # 서버에는 목적지 경로만 전송
            waypoints_to_send = [
                [200, 925],
                [1475, 925],
                [1475, 1475]
            ]
            self.send_waypoints(waypoints_to_send)
            
            # ★ 변경점 2: 시뮬레이션은 '입구'부터 시작하도록 경로 재구성
            simulation_path = [ENTRANCE] + waypoints_to_send

            print("⏳ 5초 후 차량 시뮬레이션을 시작합니다...")
            time.sleep(5)
            
            # 재구성된 전체 경로로 시뮬레이션 실행
            self.simulate_movement(simulation_path, speed=300)
            
            self.close_connection()

if __name__ == "__main__":
    client = DummyCarClient()
    client.run_scenario()
# 팀원의 기존 시각화 코드에 추가할 WiFi 통신 부분

import socket
import json
import threading
from datetime import datetime
from typing import List, Tuple, Optional

class WaypointReceiver:
    """라즈베리파이로부터 waypoint를 수신하는 클래스"""
    
    def __init__(self, host='0.0.0.0', port=9999, raspberry_ip='192.168.1.200'):
        self.host = host
        self.port = port
        self.raspberry_ip = raspberry_ip
        
        # 수신된 데이터
        self.current_waypoints = []
        self.current_vehicle_id = None
        self.current_assigned_spot = None
        self.last_update_time = None
        
        # 서버 소켓
        self.server_socket = None
        self.running = False
        
        # 콜백 함수 (시각화 업데이트용)
        self.waypoint_callback = None
        
        print(f"📡 Waypoint 수신기 초기화")
        print(f"   수신 주소: {self.host}:{self.port}")
        print(f"   라즈베리파이: {self.raspberry_ip}")
    
    def set_waypoint_callback(self, callback_function):
        """새 waypoint 수신 시 호출될 콜백 함수 설정"""
        self.waypoint_callback = callback_function
    
    def start_receiver(self):
        """waypoint 수신 서버 시작 (별도 스레드)"""
        def server_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind((self.host, self.port))
                self.server_socket.listen(5)
                
                print(f"✅ 서버가 {self.host}:{self.port}에서 대기 중...")
                self.running = True
                
                while self.running:
                    try:
                        client_socket, addr = self.server_socket.accept()
                        print(f"🔗 라즈베리파이 연결: {addr}")
                        
                        # 데이터 수신 처리
                        self.handle_connection(client_socket, addr)
                        
                    except Exception as e:
                        if self.running:
                            print(f"❌ 연결 오류: {e}")
                        break
                        
            except Exception as e:
                print(f"❌ 서버 시작 오류: {e}")
        
        # 백그라운드에서 서버 실행
        self.server_thread = threading.Thread(target=server_thread)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def handle_connection(self, client_socket, addr):
        """라즈베리파이 연결 처리"""
        try:
            while self.running:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                try:
                    # JSON 데이터 파싱
                    message = json.loads(data)
                    self.process_waypoint_data(message)
                    
                    # 응답 전송
                    response = {
                        "status": "received", 
                        "timestamp": datetime.now().isoformat()
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
                except json.JSONDecodeError:
                    print(f"❌ 잘못된 JSON 데이터: {data}")
                    
        except Exception as e:
            print(f"❌ 데이터 수신 오류: {e}")
        finally:
            client_socket.close()
            print(f"📱 라즈베리파이 {addr} 연결 종료")
    
    def process_waypoint_data(self, data):
        """수신된 waypoint 데이터 처리"""
        if data.get('type') == 'waypoint_assignment':
            # 데이터 추출
            self.current_vehicle_id = data.get('vehicle_id')
            self.current_assigned_spot = data.get('assigned_spot')
            self.current_waypoints = data.get('waypoints', [])
            self.last_update_time = datetime.now()
            
            # 콘솔 출력
            print(f"\n🎯 새로운 waypoint 수신!")
            print(f"   차량 ID: {self.current_vehicle_id}")
            print(f"   배정 구역: {self.current_assigned_spot}번")
            print(f"   수신 시간: {data.get('timestamp')}")
            print(f"   Waypoints: {self.current_waypoints}")
            print(f"   총 {len(self.current_waypoints)}개 waypoint")
            
            # 기존 시각화 코드 업데이트를 위한 콜백 호출
            if self.waypoint_callback:
                self.waypoint_callback(
                    waypoints=self.current_waypoints,
                    vehicle_id=self.current_vehicle_id,
                    assigned_spot=self.current_assigned_spot
                )
            
            print("=" * 50)
    
    def get_latest_waypoints(self) -> Optional[List[Tuple[int, int]]]:
        """최신 waypoint 반환"""
        return self.current_waypoints if self.current_waypoints else None
    
    def get_current_info(self) -> dict:
        """현재 수신된 정보 반환"""
        return {
            'vehicle_id': self.current_vehicle_id,
            'assigned_spot': self.current_assigned_spot,
            'waypoints': self.current_waypoints,
            'last_update': self.last_update_time,
            'waypoint_count': len(self.current_waypoints) if self.current_waypoints else 0
        }
    
    def stop(self):
        """수신 서버 중지"""
        print("🛑 Waypoint 수신기를 종료합니다...")
        self.running = False
        if self.server_socket:
            self.server_socket.close()

# ============================================================================
# 기존 시각화 코드에 통합하는 방법
# ============================================================================

"""
기존 시각화 코드에 추가하는 방법:

1. 위의 WaypointReceiver 클래스를 복사해서 시각화 파일 상단에 추가

2. 시각화 클래스에서 waypoint 수신기 초기화:

class YourVisualizationClass:
    def __init__(self):
        # 기존 시각화 초기화 코드...
        
        # Waypoint 수신기 추가
        self.waypoint_receiver = WaypointReceiver(
            host='0.0.0.0', 
            port=9999, 
            raspberry_ip='192.168.1.200'  # 라즈베리파이 IP
        )
        
        # 새 waypoint 수신 시 호출될 함수 설정
        self.waypoint_receiver.set_waypoint_callback(self.update_waypoints)
        
        # 수신 서버 시작
        self.waypoint_receiver.start_receiver()
    
    def update_waypoints(self, waypoints, vehicle_id, assigned_spot):
        \"\"\"새 waypoint 수신 시 호출되는 함수\"\"\"
        print(f"시각화 업데이트: {vehicle_id} -> {assigned_spot}번 구역")
        print(f"새 경로: {waypoints}")
        
        # 여기에 기존 시각화 업데이트 코드 추가
        # 예: self.plot_waypoints(waypoints)
        #    self.update_display()
        #    등등...
    
    def plot_waypoints(self, waypoints):
        \"\"\"waypoint를 시각화하는 기존 함수\"\"\"
        # 기존 시각화 코드...
        pass

3. 메인 실행 부분:

if __name__ == '__main__':
    # 시각화 클래스 생성
    visualizer = YourVisualizationClass()
    
    try:
        # 기존 시각화 루프...
        while True:
            # 시각화 업데이트
            # matplotlib 애니메이션이나 기타 업데이트 코드
            pass
            
    except KeyboardInterrupt:
        print("종료 중...")
    finally:
        # 수신기 정리
        visualizer.waypoint_receiver.stop()

"""

# ============================================================================
# 사용 예시 (독립 실행용)
# ============================================================================

def example_callback(waypoints, vehicle_id, assigned_spot):
    """예시 콜백 함수"""
    print(f"📊 시각화 업데이트 호출됨!")
    print(f"   차량: {vehicle_id}")
    print(f"   구역: {assigned_spot}번")
    print(f"   경로: {waypoints}")
    
    # 여기에 실제 시각화 업데이트 코드 추가
    # 예: matplotlib으로 점과 선 그리기

if __name__ == '__main__':
    # 독립 실행 시 테스트
    print("🎯 Waypoint 수신기 테스트 시작")
    print("라즈베리파이 IP를 입력하세요 (기본: 192.168.1.200):")
    
    raspberry_ip = input().strip()
    if not raspberry_ip:
        raspberry_ip = "192.168.1.200"
    
    receiver = WaypointReceiver(raspberry_ip=raspberry_ip)
    receiver.set_waypoint_callback(example_callback)
    receiver.start_receiver()
    
    try:
        print("📡 waypoint 수신 대기 중... (Ctrl+C로 종료)")
        while True:
            import time
            time.sleep(1)
            
            # 현재 정보 주기적 출력 (선택사항)
            # info = receiver.get_current_info()
            # if info['waypoints']:
            #     print(f"현재: {info['vehicle_id']} -> {info['assigned_spot']}번")
            
    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
        print("✅ 수신기 종료 완료")
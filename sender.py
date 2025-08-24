import socket
import json

# 네비게이션(서버) 정보
HOST = '127.0.0.1'  # 내 컴퓨터에서 실행 중인 서버
PORT = 9999        # 네비게이션이 대기 중인 포트

# [수정] 사용자가 요청한 3가지 경로 조합
TEST_ROUTES = {
    '1': {
        "name": "필수 경로 (목적지 1개)",
        "waypoints": [
            [200, 925]
        ]
    },
    '2': {
        "name": "필수 + 경유지 1 (목적지 2개)",
        "waypoints": [
            [200, 925], 
            [1475, 925]
        ]
    },
    '3': {
        "name": "전체 경로 (목적지 3개)",
        "waypoints": [
            [200, 925], 
            [1475, 925], 
            [1475, 1475]
        ]
    }
}

def send_command(waypoints_data):
    """지정된 웨이포인트 데이터를 서버로 전송하는 함수"""
    
    # 서버로 보낼 JSON 메시지 생성
    message = {
        "type": "waypoint_assignment",
        "waypoints": waypoints_data
    }
    
    try:
        # 소켓을 사용해 서버에 연결하고 데이터 전송
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"\n📡 네비게이션({HOST}:{PORT})에 연결 시도 중...")
            s.connect((HOST, PORT))
            print("✅ 연결 성공!")
            
            json_message = json.dumps(message)
            s.sendall(json_message.encode('utf-8'))
            print(f"🚀 전송 데이터: {json_message}")
            
            # 서버로부터 응답 수신
            response = s.recv(1024).decode('utf-8')
            print(f"📬 서버 응답: {response}")

    except ConnectionRefusedError:
        print(f"❌ 연결 실패! parking_navigation.py를 먼저 실행했는지 확인하세요.")
    except Exception as e:
        print(f"❌ 전송 중 오류 발생: {e}")

if __name__ == "__main__":
    while True:
        print("\n" + "="*50)
        print("경로 전송 테스트 메뉴")
        print("="*50)
        for key, value in TEST_ROUTES.items():
            print(f"  {key}. {value['name']}")
        print("  q. 종료")
        
        choice = input("\n👉 전송할 경로 번호를 입력하세요: ")
        
        if choice.lower() == 'q':
            break
        
        if choice in TEST_ROUTES:
            send_command(TEST_ROUTES[choice]['waypoints'])
        else:
            print("❌ 잘못된 번호입니다. 다시 입력해주세요.")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주차 정산 서버 구현 예시 코드
이 파일은 서버 팀원이 참고하여 실제 서버에 정산 기능을 통합할 수 있도록 작성된 예시입니다.
"""

import socket
import json
import zmq
from datetime import datetime
from typing import Dict, Any

# ===================================================================
# 1. 정산 요청 수신 모듈 (TCP/IP 소켓)
# ===================================================================

class PaymentRequestHandler:
    """정산 요청을 처리하는 클래스"""
    
    def __init__(self, tcp_port=9999, zmq_port=5555):
        self.tcp_port = tcp_port
        self.zmq_port = zmq_port
        
        # ZeroMQ Publisher 초기화
        self.zmq_context = zmq.Context()
        self.zmq_publisher = self.zmq_context.socket(zmq.PUB)
        self.zmq_publisher.bind(f"tcp://*:{zmq_port}")
        print(f"✅ ZeroMQ Publisher 시작됨 - 포트: {zmq_port}")
        
        # TCP/IP 서버 소켓 초기화
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', tcp_port))
        self.server_socket.listen(5)
        print(f"✅ TCP/IP 서버 시작됨 - 포트: {tcp_port}")
    
    def handle_pay_request(self, pay_data: Dict[str, Any]):
        """
        정산 요청 처리
        
        Args:
            pay_data: {'type': 'pay', 'parking_spot': 7}
        
        Returns:
            None (ZeroMQ로 정산 금액 브로드캐스트)
        """
        parking_spot = pay_data.get('parking_spot')
        
        if not parking_spot or not (1 <= parking_spot <= 11):
            print(f"❌ 잘못된 주차 구역 번호: {parking_spot}")
            return
        
        print(f"💰 정산 요청 수신: 주차구역 {parking_spot}번")
        
        # ============================================================
        # 여기에 실제 정산 금액 계산 로직을 구현하세요
        # ============================================================
        amount = self.calculate_payment(parking_spot)
        
        # ============================================================
        # ZeroMQ로 정산 금액 브로드캐스트
        # ============================================================
        self.broadcast_payment_amount(amount, parking_spot)
    
    def calculate_payment(self, parking_spot: int) -> int:
        """
        정산 금액 계산 (예시)
        
        실제 구현 시:
        1. 주차 시간 계산 (입차 시간 ~ 현재 시간)
        2. 요금 체계 적용
        3. 특별 요금 적용 (장애인, 전기차 등)
        
        Args:
            parking_spot: 주차 구역 번호
        
        Returns:
            정산 금액 (원 단위)
        """
        # ============================================================
        # TODO: 실제 정산 금액 계산 로직 구현
        # 예시:
        # - 입차 시간 조회 (DB 또는 메모리)
        # - 현재 시간과의 차이 계산
        # - 시간당 요금 또는 기본 요금 적용
        # ============================================================
        
        # 예시: 고정 금액 반환
        # 실제로는 주차 시간 기반 계산 필요
        simulated_amount = 5000
        
        # 예시: 주차 시간 기반 계산
        # parking_duration_minutes = get_parking_duration(parking_spot)
        # base_fee = 1000  # 기본 요금
        # hourly_rate = 500  # 시간당 요금
        # hours = parking_duration_minutes / 60
        # simulated_amount = base_fee + (int(hours) * hourly_rate)
        
        return simulated_amount
    
    def broadcast_payment_amount(self, amount: int, parking_spot: int):
        """
        정산 금액을 ZeroMQ로 브로드캐스트
        
        Args:
            amount: 정산 금액
            parking_spot: 주차 구역 번호
        """
        payment_data = {
            "type": "payment",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "amount": amount,
                "parking_spot": parking_spot,
                "parking_duration_minutes": 120,  # 예시, 실제 주차 시간 계산 필요
                "currency": "KRW"
            }
        }
        
        # ZeroMQ 메시지 전송
        topic = "payment_data"
        message = json.dumps(payment_data, ensure_ascii=False)
        self.zmq_publisher.send_string(f"{topic} {message}")
        
        print(f"📡 정산 금액 브로드캐스트: {amount:,}원 (주차구역 {parking_spot}번)")
    
    def handle_payment_confirmation(self, confirmation_data: Dict[str, Any]):
        """
        정산 확인 결과 처리
        
        Args:
            confirmation_data: {
                'type': 'payment_confirmation',
                'confirmed': True/False,
                'amount': 5000,
                'parking_spot': 7
            }
        """
        confirmed = confirmation_data.get('confirmed', False)
        amount = confirmation_data.get('amount', 0)
        parking_spot = confirmation_data.get('parking_spot')
        
        print(f"💰 정산 확인 결과 수신: {'확인' if confirmed else '취소'}, 금액: {amount:,}원, 주차구역: {parking_spot}번")
        
        if confirmed:
            # ============================================================
            # TODO: 정산 확인 후 처리 로직 구현
            # 예시:
            # - 결제 처리
            # - 출차 승인
            # - 로그 기록
            # ============================================================
            print(f"✅ 정산 확인: 결제 처리 완료")
        else:
            # ============================================================
            # TODO: 정산 취소 후 처리 로직 구현
            # 예시:
            # - 취소 처리
            # - 로그 기록
            # ============================================================
            print(f"❌ 정산 취소: 출차 요청 취소됨")
    
    def run(self):
        """서버 실행 (메인 루프)"""
        print("🚀 정산 서버 시작...")
        
        while True:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"🔗 클라이언트 연결됨: {addr}")
                
                # JSON 메시지 수신
                buffer = ""
                while True:
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        break
                    buffer += data
                    
                    # 완전한 JSON 메시지 처리
                    try:
                        start = buffer.find('{')
                        if start == -1:
                            break
                        buffer = buffer[start:]
                        
                        brace_count = 0
                        end_pos = -1
                        for i, char in enumerate(buffer):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_pos = i
                                    break
                        
                        if end_pos == -1:
                            break
                        
                        json_str = buffer[:end_pos + 1]
                        buffer = buffer[end_pos + 1:]
                        
                        data = json.loads(json_str)
                        data_type = data.get('type')
                        
                        # 정산 요청 처리
                        if data_type == 'pay':
                            self.handle_pay_request(data)
                        
                        # 정산 확인 처리
                        elif data_type == 'payment_confirmation':
                            self.handle_payment_confirmation(data)
                        
                        else:
                            print(f"⚠️ 알 수 없는 데이터 타입: {data_type}")
                    
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON 파싱 오류: {e}")
                        break
                
                client_socket.close()
                
            except Exception as e:
                print(f"❌ 서버 오류: {e}")
                break


# ===================================================================
# 2. 사용 예시
# ===================================================================

if __name__ == "__main__":
    # 서버 인스턴스 생성 및 실행
    server = PaymentRequestHandler(tcp_port=9999, zmq_port=5555)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n🛑 서버 종료")
    finally:
        server.zmq_publisher.close()
        server.zmq_context.term()
        server.server_socket.close()


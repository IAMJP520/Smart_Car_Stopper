#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
메인 컨트롤러 - 외부 서버와 TCP/IP 통신 및 ZeroMQ 브로드캐스터
외부 관제 서버로부터 차량 위치 및 경로 데이터를 받아서 
두 개의 디스플레이 화면(탑뷰, HUD)에 실시간 전송
"""

import sys
import os
import socket
import json
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any
from math import sqrt, atan2, degrees
import zmq
import signal

# QPointF는 parking_topview에서만 사용하므로 여기서는 튜플로 처리

# ===================================================================
# ZeroMQ 브로드캐스터 클래스
# ===================================================================
class DataBroadcaster:
    """ZeroMQ를 이용한 실시간 데이터 브로드캐스터"""
    
    def __init__(self, port=5555):
        self.port = port
        self.context = None
        self.pub_socket = None
        self.running = False
        
    def start(self):
        """ZeroMQ Publisher 시작"""
        try:
            self.context = zmq.Context()
            self.pub_socket = self.context.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://*:{self.port}")
            self.running = True
            print(f"✅ ZeroMQ Publisher 시작됨 - 포트: {self.port}")
            
            # 소켓이 완전히 바인딩될 때까지 잠시 대기
            time.sleep(0.1)
            return True
            
        except Exception as e:
            print(f"❌ ZeroMQ Publisher 시작 실패: {e}")
            return False
    
    def publish_vehicle_position(self, data: Dict[str, Any]):
        """차량 위치 데이터 브로드캐스트"""
        if not self.running or not self.pub_socket:
            return
            
        try:
            # 동기화를 위한 타임스탬프 및 시퀀스 번호 포함
            now = datetime.now()
            message = {
                "timestamp": now.isoformat(),
                "timestamp_unix": now.timestamp(),  # 정밀한 타이밍 동기화용
                "type": "position",
                "data": data,
                "sync_id": f"pos_{now.timestamp()}"  # 동기화 ID 추가
            }
            topic = "vehicle_position"
            self.pub_socket.send_string(f"{topic} {json.dumps(message)}")
            print(f"📡 위치 데이터 전송: ({data.get('x', 0):.1f}, {data.get('y', 0):.1f}) [ID: {message['sync_id']}]")
            
        except Exception as e:
            print(f"❌ 위치 데이터 전송 실패: {e}")
    
    def publish_waypoint_data(self, data: Dict[str, Any]):
        """웨이포인트/경로 데이터 브로드캐스트"""
        if not self.running or not self.pub_socket:
            return
            
        try:
            message = {
                "timestamp": datetime.now().isoformat(),
                "type": "waypoint",
                "data": data
            }
            topic = "waypoint_data"
            self.pub_socket.send_string(f"{topic} {json.dumps(message)}")
            print(f"📡 웨이포인트 데이터 전송: {len(data.get('waypoints', []))}개 포인트")
            
        except Exception as e:
            print(f"❌ 웨이포인트 데이터 전송 실패: {e}")
    
    def publish_navigation_instruction(self, data: Dict[str, Any]):
        """네비게이션 안내 데이터 브로드캐스트 (탑뷰와 동기화)"""
        if not self.running or not self.pub_socket:
            return
            
        try:
            # 타이밍 동기화를 위한 타임스탬프 포함
            now = datetime.now()
            message = {
                "timestamp": now.isoformat(),
                "timestamp_unix": now.timestamp(),  # 정밀한 타이밍 동기화용
                "type": "navigation",
                "data": data,
                "sync_id": f"nav_{now.timestamp()}",  # 동기화 ID 추가
                "position_sync": data.get('position_sync_id')  # 위치 데이터와 연결
            }
            topic = "navigation_instruction"
            self.pub_socket.send_string(f"{topic} {json.dumps(message)}")
            print(f"📡 네비게이션 안내 전송: {data.get('instruction', 'N/A')} [ID: {message['sync_id']}]")
            
        except Exception as e:
            print(f"❌ 네비게이션 안내 전송 실패: {e}")
    
    def publish_payment_data(self, data: Dict[str, Any]):
        """정산 데이터 브로드캐스트"""
        if not self.running or not self.pub_socket:
            return
            
        try:
            message = {
                "timestamp": datetime.now().isoformat(),
                "type": "payment",
                "data": data
            }
            topic = "payment_data"
            self.pub_socket.send_string(f"{topic} {json.dumps(message)}")
            print(f"📡 정산 데이터 전송: 금액 {data.get('amount', 0):,}원")
            
        except Exception as e:
            print(f"❌ 정산 데이터 전송 실패: {e}")
    
    def stop(self):
        """ZeroMQ Publisher 종료"""
        try:
            self.running = False
            if self.pub_socket:
                self.pub_socket.close()
            if self.context:
                self.context.term()
            print("🔄 ZeroMQ Publisher 종료됨")
            
        except Exception as e:
            print(f"❌ ZeroMQ Publisher 종료 중 오류: {e}")

# ===================================================================
# TCP/IP 소켓 수신기 클래스 (기존 WaypointReceiver 개선)
# ===================================================================
class ExternalServerReceiver:
    """외부 관제 서버로부터 TCP/IP로 데이터 수신"""
    
    def __init__(self, host='0.0.0.0', port=9999, broadcaster: DataBroadcaster = None, 
                 payment_server_host='localhost', payment_server_port=8888):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.broadcaster = broadcaster
        self.last_position = None
        self.last_waypoints = None
        # Smart_Parking_GUI.py와 동일하게 현재 세그먼트 인덱스 및 경로 포인트 유지
        self.current_path_segment_index = 0
        self.full_path_points = []
        # 외부 정산 서버 주소 (정산 금액을 받아오는 서버)
        self.payment_server_host = payment_server_host
        self.payment_server_port = payment_server_port
        print(f"📡 외부 서버 수신기 초기화됨. 수신 대기 주소: {self.host}:{self.port}")
        print(f"💰 정산 서버 주소: {self.payment_server_host}:{self.payment_server_port}")

    def start_receiver(self):
        """수신 서버 시작 (별도 스레드)"""
        def server_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self.server_socket.settimeout(1.0)
                self.server_socket.bind((self.host, self.port))
                self.server_socket.listen(5)
                print(f"✅ 외부 서버 수신 대기 중... {self.host}:{self.port}")
                self.running = True

                while self.running:
                    try:
                        client_socket, addr = self.server_socket.accept()
                        print(f"🔗 외부 서버 연결됨: {addr}")
                        
                        # 연결별로 별도 스레드에서 처리
                        threading.Thread(
                            target=self.handle_connection, 
                            args=(client_socket,), 
                            daemon=True,
                            name=f"ExternalServer-{addr[0]}:{addr[1]}"
                        ).start()
                        
                    except socket.timeout:
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

        threading.Thread(target=server_thread, daemon=True, name="ExternalServerReceiver").start()

    def handle_connection(self, client_socket):
        """클라이언트 연결 처리 및 데이터 파싱"""
        try:
            buffer = ""
            client_socket.settimeout(30.0)  # 클라이언트 소켓 타임아웃 설정
            
            while self.running:
                try:
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        print(f"⚠️ 클라이언트 연결 종료 (빈 데이터)")
                        break
                    
                    print(f"📨 원시 데이터 수신 ({len(data)} bytes): {data[:200]}...")
                    buffer += data
                    
                    # 완전한 JSON 메시지들을 처리
                    while buffer:
                        try:
                            start = buffer.find('{')
                            if start == -1:
                                buffer = ""
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
                            
                            # JSON 파싱 및 처리 (client_socket 전달하여 응답 가능하도록)
                            response = self.process_received_data(json_str, client_socket)
                            
                            # payment_confirmation에 대한 응답 전송
                            if response:
                                try:
                                    response_json = json.dumps(response, ensure_ascii=False)
                                    client_socket.sendall(response_json.encode('utf-8'))
                                    print(f"📤 클라이언트에 응답 전송: {response_json}")
                                except Exception as e:
                                    print(f"❌ 응답 전송 실패: {e}")
                            
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON 파싱 오류: {e}")
                            print(f"❌ 파싱 실패한 버퍼: {buffer[:500]}")
                            buffer = ""
                            break
                        except Exception as e:
                            print(f"❌ 데이터 처리 오류: {e}")
                            import traceback
                            print(f"❌ 트레이스백:\n{traceback.format_exc()}")
                            break
                            
                except socket.timeout:
                    # 타임아웃은 정상적인 상황일 수 있음 (연결 유지 중)
                    continue
                except socket.error as e:
                    print(f"⚠️ 소켓 오류: {e}")
                    break
                        
        except Exception as e:
            print(f"❌ 연결 처리 중 오류: {e}")
            import traceback
            print(traceback.format_exc())
        finally:
            try:
                client_socket.close()
            except:
                pass

    def process_received_data(self, json_str: str, client_socket=None):
        """수신된 JSON 데이터 처리 및 ZeroMQ로 브로드캐스트
        
        Returns:
            응답이 필요한 경우 dict, 아니면 None
        """
        try:
            data = json.loads(json_str)
            data_type = data.get('type', 'unknown')
            
            print(f"📥 수신된 데이터 타입: {data_type}")
            print(f"📋 수신된 전체 데이터: {json_str}")
            
            if data_type == 'position' and self.broadcaster:
                # 실시간 위치 데이터
                position_data = {
                    'x': data.get('x', 0),
                    'y': data.get('y', 0),
                    'heading': data.get('heading', 0),
                    'speed': data.get('speed', 0)
                }
                self.last_position = position_data
                self.broadcaster.publish_vehicle_position(position_data)
                
                # 위치 기반으로 네비게이션 안내 업데이트
                self.update_navigation_instruction(position_data)
            
            elif data_type == 'waypoint' and self.broadcaster:
                # 웨이포인트/경로 데이터
                waypoint_data = {
                    'waypoints': data.get('waypoints', []),
                    'parking_spot': data.get('parking_spot', None),
                    'route_type': data.get('route_type', 'entry')  # 'entry' or 'exit'
                }
                self.last_waypoints = waypoint_data
                
                # 전체 경로 포인트 재구성 및 세그먼트 인덱스 초기화
                route_type = waypoint_data.get('route_type', 'entry')
                
                if route_type == 'exit':
                    # 출차 시나리오: 주차 좌표 포인트부터 시작 (첫 번째 웨이포인트가 주차 좌표)
                    # waypoints에 주차 좌표부터 전체 경로가 포함되어 있음
                    self.full_path_points = [(wp[0], wp[1]) for wp in waypoint_data.get('waypoints', [])]
                else:
                    # 입차 시나리오: 입구(ENTRANCE)부터 시작
                    ENTRANCE = [200, 200]
                    self.full_path_points = [(ENTRANCE[0], ENTRANCE[1])]
                    for wp in waypoint_data.get('waypoints', []):
                        self.full_path_points.append((wp[0], wp[1]))
                
                self.current_path_segment_index = 0  # 경로 변경 시 인덱스 초기화
                
                self.broadcaster.publish_waypoint_data(waypoint_data)
                print(f"✅ 경로 수신 완료: {len(waypoint_data.get('waypoints', []))}개 웨이포인트")
            
            elif data_type == 'waypoint_reassignment' and self.broadcaster:
                # 팀원 서버로부터 재할당된 경로 데이터 (그대로 ZeroMQ로 브로드캐스트)
                # 팀원 서버가 보낸 데이터를 그대로 전달
                reassignment_data = {
                    'type': 'waypoint_reassignment',  # 재할당 타입 명시
                    'waypoints': data.get('waypoints', []),
                    'assigned_spot': data.get('assigned_spot', None),
                    'vehicle_id': data.get('vehicle_id', None),
                    'assignment_mode': data.get('assignment_mode', None),
                    'timestamp': data.get('timestamp', None),
                    'description': data.get('description', None)
                }
                
                # 재할당된 경로도 경로 데이터로 처리하기 위해 waypoint_data 형식으로 변환
                waypoint_data = {
                    'waypoints': reassignment_data.get('waypoints', []),
                    'parking_spot': reassignment_data.get('assigned_spot', None),
                    'route_type': 'entry',  # 재할당은 항상 입차 시나리오
                    'type': 'waypoint_reassignment',  # 재할당 표시
                    'assignment_mode': reassignment_data.get('assignment_mode', None)
                }
                
                self.last_waypoints = waypoint_data
                
                # 입차 시나리오와 동일하게 처리 (ENTRANCE부터 시작)
                ENTRANCE = [200, 200]
                self.full_path_points = [(ENTRANCE[0], ENTRANCE[1])]
                for wp in waypoint_data.get('waypoints', []):
                    self.full_path_points.append((wp[0], wp[1]))
                
                self.current_path_segment_index = 0
                
                # 재할당 데이터를 그대로 브로드캐스트
                message = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "waypoint_reassignment",  # 재할당 타입으로 브로드캐스트
                    "data": reassignment_data
                }
                topic = "waypoint_data"  # waypoint_data 토픽으로 브로드캐스트
                self.broadcaster.pub_socket.send_string(f"{topic} {json.dumps(message)}")
                print(f"✅ 재할당 경로 수신 완료: {len(reassignment_data.get('waypoints', []))}개 웨이포인트, {reassignment_data.get('assigned_spot')}번 주차구역")
                
            elif data_type == 'manual_instruction' and self.broadcaster:
                # 수동 안내 메시지
                instruction_data = {
                    'instruction': data.get('instruction', ''),
                    'distance': data.get('distance', 0),
                    'action': data.get('action', 'continue')
                }
                self.broadcaster.publish_navigation_instruction(instruction_data)
                
            elif data_type == 'pay' and self.broadcaster:
                # 정산 요청: 외부 서버로 전달하여 정산 금액 받아오기
                parking_spot = data.get('parking_spot')
                print(f"💰 정산 요청 수신: 주차구역 {parking_spot}번")
                
                # 외부 서버에 정산 요청 전송 및 금액 받아오기
                amount = self.request_payment_from_external_server(parking_spot)
                
                if amount is not None:
                    payment_data = {
                        'amount': amount,
                        'parking_spot': parking_spot
                    }
                    
                    # 정산 금액을 ZeroMQ로 브로드캐스트
                    self.broadcaster.publish_payment_data(payment_data)
                    print(f"📡 정산 금액 브로드캐스트: {amount:,}원")
                else:
                    print(f"❌ 외부 서버에서 정산 금액을 받아오지 못했습니다.")
                
            elif data_type == 'payment_confirmation':
                # 정산 확인 결과: 외부 서버로 전달 (broadcaster 불필요)
                confirmed = data.get('confirmed', False)
                amount = data.get('amount', 0)
                parking_spot = data.get('parking_spot')
                
                print(f"💰 정산 확인 결과 수신: {'확인' if confirmed else '취소'}, 금액: {amount:,}원, 주차구역: {parking_spot}번")
                
                # 외부 정산 서버로 정산 확인 전달
                print(f"➡ 외부 정산 서버로 확인 전달 준비: {self.payment_server_host}:{self.payment_server_port}")
                self.send_payment_confirmation_to_external_server(confirmed, amount, parking_spot)
                print(f"✅ 외부 정산 서버로 확인 전달 요청 완료")
                
                # HUD에 응답 반환
                return {"status": "success", "message": "정산 확인 처리 완료"}
                
                # 정산 확인 후 출차 경로는 navigation_hud.py에서 처리
                
            # 기본적으로 응답 없음
            return None
                
        except Exception as e:
            print(f"❌ 데이터 처리 오류: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def request_payment_from_external_server(self, parking_spot: int) -> Optional[int]:
        """
        외부 정산 서버에 정산 요청을 보내고 금액을 받아옵니다.
        
        Args:
            parking_spot: 주차 구역 번호
            
        Returns:
            정산 금액 (원 단위), 실패 시 None
        """
        try:
            # 외부 정산 서버에 연결
            payment_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            payment_socket.settimeout(5.0)
            
            try:
                payment_socket.connect((self.payment_server_host, self.payment_server_port))
                
                # 정산 요청 전송
                pay_request = {
                    'type': 'pay',
                    'parking_spot': parking_spot
                }
                
                request_json = json.dumps(pay_request, ensure_ascii=False)
                payment_socket.sendall(request_json.encode('utf-8'))
                print(f"📤 외부 정산 서버로 요청 전송: {request_json}")
                
                # 응답 수신 (완전한 데이터 수신 보장)
                response_data = b""
                while True:
                    chunk = payment_socket.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                    # JSON이 완성되었는지 확인 (중괄호 매칭)
                    try:
                        decoded = response_data.decode('utf-8')
                        if decoded.count('{') == decoded.count('}'):
                            break
                    except:
                        pass
                
                response_str = response_data.decode('utf-8')
                print(f"📥 외부 서버 응답 수신: {response_str}")
                response_json = json.loads(response_str)
                
                # 응답에서 정산 금액 추출
                if response_json.get('type') == 'payment':
                    amount = response_json.get('data', {}).get('amount')
                    if amount is not None:
                        print(f"✅ 외부 서버로부터 정산 금액 수신: {amount:,}원")
                        return amount
                    else:
                        print(f"⚠️ 응답에 정산 금액이 없습니다: {response_json}")
                        return None
                else:
                    print(f"⚠️ 예상하지 못한 응답 형식: {response_json.get('type')}")
                    return None
                    
            except socket.timeout:
                print(f"❌ 외부 정산 서버 연결 시간 초과: {self.payment_server_host}:{self.payment_server_port}")
                return None
            except ConnectionRefusedError:
                print(f"❌ 외부 정산 서버 연결 거부됨: {self.payment_server_host}:{self.payment_server_port}")
                return None
            finally:
                payment_socket.close()
                
        except Exception as e:
            print(f"❌ 외부 서버 정산 요청 실패: {e}")
            return None

    def send_payment_confirmation_to_external_server(self, confirmed: bool, amount: int, parking_spot: int) -> None:
        """정산 확인 결과를 외부 정산 서버로 전달"""
        try:
            print(f"🔌 외부 정산 서버 연결 시도: {self.payment_server_host}:{self.payment_server_port}")
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            try:
                sock.connect((self.payment_server_host, self.payment_server_port))
                print(f"✅ 외부 정산 서버 연결 성공")
                
                payload = {
                    'type': 'payment_confirmation',
                    'confirmed': bool(confirmed),
                    'amount': int(amount),
                    'parking_spot': int(parking_spot) if parking_spot is not None else None
                }
                json_str = json.dumps(payload, ensure_ascii=False)
                sock.sendall(json_str.encode('utf-8'))
                print(f"📤 외부 정산 서버로 확인 전송: {json_str}")
                try:
                    resp = sock.recv(4096).decode('utf-8')
                    print(f"📥 외부 서버 확인 응답: {resp}")
                except Exception:
                    pass
            except socket.timeout:
                print(f"❌ 정산 확인 전송 타임아웃: {self.payment_server_host}:{self.payment_server_port}")
            except ConnectionRefusedError:
                print(f"❌ 정산 확인 전송 실패(연결 거부): {self.payment_server_host}:{self.payment_server_port}")
            finally:
                sock.close()
        except Exception as e:
            print(f"❌ 정산 확인 전송 실패: {e}")

    def update_navigation_instruction(self, position_data: Dict[str, Any]):
        """현재 위치를 기반으로 네비게이션 안내 업데이트 - Smart_Parking_GUI.py 방식"""
        if not self.last_waypoints or not self.broadcaster:
            return
            
        try:
            current_x = position_data['x']
            current_y = position_data['y']
            route_type = self.last_waypoints.get('route_type', 'entry')
            is_exit_scenario = (route_type == 'exit')
            
            if not self.full_path_points or len(self.full_path_points) < 2:
                return
            
            current_pos = (current_x, current_y)
            
            # Smart_Parking_GUI.py와 동일하게 while 루프로 여러 세그먼트를 넘어가도록 업데이트
            self._update_current_segment(current_pos)
            
            # 남은 경로 포인트 계산 (Smart_Parking_GUI.py와 동일)
            remaining_pts = self.full_path_points[self.current_path_segment_index+1:]
            path_for_hud = [current_pos] + remaining_pts
            
            if len(path_for_hud) < 2:
                # 목적지 도착
                if is_exit_scenario:
                    instructions = [("출차 완료", 0)]
                    speed = 0
                    progress = 100
                else:
                    instructions = [("목적지 도착", 0)]
                    speed = 0
                    progress = 100
            else:
                # 현재 위치부터 남은 경로까지의 instructions 생성
                instructions = self.generate_hud_instructions(path_for_hud, is_exit_scenario)
                progress = self.calculate_route_progress(current_pos, self.full_path_points)
                speed = self.calculate_realistic_speed(instructions, progress, is_exit_scenario)
            
            # HUD 형식으로 변환하여 브로드캐스트
            if instructions:
                direction, distance = instructions[0]
                
                # 목적지 도착인 경우 거리 추가 처리
                if ("목적지" in direction or "도착" in direction) and distance <= 1.0:
                    distance = 0.0
                
                next_instruction = instructions[1][0] if len(instructions) > 1 else ""
                next_distance = instructions[1][1] if len(instructions) > 1 else 0
                
                # 다음 안내도 목적지인 경우 거리 처리
                if ("목적지" in next_instruction or "도착" in next_instruction) and next_distance <= 1.0:
                    next_distance = 0.0
                
                instruction_data = {
                    'instruction': direction,
                    'distance': distance,
                    'action': direction,
                    'speed': speed,
                    'progress': progress,
                    'next_instruction': next_instruction,
                    'next_distance': next_distance,
                    'position_sync_id': f"pos_{datetime.now().timestamp()}",
                    'current_position': {'x': current_x, 'y': current_y}
                }
                
                self.broadcaster.publish_navigation_instruction(instruction_data)
                
        except Exception as e:
            print(f"❌ 네비게이션 안내 업데이트 오류: {e}")
    
    def _update_current_segment(self, current_pos):
        """Smart_Parking_GUI.py와 동일한 로직으로 현재 세그먼트 인덱스 업데이트"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return
        
        current_x, current_y = current_pos[0], current_pos[1]
        
        # while 루프로 여러 세그먼트를 넘어갈 수 있도록 구현
        while self.current_path_segment_index < len(self.full_path_points) - 1:
            p_curr = self.full_path_points[self.current_path_segment_index]
            p_next = self.full_path_points[self.current_path_segment_index + 1]
            
            dist_to_next = sqrt((current_x - p_next[0])**2 + (current_y - p_next[1])**2)
            
            # 세그먼트 벡터와 차량 벡터
            v_seg_x = p_next[0] - p_curr[0]
            v_seg_y = p_next[1] - p_curr[1]
            v_car_x = current_x - p_curr[0]
            v_car_y = current_y - p_curr[1]
            seg_len_sq = v_seg_x**2 + v_seg_y**2
            
            proj_ratio = 1.0
            if seg_len_sq > 0:
                proj_ratio = (v_car_x * v_seg_x + v_car_y * v_seg_y) / seg_len_sq
            
            # 다음 세그먼트로 넘어가는 조건: 거리가 가깝거나 투영 비율이 1.0을 넘으면
            if dist_to_next < 50 or proj_ratio > 1.0:
                self.current_path_segment_index += 1
            else:
                break
    
    def generate_hud_instructions(self, pts, is_exit_scenario=False):
        """
        HUD 안내 메시지 생성 - Smart_Parking_GUI.py와 동일한 로직
        
        주차장 크기와 거리 변환 로직:
        - 주차장 크기: 2000 x 2000 픽셀 (SCENE_W, SCENE_H)
        - PIXELS_PER_METER = 50 (1미터 = 50픽셀)
        - 변환 계산: 주차장 한 변 = 2000픽셀 / 50 = 40미터
        - 따라서 주차장은 실제로 40m x 40m 크기
        
        거리 계산 예시:
        - 두 점 사이 픽셀 거리: sqrt((x2-x1)^2 + (y2-y1)^2)
        - 미터로 변환: 픽셀 거리 / PIXELS_PER_METER = 픽셀 거리 / 50
        - 예: (200, 200)에서 (200, 925)까지 = 725픽셀 = 725/50 = 14.5미터
        """
        PIXELS_PER_METER = 50
        
        if len(pts) < 2:
            return []
        
        instructions = []
        total_dist = 0
        
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i+1]
            # pts는 튜플 리스트 (x, y) 형식
            dist_m = sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2) / PIXELS_PER_METER
            total_dist += dist_m
            
            if i < len(pts) - 2:
                p3 = pts[i+2]
                angle = (degrees(atan2(p3[1]-p2[1], p3[0]-p2[0])) - 
                        degrees(atan2(p2[1]-p1[1], p2[0]-p1[0])) + 180) % 360 - 180
                direction = "좌회전" if angle > 45 else ("우회전" if angle < -45 else "")
                
                if direction:
                    # 직진 구간 시작점(p1)과 회전 좌표(p2) 간 거리 계산 (픽셀 단위)
                    straight_to_turn_dist = sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    
                    # 회전 좌표(p2)와 다음 좌표(p3) 간 거리 계산 (픽셀 단위)
                    turn_to_next_dist = sqrt((p3[0]-p2[0])**2 + (p3[1]-p2[1])**2)
                    
                    # 출차 시나리오: 직진 시작점과 회전 좌표가 100픽셀 이내이면 회전 무시
                    if is_exit_scenario and straight_to_turn_dist <= 100:
                        # 회전 안내를 추가하지 않고 거리만 누적 (직진으로 처리)
                        continue
                    
                    # 회전이 목적지와 너무 가까운지 확인 (100픽셀 이내)
                    # p3가 마지막 포인트이거나 그 다음이 마지막 포인트인 경우
                    is_too_close_to_destination = (
                        turn_to_next_dist <= 100 and 
                        (i + 2 == len(pts) - 1)  # p3가 마지막 포인트 (목적지)
                    )
                    
                    # 회전이 목적지와 너무 가까우면 해당 회전 안내를 건너뜀
                    if is_too_close_to_destination:
                        # 회전 안내를 추가하지 않고 거리만 누적 (직진으로 처리)
                        continue
                    
                    if is_exit_scenario:
                        direction = f"출차 {direction}"
                    instructions.append((direction, total_dist))
                    total_dist = 0
        
        # 목적지 도착 거리 처리: 1m 이하면 0으로 고정
        final_distance = total_dist
        if final_distance <= 1.0:
            final_distance = 0.0
        
        if is_exit_scenario:
            instructions.append(("출차 완료", final_distance))
        else:
            instructions.append(("목적지 도착", final_distance))
        
        return instructions
    
    def calculate_route_progress(self, car_pos, full_path_points):
        """경로 진행률 계산 - Smart_Parking_GUI.py와 동일한 로직"""
        if not full_path_points or len(full_path_points) < 2:
            return 0
        
        # 전체 경로 길이 계산 (튜플 형식)
        total_len = sum(sqrt((full_path_points[i+1][0]-p[0])**2 + 
                           (full_path_points[i+1][1]-p[1])**2) 
                       for i, p in enumerate(full_path_points[:-1]))
        
        if total_len == 0:
            return 0
        
        # 가장 가까운 세그먼트와 투영 비율 찾기
        min_dist = float('inf')
        closest_seg = 0
        proj_ratio = 0
        
        for i, p1 in enumerate(full_path_points[:-1]):
            p2 = full_path_points[i+1]
            seg_vec_x = p2[0] - p1[0]
            seg_vec_y = p2[1] - p1[1]
            car_vec_x = car_pos[0] - p1[0]
            car_vec_y = car_pos[1] - p1[1]
            
            seg_len_sq = seg_vec_x**2 + seg_vec_y**2
            
            if seg_len_sq == 0:
                continue
            
            t = max(0, min(1, (car_vec_x * seg_vec_x + car_vec_y * seg_vec_y) / seg_len_sq))
            proj_x = p1[0] + t * seg_vec_x
            proj_y = p1[1] + t * seg_vec_y
            dist = sqrt((car_pos[0]-proj_x)**2 + (car_pos[1]-proj_y)**2)
            
            if dist < min_dist:
                min_dist = dist
                closest_seg = i
                proj_ratio = t
        
        # 이동한 거리 계산
        traveled = sum(sqrt((full_path_points[i+1][0]-p[0])**2 +
                           (full_path_points[i+1][1]-p[1])**2) 
                       for i, p in enumerate(full_path_points[:closest_seg]))
        
        if closest_seg < len(full_path_points) - 1:
            p1, p2 = full_path_points[closest_seg], full_path_points[closest_seg+1]
            traveled += sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2) * proj_ratio
        
        return min(100, (traveled / total_len) * 100)
    
    def calculate_realistic_speed(self, instructions, progress, is_exit_scenario):
        """현실적인 속도 계산 - Smart_Parking_GUI.py와 동일한 로직"""
        if not instructions:
            return 0
        
        direction, distance = instructions[0]
        
        # 기본 속도 설정
        base_speed = 20  # 기본 20km/h
        
        # 거리에 따른 속도 조절
        if distance <= 5:
            speed = 5 + (distance / 5) * 10  # 5-15km/h
        elif distance <= 20:
            speed = 15 + (distance / 20) * 10  # 15-25km/h
        else:
            speed = 20 + min(10, (distance - 20) / 50 * 10)  # 20-30km/h
        
        # 방향에 따른 속도 조절
        if "좌회전" in direction or "우회전" in direction:
            speed = min(speed, 15)  # 회전 시 감속
        elif "목적지" in direction or "도착" in direction:
            speed = min(speed, 15)  # 목적지 근처 감속
        elif "출차" in direction:
            speed = min(speed, 20)  # 출차 시 조심스럽게
        
        # 진행률에 따른 미세 조절
        if progress < 20:
            speed *= 0.8  # 시작 구간
        elif progress > 80:
            speed *= 0.7  # 마지막 구간
        
        # 출차 시나리오에서는 더 조심스럽게
        if is_exit_scenario:
            speed *= 0.75
        
        # 최종 속도 범위 제한 (0-30km/h)
        speed = max(0, min(30, int(speed)))
        
        return speed

    def stop(self):
        """수신기 종료"""
        try:
            self.running = False
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            print("🔄 외부 서버 수신기 종료됨")
        except Exception as e:
            print(f"❌ 수신기 종료 중 오류: {e}")

# ===================================================================
# 메인 컨트롤러 클래스
# ===================================================================
class MainController:
    """메인 컨트롤러 - 외부 서버 통신과 ZeroMQ 브로드캐스팅 통합 관리"""
    
    def __init__(self, tcp_port=9999, zmq_port=5555, payment_host='localhost', payment_port=8888):
        self.tcp_port = tcp_port
        self.zmq_port = zmq_port
        self.broadcaster = DataBroadcaster(zmq_port)
        self.receiver = ExternalServerReceiver('0.0.0.0', tcp_port, self.broadcaster, payment_server_host=payment_host, payment_server_port=payment_port)
        self.running = False
        
        # 시그널 핸들러 설정 (Ctrl+C 처리)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """시그널 핸들러 (종료 처리)"""
        print(f"\n🛑 종료 신호 수신됨 (Signal: {signum})")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """메인 컨트롤러 시작"""
        print("🚀 Smart Parking 메인 컨트롤러 시작...")
        print(f"   - TCP 수신 포트: {self.tcp_port}")
        print(f"   - ZeroMQ 브로드캐스트 포트: {self.zmq_port}")
        print("   - 종료하려면 Ctrl+C를 누르세요")
        
        # ZeroMQ 브로드캐스터 시작
        if not self.broadcaster.start():
            print("❌ ZeroMQ 브로드캐스터 시작 실패")
            return False
        
        # TCP 수신기 시작
        self.receiver.start_receiver()
        self.running = True
        
        print("✅ 메인 컨트롤러 시작 완료")
        print("📱 이제 두 개의 디스플레이 화면을 실행하세요:")
        print("   1. python parking_topview.py")
        print("   2. python navigation_hud.py")
        
        # 메인 루프 (종료 신호까지 대기)
        try:
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Ctrl+C 감지됨")
            self.stop()
    
    def stop(self):
        """메인 컨트롤러 종료"""
        if not self.running:
            return
            
        print("🔄 메인 컨트롤러 종료 중...")
        self.running = False
        
        # 각 컴포넌트 종료
        if self.receiver:
            self.receiver.stop()
        
        if self.broadcaster:
            self.broadcaster.stop()
        
        print("✅ 메인 컨트롤러 종료 완료")

# ===================================================================
# 테스트용 더미 데이터 전송기 (개발/테스트용)
# ===================================================================
class DummyDataSender:
    """테스트용 더미 데이터 전송기"""
    
    def __init__(self, target_host='localhost', target_port=9999):
        self.target_host = target_host
        self.target_port = target_port
    
    def send_test_waypoints(self):
        """테스트용 웨이포인트 전송"""
        test_waypoints = {
            "type": "waypoint",
            "waypoints": [
                [200, 200],   # 시작점
                [200, 925],   # 중간점
                [550, 925],   # 목적지
            ],
            "parking_spot": 11,
            "route_type": "entry"
        }
        
        self.send_data(test_waypoints)
    
    def send_test_position(self, x=200, y=200):
        """테스트용 위치 데이터 전송"""
        test_position = {
            "type": "position",
            "x": x,
            "y": y,
            "heading": 0,
            "speed": 10
        }
        
        self.send_data(test_position)
    
    def send_data(self, data_dict):
        """실제 데이터 전송"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.target_host, self.target_port))
            
            json_data = json.dumps(data_dict)
            sock.send(json_data.encode('utf-8'))
            sock.close()
            
            print(f"📤 테스트 데이터 전송됨: {data_dict['type']}")
            
        except Exception as e:
            print(f"❌ 테스트 데이터 전송 실패: {e}")

# ===================================================================
# 메인 실행부
# ===================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚗 Smart Parking System - 메인 컨트롤러")
    print("=" * 60)
    
    # 명령행 인자 처리
    tcp_port = 9999
    zmq_port = 5555
    payment_host = os.environ.get('PAYMENT_SERVER_HOST', 'localhost')
    try:
        payment_port = int(os.environ.get('PAYMENT_SERVER_PORT', '8888'))
    except:
        payment_port = 8888
    test_mode = False
    
    if len(sys.argv) > 1:
        if "--test" in sys.argv:
            test_mode = True
        if "--tcp-port" in sys.argv:
            tcp_idx = sys.argv.index("--tcp-port")
            if tcp_idx + 1 < len(sys.argv):
                tcp_port = int(sys.argv[tcp_idx + 1])
        if "--zmq-port" in sys.argv:
            zmq_idx = sys.argv.index("--zmq-port")
            if zmq_idx + 1 < len(sys.argv):
                zmq_port = int(sys.argv[zmq_idx + 1])
        if "--payment-host" in sys.argv:
            ph_idx = sys.argv.index("--payment-host")
            if ph_idx + 1 < len(sys.argv):
                payment_host = sys.argv[ph_idx + 1]
        if "--payment-port" in sys.argv:
            pp_idx = sys.argv.index("--payment-port")
            if pp_idx + 1 < len(sys.argv):
                payment_port = int(sys.argv[pp_idx + 1])
    
    # 메인 컨트롤러 시작
    controller = MainController(tcp_port, zmq_port, payment_host, payment_port)
    
    if test_mode:
        print("🧪 테스트 모드 활성화됨")
        
        # 별도 스레드에서 테스트 데이터 전송
        def test_data_thread():
            time.sleep(2)  # 컨트롤러 시작 대기
            sender = DummyDataSender()
            
            # 웨이포인트 전송
            sender.send_test_waypoints()
            time.sleep(1)
            
            # 위치 데이터 시뮬레이션
            test_positions = [
                (200, 200), (200, 400), (200, 600), (200, 800), 
                (200, 925), (350, 925), (500, 925), (550, 925)
            ]
            
            for x, y in test_positions:
                sender.send_test_position(x, y)
                time.sleep(2)
        
        threading.Thread(target=test_data_thread, daemon=True).start()
    
    # 컨트롤러 실행
    controller.start()

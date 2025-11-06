#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주차장 탑뷰 화면 - Smart_Parking_GUI.py 기반 디자인
ZeroMQ로 메인 컨트롤러로부터 실시간 데이터 수신하여
주차장 맵, 차량 위치, 배정된 경로를 시각화
"""

import sys
import json
import threading
import tempfile
import os
import socket
import time
from typing import List, Tuple, Optional, Dict, Any
from math import sqrt, atan2, degrees, sin, cos, radians
from datetime import datetime

import zmq
import pygame
from gtts import gTTS

from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem, QGraphicsPolygonItem,
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QGraphicsItemGroup, QFrame, QGraphicsObject, QMessageBox
)
from PyQt5.QtGui import (
    QBrush, QPainter, QPen, QColor, QPainterPath, QFont, QPolygonF,
    QLinearGradient, QRadialGradient, QTransform, QFontMetrics
)
from PyQt5.QtCore import (
    Qt, QPointF, QRectF, pyqtSignal, QTimer, QPropertyAnimation,
    pyqtProperty, QEasingCurve, QParallelAnimationGroup, QObject
)

# ===================================================================
# 개선된 현대차 스타일 컬러 팔레트 - Smart_Parking_GUI.py와 동일
# ===================================================================
HYUNDAI_COLORS = {
    'primary': '#1a1a1a',        # 진한 차콜 그레이
    'secondary': "#2d2d2d",      # 미디엄 그레이  
    'accent': '#4a9eff',         # 부드러운 블루
    'success': '#00d084',        # 민트 그린
    'warning': '#ffa726',        # 소프트 오렌지
    'danger': '#ef5350',         # 소프트 레드
    'background': '#0f0f0f',     # 더 깊은 블랙
    'surface': '#1e1e1e',        # 다크 서페이스
    'text_primary': '#ffffff',   # 순백
    'text_secondary': '#9e9e9e', # 쿨 그레이
    'glass': 'rgba(255, 255, 255, 0.08)',
    'blue_soft': '#6bb6ff',      # 소프트 블루
    'blue_muted': '#4285f4',     # 뮤트 블루
    'white_soft': '#f5f5f5',     # 소프트 화이트
    'gray_light': '#757575',     # 라이트 그레이
    'gray_medium': '#424242'     # 미디엄 그레이
}

FONT_SIZES = {
    'hud_distance': 42, 'hud_direction': 12, 'hud_speed': 28, 'hud_speed_unit': 10,
    'hud_progress': 14, 'hud_next_label': 10, 'hud_next_direction': 14,
    'map_label': 10, 'map_io_label': 12, 'map_waypoint_label': 12,
    'controls_title': 16, 'controls_info': 12, 'controls_button': 16, 'msgbox_button': 10
}

# ===================================================================
# TTS 음성 안내 모듈 (Smart_Parking_GUI.py와 동일)
# ===================================================================
class VoiceGuide:
    """음성 경로 안내를 담당하는 클래스 (Google TTS 사용)"""
    
    def __init__(self):
        self.last_instruction = None
        self.temp_files = []
        self.init_tts()
    
    def init_tts(self):
        """TTS 엔진 초기화 (Google TTS 사용)"""
        try:
            pygame.mixer.init()
            print("🔊 Google TTS 엔진 초기화 완료")
        except Exception as e:
            print(f"❌ TTS 초기화 실패: {e}")
            self.engine = None
    
    def speak_instruction(self, instruction_text):
        """음성 안내 재생"""
        if not instruction_text:
            return
        
        if self.last_instruction == instruction_text:
            return
        
        self.last_instruction = instruction_text
        
        try:
            threading.Thread(
                target=self._speak_thread,
                args=(instruction_text,),
                daemon=True,
                name="VoiceGuide"
            ).start()
        except Exception as e:
            print(f"❌ 음성 안내 재생 실패: {e}")
    
    def _speak_thread(self, text):
        """음성 재생 스레드 (Google TTS 사용)"""
        try:
            tts = gTTS(text=text, lang='ko', slow=False)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_path = temp_file.name
                tts.save(temp_path)
                self.temp_files.append(temp_path)
            
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            
            try:
                os.unlink(temp_path)
                if temp_path in self.temp_files:
                    self.temp_files.remove(temp_path)
            except:
                pass
            
            print(f"🔊 음성 안내: {text}")
            
        except Exception as e:
            print(f"❌ 음성 재생 중 오류: {e}")
    
    def stop(self):
        """TTS 엔진 정리"""
        try:
            pygame.mixer.quit()
            
            for temp_file in self.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except:
                    pass
            self.temp_files.clear()
            
            print("🔇 TTS 엔진 정리 완료")
        except Exception as e:
            print(f"❌ TTS 정리 중 오류: {e}")

# ===================================================================
# ZeroMQ 데이터 수신기 클래스
# ===================================================================
class ZMQDataReceiver(QObject):
    """ZeroMQ로부터 실시간 데이터 수신"""
    
    position_received = pyqtSignal(dict)
    waypoint_received = pyqtSignal(dict)
    
    def __init__(self, zmq_host='localhost', zmq_port=5555):
        super().__init__()
        self.zmq_host = zmq_host
        self.zmq_port = zmq_port
        self.context = None
        self.socket = None
        self.running = False
        
    def start(self):
        """ZeroMQ 구독 시작"""
        try:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.SUB)
            self.socket.connect(f"tcp://{self.zmq_host}:{self.zmq_port}")
            
            self.socket.setsockopt_string(zmq.SUBSCRIBE, "vehicle_position")
            self.socket.setsockopt_string(zmq.SUBSCRIBE, "waypoint_data")
            
            self.socket.setsockopt(zmq.RCVTIMEO, 100)
            
            self.running = True
            print(f"✅ ZeroMQ 구독 시작됨 - {self.zmq_host}:{self.zmq_port}")
            
            threading.Thread(target=self._receive_loop, daemon=True, name="ZMQReceiver").start()
            return True
            
        except Exception as e:
            print(f"❌ ZeroMQ 구독 시작 실패: {e}")
            return False
    
    def _receive_loop(self):
        """데이터 수신 루프"""
        while self.running:
            try:
                message = self.socket.recv_string(zmq.NOBLOCK)
                self._process_message(message)
                
            except zmq.Again:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ ZeroMQ 메시지 수신 오류: {e}")
                break
    
    def _process_message(self, message: str):
        """수신된 메시지 처리"""
        try:
            parts = message.split(' ', 1)
            if len(parts) != 2:
                return
                
            topic, json_data = parts
            data = json.loads(json_data)
            
            if topic == "vehicle_position":
                self.position_received.emit(data)
            elif topic == "waypoint_data":
                self.waypoint_received.emit(data)
                
        except Exception as e:
            print(f"❌ 메시지 처리 오류: {e}")
    
    def stop(self):
        """ZeroMQ 구독 종료"""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.context:
            self.context.term()
        print("🔄 ZeroMQ 구독 종료됨")

# ===================================================================
# 자동차 아이템: Smart_Parking_GUI.py와 동일
# ===================================================================
class CarItem(QGraphicsObject):
    positionChanged = pyqtSignal(QPointF)

    def __init__(self, parent=None, car_color="red"):
        super().__init__(parent)
        self.car_color = car_color
        
        self.car_body = QPolygonF([
            QPointF(-45, -45), QPointF(45, -45), QPointF(40, 15), QPointF(-40, 15)
        ])
        
        self.car_cabin = QPolygonF([
            QPointF(-30, 15), QPointF(30, 15), QPointF(25, 45), QPointF(-25, 45)
        ])
        
        self.headlight_left = QRectF(-35, -10, 15, 10)
        self.headlight_right = QRectF(20, -10, 15, 10)
        self.grille = QRectF(-15, -15, 30, 10)
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(100)
        self.setRotation(0)

    def boundingRect(self):
        return self.car_body.boundingRect().united(self.car_cabin.boundingRect()).adjusted(-5, -5, 5, 5)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        painter.save()
        painter.translate(4, 4)
        painter.setBrush(QBrush(QColor(0, 0, 0, 70)))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(self.car_body)
        painter.drawPolygon(self.car_cabin)
        painter.restore()

        body_gradient = QLinearGradient(0, 15, 0, -45)
        
        if self.car_color == "red":
            body_gradient.setColorAt(0, QColor(220, 30, 30))
            body_gradient.setColorAt(1, QColor(150, 20, 20))
            pen_color = QColor(255, 200, 200, 150)
        elif self.car_color == "blue":
            body_gradient.setColorAt(0, QColor(30, 30, 220))
            body_gradient.setColorAt(1, QColor(20, 20, 150))
            pen_color = QColor(200, 200, 255, 150)
        elif self.car_color == "green":
            body_gradient.setColorAt(0, QColor(30, 220, 30))
            body_gradient.setColorAt(1, QColor(20, 150, 20))
            pen_color = QColor(200, 255, 200, 150)
        elif self.car_color == "yellow":
            body_gradient.setColorAt(0, QColor(220, 220, 30))
            body_gradient.setColorAt(1, QColor(150, 150, 20))
            pen_color = QColor(255, 255, 200, 150)
        else:
            body_gradient.setColorAt(0, QColor(220, 30, 30))
            body_gradient.setColorAt(1, QColor(150, 20, 20))
            pen_color = QColor(255, 200, 200, 150)
            
        painter.setBrush(QBrush(body_gradient))
        painter.setPen(QPen(pen_color, 2))
        painter.drawPolygon(self.car_body)

        cabin_gradient = QLinearGradient(0, 45, 0, 15)
        cabin_gradient.setColorAt(0, QColor(50, 60, 80))
        cabin_gradient.setColorAt(1, QColor(20, 30, 50))
        painter.setBrush(QBrush(cabin_gradient))
        painter.setPen(QPen(QColor(150, 180, 200, 100), 1))
        painter.drawPolygon(self.car_cabin)

        headlight_gradient = QRadialGradient(0, 0, 15)
        headlight_gradient.setColorAt(0, QColor(255, 255, 220))
        headlight_gradient.setColorAt(1, QColor(200, 200, 150, 100))
        
        painter.save()
        painter.translate(self.headlight_left.center())
        painter.setBrush(QBrush(headlight_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(-7.5, -5, 15, 10))
        painter.restore()

        painter.save()
        painter.translate(self.headlight_right.center())
        painter.setBrush(QBrush(headlight_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(-7.5, -5, 15, 10))
        painter.restore()

        painter.setBrush(QBrush(QColor(50, 60, 70)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.grille, 3, 3)
        painter.setPen(QPen(QColor(100, 110, 120), 1.5))
        painter.drawLine(int(self.grille.left()), int(self.grille.center().y()), int(self.grille.right()), int(self.grille.center().y()))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)
        return super().itemChange(change, value)

# ===================================================================
# 메인 UI: 현대차 스타일 주차장 지도 (ZeroMQ 통합)
# ===================================================================
class ParkingLotUI(QWidget):
    """
    주차장 탑뷰 UI
    
    주차장 크기와 거리 변환:
    - SCENE_W, SCENE_H = 2000, 2000: 주차장 크기 (픽셀)
    - PIXELS_PER_METER = 50: 1미터 = 50픽셀
    - 주차장 실제 크기: 2000픽셀 / 50 = 40미터 x 40미터
    
    거리 계산:
    - 픽셀 거리 = sqrt((x2-x1)^2 + (y2-y1)^2)
    - 미터 거리 = 픽셀 거리 / PIXELS_PER_METER = 픽셀 거리 / 50
    """
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH = 30, 10, 50
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)
    
    # HUD 안내 계산 결과 저장
    last_calculated_instructions = None
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartParking Navigation System")
        # 최대화/최소화 버튼 활성화
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.initial_fit = False
        self.received_waypoints = []
        
        self.route_deviation_timer = QTimer(self)
        self.route_deviation_timer.timeout.connect(self.check_route_deviation)
        self.deviation_start_time = None
        self.is_deviating = False
        self.deviation_threshold = 2.0  # 2초 이상 이탈 시 경로 이탈로 인지
        self.route_tolerance = 200  # 상하좌우 기준 200픽셀 이상 벗어나면 이탈로 인지
        
        # 음성 안내 모듈 초기화
        self.voice_guide = VoiceGuide()
        
        # 재할당 서버 설정
        self.reassign_server_host = '192.168.0.111'  # 팀원 서버 주소
        self.reassign_server_port = 9999  # 기본 포트, 필요시 변경 가능
        self.waiting_for_reassignment = False  # 재할당 대기 플래그
        self.is_reassigned_route = False  # 재할당된 경로인지 여부
        self.requesting_reassignment = False  # 재할당 요청 중인지 여부 (중복 방지)
        
        self.setup_styles()
        self.init_ui()
        self.init_map()
        self.init_zmq()

    def setup_styles(self):
        self.setStyleSheet(f"""
            QWidget {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HYUNDAI_COLORS['background']}, stop:1 {HYUNDAI_COLORS['surface']}); color: {HYUNDAI_COLORS['text_primary']}; font-family: 'Malgun Gothic'; }}
            QGraphicsView {{ border: 3px solid {HYUNDAI_COLORS['accent']}; border-radius: 15px; background: '#303030'; }}
        """)

    def init_ui(self):
        from PyQt5.QtWidgets import QHBoxLayout
        main_layout = QHBoxLayout(self)
        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.scale(1, -1)
        self.view.translate(0, -self.SCENE_H)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(self.view)

    def init_map(self):
        self.layer_static = QGraphicsItemGroup()
        self.layer_path = QGraphicsItemGroup()
        self.scene.addItem(self.layer_static)
        self.scene.addItem(self.layer_path)
        self.full_path_points = []
        self.snapped_waypoints = []
        self.current_path_segment_index = 0
        self.is_exit_scenario = False
        self.car = CarItem()
        self.car.positionChanged.connect(self.update_hud_from_car_position)
        self.scene.addItem(self.car)
        self.car.hide()
        
        self.parked_cars = {}
        
        parked_car_positions = {
            2: (QPointF(550, 1800), "blue"),
            3: (QPointF(850, 1800), "green"),
            7: (QPointF(1800, 1000), "yellow"),
            9: (QPointF(1150, 600), "red")
        }
        
        for spot_num, (position, color) in parked_car_positions.items():
            parked_car = CarItem(car_color=color)
            parked_car.setPos(position)
            parked_car.setZValue(50)
            self.scene.addItem(parked_car)
            self.parked_cars[spot_num] = parked_car
            print(f"🚗 주차구역 {spot_num}번에 {color}색 차량 배치: ({position.x()}, {position.y()})")
        
        self.parking_spots = {}
        self.current_parking_spot = None
        
        self.build_static_layout()
        self.build_occupancy()

    def init_zmq(self):
        self.zmq_receiver = ZMQDataReceiver()
        self.zmq_receiver.position_received.connect(self.on_position_received)
        self.zmq_receiver.waypoint_received.connect(self.on_waypoint_received)
        
        if self.zmq_receiver.start():
            print("✅ 탑뷰 ZeroMQ 연결 성공")
            QMessageBox.information(self, "ZeroMQ 연결", f"ZeroMQ 수신기가 시작되었습니다.\n메인 컨트롤러로부터 데이터를 수신합니다.")
        else:
            QMessageBox.warning(self, "ZeroMQ 연결 실패", "ZeroMQ 수신기 시작에 실패했습니다.")

    def on_position_received(self, message_data):
        """차량 위치 데이터 수신 처리"""
        try:
            position_data = message_data.get('data', {})
            x = position_data.get('x', 0)
            y = position_data.get('y', 0)
            
            if x == 9000 and y == 9000:
                print("🚗 출차 신호 감지: (9000, 9000) 좌표 수신")
                self.handle_car_exit()
                return
            
            new_pos = QPointF(x, y)
            self.car.setPos(new_pos)
            if not self.car.isVisible():
                self.car.show()
            
            # Smart_Parking_GUI.py와 동일하게 위치 변경 시 HUD 안내 업데이트
            self.update_hud_from_car_position(new_pos)
            
        except Exception as e:
            print(f"❌ 위치 데이터 처리 오류: {e}")

    def on_waypoint_received(self, message_data):
        """웨이포인트 데이터 수신 처리"""
        try:
            # 디버깅: 수신된 메시지 전체 출력
            print(f"📥 수신된 메시지 타입: {message_data.get('type', 'unknown')}")
            print(f"📥 메시지 데이터 키: {message_data.keys()}")
            
            waypoint_data = message_data.get('data', {})
            
            # 재할당된 경로인지 확인 (팀원 서버가 보낸 형식)
            # main_controller가 팀원 서버 데이터를 받으면 그대로 전달하므로,
            # waypoint_data에 직접 waypoint_reassignment 타입이 있을 수 있음
            is_reassignment = (
                message_data.get('type') == 'waypoint_reassignment' or 
                waypoint_data.get('type') == 'waypoint_reassignment' or
                waypoint_data.get('assignment_mode') == 'test_reassignment'
            )
            
            print(f"🔍 재할당 경로 여부: {is_reassignment}")
            print(f"   message_data.type: {message_data.get('type')}")
            print(f"   waypoint_data.type: {waypoint_data.get('type')}")
            print(f"   assignment_mode: {waypoint_data.get('assignment_mode')}")
            
            if is_reassignment:
                # 재할당된 경로 처리
                waypoints = waypoint_data.get('waypoints', [])
                assigned_spot = waypoint_data.get('assigned_spot')
                
                print(f"📋 재할당 경로 데이터: waypoints={waypoints}, assigned_spot={assigned_spot}")
                
                if waypoints:
                    print(f"✅ 재할당된 경로 수신: {len(waypoints)}개 웨이포인트, {assigned_spot}번 주차구역")
                    print(f"   웨이포인트: {waypoints}")
                    
                    self.received_waypoints = waypoints
                    self.is_exit_scenario = False  # 재할당은 항상 입차 시나리오
                    self.is_reassigned_route = True  # 재할당된 경로 표시
                    self.waiting_for_reassignment = False
                    self.requesting_reassignment = False  # 재할당 요청 플래그 리셋
                    
                    self.calculate_and_display_route()
                    
                    # 팝업 제거: 재할당 완료 팝업도 표시하지 않음
                    return
                else:
                    print(f"⚠️ 재할당 경로 감지되었으나 waypoints가 비어있음")
            
            # 일반 웨이포인트 데이터 처리
            waypoints = waypoint_data.get('waypoints', [])
            parking_spot = waypoint_data.get('parking_spot')
            route_type = waypoint_data.get('route_type', 'entry')
            
            if not waypoints:
                return
            
            # 재할당 대기 중이 아닐 때만 일반 경로로 처리
            if not self.waiting_for_reassignment:
                self.received_waypoints = waypoints
                self.is_exit_scenario = (route_type == 'exit')
                self.is_reassigned_route = False  # 일반 경로는 재할당 아님
                
                QMessageBox.information(self, "경로 수신", f"새로운 경로가 수신되었습니다:\n{len(waypoints)}개 웨이포인트\n주차구역: {parking_spot}번\n경로 타입: {route_type}")
                
                self.calculate_and_display_route()
            
        except Exception as e:
            print(f"❌ 웨이포인트 데이터 처리 오류: {e}")

    def handle_car_exit(self):
        """차량 출차 처리"""
        print("🚗 차량 출차 처리 시작")
        
        if self.car.isVisible():
            self.car.hide()
            print("✅ 차량을 UI에서 제거했습니다")
        
        if hasattr(self, 'current_parking_spot') and self.current_parking_spot:
            self.restore_parking_spot_color(self.current_parking_spot)
            print(f"✅ 주차구역 {self.current_parking_spot}번 색상을 복원했습니다")
            self.current_parking_spot = None
        
        self.clear_path_layer()
        self.full_path_points = []
        self.current_path_segment_index = 0
        self.is_exit_scenario = False
        
        self.route_deviation_timer.stop()
        self.is_deviating = False
        self.deviation_start_time = None
        
        self.received_waypoints = []
        
        print("✅ 차량 출차 처리 완료")

    def detect_parking_spot_from_waypoint(self, waypoint):
        """웨이포인트 좌표를 기반으로 주차구역 번호 감지"""
        x, y = waypoint[0], waypoint[1]
        
        parking_waypoints = {
            1: [200, 1475], 2: [550, 1475], 3: [850, 1475], 4: [1150, 1475],
            5: [1450, 1475],
            6: [1475, 1400], 7: [1475, 1000],
            8: [1475, 925], 9: [1150, 925], 10: [850, 925], 11: [550, 925]
        }
        
        tolerance = 50
        for spot_num, coord in parking_waypoints.items():
            if abs(x - coord[0]) <= tolerance and abs(y - coord[1]) <= tolerance:
                return spot_num
        
        return None

    def change_parking_spot_color(self, parking_spot_num, color):
        """특정 주차구역의 색상을 변경합니다."""
        if parking_spot_num in self.parking_spots:
            rect_item = self.parking_spots[parking_spot_num]
            
            if color == "orange":
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(255, 165, 0, 250))
                gradient.setColorAt(1, QColor(255, 140, 0, 200))
                rect_item.setBrush(QBrush(gradient))
                rect_item.setPen(QPen(QColor("white"), 20))
                print(f"🎯 주차구역 {parking_spot_num}번 색상을 주황색으로 변경")

    def restore_parking_spot_color(self, parking_spot_num):
        """주차구역 색상을 원래 색상으로 복원합니다."""
        if parking_spot_num in self.parking_spots:
            rect_item = self.parking_spots[parking_spot_num]
            
            if parking_spot_num in [2, 3, 7, 9]:
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(255, 165, 0, 250))
                gradient.setColorAt(1, QColor(255, 140, 0, 200))
                rect_item.setBrush(QBrush(gradient))
                rect_item.setPen(QPen(QColor("white"), 20))
                return
            
            if parking_spot_num in [1, 7]:
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(135, 206, 250, 200))
                gradient.setColorAt(1, QColor(70, 130, 180, 150))
                rect_item.setBrush(QBrush(gradient))
            elif parking_spot_num in [4, 5, 10, 11]:
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor(0, 200, 130, 200))
                gradient.setColorAt(1, QColor(0, 150, 100, 150))
                rect_item.setBrush(QBrush(gradient))
            else:
                gradient = QLinearGradient(rect_item.rect().x(), rect_item.rect().y(),
                                        rect_item.rect().x() + rect_item.rect().width(),
                                        rect_item.rect().y() + rect_item.rect().height())
                gradient.setColorAt(0, QColor("#303030"))
                gradient.setColorAt(1, QColor("#303030"))
                rect_item.setBrush(QBrush(gradient))
            
            rect_item.setPen(QPen(QColor("white"), 20))

    def calculate_and_display_route(self):
        """받은 웨이포인트들을 직선으로 연결하여 경로를 표시합니다."""
        if not self.received_waypoints:
            QMessageBox.warning(self, "경로 오류", "경로를 계산할 웨이포인트가 없습니다.")
            return

        print(f"🗺️ 웨이포인트 경로 생성: {self.received_waypoints}")
        print(f"   is_exit_scenario: {self.is_exit_scenario}")
        print(f"   is_reassigned_route: {self.is_reassigned_route}")
        
        waypoints_qpoints = [QPointF(p[0], p[1]) for p in self.received_waypoints]
        
        if self.is_exit_scenario:
            # 출차 시나리오: 첫 번째 웨이포인트가 주차 좌표 포인트이므로 그대로 사용
            self.full_path_points = waypoints_qpoints
            start_point = waypoints_qpoints[0] if waypoints_qpoints else QPointF(200, 200)
            print(f"🚗 출차 경로: waypoints를 그대로 사용 ({len(waypoints_qpoints)}개 포인트)")
        elif self.is_reassigned_route:
            # 재할당된 경로: 서버에서 보낸 waypoints를 그대로 사용
            # 서버가 계산한 전체 경로를 보내므로 (200, 200)을 자동으로 추가하지 않음
            # 재할당 경로는 서버에서 받은 좌표를 그대로 시각화
            self.full_path_points = waypoints_qpoints.copy()  # 복사본 사용
            start_point = waypoints_qpoints[0] if waypoints_qpoints else QPointF(200, 200)
            print(f"🔄 재할당된 경로: 서버에서 받은 waypoints를 그대로 사용 ({len(waypoints_qpoints)}개 포인트)")
            print(f"   첫 번째 포인트: ({start_point.x()}, {start_point.y()})")
            print(f"   (200, 200) 추가 안 함 - 서버가 계산한 전체 경로 그대로 표시")
        else:
            # 일반 입차 시나리오: 입구(200, 200)부터 시작
            start_point = QPointF(200, 200)
            self.full_path_points = [start_point] + waypoints_qpoints
            print(f"🚗 일반 입차 경로: (200, 200) + waypoints ({len(self.full_path_points)}개 포인트)")
        
        if self.received_waypoints:
            last_waypoint = self.received_waypoints[-1]
            destination_parking_spot = self.detect_parking_spot_from_waypoint(last_waypoint)
            
            if destination_parking_spot:
                print(f"🎯 마지막 웨이포인트는 주차구역 {destination_parking_spot}번 입니다.")
                self.change_parking_spot_color(destination_parking_spot, "orange")
                self.current_parking_spot = destination_parking_spot

        print(f"✅ 최종 경로: {len(self.full_path_points)}개 포인트")
        
        self.clear_path_layer()
        if self.is_exit_scenario:
            self.draw_exit_path(self.full_path_points)
        else:
            self.draw_straight_path(self.full_path_points)
        
        self.current_path_segment_index = 0
        
        if not self.car.isVisible():
            self.car.setPos(start_point)
            self.car.show()
        
        self.route_deviation_timer.start(1000)
        
        self.update_hud_from_car_position(self.car.pos())

    def check_route_deviation(self):
        """경로 이탈 상태를 주기적으로 체크"""
        if not self.full_path_points or not self.car.isVisible():
            return
        
        car_pos = self.car.pos()
        
        if self.is_in_parking_spot(car_pos):
            if self.is_deviating:
                self.is_deviating = False
                self.deviation_start_time = None
            return
        
        distance_to_route = self.calculate_distance_to_route(car_pos)
        
        if distance_to_route > self.route_tolerance:
            if not self.is_deviating:
                self.is_deviating = True
                self.deviation_start_time = datetime.now()
                print(f"⚠️ 경로 이탈 감지 - 거리: {distance_to_route:.1f}픽셀")
            else:
                if self.deviation_start_time:
                    deviation_duration = (datetime.now() - self.deviation_start_time).total_seconds()
                    if deviation_duration >= self.deviation_threshold:
                        # 재할당 요청 중이 아니고, 재할당 대기 중이 아닐 때만 요청
                        if not self.requesting_reassignment and not self.waiting_for_reassignment:
                            self.show_route_recalculation_popup()
                        else:
                            print("⚠️ 이미 재할당 요청이 진행 중입니다. 추가 요청을 건너뜁니다.")
                        self.is_deviating = False
                        self.deviation_start_time = None
        else:
            if self.is_deviating:
                self.is_deviating = False
                self.deviation_start_time = None

    def is_in_parking_spot(self, car_pos):
        """차량이 주차 칸 박스 안에 있는지 확인"""
        x, y = car_pos.x(), car_pos.y()
        
        parking_spots = {
            1: (0, 1600, 400, 400),
            2: (400, 1600, 300, 400),
            3: (700, 1600, 300, 400),
            4: (1000, 1600, 300, 400),
            5: (1300, 1600, 300, 400),
            6: (1600, 1200, 400, 400),
            7: (1600, 800, 400, 400),
            8: (1300, 400, 300, 400),
            9: (1000, 400, 300, 400),
            10: (700, 400, 300, 400),
            11: (400, 400, 300, 400),
        }
        
        for spot_num, (spot_x, spot_y, spot_w, spot_h) in parking_spots.items():
            if spot_x <= x <= spot_x + spot_w and spot_y <= y <= spot_y + spot_h:
                return True
        
        return False

    def calculate_distance_to_route(self, car_pos):
        """차량 위치에서 가장 가까운 경로까지의 거리 계산"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return float('inf')
        
        min_distance = float('inf')
        
        for i in range(len(self.full_path_points) - 1):
            p1 = self.full_path_points[i]
            p2 = self.full_path_points[i + 1]
            
            distance = self.point_to_line_distance(car_pos, p1, p2)
            min_distance = min(min_distance, distance)
        
        return min_distance

    def point_to_line_distance(self, point, line_start, line_end):
        """점과 선분 사이의 최단 거리 계산"""
        line_vec = line_end - line_start
        point_vec = point - line_start
        
        line_len_sq = QPointF.dotProduct(line_vec, line_vec)
        
        if line_len_sq == 0:
            return sqrt((point.x() - line_start.x())**2 + (point.y() - line_start.y())**2)
        
        t = QPointF.dotProduct(point_vec, line_vec) / line_len_sq
        t = max(0, min(1, t))
        
        closest_point = line_start + t * line_vec
        
        return sqrt((point.x() - closest_point.x())**2 + (point.y() - closest_point.y())**2)

    def show_route_recalculation_popup(self):
        """경로 재탐색 트리거 - 서버에 재할당 요청 (팝업 없이)"""
        # 이미 재할당 요청 중이면 중복 방지
        if self.requesting_reassignment:
            print("⚠️ 이미 재할당 요청이 진행 중입니다. 중복 요청을 방지합니다.")
            return
        
        # 음성 안내 재생
        self.voice_guide.speak_instruction("경로를 재탐색합니다. 잠시만 기다려주세요")
        
        # 현재 차량 위치 가져오기
        current_car_pos = self.car.pos() if self.car.isVisible() else None
        
        # 재할당 요청 플래그 설정 (중복 방지)
        self.requesting_reassignment = True
        self.waiting_for_reassignment = True
        
        # 서버에 재할당 요청 전송 (팀원 서버 형식에 맞춤)
        success = self.request_route_reassign(current_car_pos)
        
        if success:
            # 서버가 팀원 노트북으로 waypoints를 전송하므로, 
            # ZeroMQ로 waypoints가 수신될 때까지 대기
            # on_waypoint_received에서 처리됨
            print("✅ 경로 재할당 요청 전송 완료, 서버 응답 대기 중...")
        else:
            # 재할당 요청 실패 시 플래그 리셋
            self.waiting_for_reassignment = False
            self.requesting_reassignment = False
            print("❌ 경로 재할당 요청 실패: 서버 연결 실패")
    
    def request_route_reassign(self, current_position: Optional[QPointF] = None) -> bool:
        """
        서버에 경로 재할당 요청 전송 (팀원 서버 형식에 맞춤)
        
        서버는 요청을 받아서 계산한 경로를 팀원 노트북으로 전송하므로,
        이 메서드는 요청만 보내고 성공/실패만 반환합니다.
        실제 waypoints는 ZeroMQ를 통해 on_waypoint_received에서 수신됩니다.
        
        Args:
            current_position: 현재 차량 위치 (QPointF)
        
        Returns:
            요청 전송 성공 여부 (bool)
        """
        try:
            # TCP/IP 소켓으로 서버에 연결
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10.0)  # 10초 타임아웃
            client_socket.connect((self.reassign_server_host, self.reassign_server_port))
            
            # 재할당 요청 메시지 생성 (팀원 서버 형식)
            reassign_request = {
                'type': 'reassign'
            }
            
            # 현재 위치 정보가 있으면 추가 (필수)
            if current_position:
                reassign_request['current_x'] = float(current_position.x())
                reassign_request['current_y'] = float(current_position.y())
            else:
                # 현재 위치가 없으면 에러
                print("❌ 경로 재할당 요청 실패: 현재 차량 위치 정보가 없습니다.")
                client_socket.close()
                return False
            
            # JSON 문자열로 전송
            json_str = json.dumps(reassign_request, ensure_ascii=False)
            client_socket.sendall(json_str.encode('utf-8'))
            
            print(f"📤 경로 재할당 요청 전송: {self.reassign_server_host}:{self.reassign_server_port}")
            print(f"   요청 데이터: {json_str}")
            
            # 서버 응답 수신 (팀원 서버는 {'status': 'success'/'failed', 'message': '...'} 형식)
            response_data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            
            client_socket.close()
            
            # JSON 응답 파싱
            response_str = response_data.decode('utf-8')
            response_json = json.loads(response_str)
            
            print(f"📥 서버 응답 수신: {response_str}")
            
            # 응답 상태 확인
            status = response_json.get('status', 'failed')
            message = response_json.get('message', '')
            
            if status == 'success':
                print(f"✅ 서버 재할당 요청 성공: {message}")
                print("   서버가 팀원 노트북으로 waypoints를 전송 중입니다.")
                return True
            else:
                print(f"❌ 서버 재할당 요청 실패: {message}")
                return False
                
        except socket.timeout:
            print(f"❌ 경로 재할당 요청 실패: 연결 시간 초과")
            return False
        except ConnectionRefusedError:
            print(f"❌ 경로 재할당 요청 실패: 서버 연결 거부됨 ({self.reassign_server_host}:{self.reassign_server_port})")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ 서버 응답 JSON 파싱 실패: {e}")
            return False
        except Exception as e:
            print(f"❌ 경로 재할당 요청 중 오류: {e}")
            return False

    def showEvent(self, event):
        super().showEvent(event)
        if not self.initial_fit:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.initial_fit = True
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.initial_fit:
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            
    def closeEvent(self, event):
        if self.zmq_receiver:
            self.zmq_receiver.stop()
        self.route_deviation_timer.stop()
        if hasattr(self, 'voice_guide'):
            self.voice_guide.stop()
        super().closeEvent(event)

    def add_block(self, x, y, w, h, color, label=""):
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        
        if "장애인" in label:
            gradient = QLinearGradient(x,y,x+w,y+h)
            gradient.setColorAt(0,QColor(135, 206, 250, 200))
            gradient.setColorAt(1,QColor(70, 130, 180,150))
            r.setBrush(QBrush(gradient))
        elif "전기차" in label:
            gradient = QLinearGradient(x,y,x+w,y+h)
            gradient.setColorAt(0,QColor(0,200,130,200))
            gradient.setColorAt(1,QColor(0,150,100,150))
            r.setBrush(QBrush(gradient))
        elif "일반" in label:
            gradient = QLinearGradient(x,y,x+w,y+h)
            gradient.setColorAt(0,QColor("#303030"))
            gradient.setColorAt(1,QColor("#303030"))
            r.setBrush(QBrush(gradient))
        else:
            r.setBrush(QBrush(color))
            
        if "장애인" in label or "전기" in label or "일반" in label:
            pen = QPen(QColor("white"), 20)
            r.setPen(pen)
        elif label in ["백화점 본관 입구", "영화관 입구", "문화시설 입구"]:
            pen = QPen(QColor(255, 255, 0), 20)
            r.setPen(pen)
        elif "입출차" in label:
            r.setPen(QPen(Qt.NoPen))
        else:
            r.setPen(QPen(QColor(255,255,255,100), 2))

        r.setParentItem(self.layer_static)

        if label:
            t = QGraphicsSimpleTextItem(label)
            t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setBrush(QColor(255,255,255))
            if label in ["백화점 본관 입구", "영화관 입구", "문화시설 입구"]:
                font = QFont("Malgun Gothic", int(FONT_SIZES['map_label'] * 2.25), QFont.Bold)
                if label == "백화점 본관 입구":
                    t.setPos(x+w//2-50-310, y-20)
                elif label == "영화관 입구":
                    t.setPos(x+w+20, y+h-40)
                elif label == "문화시설 입구":
                    t.setPos(x+w+20, y+h-60)
            elif label in ["장애인", "전기", "일반"]:
                font = QFont("Malgun Gothic", int(FONT_SIZES['map_label'] * 1.5), QFont.Bold)
                t.setPos(x+5,y+h-25)
            else:
                font = QFont("Malgun Gothic", FONT_SIZES['map_label'], QFont.Bold)
                t.setPos(x+5,y+h-25)
            t.setFont(font)
            t.setParentItem(self.layer_static)
        
        return r

    def add_hatched(self, x, y, w, h, edge=QColor("black"), fill=QColor(220, 20, 60, 90)):
        r = QGraphicsRectItem(QRectF(x,y,w,h)); b = QBrush(fill); b.setStyle(Qt.BDiagPattern); r.setBrush(b); r.setPen(QPen(edge,3)); r.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem("통행 불가"); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setBrush(QColor(255,100,100))
        font = QFont("Malgun Gothic", int(FONT_SIZES['map_label'] * 1.5), QFont.Bold); t.setFont(font); t.setPos(x+10,y+h-30); t.setParentItem(self.layer_static)

    def add_dot_label_static(self, p: QPointF, text: str, color=QColor("blue")):
        t = QGraphicsSimpleTextItem(text); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setBrush(QColor(0,200,255))
        font = QFont("Malgun Gothic", FONT_SIZES['map_io_label'], QFont.Bold); t.setFont(font); t.setPos(p.x()-20,p.y()+25); t.setParentItem(self.layer_static)

    def build_static_layout(self):
        c_dis, c_ele, c_gen, c_obs, c_emp, c_io = QColor(135, 206, 250), QColor(0, 200, 130), QColor("#303030"), QColor(108, 117, 125), QColor(206, 212, 218), QColor("#303030")
        border = QGraphicsRectItem(0, 0, self.SCENE_W, self.SCENE_H); border.setPen(QPen(QColor(0, 170, 210), 12)); border.setBrush(QBrush(Qt.NoBrush)); border.setParentItem(self.layer_static)
        
        self.add_hatched(400, 0, 1600, 400)
        
        self.add_block(0, 0, 400, 400, c_io, "입출차")
        
        base = [
            (-400, 1600, 400, 400, c_emp, "백화점 본관 입구"),
            (1600, 1600, 400, 400, c_emp, "영화관 입구"),
            (550, 1050, 800, 300, c_obs, "장애물")
        ]
        
        parking_spots = [
            (0, 1600, 400, 400, c_dis, "장애인"),
            (400, 1600, 300, 400, c_gen, "일반"),
            (700, 1600, 300, 400, c_gen, "일반"),
            (1000, 1600, 300, 400, c_ele, "전기"),
            (1300, 1600, 300, 400, c_ele, "전기"),
            (1600, 1200, 400, 400, c_dis, "장애인"),
            (1000, 400, 300, 400, c_gen, "일반"),
            (700, 400, 300, 400, c_ele, "전기"),
            (400, 400, 300, 400, c_ele, "전기")
        ]
        
        for x, y, w, h, c, l in base: self.add_block(x, y, w, h, c, l)
        
        self.add_dot_label_static(self.ENTRANCE, "입구", QColor(0, 170, 210))
        
        spot_numbers = [1, 2, 3, 4, 5, 6, 9, 10, 11]
        for i, (x, y, w, h, c, l) in enumerate(parking_spots):
            rect_item = self.add_block(x, y, w, h, c, l)
            if rect_item:
                self.parking_spots[spot_numbers[i]] = rect_item
        
        self.change_parking_spot_color(2, "orange")
        self.change_parking_spot_color(3, "orange")
        self.change_parking_spot_color(9, "orange")
        
        self.add_block(1600, 400, 400, 400, c_emp, "문화시설 입구")
        
        rect_item = self.add_block(1600, 800, 400, 400, c_dis, "장애인")
        self.parking_spots[7] = rect_item
        
        rect_item = self.add_block(1300, 400, 300, 400, c_gen, "일반")
        self.parking_spots[8] = rect_item
        
        self.change_parking_spot_color(7, "orange")

    def build_occupancy(self):
        W, H, C = self.SCENE_W, self.SCENE_H, self.CELL
        gx, gy = (W + C - 1) // C, (H + C - 1) // C
        self.grid_w, self.grid_h = gx, gy
        self.occ = bytearray(gx * gy)
        def idx(cx, cy): return cy * gx + cx
        def block_rect(x, y, w, h):
            x0,y0,x1,y1 = max(0,x-self.MARGIN), max(0,y-self.MARGIN), min(W,x+w+self.MARGIN), min(H,y+h+self.MARGIN)
            cx0,cy0,cx1,cy1 = int(x0//C), int(y0//C), int((x1-1)//C), int((y1-1)//C)
            for cy in range(cy0,cy1+1):
                for cx in range(cx0,cx1+1):
                    if 0<=cx<gx and 0<=cy<gy: self.occ[cy*gx+cx] = 1
        
        for x,y,w,h,c,l in [
            (550,1050,800,300,0,""),
            (400,0,1600,400,0,""),
            (1600,400,400,400,0,""),
            (1600,1600,400,400,0,""),
            (-400,1600,400,400,0,""),
            (0,0,400,400,0,"")
        ]: 
            block_rect(x,y,w,h)
        
        parking_blocks = [
            (0, 1600, 400, 400, 0, ""),
            (400, 1600, 300, 400, 0, ""),
            (700, 1600, 300, 400, 0, ""),
            (1000, 1600, 300, 400, 0, ""),
            (1300, 1600, 300, 400, 0, ""),
            (1600, 1200, 400, 400, 0, ""),
            (1600, 800, 400, 400, 0, ""),
            (1300, 400, 300, 400, 0, ""),
            (1000, 400, 300, 400, 0, ""),
            (700, 400, 300, 400, 0, ""),
            (400, 400, 300, 400, 0, "")
        ]
        
        for x,y,w,h,c,l in parking_blocks: 
            block_rect(x,y,w,h)
        
        self._occ_idx = idx

    def clear_path_layer(self):
        for child in self.layer_path.childItems(): self.scene.removeItem(child)

    def draw_straight_path(self, pts):
        if len(pts) < 2: return
        
        for i in range(len(pts) - 1):
            start = pts[i]
            end = pts[i + 1]
            
            for width, alpha in [(self.PATH_WIDTH + 12, 60), (self.PATH_WIDTH + 6, 100)]:
                glow_pen = QPen(QColor(0,170,210,alpha), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                self.scene.addLine(start.x(), start.y(), end.x(), end.y(), glow_pen).setParentItem(self.layer_path)
            
            main_pen = QPen(QColor(0,200,255), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self.scene.addLine(start.x(), start.y(), end.x(), end.y(), main_pen).setParentItem(self.layer_path)
            
            center_pen = QPen(QColor(255,255,255,150), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self.scene.addLine(start.x(), start.y(), end.x(), end.y(), center_pen).setParentItem(self.layer_path)

    def draw_exit_path(self, pts):
        if len(pts) < 2: return
        
        for i in range(len(pts) - 1):
            start, end = pts[i], pts[i + 1]
            
            for width, alpha in [(self.PATH_WIDTH + 12, 60), (self.PATH_WIDTH + 6, 100)]:
                glow_pen = QPen(QColor(255, 165, 0, alpha), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                line_item = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), glow_pen)
                line_item.setParentItem(self.layer_path)
            
            main_pen = QPen(QColor(255, 140, 0), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            line_item = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), main_pen)
            line_item.setParentItem(self.layer_path)
            
            center_pen = QPen(QColor(255, 255, 255, 150), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            line_item = self.scene.addLine(start.x(), start.y(), end.x(), end.y(), center_pen)
            line_item.setParentItem(self.layer_path)
            
            self.draw_clockwise_arrow(start, end)

    def draw_clockwise_arrow(self, start, end):
        mid_x = (start.x() + end.x()) / 2
        mid_y = (start.y() + end.y()) / 2
        
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = sqrt(dx*dx + dy*dy)
        
        if length == 0:
            return
        
        nx = dx / length
        ny = dy / length
        
        arrow_size = 20
        
        arrow_head_x = mid_x + nx * arrow_size
        arrow_head_y = mid_y + ny * arrow_size
        
        angle = radians(30)
        cos_angle = cos(angle)
        sin_angle = sin(angle)
        
        left_wing_x = mid_x + (nx * cos_angle - ny * sin_angle) * arrow_size * 0.6
        left_wing_y = mid_y + (nx * sin_angle + ny * cos_angle) * arrow_size * 0.6
        
        right_wing_x = mid_x + (nx * cos_angle + ny * sin_angle) * arrow_size * 0.6
        right_wing_y = mid_y + (-nx * sin_angle + ny * cos_angle) * arrow_size * 0.6
        
        arrow_points = [
            QPointF(arrow_head_x, arrow_head_y),
            QPointF(left_wing_x, left_wing_y),
            QPointF(right_wing_x, right_wing_y)
        ]
        
        arrow_polygon = QPolygonF(arrow_points)
        
        arrow_item = QGraphicsPolygonItem(arrow_polygon)
        arrow_item.setBrush(QBrush(QColor(255, 140, 0)))
        arrow_item.setPen(QPen(QColor(255, 255, 255), 2))
        arrow_item.setParentItem(self.layer_path)
        self.scene.addItem(arrow_item)

    def _update_current_segment(self, car_pos):
        if not self.full_path_points or len(self.full_path_points) < 2:
            return
            
        while self.current_path_segment_index < len(self.full_path_points) - 1:
            p_curr = self.full_path_points[self.current_path_segment_index]
            p_next = self.full_path_points[self.current_path_segment_index + 1]

            dist_to_next = sqrt((car_pos.x() - p_next.x())**2 + (car_pos.y() - p_next.y())**2)

            v_seg = p_next - p_curr
            v_car = car_pos - p_curr
            seg_len_sq = QPointF.dotProduct(v_seg, v_seg)
            proj_ratio = 1.0
            if seg_len_sq > 0:
                proj_ratio = QPointF.dotProduct(v_car, v_seg) / seg_len_sq

            if dist_to_next < 50 or proj_ratio > 1.0:
                self.current_path_segment_index += 1
            else:
                break

    def update_hud_from_car_position(self, car_pos):
        """차량 위치 업데이트 - Smart_Parking_GUI.py와 동일한 로직으로 HUD 안내 생성"""
        if not self.full_path_points:
            return
        
        # 현재 세그먼트 업데이트
        self._update_current_segment(car_pos)
        
        # 남은 경로 포인트 계산
        remaining_pts = self.full_path_points[self.current_path_segment_index+1:]
        path_for_hud = [car_pos] + remaining_pts
        
        if len(path_for_hud) < 2:
            # 목적지 도착
            if self.is_exit_scenario:
                instruction_str = "출차 완료"
            else:
                instruction_str = "목적지 도착"
            # main_controller로 전송할 형식으로 변환 (웨이포인트가 없는 경우 처리)
            return
        
        # HUD 안내 생성 (Smart_Parking_GUI.py와 동일한 로직)
        instructions = self.generate_hud_instructions(path_for_hud, self.is_exit_scenario)
        progress = self.calculate_route_progress(car_pos)
        speed = self.calculate_realistic_speed(instructions, progress, car_pos)
        
        # instructions를 main_controller 형식으로 변환하여 전송
        # main_controller는 별도 프로세스이므로, 여기서는 로컬 변수에 저장
        self.last_calculated_instructions = {
            'instructions': instructions,
            'speed': speed,
            'progress': progress,
            'car_pos': car_pos
        }
        
        # main_controller가 위치 수신 시 자동으로 Smart_Parking_GUI.py 방식의 안내를 생성하도록 개선됨
        # parking_topview는 경로 정보를 유지하여 경로 이탈 감지 등에 사용
    
    def generate_hud_instructions(self, pts, is_exit_scenario=False):
        """HUD 안내 메시지 생성 - Smart_Parking_GUI.py와 동일한 로직"""
        if len(pts) < 2:
            return []
        
        instructions = []
        total_dist = 0
        
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i+1]
            # QPointF 형식 처리
            dist_m = sqrt((p2.x()-p1.x())**2 + (p2.y()-p1.y())**2) / self.PIXELS_PER_METER
            total_dist += dist_m
            
            if i < len(pts) - 2:
                p3 = pts[i+2]
                angle = (degrees(atan2(p3.y()-p2.y(), p3.x()-p2.x())) - 
                        degrees(atan2(p2.y()-p1.y(), p2.x()-p1.x())) + 180) % 360 - 180
                direction = "좌회전" if angle > 45 else ("우회전" if angle < -45 else "")
                
                if direction:
                    # 직진 구간 시작점(p1)과 회전 좌표(p2) 간 거리 계산 (픽셀 단위)
                    straight_to_turn_dist = sqrt((p2.x()-p1.x())**2 + (p2.y()-p1.y())**2)
                    
                    # 회전 좌표(p2)와 다음 좌표(p3) 간 거리 계산 (픽셀 단위)
                    turn_to_next_dist = sqrt((p3.x()-p2.x())**2 + (p3.y()-p2.y())**2)
                    
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
        
        if is_exit_scenario:
            instructions.append(("출차 완료", total_dist))
        else:
            instructions.append(("목적지 도착", total_dist))
        
        return instructions
    
    def calculate_route_progress(self, car_pos):
        """경로 진행률 계산 - Smart_Parking_GUI.py와 동일한 로직"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return 0
        
        # 전체 경로 길이 계산
        total_len = sum(sqrt((self.full_path_points[i+1].x()-p.x())**2 + 
                           (self.full_path_points[i+1].y()-p.y())**2) 
                       for i, p in enumerate(self.full_path_points[:-1]))
        
        if total_len == 0:
            return 0
        
        # 가장 가까운 세그먼트와 투영 비율 찾기
        min_dist = float('inf')
        closest_seg = 0
        proj_ratio = 0
        
        for i, p1 in enumerate(self.full_path_points[:-1]):
            p2 = self.full_path_points[i+1]
            seg_vec = p2 - p1
            car_vec = car_pos - p1
            seg_len_sq = QPointF.dotProduct(seg_vec, seg_vec)
            
            if seg_len_sq == 0:
                continue
            
            t = max(0, min(1, QPointF.dotProduct(car_vec, seg_vec) / seg_len_sq))
            proj = p1 + t * seg_vec
            dist = sqrt((car_pos.x()-proj.x())**2 + (car_pos.y()-proj.y())**2)
            
            if dist < min_dist:
                min_dist = dist
                closest_seg = i
                proj_ratio = t
        
        # 이동한 거리 계산
        traveled = sum(sqrt((self.full_path_points[i+1].x()-p.x())**2 +
                           (self.full_path_points[i+1].y()-p.y())**2) 
                       for i, p in enumerate(self.full_path_points[:closest_seg]))
        
        if closest_seg < len(self.full_path_points) - 1:
            p1, p2 = self.full_path_points[closest_seg], self.full_path_points[closest_seg+1]
            traveled += sqrt((p2.x()-p1.x())**2 + (p2.y()-p1.y())**2) * proj_ratio
        
        return min(100, (traveled / total_len) * 100)
    
    def calculate_realistic_speed(self, instructions, progress, car_pos):
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
        if self.is_exit_scenario:
            speed *= 0.75
        
        # 최종 속도 범위 제한 (0-30km/h)
        speed = max(0, min(30, int(speed)))
        
        return speed

# ===================================================================
# 메인 실행부
# ===================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚗 Smart Parking System - 주차장 탑뷰")
    print("=" * 60)
    
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    font = QFont("Malgun Gothic")
    font.setPointSize(10)
    app.setFont(font)
    
    app.setStyleSheet(f"""
        QApplication {{ background-color: '#303030'; }}
    """)
    
    main_window = ParkingLotUI()
    
    screens = app.screens()
    if len(screens) > 0:
        screen_geometry = screens[0].geometry()
        main_window.setGeometry(screen_geometry)
        print(f"🖥️ 첫 번째 디스플레이에 배치: {screen_geometry.width()}x{screen_geometry.height()}")
    
    main_window.showMaximized()
    
    print("✅ 주차장 탑뷰 화면 시작됨")
    print("📡 메인 컨트롤러로부터 데이터 수신 대기 중...")
    
    sys.exit(app.exec_())

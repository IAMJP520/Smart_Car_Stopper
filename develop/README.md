# Smart Parking System - 멀티 디스플레이 시스템

## 개요

이 시스템은 주차장 네비게이션을 두 개의 확장 디스플레이로 분리하여 제공합니다:

1. **1번 디스플레이 (주차장 탑뷰)**: 주차장 전체 지도, 배정된 경로, 차량의 현재 위치 시각화
2. **2번 디스플레이 (HUD 경로 안내)**: 실시간 경로 안내, 거리 정보, 음성 안내

## 시스템 구조

```
외부 관제 서버 (TCP/IP:9999)
         ↓
   main_controller.py (ZeroMQ 브로드캐스터:5555)
         ↓
    ┌────┴────┐
    ↓         ↓
parking_topview.py  navigation_hud.py
(1번 디스플레이)    (2번 디스플레이)
```

## 파일 구조

### 1. `main_controller.py`
- **역할**: 외부 관제 서버와의 TCP/IP 통신 및 ZeroMQ 브로드캐스팅
- **포트**:
  - TCP/IP 수신: `9999` (외부 서버로부터 데이터 수신)
  - ZeroMQ 발행: `5555` (두 화면으로 데이터 브로드캐스트)

### 2. `parking_topview.py`
- **역할**: 주차장 탑뷰 화면 (1번 디스플레이)
- **기능**:
  - 주차장 지도 시각화
  - 배정된 경로 표시
  - 차량 위치 실시간 업데이트
  - 웨이포인트 마커 표시

### 3. `navigation_hud.py`
- **역할**: HUD 경로 안내 화면 (2번 디스플레이)
- **기능**:
  - 실시간 경로 안내 ("#m 후 좌회전" 등)
  - 거리 표시
  - 음성 안내 (Google TTS)
  - 진행률 표시

## 타이밍 동기화 방식

### ZeroMQ 메시지 브로커 패턴

이 시스템은 **ZeroMQ**를 사용한 메시지 브로커 패턴을 채택했습니다:

1. **동기화 메커니즘**:
   - 모든 메시지에 `timestamp_unix` (Unix 타임스탬프) 포함
   - 각 메시지에 고유 `sync_id` 부여
   - 위치 데이터와 네비게이션 안내 간 `position_sync_id`로 연결

2. **실시간 동기화**:
   - ZeroMQ PUB/SUB 패턴으로 동일 데이터를 두 화면에 동시 전송
   - 네트워크 지연 최소화 (로컬 네트워크)
   - 타임스탬프 기반 동기화 보장

3. **동기화 보장 방법**:
   ```python
   # 메시지 구조 예시
   {
       "timestamp": "2025-01-XX...",
       "timestamp_unix": 1737XXX.XXX,  # 정밀 동기화용
       "sync_id": "pos_1737XXX.XXX",
       "data": {...}
   }
   ```

## 실행 방법

### 1. 메인 컨트롤러 시작

```bash
cd develop
python main_controller.py
```

또는 포트를 변경하려면:

```bash
python main_controller.py --tcp-port 9999 --zmq-port 5555
```

### 2. 탑뷰 화면 시작 (1번 디스플레이)

새 터미널에서:

```bash
cd develop
python parking_topview.py
```

자동으로 첫 번째 디스플레이에 전체 화면으로 표시됩니다.

### 3. HUD 화면 시작 (2번 디스플레이)

새 터미널에서:

```bash
cd develop
python navigation_hud.py
```

자동으로 두 번째 디스플레이에 전체 화면으로 표시됩니다.

## 데이터 흐름

### 1. 경로 할당 (Waypoint Assignment)

```
외부 서버 → main_controller (TCP:9999)
         → ZeroMQ 브로드캐스트 (topic: "waypoint_data")
         → parking_topview.py (경로 표시)
         → navigation_hud.py (경로 정보 저장)
```

### 2. 차량 위치 업데이트 (Position Update)

```
외부 서버 → main_controller (TCP:9999)
         → ZeroMQ 브로드캐스트 (topic: "vehicle_position")
         → parking_topview.py (차량 위치 업데이트)
         → main_controller (네비게이션 안내 자동 생성)
         → ZeroMQ 브로드캐스트 (topic: "navigation_instruction")
         → navigation_hud.py (안내 표시 및 음성 재생)
```

## 필요 라이브러리

```bash
pip install PyQt5 pyzmq pygame gtts pyttsx3
```

## 테스트 모드

메인 컨트롤러를 테스트 모드로 실행하면 더미 데이터가 자동으로 전송됩니다:

```bash
python main_controller.py --test
```

## 디스플레이 설정

### 수동 디스플레이 선택

특정 디스플레이를 지정하려면 코드에서 수정:

```python
# parking_topview.py
screens = app.screens()
screen_geometry = screens[0].geometry()  # 0=첫 번째, 1=두 번째
main_window.setGeometry(screen_geometry)
```

## 문제 해결

### 1. ZeroMQ 연결 실패
- 메인 컨트롤러가 먼저 실행되어야 합니다
- 포트 5555가 다른 프로그램에 사용 중인지 확인

### 2. 디스플레이 감지 안 됨
- 시스템에서 확장 디스플레이가 올바르게 설정되었는지 확인
- `app.screens()`로 감지된 디스플레이 수 확인

### 3. 동기화 문제
- 메시지의 `timestamp_unix` 값 비교로 동기화 상태 확인
- 네트워크 지연이 큰 경우 ZeroMQ 버퍼 크기 조정

## 개선 사항

### 현재 구현된 기능
✅ ZeroMQ 기반 실시간 동기화  
✅ 타임스탬프 기반 타이밍 동기화  
✅ 자동 디스플레이 감지 및 배치  
✅ 위치 기반 자동 네비게이션 안내 생성  

### 향후 개선 가능 사항
- [ ] 동기화 지연 시간 측정 및 로깅
- [ ] 네트워크 지연 보상 메커니즘
- [ ] 화면 전환 애니메이션
- [ ] 사용자 설정 파일 지원 (포트, 디스플레이 번호 등)

## 라이센스

이 프로젝트는 내부 사용 목적으로 개발되었습니다.


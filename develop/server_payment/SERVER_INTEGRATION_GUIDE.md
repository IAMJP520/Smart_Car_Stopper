# 주차 정산 기능 서버 통합 가이드

## 📋 개요

이 문서는 **서버 팀원**이 주차 정산 기능을 서버에 통합하기 위한 실전 가이드입니다.  
클라이언트 측은 이미 구현되어 있으며, 서버 측에서 필요한 구현 사항만 설명합니다.

---

## 🎯 구현해야 할 기능

서버에서는 다음 **3가지 핵심 기능**만 구현하면 됩니다:

1. ✅ **정산 요청 수신**: 클라이언트로부터 `{'type': 'pay', 'parking_spot': ...}` 수신
2. ✅ **정산 금액 계산**: 주차 시간 기반 정산 금액 계산
3. ✅ **정산 금액 브로드캐스트**: ZeroMQ로 정산 금액 전송
4. ✅ **정산 확인 수신**: 클라이언트로부터 `{'type': 'payment_confirmation', ...}` 수신

---

## 📡 통신 프로토콜

### TCP/IP 소켓 (포트 9999)
- **정산 요청 수신**: 클라이언트 → 서버
- **정산 확인 수신**: 클라이언트 → 서버

### ZeroMQ (포트 5555)
- **정산 금액 브로드캐스트**: 서버 → 클라이언트

---

## 🚀 빠른 시작 가이드

### 1단계: JSON 데이터 형식 확인

#### 정산 요청 (클라이언트 → 서버)
```json
{
    "type": "pay",
    "parking_spot": 7
}
```

#### 정산 금액 응답 (서버 → 클라이언트, ZeroMQ)
```json
{
    "type": "payment",
    "timestamp": "2025-01-15T10:30:45.123456",
    "data": {
        "amount": 5000,
        "parking_spot": 7,
        "parking_duration_minutes": 120,
        "currency": "KRW"
    }
}
```

#### 정산 확인 (클라이언트 → 서버)
```json
{
    "type": "payment_confirmation",
    "confirmed": true,
    "amount": 5000,
    "parking_spot": 7
}
```

---

### 2단계: 모듈별 구현 체크리스트

#### ✅ 모듈 1: TCP/IP 소켓 수신기

**기능**: 클라이언트로부터 정산 요청 및 정산 확인 수신

**필수 구현 사항**:
- [ ] TCP/IP 서버 소켓 생성 (포트 9999)
- [ ] JSON 메시지 수신 및 파싱
- [ ] `type == 'pay'` 처리
- [ ] `type == 'payment_confirmation'` 처리

**예시 코드**:
```python
import socket
import json

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', 9999))
server_socket.listen(5)

while True:
    client_socket, addr = server_socket.accept()
    data = client_socket.recv(4096).decode('utf-8')
    json_data = json.loads(data)
    
    if json_data.get('type') == 'pay':
        parking_spot = json_data.get('parking_spot')
        # 정산 금액 계산 및 브로드캐스트
        handle_pay_request(parking_spot)
    
    elif json_data.get('type') == 'payment_confirmation':
        # 정산 확인 처리
        handle_payment_confirmation(json_data)
    
    client_socket.close()
```

---

#### ✅ 모듈 2: 정산 금액 계산

**기능**: 주차 시간 기반 정산 금액 계산

**필수 구현 사항**:
- [ ] 입차 시간 조회 (DB 또는 메모리)
- [ ] 주차 시간 계산 (입차 시간 ~ 현재 시간)
- [ ] 요금 체계 적용
- [ ] 특별 요금 적용 (장애인, 전기차 등)

**예시 코드**:
```python
def calculate_payment(parking_spot: int) -> int:
    # 1. 입차 시간 조회
    entry_time = get_entry_time(parking_spot)  # DB 조회 또는 메모리
    
    # 2. 주차 시간 계산
    current_time = datetime.now()
    duration = current_time - entry_time
    parking_minutes = duration.total_seconds() / 60
    
    # 3. 요금 체계 적용
    base_fee = 1000  # 기본 요금
    hourly_rate = 500  # 시간당 요금
    hours = int(parking_minutes / 60)
    amount = base_fee + (hours * hourly_rate)
    
    # 4. 특별 요금 적용
    if is_disabled_spot(parking_spot):
        amount *= 0.5  # 장애인 구역 50% 할인
    
    return amount
```

---

#### ✅ 모듈 3: ZeroMQ 브로드캐스트

**기능**: 정산 금액을 ZeroMQ로 브로드캐스트

**필수 구현 사항**:
- [ ] ZeroMQ Publisher 초기화
- [ ] `payment_data` 토픽으로 메시지 전송
- [ ] JSON 형식 준수

**예시 코드**:
```python
import zmq
from datetime import datetime

# ZeroMQ Publisher 초기화
zmq_context = zmq.Context()
zmq_publisher = zmq_context.socket(zmq.PUB)
zmq_publisher.bind("tcp://*:5555")

def broadcast_payment_amount(amount: int, parking_spot: int):
    payment_data = {
        "type": "payment",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "amount": amount,
            "parking_spot": parking_spot,
            "parking_duration_minutes": get_duration(parking_spot),
            "currency": "KRW"
        }
    }
    
    topic = "payment_data"
    message = json.dumps(payment_data, ensure_ascii=False)
    zmq_publisher.send_string(f"{topic} {message}")
```

---

### 3단계: 기존 서버에 통합하기

#### 방법 1: 독립 모듈로 추가

기존 서버 코드를 수정하지 않고, 새로운 모듈을 추가하는 방법:

```python
# payment_handler.py (새 파일 생성)
from payment_server_example import PaymentRequestHandler

# 기존 서버 코드에서 호출
payment_handler = PaymentRequestHandler(tcp_port=9999, zmq_port=5555)
payment_handler.run()  # 별도 스레드에서 실행 가능
```

#### 방법 2: 기존 소켓 핸들러에 통합

기존 서버의 소켓 핸들러가 있다면, 거기에 추가:

```python
# 기존 handle_client_request 함수에 추가
def handle_client_request(json_data):
    data_type = json_data.get('type')
    
    if data_type == 'pay':
        # 정산 요청 처리
        parking_spot = json_data.get('parking_spot')
        amount = calculate_payment(parking_spot)
        broadcast_payment_amount(amount, parking_spot)
    
    elif data_type == 'payment_confirmation':
        # 정산 확인 처리
        confirmed = json_data.get('confirmed')
        amount = json_data.get('amount')
        parking_spot = json_data.get('parking_spot')
        process_payment_confirmation(confirmed, amount, parking_spot)
    
    # ... 기존 다른 타입 처리
```

---

## 📝 구현 예시 파일

상세한 구현 예시는 다음 파일을 참고하세요:

- **`payment_server_example.py`**: 완전한 서버 구현 예시
- **`PAYMENT_API_SPEC.md`**: 상세한 API 명세서

---

## ⚠️ 주의사항

### 1. JSON 파싱 오류 처리
클라이언트가 보내는 JSON이 깨질 수 있으므로, try-except로 처리:

```python
try:
    json_data = json.loads(data)
except json.JSONDecodeError as e:
    print(f"❌ JSON 파싱 오류: {e}")
    continue
```

### 2. ZeroMQ 메시지 형식
ZeroMQ 메시지는 반드시 `"topic " + JSON_STRING` 형식이어야 합니다:

```python
# ✅ 올바른 형식
zmq_publisher.send_string(f"payment_data {json.dumps(payment_data)}")

# ❌ 잘못된 형식
zmq_publisher.send_string(json.dumps(payment_data))  # topic 누락
```

### 3. 타임스탬프 형식
타임스탬프는 ISO 8601 형식을 사용하세요:

```python
from datetime import datetime

timestamp = datetime.now().isoformat()  # "2025-01-15T10:30:45.123456"
```

---

## 🔧 테스트 방법

### 1. 예시 서버 실행
```bash
cd develop
python payment_server_example.py
```

### 2. 클라이언트 실행
```bash
# 터미널 1: 메인 컨트롤러
python main_controller.py

# 터미널 2: HUD 화면
python navigation_hud.py
```

### 3. 테스트 시나리오
1. HUD 화면에서 "출차 시작" 버튼 클릭
2. 서버 콘솔에서 정산 요청 수신 확인
3. HUD 화면에서 정산 금액 팝업 확인
4. YES/NO 선택 후 서버 콘솔에서 확인 결과 확인

---

## 📞 문의사항

구현 중 문제가 발생하면 다음을 확인하세요:

1. **포트 번호**: TCP/IP 9999, ZeroMQ 5555가 사용 가능한지 확인
2. **JSON 형식**: 클라이언트가 보내는 형식과 정확히 일치하는지 확인
3. **ZeroMQ 토픽**: `payment_data` 토픽으로 정확히 전송하는지 확인
4. **에러 로그**: 서버 콘솔에서 오류 메시지 확인

---

## ✅ 체크리스트

구현 완료 후 다음을 확인하세요:

- [ ] 정산 요청 수신 시 정산 금액 계산 완료
- [ ] 정산 금액이 ZeroMQ로 브로드캐스트됨
- [ ] HUD 화면에서 정산 금액이 표시됨
- [ ] 정산 확인 결과가 서버에 전달됨
- [ ] 에러 처리 (잘못된 주차 구역 번호 등)
- [ ] 로그 기록

---

**작성일**: 2025-01-15  
**버전**: 1.0  
**작성자**: ESW_2025 개발팀


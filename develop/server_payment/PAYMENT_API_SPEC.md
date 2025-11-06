# 주차 정산 API 명세서

## 개요
주차장 시스템에서 출차 시 정산 처리를 위한 API 명세서입니다. 
이 문서는 클라이언트(`navigation_hud.py`)와 서버 간의 통신 프로토콜을 정의합니다.

## 통신 흐름

```
[클라이언트]                          [서버]                          [클라이언트]
    |                                    |                                |
    | 1. 정산 요청 {'type': 'pay'}      |                                |
    |---------------------------------->|                                |
    |                                    |                                |
    | 2. 정산 금액 응답                |                                |
    |<----------------------------------|                                |
    |                                    |                                |
    | 3. 정산 확인 {'type': 'payment_confirmation'} |                     |
    |---------------------------------->|                                |
    |                                    |                                |
```

---

## 1. 정산 요청 (Pay Request)

### 클라이언트 → 서버

클라이언트가 "출차 시작" 버튼을 클릭하면 서버로 정산 요청을 전송합니다.

#### 전송 형식
```json
{
    "type": "pay",
    "parking_spot": 7
}
```

#### 필드 설명
| 필드명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| `type` | string | ✅ | 항상 `"pay"` |
| `parking_spot` | integer | ✅ | 주차 구역 번호 (1~11) |

#### 예시
```json
{
    "type": "pay",
    "parking_spot": 7
}
```

#### 전송 방식
- **프로토콜**: TCP/IP Socket
- **포트**: 9999 (기본값, `main_controller.py`의 `tcp_port`)
- **인코딩**: UTF-8
- **포맷**: JSON 문자열을 그대로 전송 (길이 프리픽스 없음)

#### Python 예시 코드
```python
import socket
import json

# 소켓 연결
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(('localhost', 9999))

# 정산 요청 전송
pay_command = {
    'type': 'pay',
    'parking_spot': 7
}
json_str = json.dumps(pay_command, ensure_ascii=False)
client_socket.sendall(json_str.encode('utf-8'))
client_socket.close()
```

---

## 2. 정산 금액 응답 (Payment Amount Response)

### 서버 → 클라이언트

서버는 정산 요청을 받으면 정산 금액을 계산하여 ZeroMQ를 통해 브로드캐스트합니다.

#### 응답 형식
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

#### 필드 설명
| 필드명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| `type` | string | ✅ | 항상 `"payment"` |
| `timestamp` | string | ✅ | ISO 8601 형식의 타임스탬프 |
| `data` | object | ✅ | 정산 데이터 객체 |
| `data.amount` | integer | ✅ | 정산 금액 (원 단위) |
| `data.parking_spot` | integer | ✅ | 주차 구역 번호 |
| `data.parking_duration_minutes` | integer | ⭕ | 주차 시간 (분), 선택 사항 |
| `data.currency` | string | ⭕ | 통화 코드, 기본값: "KRW" |

#### ZeroMQ 브로드캐스트 방식
- **프로토콜**: ZeroMQ PUB/SUB
- **포트**: 5555 (기본값, `main_controller.py`의 `zmq_port`)
- **토픽**: `payment_data`
- **메시지 형식**: `"payment_data " + JSON_STRING`

#### ZeroMQ 메시지 예시
```
payment_data {"type":"payment","timestamp":"2025-01-15T10:30:45.123456","data":{"amount":5000,"parking_spot":7}}
```

#### 서버 구현 가이드

서버에서 정산 요청을 받으면 다음과 같이 처리하세요:

```python
# 1. 정산 요청 수신 (예시)
def handle_pay_request(pay_data):
    parking_spot = pay_data.get('parking_spot')
    
    # 2. 정산 금액 계산 (실제 주차 시간, 요금 체계 등에 따라)
    amount = calculate_payment(parking_spot)
    
    # 3. ZeroMQ로 정산 금액 브로드캐스트
    payment_response = {
        "type": "payment",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "amount": amount,
            "parking_spot": parking_spot,
            "parking_duration_minutes": get_duration(parking_spot),
            "currency": "KRW"
        }
    }
    
    # ZeroMQ Publisher로 브로드캐스트
    # topic: "payment_data"
    # message: JSON 문자열
    zmq_publisher.send_string(f"payment_data {json.dumps(payment_response)}")
```

#### 에러 처리
서버에서 정산 금액을 계산할 수 없는 경우:

```json
{
    "type": "payment_error",
    "timestamp": "2025-01-15T10:30:45.123456",
    "data": {
        "error_code": "CALCULATION_FAILED",
        "error_message": "정산 금액 계산 실패",
        "parking_spot": 7
    }
}
```

---

## 3. 정산 확인 (Payment Confirmation)

### 클라이언트 → 서버

사용자가 정산 금액을 확인하고 YES/NO를 선택하면, 선택 결과를 서버로 전송합니다.

#### 전송 형식
```json
{
    "type": "payment_confirmation",
    "confirmed": true,
    "amount": 5000,
    "parking_spot": 7
}
```

#### 필드 설명
| 필드명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| `type` | string | ✅ | 항상 `"payment_confirmation"` |
| `confirmed` | boolean | ✅ | 정산 확인 여부 (`true`: YES, `false`: NO) |
| `amount` | integer | ✅ | 정산 금액 (서버로부터 받은 금액) |
| `parking_spot` | integer | ✅ | 주차 구역 번호 |

#### 예시

**YES 선택 시:**
```json
{
    "type": "payment_confirmation",
    "confirmed": true,
    "amount": 5000,
    "parking_spot": 7
}
```

**NO 선택 시:**
```json
{
    "type": "payment_confirmation",
    "confirmed": false,
    "amount": 5000,
    "parking_spot": 7
}
```

#### 전송 방식
- **프로토콜**: TCP/IP Socket
- **포트**: 9999
- **인코딩**: UTF-8
- **포맷**: JSON 문자열을 그대로 전송

#### Python 예시 코드
```python
import socket
import json

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(('localhost', 9999))

payment_result = {
    'type': 'payment_confirmation',
    'confirmed': True,  # 또는 False
    'amount': 5000,
    'parking_spot': 7
}

json_str = json.dumps(payment_result, ensure_ascii=False)
client_socket.sendall(json_str.encode('utf-8'))
client_socket.close()
```

---

## 4. 서버 측 구현 체크리스트

### 모듈형 구현 가이드

서버 측에서 정산 기능을 추가할 때 다음 체크리스트를 따르세요:

#### ✅ 1. 정산 요청 수신 모듈
- [ ] TCP/IP 소켓에서 `{'type': 'pay', 'parking_spot': ...}` 수신
- [ ] `type`이 `"pay"`인지 확인
- [ ] `parking_spot` 값 유효성 검사 (1~11)

#### ✅ 2. 정산 금액 계산 모듈
- [ ] 주차 시간 계산 (입차 시간 ~ 현재 시간)
- [ ] 요금 체계 적용 (시간당 요금, 기본 요금 등)
- [ ] 특별 요금 적용 (장애인 구역, 전기차 구역 등)

#### ✅ 3. ZeroMQ 브로드캐스트 모듈
- [ ] ZeroMQ Publisher 초기화
- [ ] `payment_data` 토픽으로 정산 금액 브로드캐스트
- [ ] JSON 형식 준수 (`{"type": "payment", "timestamp": ..., "data": {...}}`)

#### ✅ 4. 정산 확인 수신 모듈
- [ ] TCP/IP 소켓에서 `{'type': 'payment_confirmation', ...}` 수신
- [ ] `confirmed` 값에 따른 후속 처리 (결제 처리, 출차 승인 등)
- [ ] 에러 처리 (취소 시 처리 등)

#### ✅ 5. 에러 처리
- [ ] 정산 금액 계산 실패 시 에러 응답
- [ ] 잘못된 주차 구역 번호 처리
- [ ] 네트워크 오류 처리

---

## 5. 통합 테스트 시나리오

### 정상 시나리오
1. 클라이언트: `{'type': 'pay', 'parking_spot': 7}` 전송
2. 서버: 정산 금액 계산 및 ZeroMQ 브로드캐스트
3. 클라이언트: 정산 금액 수신 및 사용자 확인
4. 클라이언트: `{'type': 'payment_confirmation', 'confirmed': true, ...}` 전송
5. 서버: 정산 확인 처리 및 출차 승인

### 취소 시나리오
1. 클라이언트: `{'type': 'pay', 'parking_spot': 7}` 전송
2. 서버: 정산 금액 계산 및 ZeroMQ 브로드캐스트
3. 클라이언트: 정산 금액 수신 및 사용자 확인
4. 클라이언트: `{'type': 'payment_confirmation', 'confirmed': false, ...}` 전송
5. 서버: 정산 취소 처리

---

## 6. 현재 구현 상태

### 클라이언트 측 (`navigation_hud.py`, `main_controller.py`)
✅ 정산 요청 전송 (`type: 'pay'`)  
✅ 정산 금액 수신 (ZeroMQ `payment_data` 토픽)  
✅ 정산 확인 팝업 표시  
✅ 정산 확인 결과 전송 (`type: 'payment_confirmation'`)  

### 서버 측
⚠️ **구현 필요**  
- [ ] 정산 요청 수신 및 처리
- [ ] 정산 금액 계산
- [ ] ZeroMQ 브로드캐스트 (`payment_data` 토픽)
- [ ] 정산 확인 결과 수신 및 처리

### 현재 시뮬레이션
`main_controller.py`에서 정산 금액을 시뮬레이션하고 있습니다:
- 정산 금액: 5000원 (고정값)
- 실제 서버와 연동 시 TODO 주석 부분 수정 필요

---

## 7. FAQ

### Q1. ZeroMQ Publisher는 어떻게 설정하나요?
```python
import zmq

context = zmq.Context()
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5555")
```

### Q2. 정산 금액은 어떤 기준으로 계산하나요?
- 주차 시간: 입차 시간 ~ 현재 시간
- 요금 체계: 기본 요금 + 시간당 요금
- 특별 요금: 장애인 구역, 전기차 구역 등

### Q3. 에러가 발생하면 어떻게 하나요?
정산 금액 계산 실패 시 `payment_error` 타입으로 응답하거나, 
클라이언트에서 타임아웃 처리됩니다.

---

## 8. 연락처 및 참고 자료

### 관련 파일
- 클라이언트: `develop/navigation_hud.py` (정산 요청/확인 전송)
- 중간 서버: `develop/main_controller.py` (정산 요청/확인 수신, ZeroMQ 브로드캐스트)
- API 명세서: `develop/PAYMENT_API_SPEC.md` (이 파일)

### 통신 프로토콜
- TCP/IP: 포트 9999 (정산 요청/확인)
- ZeroMQ: 포트 5555 (정산 금액 브로드캐스트)

---

**작성일**: 2025-01-15  
**버전**: 1.0  
**작성자**: ESW_2025 개발팀


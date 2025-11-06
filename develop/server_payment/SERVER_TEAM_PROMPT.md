# 서버 팀원을 위한 정산 기능 추가 요청

## 📧 전달 메시지 템플릿

---

안녕하세요, 서버 팀원분들!

주차 정산 기능을 서버에 추가해야 합니다. 클라이언트 측은 이미 구현 완료되어 있으며, 서버 측에서 **3가지 핵심 기능**만 구현하면 됩니다.

## 🎯 구현해야 할 기능

1. **정산 요청 수신**: 클라이언트로부터 `{'type': 'pay', 'parking_spot': 7}` 형태의 JSON 수신
2. **정산 금액 계산**: 주차 시간 기반으로 정산 금액 계산
3. **정산 금액 브로드캐스트**: ZeroMQ로 정산 금액 전송
4. **정산 확인 수신**: 클라이언트로부터 `{'type': 'payment_confirmation', ...}` 수신

## 📡 통신 방식

- **TCP/IP 소켓** (포트 9999): 정산 요청/확인 수신
- **ZeroMQ PUB/SUB** (포트 5555): 정산 금액 브로드캐스트

## 📋 JSON 데이터 형식

### 정산 요청 (클라이언트 → 서버)
```json
{
    "type": "pay",
    "parking_spot": 7
}
```

### 정산 금액 응답 (서버 → 클라이언트, ZeroMQ)
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

### 정산 확인 (클라이언트 → 서버)
```json
{
    "type": "payment_confirmation",
    "confirmed": true,
    "amount": 5000,
    "parking_spot": 7
}
```

## 📚 참고 자료

다음 파일들을 참고해주세요:

1. **`SERVER_INTEGRATION_GUIDE.md`**: 실전 통합 가이드 (우선 참고)
2. **`PAYMENT_API_SPEC.md`**: 상세한 API 명세서
3. **`payment_server_example.py`**: 완전한 구현 예시 코드

## ⚙️ 빠른 통합 방법

기존 서버 코드를 최소한으로 수정하여 통합할 수 있습니다:

### 방법 1: 독립 모듈 추가 (권장)
```python
from payment_server_example import PaymentRequestHandler

payment_handler = PaymentRequestHandler(tcp_port=9999, zmq_port=5555)
payment_handler.run()  # 별도 스레드에서 실행
```

### 방법 2: 기존 핸들러에 추가
기존 소켓 핸들러에 다음 코드만 추가:
```python
if json_data.get('type') == 'pay':
    parking_spot = json_data.get('parking_spot')
    amount = calculate_payment(parking_spot)
    broadcast_payment_amount(amount, parking_spot)
```

## 🔍 핵심 구현 포인트

1. **정산 금액 계산 함수**: 주차 시간 기반 요금 계산 (기존 요금 체계 활용)
2. **ZeroMQ Publisher**: `payment_data` 토픽으로 JSON 브로드캐스트
3. **에러 처리**: 잘못된 주차 구역 번호, 계산 실패 등

## 📞 문의사항

구현 중 문제가 있으면 알려주세요!

---

**작성일**: 2025-01-15  
**관련 파일 위치**: `develop/` 폴더


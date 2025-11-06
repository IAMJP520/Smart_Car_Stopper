# 주차 정산 기능 문서 인덱스

## 📚 문서 목록

서버 팀원이 정산 기능을 구현하기 위해 필요한 모든 문서입니다.

### 1. 🚀 빠른 시작 (우선 읽기)
**`SERVER_INTEGRATION_GUIDE.md`**
- 실전 통합 가이드
- 모듈별 체크리스트
- 구현 예시 코드
- 테스트 방법

### 2. 📖 상세 명세서
**`PAYMENT_API_SPEC.md`**
- 완전한 API 명세서
- JSON 데이터 형식 상세 설명
- 통신 프로토콜 정의
- 에러 처리 방법

### 3. 💻 구현 예시 코드
**`payment_server_example.py`**
- 완전한 서버 구현 예시
- 모듈별 구현 패턴
- 직접 실행 가능한 코드

### 4. 📧 서버 팀원용 프롬프트
**`SERVER_TEAM_PROMPT.md`**
- 서버 팀원에게 전달할 요청 메시지
- 핵심 요약 정보
- 빠른 참조용

---

## 🎯 구현 순서 (추천)

1. **`SERVER_INTEGRATION_GUIDE.md`** 읽기 (10분)
2. **`payment_server_example.py`** 실행 및 테스트 (5분)
3. 기존 서버 코드에 통합 (30분 ~ 1시간)
4. **`PAYMENT_API_SPEC.md`** 참고하여 상세 구현 (필요 시)

---

## 📡 핵심 통신 프로토콜 요약

### TCP/IP (포트 9999)
- **정산 요청**: `{'type': 'pay', 'parking_spot': 7}`
- **정산 확인**: `{'type': 'payment_confirmation', 'confirmed': true, 'amount': 5000, 'parking_spot': 7}`

### ZeroMQ (포트 5555)
- **정산 금액 브로드캐스트**: `{"type": "payment", "timestamp": "...", "data": {"amount": 5000, ...}}`
- **토픽**: `payment_data`

---

## ✅ 구현 체크리스트

- [ ] 정산 요청 수신 모듈 구현
- [ ] 정산 금액 계산 함수 구현
- [ ] ZeroMQ Publisher 초기화 및 브로드캐스트
- [ ] 정산 확인 수신 및 처리
- [ ] 에러 처리 (잘못된 입력 등)
- [ ] 테스트 완료

---

## 🔧 빠른 테스트

```bash
# 1. 예시 서버 실행
python payment_server_example.py

# 2. 클라이언트 실행 (다른 터미널)
python main_controller.py
python navigation_hud.py
```

---

## 📞 문의

구현 중 문제가 발생하면 다음을 확인하세요:
1. 포트 번호 (TCP/IP 9999, ZeroMQ 5555)
2. JSON 형식 일치 여부
3. ZeroMQ 토픽 이름 (`payment_data`)
4. 서버 콘솔 에러 로그

---

**작성일**: 2025-01-15  
**버전**: 1.0


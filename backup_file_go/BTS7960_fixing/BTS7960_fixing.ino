/*
 * 2륜 구동 로봇 PID 위치 제어 (쿼드러처 ×1 디코딩, BTS7960)
 * - Arduino Mega 2560
 * - 17PPR 엔코더, 1체배 (RISING edge)
 * - 감속비 1:200
 * - 시리얼 명령어: "전진 시작" / "후진 시작"
 */

#include <Arduino.h>

// ======== 로봇 파라미터 (mm 단위) ========
const float PPR                    = 95.0;       // 엔코더 PPR
const float GEAR_RATIO             = 200.0;      // 감속비
const float ENCODER_DECODER_FACTOR = 1.0;        // 1× 디코딩
const float WHEEL_DIAMETER_MM      = 72.0;       // 바퀴 직경 (mm)
const float WHEEL_CIRCUMFERENCE_MM = WHEEL_DIAMETER_MM * PI;
const float PULSES_PER_MM = (PPR * GEAR_RATIO * ENCODER_DECODER_FACTOR)
                           / WHEEL_CIRCUMFERENCE_MM;

// ======== BTS7960 핀 정의 ========
const int L_REN          = 11;
const int L_LEN          = 10;
const int L_RPWM         = 13;
const int L_LPWM         = 12;
const int R_REN          = 7;
const int R_LEN          = 6;
const int R_RPWM         = 9;
const int R_LPWM         = 8;

// ======== 엔코더 핀 정의 ========
const int LEFT_ENCODER_A  = 18;
const int LEFT_ENCODER_B  = 19;
const int RIGHT_ENCODER_A = 20;
const int RIGHT_ENCODER_B = 21;

// ======== 전역 상태 변수 ========
volatile long leftCount     = 0;
volatile long rightCount    = 0;
volatile long leftTarget    = 0;
volatile long rightTarget   = 0;

bool    isMoving  = false;
bool    isForward = true;

int     leftPWM   = 0;
int     rightPWM  = 0;
long    moveDistanceMM = 1000;   // 기본 이동 거리 (mm)

// ======== PID 제어 변수 ========
const unsigned long CONTROL_INTERVAL = 10;   // ms
float   Kp = 0.05, Ki = 0.0, Kd = 0.0;
long    leftPrevError   = 0;
long    rightPrevError  = 0;
long    leftIntegral    = 0;
long    rightIntegral   = 0;

// ======== 시리얼 입력 관련 ========
String  inputString    = "";
bool    stringComplete = false;

// ======== 타이밍 ========
unsigned long prevTime   = 0;
unsigned long prevPrint  = 0;
const unsigned long PRINT_INTERVAL = 100;    // ms

// ======== 함수 선언 ========
void startMoving(bool forward);
void updatePID();
void stopMotors();
void leftEncoderISR();
void rightEncoderISR();
void serialEvent();

void setup() {
  Serial.begin(115200);

  // ▶️ BTS7960: Enable 핀 모두 활성화 (HIGH)
  pinMode(L_REN, OUTPUT);  digitalWrite(L_REN, HIGH);
  pinMode(L_LEN, OUTPUT);  digitalWrite(L_LEN, HIGH);
  pinMode(R_REN, OUTPUT);  digitalWrite(R_REN, HIGH);
  pinMode(R_LEN, OUTPUT);  digitalWrite(R_LEN, HIGH);

  // ▶️ PWM 핀 초기화
  pinMode(L_RPWM, OUTPUT); analogWrite(L_RPWM, 0);
  pinMode(L_LPWM, OUTPUT); analogWrite(L_LPWM, 0);
  pinMode(R_RPWM, OUTPUT); analogWrite(R_RPWM, 0);
  pinMode(R_LPWM, OUTPUT); analogWrite(R_LPWM, 0);

  // ▶️ 엔코더 핀
  pinMode(LEFT_ENCODER_A,  INPUT_PULLUP);
  pinMode(LEFT_ENCODER_B,  INPUT_PULLUP);
  pinMode(RIGHT_ENCODER_A, INPUT_PULLUP);
  pinMode(RIGHT_ENCODER_B, INPUT_PULLUP);

  // ▶️ Rising edge 인터럽트만 걸어 펄스 부하 최소화
  attachInterrupt(digitalPinToInterrupt(LEFT_ENCODER_A),
                  leftEncoderISR,  RISING);
  attachInterrupt(digitalPinToInterrupt(RIGHT_ENCODER_A),
                  rightEncoderISR, RISING);

  Serial.println("=== 2륜 로봇 PID 위치 제어 ===");
  Serial.println("명령어: 전진 시작 / 후진 시작");
  prevTime  = millis();
  prevPrint = millis();
}

void loop() {
  unsigned long now = millis();

  // — PID 주기마다 제어
  if (now - prevTime >= CONTROL_INTERVAL) {
    if (isMoving) {
      updatePID();
      // 목표 도달 ±50펄스 허용
      if (abs(leftTarget - leftCount)  < 50 ||
          abs(rightTarget - rightCount) < 50) {
        stopMotors();
        isMoving = false;
        Serial.println(">> 목표 위치 도달");
      }
    }
    prevTime = now;
  }

  // — 디버깅 출력 (100ms 간격)
  if (now - prevPrint >= PRINT_INTERVAL) {
    if (isMoving) {
      Serial.print("Lcnt=");  Serial.print(leftCount);
      Serial.print("  Rcnt="); Serial.print(rightCount);
      Serial.print("  LPWM="); Serial.print(leftPWM);
      Serial.print("  RPWM="); Serial.println(rightPWM);
    }
    prevPrint = now;
  }

  // — 시리얼 명령 처리
  if (stringComplete) {
    if (inputString.indexOf("전진 시작") >= 0) {
      startMoving(true);
      Serial.println(">> 전진 시작");
    }
    else if (inputString.indexOf("후진 시작") >= 0) {
      startMoving(false);
      Serial.println(">> 후진 시작");
    }
    inputString    = "";
    stringComplete = false;
  }
}

// — 시리얼 한 줄 입력 시 호출
void serialEvent() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    inputString += c;
    if (c == '\n') {
      stringComplete = true;
    }
  }
}

// — 이동 시작
void startMoving(bool forward) {
  isForward = forward;
  long pulses = (long)(moveDistanceMM * PULSES_PER_MM);

  // 카운트 리셋
  noInterrupts();
  leftCount  = 0;
  rightCount = 0;
  interrupts();

  // 목표 설정
  if (forward) {
    leftTarget  =  pulses;
    rightTarget =  pulses;
  } else {
    leftTarget  = -pulses;
    rightTarget = -pulses;
  }

  // PID 초기화
  leftPrevError  = 0;
  rightPrevError = 0;
  leftIntegral   = 0;
  rightIntegral  = 0;
  isMoving       = true;

  // PWM 초기화
  analogWrite(L_RPWM, 0);  analogWrite(L_LPWM, 0);
  analogWrite(R_RPWM, 0);  analogWrite(R_LPWM, 0);
}

// — PID 제어 업데이트
void updatePID() {
  long errL = leftTarget  - leftCount;
  long errR = rightTarget - rightCount;

  // Integral with windup guard
  leftIntegral  += errL * CONTROL_INTERVAL;
  rightIntegral += errR * CONTROL_INTERVAL;
  leftIntegral  = constrain(leftIntegral,  -1000, 1000);
  rightIntegral = constrain(rightIntegral, -1000, 1000);

  // Derivative
  long dL = (errL - leftPrevError)  / CONTROL_INTERVAL;
  long dR = (errR - rightPrevError) / CONTROL_INTERVAL;

  // PID 계산
  float outL = Kp*errL + Ki*leftIntegral + Kd*dL;
  float outR = Kp*errR + Ki*rightIntegral + Kd*dR;
  leftPWM     = constrain((int)outL,  0, 255);
  rightPWM    = constrain((int)outR,  0, 255);

  // PWM 출력 (한 방향만)
  if (isForward) {
    analogWrite(L_LPWM, 0);
    analogWrite(L_RPWM, leftPWM);
    analogWrite(R_LPWM, 0);
    analogWrite(R_RPWM, rightPWM);
  } else {
    analogWrite(L_RPWM, 0);
    analogWrite(L_LPWM, leftPWM);
    analogWrite(R_RPWM, 0);
    analogWrite(R_LPWM, rightPWM);
  }

  leftPrevError  = errL;
  rightPrevError = errR;
}

// — 모터 정지
void stopMotors() {
  analogWrite(L_RPWM, 0);
  analogWrite(L_LPWM, 0);
  analogWrite(R_RPWM, 0);
  analogWrite(R_LPWM, 0);
}

// — 왼쪽 엔코더 A상 Rising ISR
void leftEncoderISR() {
  // B상이 LOW이면 +1, HIGH이면 -1
  leftCount += (digitalRead(LEFT_ENCODER_B) == LOW) ? +1 : -1;
}

// — 오른쪽 엔코더 A상 Rising ISR
void rightEncoderISR() {
  rightCount += (digitalRead(RIGHT_ENCODER_B) == LOW) ? +1 : -1;
}

// ================================================================
//   입출차 차단기 ESP32 코드 (V4.6.4 - 광고 타임아웃 로직)
//
// - [핵심] 차량이 근접하면 광고를 시작하고, 2초 이상 멀어지면
//          광고를 자동으로 중단하는 타임아웃 기능 추가.
// - [수정] 광고 타임아웃 관리를 위한 전역 변수 추가.
// ================================================================

// ========================[ 기능 활성화 스위치 ]========================
#define USE_MICRO_ROS
// =================================================================

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

#ifdef USE_MICRO_ROS
#include <micro_ros_arduino.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <std_msgs/msg/string.h>

#define RCCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){error_loop();}}
#define RCSOFTCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){}}
#endif

// --- 하드웨어 핀 설정 ---
#define ENTRY_BARRIER_GPIO 17
#define EXIT_BARRIER_GPIO 19
#define SERVO_CLOSED_ANGLE 0
#define SERVO_OPEN_ANGLE 90
#define LED_BUILTIN 2

#define ENTRY_ULTRASONIC_TRIG_PIN 22
#define ENTRY_ULTRASONIC_ECHO_PIN 23
#define EXIT_ULTRASONIC_TRIG_PIN  25
#define EXIT_ULTRASONIC_ECHO_PIN  26

// --- 설정값 ---
const unsigned long SENSOR_STABILIZATION_DELAY = 500;
const float VEHICLE_PASSED_DISTANCE = 50.0;
const float VEHICLE_APPROACH_DISTANCE = 50.0;
const int SERVO_SPEED_DELAY = 15;
const unsigned long ADVERTISING_TIMEOUT = 2000; // [추가] 광고 중단 타임아웃 (ms)

// --- BLE 설정 ---
#define DEVICE_NAME "ParkingBarrier_System"
#define SERVICE_UUID "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define PC_SERVICE_UUID        "a2b8915e-993a-4f21-91a6-575355a2c4e7"
#define PC_CHARACTERISTIC_UUID "a2b8915e-993a-4f21-91a6-575355a2c4e8"
#define ROS_STATUS_UUID        "a2b8915e-993a-4f21-91a6-575355a2c4e9"
#define LOG_UUID               "a2b8915e-993a-4f21-91a6-575355a2c4ea"

// --- BLE 명령어 정의 ---
#define CMD_READY_SIGNAL 0x01
#define CMD_ENTRY_INFO 0x10
#define CMD_INFO_REQUEST 0x15
#define CMD_EXIT_INFO 0x16

#ifdef USE_MICRO_ROS
rcl_allocator_t allocator;
rclc_support_t support;
rcl_node_t node;
rclc_executor_t executor;
rcl_publisher_t auth_req_pub, exit_req_pub, barrier_event_pub;
rcl_subscription_t barrier_control_sub;
std_msgs__msg__String auth_req_msg, exit_req_msg, barrier_event_msg, barrier_control_msg;
char msg_buffer[512];
char recv_buffer[256];
#endif

// --- 전역 객체 및 변수 선언 ---
BLEServer* pServer = nullptr;
BLECharacteristic* pCharacteristic = nullptr;
BLECharacteristic* pPCCharacteristic = nullptr;
BLECharacteristic* pRosStatusCharacteristic = nullptr;
BLECharacteristic* pLogCharacteristic = nullptr;
Servo entryServo;
Servo exitServo;

volatile int entryServoTargetAngle = SERVO_CLOSED_ANGLE;
volatile int exitServoTargetAngle = SERVO_CLOSED_ANGLE;

volatile bool entryGateOpenRequest = false;
volatile bool exitGateOpenRequest = false;

bool led_timer_active = false;
unsigned long led_timer_start_time = 0;
const unsigned long led_on_duration = 3000;

bool pcClientConnected = false;
bool isVehicleConnected = false;
bool isAdvertising = false;
uint16_t currentVehicleConnId = 0;
uint16_t lastConnectedConnId = 0;
unsigned long vehicleLastFarTime = 0; // [추가] 차량이 멀어진 시간 기록

String currentState = "BOOTING";
enum GateContext { CONTEXT_NONE, CONTEXT_ENTRY, CONTEXT_EXIT };
GateContext currentGateContext = CONTEXT_NONE;

bool entryBarrierIsOpen = false;
bool exitBarrierIsOpen = false;
unsigned long barrierLastOpenedTime = 0;

bool shouldDisconnectVehicle = false;

struct VehicleInfo {
  String vehicleId = "", type = "", disabledType = "", preferred = "", guiMac = "";
  uint8_t tagId = 0, destination = 0;
} currentVehicle;

volatile bool entryVehiclePassed = false;
volatile bool exitVehiclePassed = false;

struct SensorState {
  bool vehicleUnderSensor = false;
  unsigned long vehicleLeftTime = 0;
  unsigned long lastMeasureTime = 0;
};
SensorState entrySensorState;
SensorState exitSensorState;

// --- 함수 미리 선언 ---
void log_message(const char* format, ...);
void print_packet(const char* direction, const uint8_t* data, size_t len);
void updateState(String newState);
void controlBarrier(const char* barrier, const char* action);
void requestVehicleDisconnect();
void sendPacketToVehicle(uint8_t cmd, uint8_t* data, uint8_t len);
float measureDistance(uint8_t trigPin, uint8_t echoPin);
void publishBarrierClosed(const char* barrierType);
bool detectVehiclePassage(uint8_t trigPin, uint8_t echoPin, SensorState& state);

#ifdef USE_MICRO_ROS
void error_loop();
void initMicroROS();
void publishEntryRequest(const VehicleInfo& vehicle);
void publishExitRequest(uint8_t tagId);
void publishBarrierEvent(const char* gate, const char* state);
void barrier_control_callback(const void * msgin);
#endif

void servoTask(void *pvParameters) {
    log_message("   -> Servo control task started on Core 1.\n");
    int currentEntryAngle = SERVO_CLOSED_ANGLE;
    int currentExitAngle = SERVO_CLOSED_ANGLE;
    for (;;) {
        if (currentEntryAngle != entryServoTargetAngle) {
            currentEntryAngle += (entryServoTargetAngle > currentEntryAngle) ? 1 : -1;
            entryServo.write(currentEntryAngle);
        }
        if (currentExitAngle != exitServoTargetAngle) {
            currentExitAngle += (exitServoTargetAngle > currentExitAngle) ? 1 : -1;
            exitServo.write(currentExitAngle);
        }
        vTaskDelay(pdMS_TO_TICKS(SERVO_SPEED_DELAY));
    }
}

void ultrasonicTask(void *pvParameters) {
  log_message("   -> Ultrasonic sensor task started on Core 0.\n");
  for (;;) {
    if (entryBarrierIsOpen && !entryVehiclePassed) {
      if (detectVehiclePassage(ENTRY_ULTRASONIC_TRIG_PIN, ENTRY_ULTRASONIC_ECHO_PIN, entrySensorState)) {
        entryVehiclePassed = true;
      }
    }
    if (exitBarrierIsOpen && !exitVehiclePassed) {
      if (detectVehiclePassage(EXIT_ULTRASONIC_TRIG_PIN, EXIT_ULTRASONIC_ECHO_PIN, exitSensorState)) {
        exitVehiclePassed = true;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// --- BLE 콜백 클래스 정의 ---
class MyServerCallbacks: public BLEServerCallbacks {
  void onConnect(BLEServer* pServer, esp_ble_gatts_cb_param_t* param) {
    log_message("\n>> BLE Client Connected (Conn ID: %d)\n", param->connect.conn_id);
    lastConnectedConnId = param->connect.conn_id;
    isAdvertising = false;
  }
  void onDisconnect(BLEServer* pServer) {
    log_message("\n>> A BLE Client Disconnected.\n");
    if (isVehicleConnected) {
      isVehicleConnected = false;
      currentVehicle = VehicleInfo();
      currentGateContext = CONTEXT_NONE;
      updateState("IDLE");
      log_message("   -> Vehicle connection state has been reset.\n");
    }
    if (pcClientConnected) {
      pcClientConnected = false;
      log_message("   -> PC debugger connection state has been reset.\n");
    }
  }
};

class VehicleCharacteristicCallbacks: public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *pCharacteristic) {
    if (!isVehicleConnected) {
      isVehicleConnected = true;
      currentVehicleConnId = lastConnectedConnId;
      updateState("VEHICLE_CONNECTED");
      log_message("   -> Vehicle connection confirmed (Conn ID: %d).\n", currentVehicleConnId);
    }
    String value = pCharacteristic->getValue();
    size_t len = value.length();
    const uint8_t* data = (const uint8_t*)value.c_str();

    if (len > 0) {
      print_packet("[RECV_VEHICLE_BLE]", data, len);
      uint8_t cmd = data[1];

      if (cmd == CMD_ENTRY_INFO) {
        currentGateContext = CONTEXT_ENTRY;
        updateState("ENTRY_INFO_RECEIVED");
        char* vehicleId = (char*)&data[3];
        int vehicleIdLen = strlen(vehicleId);
        currentVehicle.vehicleId = String(vehicleId);
        currentVehicle.tagId = data[3 + vehicleIdLen + 1];
        uint8_t vehicleType = data[3 + vehicleIdLen + 2];
        uint8_t disabledType = data[3 + vehicleIdLen + 3];
        uint8_t preferred = data[3 + vehicleIdLen + 4];
        currentVehicle.destination = data[3 + vehicleIdLen + 5];

        currentVehicle.type = (vehicleType == 0x01) ? "electric" : "regular";
        currentVehicle.disabledType = (disabledType == 0x01) ? "disabled" : "normal";
        if (preferred == 1) currentVehicle.preferred = "disabled";
        else if (preferred == 2) currentVehicle.preferred = "elec";
        else currentVehicle.preferred = "normal";

        log_message("   -> [Entry] Parsed: ID=%s, Tag=%d, Dest=%d\n",
                    currentVehicle.vehicleId.c_str(), currentVehicle.tagId, currentVehicle.destination);
        #ifdef USE_MICRO_ROS
          publishEntryRequest(currentVehicle);
        #endif
        requestVehicleDisconnect();
      }
      else if (cmd == CMD_EXIT_INFO) {
        currentGateContext = CONTEXT_EXIT;
        updateState("EXIT_INFO_RECEIVED");
        char* vehicleId = (char*)&data[3];
        int vehicleIdLen = strlen(vehicleId);
        currentVehicle.vehicleId = String(vehicleId);
        currentVehicle.tagId = data[3 + vehicleIdLen + 1];

        log_message("   -> [Exit] Parsed: ID=%s, Tag=%d\n",
                    currentVehicle.vehicleId.c_str(), currentVehicle.tagId);
        #ifdef USE_MICRO_ROS
          publishExitRequest(currentVehicle.tagId);
        #endif
        requestVehicleDisconnect();
      }
      else if (cmd == CMD_READY_SIGNAL) {
        currentGateContext = CONTEXT_ENTRY;
        updateState("READY_RECEIVED");
        log_message("   -> [Entry] Vehicle Ready Signal. Requesting info.\n");
        sendPacketToVehicle(CMD_INFO_REQUEST, nullptr, 0);
      }
    }
  }
};

class PCCharacteristicCallbacks: public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *pCharacteristic) {
    if (!pcClientConnected) {
      pcClientConnected = true;
      log_message("\n>> PC Debugger Confirmed via Write event.\n");
    }
    String value = pCharacteristic->getValue().c_str();
    if (value.length() > 0) {
      log_message("   -> PC Command received: %s\n", value.c_str());
      if (value == "entry_open") controlBarrier("entry", "open");
      else if (value == "entry_close") controlBarrier("entry", "close");
      else if (value == "exit_open") controlBarrier("exit", "open");
      else if (value == "exit_close") controlBarrier("exit", "close");
    }
  }
};

#ifdef USE_MICRO_ROS
void error_loop() {
  while(1) {
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    delay(100);
  }
}
#endif

// --- 기본 실행 함수 ---
void setup() {
  Serial.begin(115200);
  log_message("\n\n===== System Booting... (V4.6.4 - Advertising Timeout) =====\n");
  updateState("INITIALIZING");

  log_message("   -> Attaching servos...\n");
  entryServo.attach(ENTRY_BARRIER_GPIO);
  exitServo.attach(EXIT_BARRIER_GPIO);
  entryServo.write(SERVO_CLOSED_ANGLE);
  exitServo.write(SERVO_CLOSED_ANGLE);

  log_message("   -> Initializing GPIO...\n");
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  pinMode(ENTRY_ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(ENTRY_ULTRASONIC_ECHO_PIN, INPUT);
  pinMode(EXIT_ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(EXIT_ULTRASONIC_ECHO_PIN, INPUT);

  log_message("   -> Initializing BLE...\n");
  BLEDevice::init(DEVICE_NAME);
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  log_message("   -> Creating BLE Services...\n");
  BLEService* pVehicleService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pVehicleService->createCharacteristic(
                      CHARACTERISTIC_UUID,
                      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_NOTIFY
                    );
  pCharacteristic->setCallbacks(new VehicleCharacteristicCallbacks());
  pCharacteristic->addDescriptor(new BLE2902());
  pVehicleService->start();

  BLEService* pPCService = pServer->createService(PC_SERVICE_UUID);
  pPCCharacteristic = pPCService->createCharacteristic(
                        PC_CHARACTERISTIC_UUID,
                        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_READ
                      );
  pPCCharacteristic->setCallbacks(new PCCharacteristicCallbacks());

  pRosStatusCharacteristic = pPCService->createCharacteristic(
                                ROS_STATUS_UUID,
                                BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
                              );
  pRosStatusCharacteristic->setValue("1");

  pLogCharacteristic = pPCService->createCharacteristic(
                         LOG_UUID,
                         BLECharacteristic::PROPERTY_NOTIFY
                       );
  pLogCharacteristic->addDescriptor(new BLE2902());
  pPCService->start();

  #ifdef USE_MICRO_ROS
  log_message("   -> Initializing Micro-ROS...\n");
  initMicroROS();
  #endif

  xTaskCreatePinnedToCore(servoTask, "ServoTask", 2048, NULL, 1, NULL, 1);
  xTaskCreatePinnedToCore(ultrasonicTask, "UltrasonicTask", 4096, NULL, 1, NULL, 0);

  updateState("IDLE");
  BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->addServiceUUID(PC_SERVICE_UUID);
}

void loop() {
  #ifdef USE_MICRO_ROS
  RCSOFTCHECK(rclc_executor_spin_some(&executor, RCL_MS_TO_NS(10)));
  #endif

  // [핵심 수정] 광고 시작 및 중단(타임아웃) 로직
  if (!isVehicleConnected) {
    bool isVehicleClose = (measureDistance(ENTRY_ULTRASONIC_TRIG_PIN, ENTRY_ULTRASONIC_ECHO_PIN) < VEHICLE_APPROACH_DISTANCE ||
                           measureDistance(EXIT_ULTRASONIC_TRIG_PIN, EXIT_ULTRASONIC_ECHO_PIN) < VEHICLE_APPROACH_DISTANCE);

    if (isVehicleClose) {
      if (!isAdvertising) {
        log_message("   -> Vehicle detected nearby. Starting BLE advertising...\n");
        updateState("ADVERTISING");
        BLEDevice::getAdvertising()->start();
        isAdvertising = true;
      }
      vehicleLastFarTime = 0; // 차량이 가까우므로 타이머 리셋
    } else { // 차량이 멀리 있을 때
      if (isAdvertising) {
        if (vehicleLastFarTime == 0) {
          vehicleLastFarTime = millis(); // 타이머 시작
        } else if (millis() - vehicleLastFarTime > ADVERTISING_TIMEOUT) {
          log_message("   -> Vehicle has been away for >2s. Stopping BLE advertising...\n");
          updateState("IDLE");
          BLEDevice::getAdvertising()->stop();
          isAdvertising = false;
          vehicleLastFarTime = 0; // 타이머 리셋
        }
      }
    }
  }

  if (entryGateOpenRequest) {
    log_message("   -> Entry gate open authorized. Opening barrier immediately.\n");
    controlBarrier("entry", "open");
    entryGateOpenRequest = false;
  }

  if (exitGateOpenRequest) {
    log_message("   -> Exit gate open authorized. Opening barrier immediately.\n");
    controlBarrier("exit", "open");
    exitGateOpenRequest = false;
  }

  if (shouldDisconnectVehicle) {
    if (isVehicleConnected) {
      log_message("   -> Executing disconnect for Conn ID: %d\n", currentVehicleConnId);
      pServer->disconnect(currentVehicleConnId);
    }
    shouldDisconnectVehicle = false;
  }

  if (entryVehiclePassed) {
    entryVehiclePassed = false;
    log_message("   -> Entry passage detected by task. Closing barrier.\n");
    controlBarrier("entry", "close");
    updateState("ENTRY_COMPLETED");
    publishBarrierClosed("entry");
  }

  if (exitVehiclePassed) {
    exitVehiclePassed = false;
    log_message("   -> Exit passage detected by task. Closing barrier.\n");
    controlBarrier("exit", "close");
    updateState("EXIT_COMPLETED");
    publishBarrierClosed("exit");
  }
  
  if (led_timer_active && (millis() - led_timer_start_time >= led_on_duration)) {
    digitalWrite(LED_BUILTIN, LOW);
    led_timer_active = false;
  }

  vTaskDelay(pdMS_TO_TICKS(10));
}

// --- 함수 구현부 ---
void log_message(const char* format, ...) {
  char buf[256];
  va_list args;
  va_start(args, format);
  vsnprintf(buf, sizeof(buf), format, args);
  va_end(args);
  Serial.print(buf);
  if (pcClientConnected && pLogCharacteristic != nullptr) {
    pLogCharacteristic->setValue(buf);
    pLogCharacteristic->notify();
  }
}

void updateState(String newState) {
  if (currentState != newState) {
    currentState = newState;
    const char* contextStr = (currentGateContext == CONTEXT_ENTRY) ? "ENTRY" : (currentGateContext == CONTEXT_EXIT) ? "EXIT" : "NONE";
    log_message("\n===== [STATE] %s (Context: %s) =====\n", newState.c_str(), contextStr);
  }
}

void controlBarrier(const char* barrier, const char* action) {
  bool open = (strcmp(action, "open") == 0);
  int targetAngle = open ? SERVO_OPEN_ANGLE : SERVO_CLOSED_ANGLE;
  if (strcmp(barrier, "entry") == 0) {
    entryServoTargetAngle = targetAngle;
    if(open) {
        barrierLastOpenedTime = millis();
        entryBarrierIsOpen = true;
        entryVehiclePassed = false;
    } else {
        entryBarrierIsOpen = false;
    }
  } else if (strcmp(barrier, "exit") == 0) {
    exitServoTargetAngle = targetAngle;
    if(open) {
        barrierLastOpenedTime = millis();
        exitBarrierIsOpen = true;
        exitVehiclePassed = false;
    } else {
        exitBarrierIsOpen = false;
    }
  }
  log_message("   -> Barrier Control Request: %s barrier %s\n", barrier, action);
}

void requestVehicleDisconnect() {
  log_message("   -> Requesting vehicle disconnect.\n");
  shouldDisconnectVehicle = true;
}

void print_packet(const char* direction, const uint8_t* data, size_t len) {
  char packet_str[len * 3 + 1];
  packet_str[0] = '\0';
  for (size_t i = 0; i < len; i++) {
    sprintf(&packet_str[i * 3], "%02X ", data[i]);
  }
  log_message("   %s (Len: %d): %s\n", direction, len, packet_str);
}

void sendPacketToVehicle(uint8_t cmd, uint8_t* data, uint8_t len) {
  if (isVehicleConnected && pCharacteristic != nullptr) {
    uint8_t packet[128];
    packet[0] = 0x02; packet[1] = cmd; packet[2] = len;
    if (data && len > 0) memcpy(&packet[3], data, len);
    uint8_t checksum = 0;
    for (int i = 1; i < 3 + len; i++) checksum ^= packet[i];
    packet[3 + len] = checksum;
    packet[4 + len] = 0x03;
    pCharacteristic->setValue(packet, 5 + len);
    pCharacteristic->notify();
    print_packet("[SEND_VEHICLE_BLE]", packet, 5 + len);
  } else {
    log_message("   -> [ERROR] Cannot send packet, vehicle not connected.\n");
  }
}

float measureDistance(uint8_t trigPin, uint8_t echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) return 999.0;
  return duration * 0.034 / 2;
}

void publishBarrierClosed(const char* barrierType) {
  #ifdef USE_MICRO_ROS
  publishBarrierEvent(barrierType, "closed");
  #else
  log_message("[DEBUG] Barrier Event: %s barrier closed\n", barrierType);
  #endif
}

bool detectVehiclePassage(uint8_t trigPin, uint8_t echoPin, SensorState& state) {
  const unsigned long PASSAGE_CONFIRM_TIME = 500;
  bool isExitSensor = (trigPin == EXIT_ULTRASONIC_TRIG_PIN);
  if (millis() - state.lastMeasureTime < 50) return false;
  state.lastMeasureTime = millis();
  float distance = measureDistance(trigPin, echoPin);
  if (distance >= 999.0) return false;

  if (isExitSensor) {
      log_message("[DEBUG-EXIT_SENSOR] Dist: %.1f cm, UnderSensor: %s\n", distance, state.vehicleUnderSensor ? "Yes" : "No");
  }

  if (distance < 15.0) {
    if (!state.vehicleUnderSensor) {
      state.vehicleUnderSensor = true;
    }
    state.vehicleLeftTime = 0;
    return false;
  }
  else if (state.vehicleUnderSensor && distance >= VEHICLE_PASSED_DISTANCE) {
    if (state.vehicleLeftTime == 0) {
      state.vehicleLeftTime = millis();
    }
    if (millis() - state.vehicleLeftTime > PASSAGE_CONFIRM_TIME) {
      state.vehicleUnderSensor = false;
      state.vehicleLeftTime = 0;
      return true;
    }
    return false;
  }
  else {
    state.vehicleUnderSensor = false;
    return false;
  }
}

#ifdef USE_MICRO_ROS
void initMicroROS() {
  set_microros_transports();
  delay(2000);
  allocator = rcl_get_default_allocator();
  RCCHECK(rclc_support_init(&support, 0, NULL, &allocator));
  RCCHECK(rclc_node_init_default(&node, "parking_barrier", "", &support));
  log_message("   -> micro-ROS: Creating publishers...\n");
  RCCHECK(rclc_publisher_init_default(&auth_req_pub, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/auth_req"));
  RCCHECK(rclc_publisher_init_default(&exit_req_pub, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/exit_req"));
  RCCHECK(rclc_publisher_init_default(&barrier_event_pub, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/barrier_event"));
  log_message("   -> micro-ROS: Creating subscriber...\n");
  RCCHECK(rclc_subscription_init_default(&barrier_control_sub, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/barrier_cmd"));
  log_message("   -> micro-ROS: Initializing executor...\n");
  RCCHECK(rclc_executor_init(&executor, &support.context, 1, &allocator));
  RCCHECK(rclc_executor_add_subscription(&executor, &barrier_control_sub, &barrier_control_msg, &barrier_control_callback, ON_NEW_DATA));
  auth_req_msg.data.data = msg_buffer; auth_req_msg.data.capacity = sizeof(msg_buffer); auth_req_msg.data.size = 0;
  exit_req_msg.data.data = msg_buffer; exit_req_msg.data.capacity = sizeof(msg_buffer); exit_req_msg.data.size = 0;
  barrier_event_msg.data.data = msg_buffer; barrier_event_msg.data.capacity = sizeof(msg_buffer); barrier_event_msg.data.size = 0;
  barrier_control_msg.data.data = recv_buffer; barrier_control_msg.data.capacity = sizeof(recv_buffer); barrier_control_msg.data.size = 0;
  log_message("   -> micro-ROS initialized successfully.\n");
}

void publishEntryRequest(const VehicleInfo& vehicle) {
  StaticJsonDocument<512> doc;
  doc["vehicle_id"] = vehicle.vehicleId; doc["tag_id"] = vehicle.tagId; doc["elec"] = (vehicle.type == "electric");
  doc["disabled"] = (vehicle.disabledType == "disabled"); doc["preferred"] = vehicle.preferred; doc["destination"] = vehicle.destination;
  serializeJson(doc, msg_buffer);
  auth_req_msg.data.size = strlen(msg_buffer);
  RCSOFTCHECK(rcl_publish(&auth_req_pub, &auth_req_msg, NULL));
  log_message("   -> ROS Published to /parking/auth_req: %s\n", msg_buffer);
}

void publishExitRequest(uint8_t tagId) {
  StaticJsonDocument<128> doc;
  doc["tag_id"] = tagId;
  serializeJson(doc, msg_buffer);
  exit_req_msg.data.size = strlen(msg_buffer);
  RCSOFTCHECK(rcl_publish(&exit_req_pub, &exit_req_msg, NULL));
  log_message("   -> ROS Published to /parking/exit_req: %s\n", msg_buffer);
}

void publishBarrierEvent(const char* gate, const char* state) {
  StaticJsonDocument<128> doc;
  doc["gate"] = gate; doc["state"] = state;
  serializeJson(doc, msg_buffer);
  barrier_event_msg.data.size = strlen(msg_buffer);
  RCSOFTCHECK(rcl_publish(&barrier_event_pub, &barrier_event_msg, NULL));
  log_message("   -> ROS Published to /parking/barrier_event: %s\n", msg_buffer);
}

void barrier_control_callback(const void * msgin) {
  digitalWrite(LED_BUILTIN, HIGH);
  led_timer_active = true;
  led_timer_start_time = millis();
  const std_msgs__msg__String * msg = (const std_msgs__msg__String *)msgin;
  log_message("\n========== BARRIER CONTROL CALLBACK START ==========\n");
  log_message("   -> Message received from /parking/barrier_cmd: '%s'\n", msg->data.data);
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, msg->data.data);
  if (error) {
    log_message("   -> [JSON_PARSE_ERROR] Failed: %s\n", error.c_str());
    log_message("========== BARRIER CONTROL CALLBACK END (FAILED) ==========\n\n");
    return;
  }
  const char* gate = doc["gate"];
  const char* action = doc["action"];
  if (gate && action) {
    if (strcmp(action, "open") == 0) {
      if (strcmp(gate, "entry") == 0) {
        log_message("   -> Entry gate open authorized. Opening immediately...\n");
        entryGateOpenRequest = true;
      } else if (strcmp(gate, "exit") == 0) {
        log_message("   -> Exit gate open authorized. Opening immediately...\n");
        exitGateOpenRequest = true;
      }
    }
    else if (strcmp(action, "close") == 0) {
        if (strcmp(gate, "entry") == 0) controlBarrier("entry", "close");
        else if (strcmp(gate, "exit") == 0) controlBarrier("exit", "close");
    }
  } else {
    log_message("   -> [ERROR] Missing 'gate' or 'action' fields!\n");
  }
  log_message("========== BARRIER CONTROL CALLBACK END ==========\n\n");
}
#endif

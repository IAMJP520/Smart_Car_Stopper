// =================================================================
//   입출차 차단기 ESP32 코드 (V4.2.0 - 라즈베리파이 호환성 강화)
//
// - [호환성] RPI 코드에 맞춰 입차 요청 토픽을 '/parking/auth_req'로 변경
// - [호환성] 입차 요청 시 elec/disabled 필드를 Boolean 타입으로 전송
// - [호환성] UWB 추적 시작/종료 토픽 발행 로직 제거 (RPI 역할)
// - [안정성] ROS Agent 연결 상태 주기적 확인(ping) 로직 복원
// - [안정성] 모든 토픽 발행 전 Agent 연결 상태 확인 로직 추가
// - [최적화] 불필요한 waypoints 구독 로직 제거
// =================================================================

// ========================[ 기능 활성화 스위치 ]========================
#define USE_MICRO_ROS // 이 줄을 주석 처리하면 자동화된 디버그 모드로 동작합니다.
// =================================================================

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

#ifdef USE_MICRO_ROS
#include <micro_ros_arduino.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <std_msgs/msg/string.h>
#endif

// --- 하드웨어 핀 설정 ---
#define ENTRY_BARRIER_GPIO 17
#define EXIT_BARRIER_GPIO 19
#define SERVO_CLOSED_ANGLE 0
#define SERVO_OPEN_ANGLE 90
#define EMERGENCY_STOP_GPIO 18
#define LED_BUILTIN 2

#define ENTRY_ULTRASONIC_TRIG_PIN 22
#define ENTRY_ULTRASONIC_ECHO_PIN 23
#define EXIT_ULTRASONIC_TRIG_PIN  25
#define EXIT_ULTRASONIC_ECHO_PIN  26

// 센서 안정화 시간 및 통과 판별 거리
const unsigned long SENSOR_STABILIZATION_DELAY = 500;
const float VEHICLE_PASSED_DISTANCE = 50.0; // 50cm 이상이면 차량이 지나간 것으로 판단

// --- BLE 설정 ---
#define SERVICE_UUID "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define DEVICE_NAME "ParkingBarrier_System"
#define PC_SERVICE_UUID "a2b8915e-993a-4f21-91a6-575355a2c4e7"
#define PC_CHARACTERISTIC_UUID "a2b8915e-993a-4f21-91a6-575355a2c4e8"
#define ROS_STATUS_UUID "a2b8915e-993a-4f21-91a6-575355a2c4e9"

// --- BLE 명령어 정의 ---
#define CMD_READY_SIGNAL 0x01
#define CMD_ENTRY_INFO 0x10
#define CMD_INFO_REQUEST 0x15
#define CMD_EXIT_INFO 0x16

#ifdef USE_MICRO_ROS
rcl_node_t node;
rclc_support_t support;
rcl_allocator_t allocator;
rclc_executor_t executor;
rcl_publisher_t auth_req_pub; // [수정] 토픽명 변경 entry_req -> auth_req
rcl_publisher_t exit_req_pub;
rcl_publisher_t barrier_event_pub;
rcl_subscription_t barrier_control_sub;
std_msgs__msg__String string_msg;
char msg_buffer[512];

bool agent_connected = false;
unsigned long last_ping_time = 0;
const long ping_interval = 2000; // 2초마다 Agent 연결 확인
#endif

// --- 전역 변수 ---
BLEServer* pServer = nullptr;
BLECharacteristic* pCharacteristic = nullptr;
BLECharacteristic* pPCCharacteristic = nullptr;
BLECharacteristic* pRosStatusCharacteristic = nullptr;
Servo entryServo;
Servo exitServo;
bool isVehicleConnected = false;
String currentState = "BOOTING";
enum GateContext { CONTEXT_NONE, CONTEXT_ENTRY, CONTEXT_EXIT };
GateContext currentGateContext = CONTEXT_NONE;
bool entryBarrierIsOpen = false;
bool exitBarrierIsOpen = false;
unsigned long barrierLastOpenedTime = 0;

uint16_t currentConnectionId = 0;
bool shouldDisconnect = false;

struct VehicleInfo {
    String vehicleId = "";
    uint8_t tagId = 0;
    String type = "";
    String disabledType = "";
    String preferred = "";
    uint8_t destination = 0;  // 0, 1, 2 중 하나
    String guiMac = "";
} currentVehicle;

// --- 함수 선언 ---
void controlBarrier(const char* barrier, const char* action);
void sendPacketToVehicle(uint8_t cmd, uint8_t* data, uint8_t len);
void updateState(String newState);
float measureDistance(uint8_t trigPin, uint8_t echoPin);
bool detectVehiclePassage(uint8_t trigPin, uint8_t echoPin);
void requestDisconnect();
void publishBarrierClosed(const char* barrierType);

#ifdef USE_MICRO_ROS
void initMicroROS();
void publishEntryRequest(const VehicleInfo& vehicle);
void publishExitRequest(uint8_t tagId);
void publishBarrierEvent(const char* gate, const char* state);
void barrier_control_callback(const void * msgin);
#else
void publishEntryRequest_Test(const VehicleInfo& vehicle);
void publishExitRequest_Test(uint8_t tagId);
#endif

void error_loop() { while(1) { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); delay(100); } }

// --- BLE 콜백 (공용) ---
class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer, esp_ble_gatts_cb_param_t *param) {
        currentConnectionId = param->connect.conn_id;
        
        Serial.println();
        Serial.println("****************************************");
        Serial.printf ("    BLE Client Connected (Conn ID: %d)\n", currentConnectionId);
        Serial.println("****************************************");
    }
    
    void onDisconnect(BLEServer* pServer) {
        isVehicleConnected = false;
        currentVehicle = VehicleInfo();
        currentGateContext = CONTEXT_NONE;
        
        updateState("ADVERTISING");
        pServer->getAdvertising()->start();
        
        Serial.printf("Vehicle disconnected. Ready for next vehicle.\n");
    }
};

// --- 차량용 Characteristic 콜백 ---
class MyCharacteristicCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
        if (!isVehicleConnected) {
            isVehicleConnected = true;
            pServer->getAdvertising()->stop();
            updateState("VEHICLE_CONNECTED");
            Serial.println("   -> Vehicle connection confirmed. Advertising stopped.");
        }
        
        size_t len = pCharacteristic->getLength();
        if (len > 0) {
            uint8_t* data = pCharacteristic->getData();
            uint8_t cmd = data[1];

            if (cmd == CMD_ENTRY_INFO) {
                // 입차 정보 처리
                currentGateContext = CONTEXT_ENTRY;
                updateState("ENTRY_INFO_RECEIVED");
                
                // 차량 정보 파싱
                char* vehicleId = (char*)&data[3];
                int vehicleIdLen = strlen(vehicleId);
                uint8_t tagId = data[3 + vehicleIdLen + 1];
                uint8_t vehicleType = data[3 + vehicleIdLen + 2];
                uint8_t disabledType = data[3 + vehicleIdLen + 3];
                uint8_t preferred = data[3 + vehicleIdLen + 4];
                uint8_t destination = data[3 + vehicleIdLen + 5];
                
                // VehicleInfo 구조체에 저장
                currentVehicle.vehicleId = String(vehicleId);
                currentVehicle.tagId = tagId;
                currentVehicle.type = (vehicleType == 0x01) ? "electric" : "regular";
                currentVehicle.disabledType = (disabledType == 0x01) ? "disabled" : "normal";
                
                if (preferred == 1) currentVehicle.preferred = "disabled";
                else if (preferred == 2) currentVehicle.preferred = "elec";
                else currentVehicle.preferred = "normal";
                
                currentVehicle.destination = destination;
                
                // GUI MAC 주소 추출 (6바이트)
                char macStr[18];
                uint8_t* macBytes = &data[3 + vehicleIdLen + 6];
                sprintf(macStr, "%02X:%02X:%02X:%02X:%02X:%02X", 
                        macBytes[0], macBytes[1], macBytes[2], 
                        macBytes[3], macBytes[4], macBytes[5]);
                currentVehicle.guiMac = String(macStr);
                
                Serial.printf("   -> [입차] 차량 정보: ID=%s, TagID=%d, Dest=%d\n", 
                              currentVehicle.vehicleId.c_str(), currentVehicle.tagId, currentVehicle.destination);
                
                #ifdef USE_MICRO_ROS
                publishEntryRequest(currentVehicle);
                // UWB 추적 시작은 RPI 역할이므로 ESP32에서 호출하지 않음
                #else
                publishEntryRequest_Test(currentVehicle);
                controlBarrier("entry", "open");
                entryBarrierIsOpen = true;
                updateState("ENTRY_BARRIER_OPEN");
                #endif
                
                requestDisconnect();
            }
            else if (cmd == CMD_EXIT_INFO) {
                // 출차 정보 처리  
                currentGateContext = CONTEXT_EXIT;
                updateState("EXIT_INFO_RECEIVED");
                
                // 기본 정보만 파싱 (차량ID, 태그ID)
                char* vehicleId = (char*)&data[3];
                int vehicleIdLen = strlen(vehicleId);
                uint8_t tagId = data[3 + vehicleIdLen + 1];
                
                currentVehicle.vehicleId = String(vehicleId);
                currentVehicle.tagId = tagId;
                
                Serial.printf("   -> [출차] 차량 정보: ID=%s, TagID=%d\n", 
                              currentVehicle.vehicleId.c_str(), currentVehicle.tagId);
                
                #ifdef USE_MICRO_ROS
                publishExitRequest(tagId);
                #else
                publishExitRequest_Test(tagId);
                controlBarrier("exit", "open");
                exitBarrierIsOpen = true;
                updateState("EXIT_BARRIER_OPEN");
                #endif
                
                requestDisconnect();
            }
            else if (cmd == CMD_READY_SIGNAL) {
                currentGateContext = CONTEXT_ENTRY;
                updateState("READY_RECEIVED");
                Serial.println("   -> [입차] 차량 준비 완료. 정보 요청(0x15)을 보냅니다.");
                sendPacketToVehicle(CMD_INFO_REQUEST, nullptr, 0);
            }
        }
    }
};

// --- PC 제어용 Characteristic 콜백 ---
class PCCharacteristicCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
        String value = pCharacteristic->getValue().c_str();
        if (value.length() > 0) {
            Serial.printf("PC Command received: %s\n", value.c_str());
            
            if (value == "entry_open") {
                controlBarrier("entry", "open");
                entryBarrierIsOpen = true;
                updateState("ENTRY_BARRIER_OPEN_BY_PC");
            }
            else if (value == "entry_close") {
                controlBarrier("entry", "close");
                entryBarrierIsOpen = false;
                updateState("ENTRY_BARRIER_CLOSED_BY_PC");
                publishBarrierClosed("entry");
            }
            else if (value == "exit_open") {
                controlBarrier("exit", "open");
                exitBarrierIsOpen = true;
                updateState("EXIT_BARRIER_OPEN_BY_PC");
            }
            else if (value == "exit_close") {
                controlBarrier("exit", "close");
                exitBarrierIsOpen = false;
                updateState("EXIT_BARRIER_CLOSED_BY_PC");
                publishBarrierClosed("exit");
            }
        }
    }
};

void setup() {
    Serial.begin(115200);
    updateState("INITIALIZING");
    
    entryServo.attach(ENTRY_BARRIER_GPIO);
    exitServo.attach(EXIT_BARRIER_GPIO);
    entryServo.write(SERVO_CLOSED_ANGLE);
    exitServo.write(SERVO_CLOSED_ANGLE);
    
    pinMode(EMERGENCY_STOP_GPIO, INPUT_PULLUP);
    pinMode(LED_BUILTIN, OUTPUT);
    
    pinMode(ENTRY_ULTRASONIC_TRIG_PIN, OUTPUT);
    pinMode(ENTRY_ULTRASONIC_ECHO_PIN, INPUT);
    pinMode(EXIT_ULTRASONIC_TRIG_PIN, OUTPUT);
    pinMode(EXIT_ULTRASONIC_ECHO_PIN, INPUT);
    
    BLEDevice::init(DEVICE_NAME);
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    
    BLEService *pService = pServer->createService(SERVICE_UUID);
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID, 
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_NOTIFY
    );
    pCharacteristic->setCallbacks(new MyCharacteristicCallbacks());
    pCharacteristic->addDescriptor(new BLE2902());
    pService->start();
    
    BLEService *pPCService = pServer->createService(PC_SERVICE_UUID);
    pPCCharacteristic = pPCService->createCharacteristic(
        PC_CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_READ
    );
    pPCCharacteristic->setCallbacks(new PCCharacteristicCallbacks());
    
    pRosStatusCharacteristic = pPCService->createCharacteristic(
        ROS_STATUS_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );
    pRosStatusCharacteristic->setValue("0");
    pPCService->start();
    
    #ifdef USE_MICRO_ROS
    initMicroROS();
    #else
    Serial.println("\n[DEBUG MODE] Switched to automated debugging mode.");
    #endif
    
    updateState("ADVERTISING");
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->addServiceUUID(PC_SERVICE_UUID);
    pAdvertising->start();
    Serial.println("   -> BLE Advertising started (Always ON)");
}

void loop() {
    #ifdef USE_MICRO_ROS
    // [추가] Agent 연결 상태 주기적 확인 로직
    if (millis() - last_ping_time >= ping_interval) {
        last_ping_time = millis();
        agent_connected = (rmw_uros_ping_agent(100, 1) == RMW_RET_OK);
        if (pRosStatusCharacteristic != nullptr) {
            pRosStatusCharacteristic->setValue(agent_connected ? "1" : "0");
            pRosStatusCharacteristic->notify();
        }
    }

    if (agent_connected) {
        rclc_executor_spin_some(&executor, RCL_MS_TO_NS(10));
    }
    #endif

    // 연결 해제 처리
    if (shouldDisconnect) {
        if (isVehicleConnected) {
            pServer->disconnect(currentConnectionId);
        }
        shouldDisconnect = false;
    }

    // 차량 통과 감지 (차단기가 열린 상태에서만)
    bool vehicleHasPassed = false;
    if ((entryBarrierIsOpen || exitBarrierIsOpen) && 
        (millis() - barrierLastOpenedTime > SENSOR_STABILIZATION_DELAY)) {
        
        if (entryBarrierIsOpen) {
            vehicleHasPassed = detectVehiclePassage(ENTRY_ULTRASONIC_TRIG_PIN, ENTRY_ULTRASONIC_ECHO_PIN);
            if (vehicleHasPassed) {
                controlBarrier("entry", "close");
                entryBarrierIsOpen = false;
                updateState("ENTRY_COMPLETED");
                publishBarrierClosed("entry");
            }
        } 
        else if (exitBarrierIsOpen) {
            vehicleHasPassed = detectVehiclePassage(EXIT_ULTRASONIC_TRIG_PIN, EXIT_ULTRASONIC_ECHO_PIN);
            if (vehicleHasPassed) {
                controlBarrier("exit", "close");
                exitBarrierIsOpen = false;
                updateState("EXIT_COMPLETED");
                publishBarrierClosed("exit");
            }
        }
    }
    
    delay(10);
}

// --- 함수 정의 ---
void requestDisconnect() {
    Serial.println("   -> Communication complete. Requesting disconnect.");
    shouldDisconnect = true;
}

void publishBarrierClosed(const char* barrierType) {
    #ifdef USE_MICRO_ROS
    publishBarrierEvent(barrierType, "closed");
    #else
    Serial.printf("[DEBUG] Barrier Event: %s barrier closed\n", barrierType);
    #endif
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

bool detectVehiclePassage(uint8_t trigPin, uint8_t echoPin) {
    static bool vehicleDetected = false;
    static int passageConfirmCount = 0;
    const int CONFIRM_THRESHOLD = 3;
    
    static unsigned long lastMeasureTime = 0;
    if (millis() - lastMeasureTime < 100) return false;
    lastMeasureTime = millis();
    
    float distance = measureDistance(trigPin, echoPin);
    
    if (distance >= 999.0) return false;
    
    if (distance < 15.0) { // 15cm 이내에 차량이 있음
        if (!vehicleDetected) {
            vehicleDetected = true;
            Serial.printf("   -> Vehicle detected at %.1fcm\n", distance);
        }
        passageConfirmCount = 0;
    } 
    else if (vehicleDetected && distance >= VEHICLE_PASSED_DISTANCE) { // 50cm 이상이면 통과
        passageConfirmCount++;
        if (passageConfirmCount >= CONFIRM_THRESHOLD) {
            vehicleDetected = false;
            passageConfirmCount = 0;
            Serial.printf("   -> Vehicle passed (distance: %.1fcm)\n", distance);
            return true;
        }
    }
    
    return false;
}

void controlBarrier(const char* barrier, const char* action) {
    bool open = (strcmp(action, "open") == 0);
    int angle = open ? SERVO_OPEN_ANGLE : SERVO_CLOSED_ANGLE;

    if (open) barrierLastOpenedTime = millis();
    
    if (strcmp(barrier, "entry") == 0) {
        entryServo.write(angle);
    } else if (strcmp(barrier, "exit") == 0) {
        exitServo.write(angle);
    }
    
    Serial.printf("   -> %s barrier %s\n", barrier, action);
}

void sendPacketToVehicle(uint8_t cmd, uint8_t* data, uint8_t len) {
    if (isVehicleConnected && pCharacteristic != nullptr) {
        uint8_t packet[128];
        packet[0] = 0x02; 
        packet[1] = cmd; 
        packet[2] = len;
        
        if (data && len > 0) {
            memcpy(&packet[3], data, len);
        }
        
        uint8_t checksum = 0;
        for (int i = 1; i < 3 + len; i++) {
            checksum ^= packet[i];
        }
        packet[3 + len] = checksum;
        packet[4 + len] = 0x03;
        
        pCharacteristic->setValue(packet, 5 + len);
        pCharacteristic->notify();
        
        Serial.printf("   -> Sent packet to vehicle: CMD=0x%02X\n", cmd);
    }
}

void updateState(String newState) {
    if (currentState != newState) {
        currentState = newState;
        Serial.printf("\n===== [STATE] %s =====\n", newState.c_str());
    }
}

#ifdef USE_MICRO_ROS
void initMicroROS() {
    set_microros_transports();
    delay(2000);
    
    allocator = rcl_get_default_allocator();
    
    rcl_init_options_t init_options = rcl_get_zero_initialized_init_options();
    rcl_init_options_init(&init_options, allocator);
    rcl_init_options_set_domain_id(&init_options, 0);
    
    rclc_support_init_with_options(&support, 0, NULL, &init_options, &allocator);
    rclc_node_init_default(&node, "parking_barrier", "", &support);
    
    // Publishers
    // [수정] RPI 코드에 맞춰 토픽명 변경 및 불필요한 토픽 제거
    rclc_publisher_init_default(&auth_req_pub, &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/auth_req");
    rclc_publisher_init_default(&exit_req_pub, &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/exit_req");
    rclc_publisher_init_default(&barrier_event_pub, &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/barrier_event");
    
    // Subscribers
    rclc_subscription_init_default(&barrier_control_sub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "/parking/barrier_cmd");
    
    // Executor
    rclc_executor_init(&executor, &support.context, 1, &allocator);
    rclc_executor_add_subscription(&executor, &barrier_control_sub, &string_msg, 
        &barrier_control_callback, ON_NEW_DATA);
    
    Serial.println("   -> Micro-ROS initialized successfully");
}

void publishEntryRequest(const VehicleInfo& vehicle) {
    if (!agent_connected) {
        Serial.println("   -> [ERROR] ROS Agent not connected. Publish failed.");
        return;
    }
    
    StaticJsonDocument<512> doc;
    doc["vehicle_id"] = vehicle.vehicleId;
    doc["tag_id"] = vehicle.tagId;
    doc["elec"] = (vehicle.type == "electric"); // [수정] Boolean으로 전송
    doc["disabled"] = (vehicle.disabledType == "disabled"); // [수정] Boolean으로 전송
    doc["preferred"] = vehicle.preferred;
    doc["destination"] = vehicle.destination;
    doc["gui_mac"] = vehicle.guiMac;
    
    serializeJson(doc, msg_buffer);
    string_msg.data.data = msg_buffer;
    string_msg.data.size = strlen(msg_buffer);
    
    rcl_publish(&auth_req_pub, &string_msg, NULL);
    Serial.printf("   -> Published to /parking/auth_req: %s\n", msg_buffer);
}

void publishExitRequest(uint8_t tagId) {
    if (!agent_connected) {
        Serial.println("   -> [ERROR] ROS Agent not connected. Publish failed.");
        return;
    }
    
    StaticJsonDocument<128> doc;
    doc["tag_id"] = tagId;
    
    serializeJson(doc, msg_buffer);
    string_msg.data.data = msg_buffer;
    string_msg.data.size = strlen(msg_buffer);
    
    rcl_publish(&exit_req_pub, &string_msg, NULL);
    Serial.printf("   -> Published to /parking/exit_req: %s\n", msg_buffer);
}

void publishBarrierEvent(const char* gate, const char* state) {
    if (!agent_connected) {
        Serial.println("   -> [ERROR] ROS Agent not connected. Publish failed.");
        return;
    }
    
    StaticJsonDocument<128> doc;
    doc["gate"] = gate;
    doc["state"] = state;

    serializeJson(doc, msg_buffer);
    string_msg.data.data = msg_buffer;
    string_msg.data.size = strlen(msg_buffer);
    
    rcl_publish(&barrier_event_pub, &string_msg, NULL);
    Serial.printf("   -> Published to /parking/barrier_event: %s\n", msg_buffer);
}

void barrier_control_callback(const void * msgin) {
    const std_msgs__msg__String * msg = (const std_msgs__msg__String *)msgin;
    
    StaticJsonDocument<256> doc;
    deserializeJson(doc, msg->data.data);
    
    const char* gate = doc["gate"];
    const char* action = doc["action"];

    if (gate && action) {
        Serial.printf("   -> Received barrier control: gate=%s, action=%s\n", gate, action);
        if (strcmp(action, "open") == 0) {
            if (strcmp(gate, "entry") == 0) {
                controlBarrier("entry", "open");
                entryBarrierIsOpen = true;
                updateState("ENTRY_BARRIER_OPEN_BY_ROS");
            } else if (strcmp(gate, "exit") == 0) {
                controlBarrier("exit", "open");
                exitBarrierIsOpen = true;
                updateState("EXIT_BARRIER_OPEN_BY_ROS");
            }
        }
    }
}

#else
// 디버그 모드 함수들
void publishEntryRequest_Test(const VehicleInfo& vehicle) {
    Serial.printf("[DEBUG] Entry Request: ID=%s, TagID=%d, Type=%s, Dest=%d\n", 
                  vehicle.vehicleId.c_str(), vehicle.tagId, vehicle.type.c_str(), vehicle.destination);
    Serial.printf("[DEBUG] Additional info: disabled=%s, preferred=%s, gui_mac=%s\n",
                  vehicle.disabledType.c_str(), vehicle.preferred.c_str(), vehicle.guiMac.c_str());
}

void publishExitRequest_Test(uint8_t tagId) {
    Serial.printf("[DEBUG] Exit Request: TagID=%d\n", tagId);
}
#endif
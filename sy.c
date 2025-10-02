// =================================================================
//   ESP32 Vehicle Code (V3.0.0 - 입출차 플래그 기반 로직)
//
// - [새기능] 입출차 플래그 변수 추가 (차단기 연결시마다 토글)
// - [수정] 태그번호 2자리, 목적지 1자리(0,1,2)로 변경
// - [수정] RSSI 임계값 -25로 변경
// - [수정] 차량→차단기 정보 전송 후 즉시 연결 해제
// - [수정] 동일 차량 5초간 재연결 방지 로직 추가
// =================================================================

// ========================[ 기능 활성화 스위치 ]========================
#define USE_GUI // GUI 연동 없이 단독 테스트 시 이 줄을 주석 처리하세요.
// =================================================================

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <WiFi.h>
#include <ArduinoJson.h>

// --- Configuration ---
#define WIFI_SSID "aaaa"
#define WIFI_PASSWORD "00000906"
#define TRIGGER_HOST "192.168.204.86"
//#define WIFI_SSID "HANULSO_2.4G"
//#define WIFI_PASSWORD "hanulso8421"
//#define TRIGGER_HOST "192.168.0.74"
#define TRIGGER_PORT 7777
#define SERVICE_UUID "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define RSSI_THRESHOLD -25
#define SCAN_TIME 1
#define RECONNECT_BLOCK_TIME 7000  // 5초간 재연결 방지

const char* VEHICLE_ID = "23가1234";
const uint8_t TAG_ID = 19;  // 2자리 태그 번호
const uint8_t GUI_MAC[] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};

#ifdef USE_GUI
#define RECEIVER_PORT 7777
#define WAYPOINT_PORT 8888
#endif

// --- 입출차 플래그 및 연결 제어 변수 ---
bool isEntryVehicle = false;  // true: 입차, false: 출차 (초기값 출차)
unsigned long lastDisconnectTime = 0;
bool canReconnect = true;
bool triggerSent = false;

// GUI로부터 수신한 데이터를 저장할 전역 변수
String receivedVehicleType = "regular";
bool receivedIsHandicapped = false;
String receivedSpotType = "normal";
uint8_t receivedDestination = 0;  // 0, 1, 2 중 하나

// --- Global Objects & State Variables ---
BLEScan* pBLEScan;
BLERemoteCharacteristic* pRemoteCharacteristic = nullptr;
BLEAdvertisedDevice* myDevice = nullptr;
BLEClient* pClient = nullptr;
#ifdef USE_GUI
WiFiServer server(RECEIVER_PORT);
WiFiServer waypointServer(WAYPOINT_PORT);
#endif
bool doConnect = false;
bool isConnected = false;
bool isScanning = false;
String currentState = "BOOTING";
bool shouldSendVehicleInfo = false;
bool exitRequested = false;

// --- Function Declarations ---
void connectToServer();
void printPacket(const char* direction, const uint8_t* data, size_t len);
void updateState(String newState);
void sendTriggerToPC();
void sendSerialCommandToTagESP(uint8_t tagId);
#ifdef USE_GUI
void handleNewClient(WiFiClient client);
void handleWaypointClient(WiFiClient client);
#endif
void onDataReceived(String vehicleType, bool isHandicapped, String spotType, uint8_t destination);
void sendExitRequest();
void sendVehicleInfo();
void resetConnectionState();
void forceDisconnect();

// =================================================================
//                         BLE Callback Functions
// =================================================================

static void notifyCallback(BLERemoteCharacteristic* pBLERemoteCharacteristic, uint8_t* pData, size_t length, bool isNotify) {
    printPacket("[RECV_BLE]", pData, length);
    if (length > 4 && pData[0] == 0x02) {
        uint8_t cmd = pData[1];
        uint8_t* data = &pData[3];
        
        if (cmd == 0x15) { // 정보 요청
            Serial.println("   -> Vehicle info request (0x15) received. Preparing response.");
            shouldSendVehicleInfo = true;
        }
        else if (cmd == 0x13) { // AUTH_REJECT 처리
            Serial.println("   -> Authentication REJECTED (0x13) by barrier. Disconnecting.");
            if(pClient->isConnected()) {
                pClient->disconnect();
            }
        }
        else if (cmd == 0x11) { // 태그 정보
            uint8_t tagId = data[0];
            Serial.printf("   -> Assigned Tag ID: %d\n", tagId);
            sendSerialCommandToTagESP(tagId);
        }
    }
}

class MyClientCallbacks : public BLEClientCallbacks {
    void onConnect(BLEClient* pclient) {
        isConnected = true;
        
        // 연결될 때마다 입출차 플래그 토글
        isEntryVehicle = !isEntryVehicle;
        Serial.printf("   -> Connection established. Flag toggled: %s\n", 
                     isEntryVehicle ? "ENTRY" : "EXIT");
        
        updateState("CONNECTED_TO_BARRIER");
    }
    
    void onDisconnect(BLEClient* pclient) {
        // 연결 해제 시 재연결 방지 타이머 시작
        lastDisconnectTime = millis();
        canReconnect = false;
        triggerSent = false; // 다시 스캔을 시작할 수 있도록 리셋
        resetConnectionState();
    }
};

class MyAdvertisedDeviceCallbacks: public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice advertisedDevice) {
        // 재연결 방지 시간 체크
        if (!canReconnect && (millis() - lastDisconnectTime < RECONNECT_BLOCK_TIME)) {
            return; // 7초 이내이면 연결 시도 안함
        }
        
        if (advertisedDevice.haveServiceUUID() && advertisedDevice.getServiceUUID().equals(BLEUUID(SERVICE_UUID))) {
            if (advertisedDevice.getRSSI() > RSSI_THRESHOLD) {
                Serial.printf("Barrier found! (RSSI: %d)\n", advertisedDevice.getRSSI());
                updateState("DEVICE_FOUND");
                BLEDevice::getScan()->stop();
                isScanning = false;
                canReconnect = true;  // 새로운 연결 허용
                
                // PC에 트리거 전송 (한 번만)
                if (!triggerSent) {
                    sendTriggerToPC();
                    triggerSent = true;
                }
                
                if (myDevice == nullptr) {
                    myDevice = new BLEAdvertisedDevice(advertisedDevice);
                    
                    #ifndef USE_GUI
                    // 디버그 모드에서는 기본값으로 데이터 수신 처리
                    onDataReceived("regular", false, "normal", 0);
                    #else
                    // GUI 모드에서는 데이터 수신 대기
                    updateState("WAITING_FOR_GUI_DATA");
                    #endif
                }
            }
        }
    }
};

// =================================================================
//                                SETUP
// =================================================================
void setup() {
    Serial.begin(115200);
    Serial2.begin(9600, SERIAL_8N1, 26, 27); // UWB 태그 ESP와 통신용
    updateState("INITIALIZING");
    
    #ifdef USE_GUI
    Serial.print("Connecting to Wi-Fi: ");
    Serial.println(WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500); Serial.print(".");
    }
    Serial.println("\nWiFi connected!");
    Serial.print("   My IP address is: ");
    Serial.println(WiFi.localIP());
    
    server.begin();
    waypointServer.begin();
    Serial.printf("   TCP Server for data reception started on port %d\n", RECEIVER_PORT);
    #endif

    BLEDevice::init("");
    BLEDevice::setMTU(50);
    pClient = BLEDevice::createClient();
    pClient->setClientCallbacks(new MyClientCallbacks());
    pBLEScan = BLEDevice::getScan();
    pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
    pBLEScan->setActiveScan(true);
    updateState("IDLE");
}

// =================================================================
//                                 LOOP
// =================================================================
void loop() {
    #ifdef USE_GUI
    WiFiClient client = server.available();
    if (client) { handleNewClient(client); }

    WiFiClient waypointClient = waypointServer.available();
    if (waypointClient) { handleWaypointClient(waypointClient); }
    #endif

    // 재연결 방지 시간 해제 체크
    if (!canReconnect && (millis() - lastDisconnectTime >= RECONNECT_BLOCK_TIME)) {
        canReconnect = true;
        Serial.println("   -> Reconnection allowed after 5 seconds.");
    }

    if (!isConnected && myDevice == nullptr && !isScanning && canReconnect) {
        updateState("SCANNING_FOR_BARRIER");
        pBLEScan->start(SCAN_TIME, [](BLEScanResults results){ 
            isScanning = false; 
            if(!isConnected && myDevice == nullptr) updateState("IDLE");
        }, false);
        isScanning = true;
    }

    if (doConnect && myDevice != nullptr && !isConnected) {
        connectToServer();
        doConnect = false;
    }

    if (isConnected) {
        if (shouldSendVehicleInfo) {
            sendVehicleInfo();
            shouldSendVehicleInfo = false;
            // 정보 전송 후 즉시 연결 해제
            forceDisconnect();
        } else if (exitRequested) {
            sendExitRequest();
            exitRequested = false;
            // 출차 요청 후 즉시 연결 해제
            forceDisconnect();
        }
    }

    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        if (command == "exit") {
            if (!isConnected) {
                Serial.println("Not connected. Trying to scan and connect for exit...");
                exitRequested = true;
                isScanning = false;
            } else {
                sendExitRequest();
                forceDisconnect();
            }
        }
    }
    delay(100);
}

// =================================================================
//                     Core Function Implementations
// =================================================================

void resetConnectionState() {
    isConnected = false;
    pRemoteCharacteristic = nullptr;
    if (myDevice != nullptr) {
        delete myDevice;
        myDevice = nullptr;
    }
    shouldSendVehicleInfo = false;
    exitRequested = false;
    doConnect = false;
    isScanning = false; 
    updateState("DISCONNECTED_AND_IDLE");
}

void forceDisconnect() {
    if (isConnected && pClient != nullptr) {
        Serial.println("   -> Force disconnecting from barrier...");
        pClient->disconnect();
    }
}

void onDataReceived(String vehicleType, bool isHandicapped, String spotType, uint8_t destination) {
    receivedVehicleType = vehicleType;
    receivedIsHandicapped = isHandicapped;
    receivedSpotType = spotType;
    receivedDestination = destination;

    Serial.println("========== Parking Choice Info (Updated) ==========");
    Serial.printf("  - Vehicle Type: %s\n", receivedVehicleType.c_str());
    Serial.printf("  - Is Disabled: %s\n", receivedIsHandicapped ? "Yes" : "No");
    Serial.printf("  - Preferred Spot: %s\n", receivedSpotType.c_str());
    Serial.printf("  - Destination: %d\n", receivedDestination);
    Serial.println("=================================================");

    // GUI에서 데이터를 성공적으로 수신했으므로 이제 차단기 연결을 시작합니다.
    if (myDevice != nullptr && !isConnected) {
        doConnect = true; 
    }
}

void connectToServer() {
    if (!pClient->connect(myDevice)) {
        resetConnectionState(); 
        return;
    }
    BLERemoteService* pRemoteService = pClient->getService(SERVICE_UUID);
    if (pRemoteService == nullptr) { pClient->disconnect(); return; }
    
    pRemoteCharacteristic = pRemoteService->getCharacteristic(CHARACTERISTIC_UUID);
    if (pRemoteCharacteristic == nullptr) { pClient->disconnect(); return; }
    
    if(pRemoteCharacteristic->canNotify()) {
        pRemoteCharacteristic->registerForNotify(notifyCallback);
    }
    
    if (pRemoteCharacteristic->canWrite()) {
        if (exitRequested) {
            sendExitRequest();
        } else {
            uint8_t readyPacket[] = {0x02, 0x01, 0x00, 0x01, 0x03};
            pRemoteCharacteristic->writeValue(readyPacket, sizeof(readyPacket), false);
        }
    }
}

void sendVehicleInfo() {
    if (!isConnected || pRemoteCharacteristic == nullptr || !pRemoteCharacteristic->canWrite()) return;
    
    uint8_t vehicleTypeByte = (receivedVehicleType == "electric") ? 0x01 : 0x00;
    uint8_t disabledTypeByte = receivedIsHandicapped ? 0x01 : 0x00;
    
    uint8_t preferredByte = 0;
    if (receivedSpotType == "disabled") preferredByte = 1;
    else if (receivedSpotType == "elec") preferredByte = 2;
    
    size_t vehicleIdLen = strlen(VEHICLE_ID);
    
    uint8_t responsePacket[128];
    int idx = 0;
    
    responsePacket[idx++] = 0x02; // STX
    
    // 입차/출차에 따라 다른 명령어 사용
    if (isEntryVehicle) {
        responsePacket[idx++] = 0x10; // CMD_ENTRY_INFO
    } else {
        responsePacket[idx++] = 0x16; // CMD_EXIT_INFO  
    }
    
    int dataStartIdx = idx + 1;
    
    // 차량 ID
    memcpy(&responsePacket[idx], VEHICLE_ID, vehicleIdLen);
    idx += vehicleIdLen; 
    responsePacket[idx++] = 0x00;
    
    // 태그 ID (2자리)
    responsePacket[idx++] = TAG_ID;
    
    // 입차인 경우에만 추가 정보 포함
    if (isEntryVehicle) {
        responsePacket[idx++] = vehicleTypeByte;
        responsePacket[idx++] = disabledTypeByte;
        responsePacket[idx++] = preferredByte;
        
        // 목적지 (1자리: 0, 1, 2)
        responsePacket[idx++] = receivedDestination;
        
        // GUI MAC
        memcpy(&responsePacket[idx], GUI_MAC, 6);
        idx += 6;
    }
    
    uint8_t dataLen = idx - dataStartIdx;
    responsePacket[2] = dataLen;
    
    uint8_t checksum = 0;
    for(int i = 1; i < idx; i++) checksum ^= responsePacket[i];
    responsePacket[idx++] = checksum;
    
    responsePacket[idx++] = 0x03; // ETX

    pRemoteCharacteristic->writeValue(responsePacket, idx, false);
    printPacket("[SEND_BLE]", responsePacket, idx);
    
    if (isEntryVehicle) {
        Serial.printf("   -> Sent ENTRY info (0x10) - TagID: %d, Destination: %d\n", TAG_ID, receivedDestination);
    } else {
        Serial.printf("   -> Sent EXIT info (0x16) - TagID: %d\n", TAG_ID);
    }
}

void sendExitRequest() {
    if (!isConnected || pRemoteCharacteristic == nullptr || !pRemoteCharacteristic->canWrite()) {
        exitRequested = true;
        return;
    }
    
    updateState("REQUESTING_EXIT");
    
    uint8_t exitPacket[8];
    exitPacket[0] = 0x02;
    exitPacket[1] = 0x16; // CMD_EXIT_REQUEST
    exitPacket[2] = 0x01; // Data length
    exitPacket[3] = TAG_ID; // tag_id
    
    uint8_t checksum = 0;
    for(int i = 1; i < 4; i++) checksum ^= exitPacket[i];
    exitPacket[4] = checksum;
    exitPacket[5] = 0x03; // ETX
    
    pRemoteCharacteristic->writeValue(exitPacket, 6, false);
    printPacket("[SEND_BLE]", exitPacket, 6);
    Serial.printf("   -> Sent exit request with Tag ID: %d\n", TAG_ID);
}

void printPacket(const char* direction, const uint8_t* data, size_t len) {
    Serial.printf("%s (Len: %d): ", direction, len);
    for (size_t i = 0; i < len; i++) {
        Serial.printf("%02X ", data[i]);
    }
    Serial.println();
}

void updateState(String newState) {
    if (currentState != newState) {
        currentState = newState;
        Serial.printf("\n===== [STATE] %s =====\n", newState.c_str());
        Serial.printf("   Current Flag: %s\n", isEntryVehicle ? "ENTRY" : "EXIT");
    }
}

// GUI 통신 및 트리거 함수들
void sendTriggerToPC() {
    #ifdef USE_GUI
    WiFiClient client;
    Serial.printf("\n[PC Trigger] Connecting to PC server: %s:%d\n", TRIGGER_HOST, TRIGGER_PORT);
    if (!client.connect(TRIGGER_HOST, TRIGGER_PORT)) {
        Serial.println("[PC Trigger] Connection failed.");
        triggerSent = false; // 실패 시 다시 보낼 수 있도록
        return;
    }
    Serial.println("[PC Trigger] Connected to server!");
    StaticJsonDocument<256> doc;
    doc["command"] = "start_simulation";
    doc["vehicle_id"] = VEHICLE_ID;
    String output;
    serializeJson(doc, output);
    client.print(output);
    Serial.print("[PC Trigger] Sent: ");
    Serial.println(output);
    client.stop();
    Serial.println("[PC Trigger] Connection closed.");
    #endif
}

void sendSerialCommandToTagESP(uint8_t tagId) {
    uint8_t command[4];
    command[0] = 20;
    command[1] = 2;
    command[2] = tagId;
    command[3] = 21;
    Serial.printf("\n[UWB] Sending command to set Tag ID to %d...\n", tagId);
    Serial2.write(command, sizeof(command));
}

#ifdef USE_GUI
void handleNewClient(WiFiClient client) {
    Serial.println("\nPC GUI Client connected!");
    while (client.connected()) {
        if (client.available()) {
            String jsonData = client.readString();
            Serial.print("Received Data from GUI: ");
            Serial.println(jsonData);
            StaticJsonDocument<256> doc;
            DeserializationError error = deserializeJson(doc, jsonData);
            if (error) {
                Serial.print("JSON parsing failed: ");
                Serial.println(error.c_str());
                client.println("{\"status\": \"error\", \"message\": \"Invalid JSON\"}");
                break;
            }
            
            // JSON 파싱 (문자열로 받는 경우와 boolean으로 받는 경우 모두 처리)
            String vehicleType = "regular";
            bool isHandicapped = false;
            String spotType = "normal";
            uint8_t destination = 0;
            
            // elec 필드 처리
            if (doc["elec"].is<bool>()) {
                vehicleType = doc["elec"].as<bool>() ? "electric" : "regular";
            } else if (doc["elec"].is<const char*>()) {
                const char* elec_str = doc["elec"];
                vehicleType = (strcmp(elec_str, "true") == 0) ? "electric" : "regular";
            }
            
            // disabled 필드 처리
            if (doc["disabled"].is<bool>()) {
                isHandicapped = doc["disabled"].as<bool>();
            } else if (doc["disabled"].is<const char*>()) {
                const char* disabled_str = doc["disabled"];
                isHandicapped = (strcmp(disabled_str, "true") == 0);
            }
            
            // preferred 필드 처리
            if (doc["preferred"].is<const char*>()) {
                spotType = String(doc["preferred"].as<const char*>());
            }
            
            // destination 필드 처리
            if (doc["destination"].is<int>()) {
                destination = doc["destination"].as<uint8_t>();
            }
            
            onDataReceived(vehicleType, isHandicapped, spotType, destination);
            client.println("{\"status\": \"success\", \"message\": \"Data received by ESP32\"}");
            break;
        }
    }
    client.stop();
    Serial.println("PC GUI Client disconnected.");
}

void handleWaypointClient(WiFiClient client) {
     if (client.available()) {
        String jsonData = client.readString();
        Serial.print("Received Waypoints: ");
        Serial.println(jsonData);
     }
}
#endif
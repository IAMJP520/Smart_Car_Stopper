# 파일명: RSSI_start_laptop.py

import bluetooth
import time
import subprocess
import sys

# --- 설정 ---
# 여기에 실제 라즈베리파이의 블루투스 MAC 주소를 입력하세요.
RPI_MAC_ADDRESS = "2C:CF:67:47:BF:50"
SCAN_INTERVAL = 3  # 3초마다 스캔

def find_rpi():
    """ 주변 블루투스 장치를 스캔하여 라즈베리파이를 찾습니다. """
    print("주변 장치를 스캔하는 중...")
    try:
        # discover_devices는 RSSI 값을 직접 반환하지 않으므로, 장치 발견 여부로 근접성을 판단합니다.
        nearby_devices = bluetooth.discover_devices(duration=4, lookup_names=False, flush_cache=True)
        
        if RPI_MAC_ADDRESS in nearby_devices:
            print(f"라즈베리파이({RPI_MAC_ADDRESS}) 발견! 근접한 것으로 판단합니다.")
            return True
    except Exception as e:
        # 권한 문제 등이 발생할 수 있습니다 (특히 리눅스).
        print(f"스캔 오류: {e}")
        print("블루투스 권한이 올바른지 확인해주세요. (예: sudo python3 RSSI_start_laptop.py)")
        
    return False

def main():
    """ 메인 로직: 라즈베리파이가 발견되면 GUI를 실행합니다. """
    print("노트북(ECU)에서 모니터링을 시작합니다.")
    print(f"타겟 장치: {RPI_MAC_ADDRESS}")

    while True:
        if find_rpi():
            print("GUI 팝업을 실행합니다.")
            try:
                # 'RSSI_ask.py' 스크립트를 별도 프로세스로 실행합니다.
                subprocess.Popen([sys.executable, 'RSSI_ask.py'])
                print("GUI 실행됨. 모니터링을 종료합니다.")
                break  # 한 번 실행 후 종료
            except FileNotFoundError:
                print("오류: 'RSSI_ask.py' 파일을 찾을 수 없습니다. 같은 폴더에 있는지 확인하세요.")
                break
            except Exception as e:
                print(f"GUI 실행 중 오류 발생: {e}")
                break
        else:
            print(f"{SCAN_INTERVAL}초 후 재시도합니다...")

        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    if RPI_MAC_ADDRESS == "XX:XX:XX:XX:XX:XX":
        print("오류: 코드의 'RPI_MAC_ADDRESS' 변수를 실제 라즈베리파이 MAC 주소로 변경해주세요.")
    else:
        main()
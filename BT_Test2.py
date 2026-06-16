import serial
import time
import json
import threading
import socket
from Bridge_App.Library.IPC_Library import IPC_SendPacketWithIPCHeader, parse_hex_data

UART_PORT = '/dev/ttyAMA0' 
BAUD_RATE = 9600
IPC_FILE_PATH = "/dev/tcc_ipc_micom"

# 전역 변수: 중앙 차선 긴급 제동 상태
aeb_triggered = False 

# 하드웨어 연결 초기화
try:
    sndfile = open(IPC_FILE_PATH, 'wb')
    bt_serial = serial.Serial(UART_PORT, BAUD_RATE, timeout=1)
    print("⭕ [H/W] VCP 및 Bluetooth 연결 완료!")
except Exception as e:
    print(f"❌ [H/W] 연결 실패: {e}")
    exit(1)

# ---------------------------------------------------------
# 🧵 백그라운드 스레드: AI 데이터 수신 및 3차선 분석
# ---------------------------------------------------------
def internal_udp_receiver():
    global aeb_triggered
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 5005))
    print("❗[내부 통신] zonal_app으로부터 yolo 데이터 수신 대기 중...")
    
    while True:
        try:
            data, addr = sock.recvfrom(8192)
            result = json.loads(data.decode("utf-8"))
            
            # JSON에서 객체 리스트 추출
            objects = result.get("objects", []) if isinstance(result, dict) else []
            
            # 각 차선별 최단 거리 초기화 (999.0 = 차 없음)
            min_dist_L = 999.0
            min_dist_C = 999.0
            min_dist_R = 999.0
            
            for obj in objects:
                # 1. Y좌표로 박스 높이 계산 ('y_min', 'y_max' 완벽 대응)
                y1 = float(obj.get("y_min", obj.get("ymin", obj.get("y1", 0))))
                y2 = float(obj.get("y_max", obj.get("ymax", obj.get("y2", 0))))
                box_height = abs(y2 - y1)
                
                # 2. X좌표로 차량 가로 위치(중앙값) 계산
                x1 = float(obj.get("x_min", obj.get("xmin", obj.get("x1", 0))))
                x2 = float(obj.get("x_max", obj.get("xmax", obj.get("x2", 0))))
                x_center = (x1 + x2) / 2.0
                
                # 3. 박스 높이를 거리(m)로 환산
                if box_height > 0:
                    dist = max(2.0, 50.0 - (box_height * 0.25)) 
                else:
                    dist = 15.0 
                
                # 4. 차선(ROI) 분류 및 최단 거리 갱신 (해상도 1280 기준)
                if x_center < 500: 
                    if dist < min_dist_L: min_dist_L = dist       # [좌측 차선]
                elif x_center > 780: 
                    if dist < min_dist_R: min_dist_R = dist       # [우측 차선]
                else: 
                    if dist < min_dist_C: min_dist_C = dist       # [내 차선(중앙)]
            
            # 5. 긴급 제동(AEB) 판단: '내 차선'에 있는 차가 5m 이내일 때만 작동!
            if min_dist_C < 5.0: 
                aeb_triggered = True
            else:
                aeb_triggered = False

            # 6. PC 웹 대시보드로 3차선 데이터 전송
            if bt_serial.is_open:
                bt_serial.write(f"RADAR:{min_dist_L:.1f}:{min_dist_C:.1f}:{min_dist_R:.1f}\n".encode('utf-8'))
                
            # (선택) 터미널에서 실시간 데이터 흐름을 보고 싶다면 아래 주석을 해제하세요.
            def fmt(d): return "없음" if d > 100 else f"{d:.1f}m"
            print(f" 레이더 -> 좌:{fmt(min_dist_L)} | 중앙:{fmt(min_dist_C)} | 우:{fmt(min_dist_R)}")

        except Exception as e:
            pass

# 백그라운드 수신 스레드 시작
threading.Thread(target=internal_udp_receiver, daemon=True).start()

# ---------------------------------------------------------
# 🚀 메인 루프: 블루투스 제어 수신 및 VCP 하드웨어 제어
# ---------------------------------------------------------
print("❗ [system] 브릿지 가동 중... (web 연결을 기다립니다)")

try:
    while True:
        # 1순위: 자동 긴급 제동 (AEB)
        if aeb_triggered:
            print("🚨 [AEB] 정면에 차량 접근! 강제 정지!") 
            IPC_SendPacketWithIPCHeader(sndfile, 1, 0, 104, parse_hex_data('00')) # 속도 0
            IPC_SendPacketWithIPCHeader(sndfile, 1, 0, 102, parse_hex_data('01')) # 브레이크등 ON
            time.sleep(0.5) # 0.5초간 수동 조작 무시 (모터 보호)
            continue 

        # 2순위: 수동 웹 제어
        if bt_serial.in_waiting > 0:
            time.sleep(0.05) # 데이터가 다 들어올 때까지 잠깐 대기
            received_data = bt_serial.read(bt_serial.in_waiting).decode('utf-8', errors='ignore').strip()
            
            if received_data:
                print(f"💬CONTROLLER 수신명령: {received_data}")
                parts = received_data.split()
                if len(parts) == 2:
                    try:
                        canID = int(parts[0], 16) 
                        sndDataHex = parts[1]
                        
                        # VCP로 CAN 데이터 전송
                        IPC_SendPacketWithIPCHeader(sndfile, 1, 0, canID, parse_hex_data(sndDataHex))
                        
                        # 속도(104)를 올릴 때는 브레이크등(102)을 끈다
                        if canID == 104 and int(sndDataHex, 16) > 0:
                            IPC_SendPacketWithIPCHeader(sndfile, 1, 0, 102, parse_hex_data('02'))
                    except Exception as e:
                        pass
                        
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n프로그램을 안전하게 종료합니다.")
finally:
    if bt_serial.is_open: bt_serial.close()
    if not sndfile.closed: sndfile.close()
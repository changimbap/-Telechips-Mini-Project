import serial
import time
import json
import threading
import socket
from Bridge_App.Library.IPC_Library import IPC_SendPacketWithIPCHeader, parse_hex_data

UART_PORT = '/dev/ttyAMA0' 
BAUD_RATE = 9600
IPC_FILE_PATH = "/dev/tcc_ipc_micom"
aeb_triggered = False 

try:
    sndfile = open(IPC_FILE_PATH, 'wb')
    bt_serial = serial.Serial(UART_PORT, BAUD_RATE, timeout=1)
    print("🟢 [하드웨어] VCP 및 블루투스 연결 완료!")
except Exception as e:
    exit(1)

def internal_udp_receiver():
    global aeb_triggered
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 5005))
    
    while True:
        try:
            data, addr = sock.recvfrom(8192)
            result = json.loads(data.decode("utf-8"))
            
            # JSON에서 objects 리스트만 쏙 빼옵니다.
            objects = result.get("objects", []) if isinstance(result, dict) else []
            
            car_detected = False
            min_dist = 999.0
            
            for obj in objects:
                car_detected = True 
                
                box_height = 0.0
                
                if "box" in obj and len(obj["box"]) >= 4:
                    box_height = abs(obj["box"][3] - obj["box"][1])
                elif "bbox" in obj and len(obj["bbox"]) >= 4:
                    box_height = abs(obj["bbox"][3] - obj["bbox"][1])
                elif "h" in obj:
                    box_height = float(obj["h"])
                elif "height" in obj:
                    box_height = float(obj["height"])
                else:
                    # 💡 [핵심 수정] 사진에서 확인된 'y_min', 'y_max' 이름표를 정확히 찔러줍니다!
                    y1 = float(obj.get("y_min", obj.get("ymin", obj.get("y1", 0))))
                    y2 = float(obj.get("y_max", obj.get("ymax", obj.get("y2", 0))))
                    box_height = abs(y2 - y1)
                
                if box_height > 0:
                    # 💡 [레이더 민감도 튜닝]
                    # 현재 150px 정도 크기면 꽤 가까운 거리입니다. 
                    # 50m에서 시작해서 박스가 커질수록 거리가 팍팍 줄어들도록 계수를 0.25로 올렸습니다.
                    # (예: 150px * 0.25 = 37.5 -> 50 - 37.5 = 거리 12.5m)
                    dist = max(2.0, 50.0 - (box_height * 0.25)) 
                else:
                    dist = 15.0 
                    
                if dist < min_dist: min_dist = dist
            
            if car_detected:
                print(f"🚗 앞차 발견! (거리: {min_dist:.1f}m, 박스높이: {box_height:.1f}px)") 
                if bt_serial.is_open:
                    bt_serial.write(f"RADAR:car:{min_dist:.1f}\n".encode('utf-8'))
                
                if min_dist < 5.0: 
                    aeb_triggered = True
                else:
                    aeb_triggered = False
            else:
                # 💡 [수정 2] 차가 없어졌을 때 웹 화면을 지우라는 '초기화 신호' 전송!
                if bt_serial.is_open:
                    bt_serial.write("RADAR:none:0\n".encode('utf-8'))
                aeb_triggered = False

        except Exception as e:
            pass

threading.Thread(target=internal_udp_receiver, daemon=True).start()

print("🟢 [시스템] 스마트 브릿지 가동 중...")
try:
    while True:
        if aeb_triggered:
            IPC_SendPacketWithIPCHeader(sndfile, 1, 0, 104, parse_hex_data('00')) 
            IPC_SendPacketWithIPCHeader(sndfile, 1, 0, 102, parse_hex_data('01')) 
            time.sleep(0.5) 
            continue 

        if bt_serial.in_waiting > 0:
            time.sleep(0.05)
            received_data = bt_serial.read(bt_serial.in_waiting).decode('utf-8', errors='ignore').strip()
            if received_data:
                parts = received_data.split()
                if len(parts) == 2:
                    try:
                        canID = int(parts[0], 16) 
                        sndDataHex = parts[1]
                        IPC_SendPacketWithIPCHeader(sndfile, 1, 0, canID, parse_hex_data(sndDataHex))
                    except:
                        pass
        time.sleep(0.01)
except KeyboardInterrupt:
    pass
finally:
    if bt_serial.is_open: bt_serial.close()
    if not sndfile.closed: sndfile.close()
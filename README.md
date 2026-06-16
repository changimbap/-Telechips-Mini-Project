# [팹리스 일경험 프로그램] Telechips 보드 활용 미니 프로젝트
# Zonal Architecture 기반 차량 제어 시스템 고도화 프로젝트

이 저장소는 TOPST 보드(AI-G, D3-G, VCP-G)를 활용하여 Zonal Architecture(영역별 아키텍처)를 구현하고, 기존 교육용 시스템의 한계를 개선한 통합 제어 시스템의 소스 코드를 포함하고 있습니다. 웹 기반의 양방향 대시보드를 통해 인지(Sensing), 판단(HPC), 제어(Control) 파이프라인을 실시간으로 연동합니다.

## 🏗️ System Architecture

시스템은 3개의 Zone으로 나뉘어 구성되며, Ethernet 및 CAN 통신으로 데이터를 교환합니다.

* **Sensing Zone (Front):** `TOPST-AI` 보드 + MIPI 전방 카메라
  * YOLO 모델을 통한 실시간 전방/측면 차량 인식 및 Bounding Box 좌표 추출.
* **HPC Zone (Central):** `TOPST-D3` 보드 + Web Dashboard
  * 수신된 좌표 데이터를 바탕으로 3차선 ROI 분류, 스무딩 연산, AEB(긴급 제동) 판단 로직 수행.
  * Web Serial/Bluetooth API를 활용한 HTML 기반 대시보드 시각화 및 양방향 수동 제어 처리.
* **Control Zone (Rear):** `TOPST-VCP` 보드 + MCU (모터/LED)
  * HPC에서 하달된 CAN(IPC) 16진수 제어 명령 수신 및 하드웨어 즉각 제어 (조향, 가속, 브레이크등).

## ✨ Key Enhancements (주요 개선 사항)

기존 시스템의 한계를 분석하고, 다음과 같은 핵심 알고리즘을 독자적으로 구현하여 시스템을 고도화했습니다.

### 1. 3차선 다중 객체 추적 (ROI Filtering)
* **Problem:** 단일 Bounding Box로는 인접 차선의 차량과 정면 차량을 구분할 수 없어 불필요한 긴급 제동(AEB)이 개입됨.
* **Solution:** X좌표 중앙값을 기준으로 화면을 3분할(좌/중/우)하는 정적 관심 영역(Static ROI) 알고리즘을 적용. 오직 정면(Ego-Lane)에 위치한 차량에만 제동 로직이 개입하도록 정확도 향상.

### 2. 시계열 스무딩 (Temporal Smoothing)
* **Problem:** AI 모델이 조명 등의 요인으로 1~2 프레임 동안 객체를 놓칠 경우, UI 타겟이 심하게 깜빡거리고 '유령 브레이크(Phantom Braking)'가 발생.
* **Solution:** TTL(Time-To-Live) 기반의 Debouncing 알고리즘을 도입. 찰나의 미인식 구간(약 0.2초) 동안 이전 데이터를 메모리에 유지시켜 주행 제어의 신뢰도 확보.

### 3. Zero-Latency 하드웨어 제어 동기화
* **Problem:** 소프트웨어에서 AEB 조건이 성립해도, 10진수 프로토콜 오류 및 OS I/O 버퍼 지연으로 인해 물리적 모터의 정지가 지연됨.
* **Solution:** 모든 CAN ID를 하드웨어 스펙에 맞춘 16진수(`0x104`, `0x102`)로 재정렬. `flush()` 함수를 활용해 버퍼 병목 없이 즉각적으로 모터 동력 차단 및 브레이크등 점등 수행.

### 4. 원근감 스케일링 (Perspective Scaling) 기반 Web UI
* **Problem:** 기존 CLI 방식이나 선형적 렌더링 방식은 거리 왜곡이 심해 상황 인지가 어려움.
* **Solution:** 카메라의 소실점(Vanishing Point) 원리를 수학적으로 UI에 적용. 시각적 가중치(1.6x)를 부여하여 실제 주행 영상과 일치하는 입체적인 대시보드 인터페이스 구현.

## 🛠️ Tech Stack

* **Hardware:** TOPST AI-G, TOPST D3-G, TOPST VCP-G, MIPI CSI Camera, DC Motor
* **Software/Languages:** Python 3, C/C++, HTML5/CSS/JS, Web Serial API
* **Network:** UDP/TCP Socket, CAN, IPC

## 📝 Author
* **정예찬** (2026.05.28)

# mirobot_order_delivery_ros2

## 간단한 소개

주문 색상·수량에 따라 카메라 인식, 미로봇 피킹, 상자 투입과 상태·완료 응답을 처리한다.
로봇 측 프로그램과 domain_bridge 설정만 제공하며 Raspberry Pi 서버나 웹앱은 포함하지 않는다.
기존 자체 시리얼 제어와 좌표 계산을 사용한다.

## 권장 실행 환경

Ubuntu 22.04, ROS2 Humble, Python 3.10을 권장한다.
실제 실행에는 카메라 한 대와 흡착 장치가 있는 미로봇 한 대를 사용한다.
같은 기본 환경에서 빌드·정적 검사를 수행했으며 장비 인식·통신·동작은 미검증 상태이다.

## 시나리오

`fill` 주문은 다음 순서로 처리한다.

1. `/robot/cmd`에서 주문 ID와 색상별 수량을 수신한다.
2. 관측 위치로 이동하여 요청한 색상의 큐브를 인식한다.
3. 픽셀 좌표를 로봇 좌표로 변환하고 흡착하여 상자에 투입한다.
4. 요청 수량만큼 반복한 뒤 관측 위치로 복귀한다.
5. `/robot/status`와 `/robot/done`으로 상태와 완료 정보를 발행한다.

`pack`은 기본 설정에서 완료 응답만 통과시키며 실제 포장 동작을 구현하지 않는다.

## 패키지 구조

| 경로 | 역할 |
| --- | --- |
| `mirobot_order_delivery/mirobot_order_delivery/delivery_node.py` | 주문 큐와 피킹 작업을 처리한다. |
| `mirobot_order_delivery/mirobot_order_delivery/{vision,calibration,geometry,robot_gcode}.py` | 인식·좌표 변환·경로·시리얼 통신을 구현한다. |
| `mirobot_order_delivery/config/order_delivery.yaml` | 카메라·모델·보정·작업 좌표를 지정한다. |
| `mirobot_order_delivery/config/mirobot_domain_bridge.yaml` | 주문·정지 전달과 상태·완료 역방향 전달을 구성한다. |
| `mirobot_order_delivery/launch` | 로봇 단독·브리지 단독·동시 실행을 제공한다. |

## 빌드 및 실행 방법

ROS2 Humble이 설치된 새 터미널에서 다음 순서로 구성한다.

```bash
source /opt/ros/humble/setup.bash
sudo apt install python3-colcon-common-extensions python3-rosdep python3-vcstool python3-venv
mkdir -p ~/mirobot_order_delivery_ws/src
cd ~/mirobot_order_delivery_ws
git clone https://github.com/Jeong-Yun-Kim/mirobot_order_delivery_ros2.git src/mirobot_order_delivery_ros2
rosdep update
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -r src/mirobot_order_delivery_ros2/mirobot_order_delivery/requirements.txt
python -m colcon build
source install/setup.bash
```

`rosdep`을 처음 사용하는 시스템은 `sudo rosdep init`을 먼저 실행한다.

카메라 실행 전에 로컬 YOLOv5 코드와 `red-cube`, `green-cube`, `blue-cube`를 학습한 가중치를 준비한다.
아래 명령은 YOLOv5 코드와 Python 의존성을 준비하며, 가중치는 제공하지 않으므로 사용자가 학습·내보내기한 `best.onnx` 등을 지정한다.
모델과 PyTorch·ONNX Runtime 조합의 실제 추론 호환성은 사용자 모델로 확인한다.

```bash
git clone https://github.com/ultralytics/yolov5.git ~/yolov5
python -m pip install -r ~/yolov5/requirements.txt -r src/mirobot_order_delivery_ros2/mirobot_order_delivery/requirements.txt
```

설정의 `yolo.repo`, `yolo.weight`에 준비한 경로를 지정한다.
카메라는 기본 4, 시리얼은 `/dev/ttyUSB0`·115200이며 장비에 맞춰 변경한다.
기본 동적 변환은 원점 픽셀 (640,360), 로봇 원점 (200,0)mm, 축척 0.20mm/px를 사용하므로 실제 장비에서 측정한 값으로 보정한다.
기본 상자 위치 (0,250,170)mm와 작업 범위, 피킹 보정 (10,5)mm도 확인한다.
정적 보정을 선택하면 `H_inv` 3×3·`T_base_board` 4×4가 있는 외부 NPZ를 `calibration.static_board_path`로 지정하며, 파일 오류를 동적 보정으로 자동 대체하지 않는다.

```bash
cp src/mirobot_order_delivery_ros2/mirobot_order_delivery/config/order_delivery.yaml order.local.yaml
nano order.local.yaml
```

장치 없이 launch 인자만 확인하며, 주문 발행 예시는 실제 로봇 동작을 유발하므로 장비 없는 시험으로 사용하지 않는다.

```bash
ros2 launch mirobot_order_delivery robot_only.launch.py --show-args
ros2 launch mirobot_order_delivery robot_with_bridge.launch.py --show-args
```

실제 로봇 단독 실행은 다음 명령을 사용하며, 이 프로그램에는 dry-run 모드가 없다.

```bash
ros2 launch mirobot_order_delivery robot_only.launch.py params:="$PWD/order.local.yaml" robot_domain:=30
```

외부 서버 domain 18과 로봇 domain 30을 연결할 때는 단독 실행 대신 다음 명령을 사용한다.
브리지만 필요한 경우는 두 번째 명령을 선택한다.

```bash
ros2 launch mirobot_order_delivery robot_with_bridge.launch.py   params:="$PWD/order.local.yaml" server_domain:=18 robot_domain:=30
ros2 launch mirobot_order_delivery bridge_only.launch.py server_domain:=18 robot_domain:=30
```

새 터미널에서 환경을 source하고 다음 주문을 발행하며, 로봇 단독 연결에는 `ROS_DOMAIN_ID=30`, 브리지 경유 서버 측 발행에는 18을 사용한다.

```bash
source /opt/ros/humble/setup.bash
source ~/mirobot_order_delivery_ws/.venv/bin/activate
source ~/mirobot_order_delivery_ws/install/setup.bash
ROS_DOMAIN_ID=30 ros2 run mirobot_order_delivery simulate_order --id 1 --red 1 --green 0 --blue 0
```

같은 시리얼 포트를 사용하는 다른 드라이버는 함께 실행하지 않는다.
펌프 명령·설정된 이동 완료 대기·마지막 관측 위치 복귀가 실패하면 후속 이동과 주문 성공 응답을 중단한다.
실패 원인과 이미 처리한 수량은 `/robot/status`로 알리며, `task.publish_failed_done: true`이면 `/robot/done`에도 `ok: false`로 알린다.
실패·중단 시 자동 복귀나 무조건적인 흡착 해제를 수행하지 않으므로 작업물과 로봇 상태를 확인한 뒤 복구한다.
`motion.use_m400`과 `motion.use_status_wait`는 기본 false를 유지하며, 둘 다 끈 경우의 정착 시간 대기는 실제 완료 확인을 대신하지 않는다.
지원 여부를 확인한 완료 대기 방식을 켠 경우 응답 실패와 시간 초과를 작업 실패로 처리한다.

## 참고 목록

- [Jeong-Yun-Kim/Mirobot_ros2](https://github.com/Jeong-Yun-Kim/Mirobot_ros2)의 소스를 분리하여 사용한다.
- [ultralytics/yolov5](https://github.com/ultralytics/yolov5)를 로컬 `torch.hub` 모델 로딩에 사용한다.
- 기존 파일의 저작권과 라이선스 선언을 보존하며, 상충하거나 미정인 선언은 새 라이선스로 확정하지 않는다.

"""Check failure propagation using transport mocks, never a serial connection."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mirobot_order_delivery.delivery_node import MirobotOrderDeliveryNode
from mirobot_order_delivery.robot_gcode import MirobotGCode, RobotConfig


@pytest.fixture(autouse=True)
def no_devices(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('hardware access is forbidden')
    monkeypatch.setattr('serial.Serial', forbidden)
    monkeypatch.setattr('cv2.VideoCapture', forbidden)
    monkeypatch.setattr('time.sleep', lambda _: None)


def robot():
    device = MirobotGCode(RobotConfig())
    device.move_xyz = Mock(return_value=True)
    device.wait_motion_done = Mock(return_value=True)
    device.pump_on = Mock(return_value=True)
    device.pump_off = Mock(return_value=True)
    return device


def pick(device):
    return device.pick_and_place((200, 0, 55), (240, 0, 60), travel_z=120, n_points=3)


@pytest.mark.parametrize('failed_pump', ['pump_on', 'pump_off'])
def test_pump_failure_aborts_without_next_motion(failed_pump):
    device = robot()
    counts = []
    def fail():
        counts.append(device.move_xyz.call_count)
        return False
    getattr(device, failed_pump).side_effect = fail
    assert pick(device) is False
    assert device.move_xyz.call_count == counts[0]
    assert failed_pump in device.last_error


def test_motion_wait_failure_prevents_pick_and_pump():
    device = robot()
    device.wait_motion_done.return_value = False
    assert pick(device) is False
    assert device.move_xyz.call_count == 1
    device.pump_on.assert_not_called()


@pytest.mark.parametrize('kind', ['m400', 'missing_status', 'hold', 'timeout'])
def test_configured_wait_propagates_failure(kind, monkeypatch):
    device = MirobotGCode(RobotConfig(use_m400=kind == 'm400', use_status_wait=kind != 'm400'))
    device.send_and_wait = Mock(return_value=False)
    device.query_status_pose = Mock(return_value=(kind != 'missing_status', 'Hold' if kind == 'hold' else 'Run', None, None, ''))
    ticks = iter([0.0, 0.0, 2.0, 3.0])
    monkeypatch.setattr('time.monotonic', lambda: next(ticks))
    assert device.wait_motion_done(timeout=1.0) is False


def delivery():
    node = MirobotOrderDeliveryNode.__new__(MirobotOrderDeliveryNode)
    node.stats = SimpleNamespace()
    node.stop_event = threading.Event()
    node.shutdown_event = threading.Event()
    node.order_cancelled = threading.Event()
    node.robot = robot()
    node.robot_cfg = node.robot.cfg
    node.observe_xyz = (200, 0, 220)
    node.order_sequence = ['red', 'green', 'blue']
    node.publish_status = Mock()
    node.publish_done = Mock()
    node.get_logger = Mock(return_value=Mock())
    node.ensure_hardware_ready = Mock()
    node.return_to_observe_after_each_cube = False
    node.find_pick_pose = Mock(return_value=(200, 0, 55))
    node.compute_box_pose = Mock(return_value=(240, 0, 60))
    node.travel_z = 120
    node.box_approach_z = 120
    node.motion_arc_points = 3
    node.publish_failed_done = True
    return node


@pytest.mark.parametrize('pump', ['pump_on', 'pump_off'])
def test_pump_failure_never_counts_cube_or_reports_order_success(pump):
    node = delivery()
    getattr(node.robot, pump).return_value = False
    node.execute_command({'id': 1, 'red': 1})
    result = node.publish_done.call_args.kwargs
    assert result['ok'] is False and result['delivered']['red'] == 0
    assert all(call.kwargs.get('ok') is not True for call in node.publish_done.call_args_list)


@pytest.mark.parametrize('wait_failed', [False, True])
def test_last_return_failure_preserves_counts_but_never_reports_success(wait_failed):
    node = delivery()
    node.robot.pick_and_place = Mock(return_value=True)
    if wait_failed:
        node.robot.wait_motion_done.side_effect = [True, False]
    else:
        node.robot.move_xyz.side_effect = [True, False]
    node.execute_command({'id': 1, 'red': 1})
    result = node.publish_done.call_args.kwargs
    assert result['ok'] is False and result['delivered']['red'] == 1
    assert result['phase'] == 'final_return'
    assert node.robot.move_xyz.call_count == 2


def test_normal_order_sequence_and_pack_behavior_stay_separate():
    node = delivery()
    node.robot.pick_and_place = Mock(return_value=True)
    node.execute_command({'id': 1, 'red': 2})
    assert node.publish_done.call_args.kwargs['ok'] is True
    assert node.publish_done.call_args.kwargs['delivered']['red'] == 2


def test_stop_during_drop_dwell_prevents_release_and_return(monkeypatch):
    device = robot()
    stopped = threading.Event()
    device.cfg.drop_dwell_s = 0.4
    monkeypatch.setattr('time.sleep', lambda delay: stopped.set() if delay == 0.4 else None)
    assert device.pick_and_place((200, 0, 55), (240, 0, 60), travel_z=120, n_points=3,
                                 should_stop=stopped.is_set) is False
    device.pump_off.assert_not_called()

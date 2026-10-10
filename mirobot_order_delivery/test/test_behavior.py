from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from mirobot_order_delivery.calibration import PixelToRobotMapper
from mirobot_order_delivery.delivery_node import MirobotOrderDeliveryNode
from mirobot_order_delivery.vision import YoloCubeDetector


def test_dynamic_mapping_and_missing_static_calibration():
    mapper = PixelToRobotMapper(fallback_mm_per_px=0.2)
    mapper.load()
    assert mapper.pixel_to_base_xy(650, 370) == (198.0, -2.0)
    mapper.use_static = True
    mapper.static_board_path = '/nonexistent/mirobot-test.npz'
    with pytest.raises(FileNotFoundError):
        mapper.load()


def test_order_sequence_and_empty_assets_without_devices():
    state = SimpleNamespace(order_sequence=['red', 'green', 'blue'])
    counts = MirobotOrderDeliveryNode.extract_counts(state, {'red': 2, 'green': -1, 'blue': 1})
    assert MirobotOrderDeliveryNode.build_color_sequence(state, counts) == ['red', 'red', 'blue']
    with patch('cv2.VideoCapture', side_effect=AssertionError('camera access')), \
         patch('serial.Serial', side_effect=AssertionError('serial access')):
        with pytest.raises(FileNotFoundError):
            YoloCubeDetector('', '').load()


def test_pack_is_only_a_response_passthrough():
    state = SimpleNamespace(stats=SimpleNamespace(), pack_passthrough=True,
                            publish_status=Mock(), publish_done=Mock(), ensure_hardware_ready=Mock())
    MirobotOrderDeliveryNode.execute_command(state, {'task': 'pack', 'id': 3})
    state.ensure_hardware_ready.assert_not_called()
    state.publish_done.assert_called_once_with('pack', 3, ok=True, note='pack passthrough')

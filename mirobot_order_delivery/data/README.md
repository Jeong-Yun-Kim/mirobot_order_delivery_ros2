정적 보정 모드는 측정한 `H_inv` 3×3 행렬과 `T_base_board` 4×4 행렬을 담은 NPZ 파일을 사용한다.
보정 파일은 이 패키지에 포함하지 않으며 `calibration.static_board_path`로 지정한다.
동적 모드는 `calibration.fallback_*`와 회전각을 실제 장비에 맞춰 측정한 뒤 사용한다.

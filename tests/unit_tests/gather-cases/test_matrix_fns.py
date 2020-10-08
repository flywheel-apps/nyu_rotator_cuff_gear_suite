import numpy as np
import pytest
from gears.gather_cases.utils.manage_cases import (
    InvalidWCSStringERROR,
    change_world_coordinate_system,
    create_ijk_to_WCS_matrix,
)

WCS_DATA = {
    "LPS": np.diag([1, 1, 1, 1]),
    "LAS": np.diag([1, -1, 1, 1]),
    "LPI": np.diag([1, 1, -1, 1]),
    "LAI": np.diag([1, -1, -1, 1]),
    "RPS": np.diag([-1, 1, 1, 1]),
    "RAS": np.diag([-1, -1, 1, 1]),
    "RPI": np.diag([-1, 1, -1, 1]),
    "RAI": np.diag([-1, -1, -1, 1]),
}

N = 28
MATRIX_DATA = {
    # ImageOrientationPatient
    "ImageOrientation": np.array(
        [
            -0.6097571277536,
            0.6550876413628,
            0.44615740191932,
            -0.3149489187547,
            0.31629830220925,
            -0.8948533749139,
        ]
    ),
    # ImagePositionPatient
    "ImagePosition": {
        1: np.array([-87.957725792268, -140.59588537377, 47.761223406088]),
        2: np.array([-85.557548790315, -138.33155737084, 47.716825187695]),
        N: np.array([-23.152969627717, -79.459024526301, 46.562471747887]),
    },
    "PixelSpacing": np.array([0.4375, 0.4375]),
}


def test_world_coordinate_system():
    for k, v in WCS_DATA.items():
        assert v == change_world_coordinate_system(k)


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
    "WCS": "LPS",
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
    "VoxelStart": np.array([142.15722120658137, 128.7020109689214, 11.0]),
    "VoxelEnd": np.array([220.54844606946983, 165.55758683729434, 11.0]),
    "WCS_Start": np.array([-120.20618, -61.17000, 24.99548, 1.0]),
    "WCS_End": np.array([-146.19684, -33.60292, 25.86807, 1.0]),
}


def test_world_coordinate_system():
    for k, v in WCS_DATA.items():
        assert np.all(v == change_world_coordinate_system(k))


def test_bad_WCS_code():
    WCS = "LPH"
    try:
        mat = change_world_coordinate_system(WCS)
    except InvalidWCSStringERROR as e:
        assert e.message == "Invalid WCS String. Check and try again."
    else:
        assert False  # Fail

    WCS = "LPIR"
    try:
        mat = change_world_coordinate_system(WCS)
    except InvalidWCSStringERROR as e:
        assert e.message == "Invalid WCS String. Check and try again."
    else:
        assert False  # Fail

    WCS = "LP"
    try:
        mat = change_world_coordinate_system(WCS)
    except InvalidWCSStringERROR as e:
        assert e.message == "Invalid WCS String. Check and try again."
    else:
        assert False  # Fail


def test_apply_matrix():
    voxel_start = np.ones((4,))
    voxel_end = np.ones((4,))
    # Offsets to turn ohif, one-indexed coordinates to zero and then 1/2-voxel indexed
    # 1/2-voxel indexed makes the center of the origin voxel map to the origin of the
    # patient space.
    one_index_offset = np.array([1.0, 1.0, 1.0]).reshape((3,))
    half_voxel_offest = np.array([0.5, 0.5, 0.5]).reshape((3,))
    offset = one_index_offset + half_voxel_offest

    voxel_start[:3] = MATRIX_DATA["VoxelStart"] - offset
    voxel_end[:3] = MATRIX_DATA["VoxelEnd"] - offset

    WCS = MATRIX_DATA["WCS"]
    ImageOrientation = MATRIX_DATA["ImageOrientation"]
    ImagePosition = MATRIX_DATA["ImagePosition"]
    PixelSpacing = MATRIX_DATA["PixelSpacing"]

    ijk_WCS_matrix = create_ijk_to_WCS_matrix(
        WCS, ImageOrientation, ImagePosition, PixelSpacing
    )

    wcs_start = np.matmul(ijk_WCS_matrix, voxel_start)
    wcs_end = np.matmul(ijk_WCS_matrix, voxel_end)

    assert np.linalg.norm(wcs_start - MATRIX_DATA["WCS_Start"]) < 0.0001
    assert np.linalg.norm(wcs_end - MATRIX_DATA["WCS_End"]) < 0.0001

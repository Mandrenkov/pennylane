# Copyright 2018-2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utility functions for circuit optimization."""

from pennylane import numpy as np


def yzy_to_zyz(y1, z, y2):
    """Converts a set of angles representing a sequence of rotations RY, RZ, RY into
    an equivalent sequence of the form RZ, RY, RZ.

    Any rotation in 3-dimensional space (or, equivalently, any single-qubit unitary)
    can be expressed as a sequence of rotations about 3 axes in 12 different ways.
    Typically, the arbitrary single-qubit rotation is expressed as RZ(a) RY(b) RZ(c),
    but there are some situations, e.g., composing two such rotations, where we need
    to convert between representations. This function converts the angles of a sequence

    .. math::

       RY(y_1) RZ(z) RY(y_2)

    into the form

    .. math::

       RZ(z_1) RY(y) RZ(z_2)

    This is accomplished by first converting the rotation to quaternion form, and then
    extracting the desired set of angles.

    Args:
        y1 (float): The angle of the first ``RY`` rotation.
        z (float): The angle of the inner ``RZ`` rotation.
        y2 (float): The angle of the second ``RY`` rotation.

    Returns:
        (float, float, float): A tuple of rotation angles in the ZYZ representation.
    """
    # print([y1, z, y2])
    # Catch the case where everything is close to 0
    # if np.allclose([y1, z, y2], [0.0, 0.0, 0.0]):
    #    return (0.0, 0.0, 0.0)

    # First, compute the quaternion representation
    # https://ntrs.nasa.gov/api/citations/19770024290/downloads/19770024290.pdf
    qw = np.cos(z / 2) * np.cos(0.5 * (y1 + y2))
    qx = np.sin(z / 2) * np.sin(0.5 * (y1 - y2))
    qy = np.cos(z / 2) * np.sin(0.5 * (y1 + y2))
    qz = np.sin(z / 2) * np.cos(0.5 * (y1 - y2))

    # Now convert from YZY Euler angles to ZYZ angles
    # Source: http://bediyap.com/programming/convert-quaternion-to-euler-rotations/
    z1_arg1 = 2 * (qy * qz - qw * qx)
    z1_arg2 = 2 * (qx * qz + qw * qy)
    z1 = np.arctan2(z1_arg1, z1_arg2)

    y = np.arccos(qw ** 2 - qx ** 2 - qy ** 2 + qz ** 2)

    z2_arg1 = 2 * (qy * qz + qw * qx)
    z2_arg2 = -2 * (qx * qz - qw * qy)
    z2 = np.arctan2(z2_arg1, z2_arg2)

    return (z1, y, z2)


def fuse_rot(angles_1, angles_2):
    """Computed the set of rotation angles that is obtained when composing
    two ``qml.Rot`` operations.

    The ``qml.Rot`` operation represents the most general single-qubit operation.
    Two such operations can be fused into a new operation, however the angular dependence
    is non-trivial.

    Args:
        angles_1 (float): A set of three angles for the first ``qml.Rot`` operation.
        angles_2 (float): A set of three angles for the second ``qml.Rot`` operation.

    Returns:
        array[float]: A tuple of rotation angles for a single ``qml.Rot`` operation
        that implements the same operation as the two sets of input angles.
    """
    # RZ(a) RY(b) RZ(c) fused with RZ(d) RY(e) RZ(f)
    # first produces RZ(a) RY(b) RZ(c+d) RY(e) RZ(f)
    leftmost_z_init = angles_1[0]
    middle_yzy = angles_1[1], angles_1[2] + angles_2[0], angles_2[1]
    rightmost_z_init = angles_2[2]

    # Now we need to turn the RY(b) RZ(c+d) RY(e) into something
    # of the form RZ(u) RY(v) RZ(w)
    u, v, w = yzy_to_zyz(*middle_yzy)

    # Then we can combine to create
    # RZ(a + u) RY(v) RZ(w + f)
    return np.array([leftmost_z_init + u, v, w + rightmost_z_init])


def convert_to_rot(op):
    """Converts a single-qubit operation to a Rot gate.

    It would be nice if this information was built-in to the operations instead of
    included here as a separate method.

    Args:
        op (qml.Operation): A single-qubit operation.

    Returns:
        list[float]: A tuple of 3 angles representing the parameters required to
        implement the given gate as an instance of ``qml.Rot``.
    """

    if op.name == "Hadamard":
        return [np.pi, np.pi / 2, 0.0]

    if op.name == "PauliX":
        return [np.pi / 2, np.pi, -np.pi / 2]

    if op.name == "PauliY":
        return [0.0, np.pi, 0.0]

    if op.name == "PauliZ":
        return [np.pi, 0.0, 0.0]

    if op.name == "S":
        return [np.pi / 2, 0.0, 0.0]

    if op.name == "T":
        return [np.pi / 4, 0.0, 0.0]

    if op.name == "RX":
        return [np.pi / 2, op.parameters[0], -np.pi / 2]

    if op.name == "RY":
        return [0.0, op.parameters[0], 0.0]

    if op.name == "RZ" or op.name == "PhaseShift":
        return [op.parameters[0], 0.0, 0.0]

    return None

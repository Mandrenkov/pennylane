# Copyright 2018-2022 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Unit tests for functions needed for computing the dipole.
"""
import autograd
import pennylane as qml
import pytest
from pennylane import Identity, PauliX, PauliY, PauliZ
from pennylane import numpy as np
from pennylane.hf.dipole import (
    dipole_integrals,
    dipole_moment,
    fermionic_dipole,
    fermionic_one,
    qubit_operator,
)
from pennylane.hf.molecule import Molecule


@pytest.mark.parametrize(
    ("symbols", "geometry", "charge", "core", "active", "core_ref", "int_ref"),
    [
        (
            ["H", "H", "H"],
            np.array(
                [[0.028, 0.054, 0.0], [0.986, 1.610, 0.0], [1.855, 0.002, 0.0]], requires_grad=False
            ),
            1,
            None,
            None,
            [0.000, 0.000, 0.000],  # computed with PL-QChem dipole function
            # computed with PL-QChem dipole function using OpenFermion and PySCF
            np.array(
                [
                    [
                        [0.95622463, 0.7827277, -0.53222294],
                        [0.7827277, 1.42895581, 0.23469918],
                        [-0.53222294, 0.23469918, 0.48381955],
                    ],
                    [
                        [0.55538736, -0.53229398, -0.78262324],
                        [-0.53229398, 0.3203965, 0.47233426],
                        [-0.78262324, 0.47233426, 0.79021614],
                    ],
                    [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
                ]
            ),
        ),
        (
            ["H", "H", "H"],
            np.array(
                [[0.028, 0.054, 0.0], [0.986, 1.610, 0.0], [1.855, 0.002, 0.0]], requires_grad=True
            ),
            1,
            [0],
            [1, 2],
            # computed manually from data obtained with PL-QChem dipole function
            [2 * 0.95622463, 2 * 0.55538736, 0.000],
            # computed manually from data obtained with PL-QChem dipole function
            np.array(
                [
                    [
                        [1.42895581, 0.23469918],
                        [0.23469918, 0.48381955],
                    ],
                    [
                        [0.3203965, 0.47233426],
                        [0.47233426, 0.79021614],
                    ],
                    [[0.0, 0.0], [0.0, 0.0]],
                ]
            ),
        ),
    ],
)
def test_dipole_integrals(symbols, geometry, charge, core, active, core_ref, int_ref):
    r"""Test that generate_electron_integrals returns the correct values."""
    mol = Molecule(symbols, geometry, charge=charge)
    args = [p for p in [geometry] if p.requires_grad]
    constants, integrals = dipole_integrals(mol, core=core, active=active)(*args)

    for i in range(3):  # loop on x, y, z components
        assert np.allclose(constants[i], core_ref[i])
        assert np.allclose(integrals[i], int_ref[i])


@pytest.mark.parametrize(
    ("symbols", "geometry", "charge", "core", "active", "f_ref"),
    [
        (
            ["H", "H", "H"],
            np.array(
                [[0.028, 0.054, 0.0], [0.986, 1.610, 0.0], [1.855, 0.002, 0.0]], requires_grad=False
            ),
            1,
            None,
            None,
            # x component of fermionic dipole computed with PL-QChem dipole (format is modified:
            # the signs of the coefficients, except that from the nuclear contribution, is flipped.
            (
                np.array(
                    [
                        2.869,
                        -0.956224634652776,
                        -0.782727697897828,
                        0.532222940905614,
                        -0.956224634652776,
                        -0.782727697897828,
                        0.532222940905614,
                        -0.782727697897828,
                        -1.42895581236226,
                        -0.234699175620383,
                        -0.782727697897828,
                        -1.42895581236226,
                        -0.234699175620383,
                        0.532222940905614,
                        -0.234699175620383,
                        -0.483819552892797,
                        0.532222940905614,
                        -0.234699175620383,
                        -0.483819552892797,
                    ]
                ),
                [
                    [],
                    [0, 0],
                    [0, 2],
                    [0, 4],
                    [1, 1],
                    [1, 3],
                    [1, 5],
                    [2, 0],
                    [2, 2],
                    [2, 4],
                    [3, 1],
                    [3, 3],
                    [3, 5],
                    [4, 0],
                    [4, 2],
                    [4, 4],
                    [5, 1],
                    [5, 3],
                    [5, 5],
                ],
            ),
        ),
        (
            ["H", "H", "H"],
            np.array(
                [[0.028, 0.054, 0.0], [0.986, 1.610, 0.0], [1.855, 0.002, 0.0]], requires_grad=False
            ),
            1,
            [0],
            [1, 2],
            # x component of fermionic dipole computed with PL-QChem dipole (format is modified:
            # the signs of the coefficients, except that from the nuclear contribution, is flipped.
            (
                np.array(
                    [
                        2.869,
                        -1.912449269305551,
                        -1.4289558123627388,
                        -0.2346991756194219,
                        -1.4289558123627388,
                        -0.2346991756194219,
                        -0.2346991756194219,
                        -0.48381955289231976,
                        -0.2346991756194219,
                        -0.48381955289231976,
                    ]
                ),
                [
                    [],
                    [],
                    [0, 0],
                    [0, 2],
                    [1, 1],
                    [1, 3],
                    [2, 0],
                    [2, 2],
                    [3, 1],
                    [3, 3],
                ],
            ),
        ),
    ],
)
def test_fermionic_dipole(symbols, geometry, core, charge, active, f_ref):
    r"""Test that generate_electron_integrals returns the correct values."""
    mol = Molecule(symbols, geometry, charge=charge)
    args = [p for p in [geometry] if p.requires_grad]
    f = fermionic_dipole(mol, core=core, active=active)(*args)[0]

    assert np.allclose(f[0], f_ref[0])  # fermionic coefficients
    assert f[1] == f_ref[1]  # fermionic operators


@pytest.mark.parametrize(
    ("symbols", "geometry", "charge", "core", "active", "coeffs", "ops"),
    [
        (
            ["H", "H"],
            np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]], requires_grad=False),
            0,
            None,
            None,
            # coefficients and operators of the dipole observable computed with
            # PL-QChem dipole function using OpenFermion and PySCF
            np.array([0.5, 0.5, -0.5640321, -0.5640321, -0.5640321, -0.5640321, 0.5, 0.5]),
            [
                PauliZ(wires=[0]),
                PauliZ(wires=[1]),
                PauliY(wires=[0]) @ PauliZ(wires=[1]) @ PauliY(wires=[2]),
                PauliX(wires=[0]) @ PauliZ(wires=[1]) @ PauliX(wires=[2]),
                PauliY(wires=[1]) @ PauliZ(wires=[2]) @ PauliY(wires=[3]),
                PauliX(wires=[1]) @ PauliZ(wires=[2]) @ PauliX(wires=[3]),
                PauliZ(wires=[2]),
                PauliZ(wires=[3]),
            ],
        ),
    ],
)
def test_dipole_moment(symbols, geometry, core, charge, active, coeffs, ops):
    r"""Test that generate_electron_integrals returns the correct values."""
    mol = Molecule(symbols, geometry, charge=charge)
    args = [p for p in [geometry] if p.requires_grad]
    d = dipole_moment(mol, core=core, active=active, cutoff=1.0e-8)(*args)[0]
    d_ref = qml.Hamiltonian(coeffs, ops)

    assert np.allclose(sorted(d.coeffs), sorted(d_ref.coeffs))
    assert qml.Hamiltonian(np.ones(len(d.coeffs)), d.ops).compare(
        qml.Hamiltonian(np.ones(len(d_ref.coeffs)), d_ref.ops)
    )


@pytest.mark.parametrize(
    ("symbols", "geometry", "charge", "core", "active", "d_ref"),
    [
        (
            ["H", "H", "H"],
            np.array(
                [[0.028, 0.054, 0.0], [0.986, 1.610, 0.0], [1.855, 0.002, 0.0]], requires_grad=False
            ),
            1,
            None,
            None,
            [0.95655073, 0.55522528, 0.0],  # x, y, z components of the dipole moment from PL-QChem
        ),
    ],
)
def test_expvalD(symbols, geometry, core, charge, active, d_ref):
    r"""Test that expval(D) is correct."""
    mol = Molecule(symbols, geometry)
    args = []
    dev = qml.device("default.qubit", wires=6)

    def dipole(mol, idx):
        @qml.qnode(dev)
        def circuit(*args):
            qml.PauliX(0)
            qml.PauliX(1)
            qml.DoubleExcitation(0.0, wires=[0, 1, 2, 3])
            qml.DoubleExcitation(0.0, wires=[0, 1, 4, 5])
            d_qubit = dipole_moment(mol)(*args)[idx]
            return qml.expval(d_qubit)

        return circuit

    for i in range(3):  # loop on x, y, z components
        d = dipole(mol, i)(*args)
        assert np.allclose(d, d_ref[i])


def test_gradient_expvalD():
    r"""Test that the gradient of expval(D) computed with ``autograd.grad`` is equal to the value
    obtained with the finite difference method."""
    symbols = ["H", "H", "H"]
    geometry = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 0.0], [2.0, 0.0, 0.0]], requires_grad=False)
    alpha = np.array(
        [
            [3.42525091, 0.62391373, 0.1688554],
            [3.42525091, 0.62391373, 0.1688554],
            [3.42525091, 0.62391373, 0.1688554],
        ],
        requires_grad=True,
    )

    mol = Molecule(symbols, geometry, charge=1, alpha=alpha)
    args = [mol.alpha]
    dev = qml.device("default.qubit", wires=6)

    def dipole(mol):
        @qml.qnode(dev)
        def circuit(*args):
            qml.PauliX(0)
            qml.PauliX(1)
            qml.DoubleExcitation(0.0, wires=[0, 1, 2, 3])
            qml.DoubleExcitation(0.0, wires=[0, 1, 4, 5])
            d_qubit = dipole_moment(mol)(*args)
            return qml.expval(d_qubit[0])

        return circuit

    grad_autograd = autograd.grad(dipole(mol))(*args)

    alpha_1 = np.array(
        [
            [3.42515091, 0.62391373, 0.1688554],
            [3.42525091, 0.62391373, 0.1688554],
            [3.42525091, 0.62391373, 0.1688554],
        ],
        requires_grad=False,
    )  # alpha[0][0] -= 0.0001

    alpha_2 = np.array(
        [
            [3.42535091, 0.62391373, 0.1688554],
            [3.42525091, 0.62391373, 0.1688554],
            [3.42525091, 0.62391373, 0.1688554],
        ],
        requires_grad=False,
    )  # alpha[0][0] += 0.0001

    d_1 = dipole(mol)(*[alpha_1])
    d_2 = dipole(mol)(*[alpha_2])

    grad_finitediff = (d_2 - d_1) / 0.0002

    assert np.allclose(grad_autograd[0][0], grad_finitediff)


@pytest.mark.parametrize(
    ("core_constant", "integral", "f_ref"),
    [
        (
            np.array([2.869]),
            np.array(
                [
                    [0.95622463, 0.7827277, -0.53222294],
                    [0.7827277, 1.42895581, 0.23469918],
                    [-0.53222294, 0.23469918, 0.48381955],
                ]
            ),
            # computed with PL-QChem dipole (format is modified)
            (
                np.array(
                    [
                        2.869,
                        0.956224634652776,
                        0.782727697897828,
                        -0.532222940905614,
                        0.956224634652776,
                        0.782727697897828,
                        -0.532222940905614,
                        0.782727697897828,
                        1.42895581236226,
                        0.234699175620383,
                        0.782727697897828,
                        1.42895581236226,
                        0.234699175620383,
                        -0.532222940905614,
                        0.234699175620383,
                        0.483819552892797,
                        -0.532222940905614,
                        0.234699175620383,
                        0.483819552892797,
                    ]
                ),
                [
                    [],
                    [0, 0],
                    [0, 2],
                    [0, 4],
                    [1, 1],
                    [1, 3],
                    [1, 5],
                    [2, 0],
                    [2, 2],
                    [2, 4],
                    [3, 1],
                    [3, 3],
                    [3, 5],
                    [4, 0],
                    [4, 2],
                    [4, 4],
                    [5, 1],
                    [5, 3],
                    [5, 5],
                ],
            ),
        ),
    ],
)
def test_fermionic_one(core_constant, integral, f_ref):
    r"""Test that fermionic_one returns the correct fermionic observable."""
    f = fermionic_one(core_constant, integral)

    assert np.allclose(f[0], f_ref[0])  # fermionic coefficients
    assert f[1] == f_ref[1]  # fermionic operators


@pytest.mark.parametrize(
    ("f_operator", "q_operator"),
    [
        (
            (np.array([1.0]), [[0, 0]]),
            # obtained with openfermion: jordan_wigner(FermionOperator('0^ 0', 1)) and reformatted
            [[0.5 + 0j, -0.5 + 0j], [qml.Identity(0), qml.PauliZ(0)]],
        ),
        (
            (np.array([1.0, 1.0]), [[0, 0], [0, 0]]),
            # obtained with openfermion: jordan_wigner(FermionOperator('0^ 0', 1)) and reformatted
            [[1.0 + 0j, -1.0 + 0j], [qml.Identity(0), qml.PauliZ(0)]],
        ),
        (
            (np.array([1.0]), [[2, 0, 2, 0]]),
            # obtained with openfermion: jordan_wigner(FermionOperator('0^ 0', 1)) and reformatted
            [
                [-0.25 + 0j, 0.25 + 0j, -0.25 + 0j, 0.25 + 0j],
                [qml.Identity(0), qml.PauliZ(0), qml.PauliZ(0) @ qml.PauliZ(2), qml.PauliZ(2)],
            ],
        ),
        (
            (np.array([1.0, 1.0]), [[2, 0, 2, 0], [2, 0]]),
            # obtained with openfermion: jordan_wigner(FermionOperator('0^ 0', 1)) and reformatted
            [
                [-0.25 + 0j, 0.25 + 0j, -0.25j, 0.25j, 0.25 + 0j, 0.25 + 0j, -0.25 + 0j, 0.25 + 0j],
                [
                    qml.Identity(0),
                    qml.PauliX(0) @ qml.PauliZ(1) @ qml.PauliX(2),
                    qml.PauliX(0) @ qml.PauliZ(1) @ qml.PauliY(2),
                    qml.PauliY(0) @ qml.PauliZ(1) @ qml.PauliX(2),
                    qml.PauliY(0) @ qml.PauliZ(1) @ qml.PauliY(2),
                    qml.PauliZ(0),
                    qml.PauliZ(0) @ qml.PauliZ(2),
                    qml.PauliZ(2),
                ],
            ],
        ),
    ],
)
def test_qubit_operator(f_operator, q_operator):
    r"""Test that qubit_operator returns the correct operator."""
    h = qubit_operator(f_operator)
    h_ref = qml.Hamiltonian(q_operator[0], q_operator[1])

    assert h.compare(h_ref)

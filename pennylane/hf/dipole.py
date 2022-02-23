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
This module contains the functions needed for computing the dipole moment.
"""
import autograd.numpy as anp
import pennylane as qml
from pennylane import numpy as np
from pennylane.hf.basis_data import atomic_numbers
from pennylane.hf.hamiltonian import _generate_qubit_operator, _return_pauli, simplify
from pennylane.hf.matrices import moment_matrix


def dipole_integrals(mol, core=None, active=None):
    r"""Return a function that computes the dipole moment integrals over the molecular orbitals.

    These integrals are required to construct the dipole operator in the second-quantized form

    .. math::

        \hat{D} = -\sum_{pq} d_{pq} [\hat{c}_{p\uparrow}^\dagger \hat{c}_{q\uparrow} +
        \hat{c}_{p\downarrow}^\dagger \hat{c}_{q\downarrow}] -
        \hat{D}_\mathrm{c} + \hat{D}_\mathrm{n},

    where the coefficients :math:`d_{pq}` are given by the integral of the position operator
    :math:`\hat{{\bf r}}` over molecular orbitals
    :math:`\phi`

    .. math::

        d_{pq} = \int \phi_p^*(r) \hat{{\bf r}} \phi_q(r) dr,

    and :math:`\hat{c}^{\dagger}` and :math:`\hat{c}` are the creation and annihilation operators,
    respectively. The contribution of the core orbitals and nuclei are denoted by
    :math:`\hat{D}_\mathrm{c}` and :math:`\hat{D}_\mathrm{n}`, respectively.

    The molecular orbitals are represented as a linear combination of atomic orbitals as

    .. math::

        \phi_i(r) = \sum_{\nu}c_{\nu}^i \chi_{\nu}(r).

    Using this equation the dipole moment integral :math:`d_{pq}` can be written as

    .. math::

        d_{pq} = \sum_{\mu \nu} C_{p \mu} d_{\mu \nu} C_{\nu q},

    where :math:`d_{\mu \nu}` is the dipole moment integral over the atomic orbitals and :math:`C`
    is the molecular orbital expansion coefficient matrix. The contribution of the core molecular
    orbitals is computed as

    .. math::

        \hat{D}_\mathrm{c} = 2 \sum_{i=1}^{N_\mathrm{core}} d_{ii},

    where :math:`N_\mathrm{core}` is the number of core orbitals.

    Args:
        mol (Molecule): the molecule object
        core (list[int]): indices of the core orbitals
        active (list[int]): indices of the active orbitals

    Returns:
        function: function that computes the dipole moment integrals in the molecular orbital basis

    **Example**

    >>> symbols  = ['H', 'H']
    >>> geometry = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], requires_grad = False)
    >>> alpha = np.array([[3.42525091, 0.62391373, 0.1688554],
    >>>                   [3.42525091, 0.62391373, 0.1688554]], requires_grad=True)
    >>> mol = qml.hf.Molecule(symbols, geometry, alpha=alpha)
    >>> args = [alpha]
    >>> constants, integrals = dipole_integrals(mol)(*args)
    >>> print(integrals)
    (array([[0., 0.],
            [0., 0.]]),
     array([[0., 0.],
            [0., 0.]]),
     array([[ 0.5      , -0.8270995],
            [-0.8270995,  0.5      ]]))
    """

    def _dipole_integrals(*args):
        r"""Compute the dipole moment integrals in the molecular orbital basis.

        Args:
            args (array[array[float]]): initial values of the differentiable parameters

        Returns:
            tuple[array[float]]: tuple containing the core orbital contributions and the dipole
            moment integrals
        """
        _, coeffs, _, _, _ = qml.hf.generate_scf(mol)(*args)

        # x, y, z components
        d_x = anp.einsum(
            "qr,rs,st->qt", coeffs.T, moment_matrix(mol.basis_set, 1, 0)(*args), coeffs
        )
        d_y = anp.einsum(
            "qr,rs,st->qt", coeffs.T, moment_matrix(mol.basis_set, 1, 1)(*args), coeffs
        )
        d_z = anp.einsum(
            "qr,rs,st->qt", coeffs.T, moment_matrix(mol.basis_set, 1, 2)(*args), coeffs
        )

        # x, y, z components (core orbitals contribution)
        core_x, core_y, core_z = anp.array([0]), anp.array([0]), anp.array([0])

        if core is None and active is None:
            return (core_x, core_y, core_z), (d_x, d_y, d_z)

        for i in core:
            core_x = core_x + 2 * d_x[i][i]
            core_y = core_y + 2 * d_y[i][i]
            core_z = core_z + 2 * d_z[i][i]

        d_x = d_x[anp.ix_(active, active)]
        d_y = d_y[anp.ix_(active, active)]
        d_z = d_z[anp.ix_(active, active)]

        return (core_x, core_y, core_z), (d_x, d_y, d_z)

    return _dipole_integrals


def fermionic_dipole(mol, cutoff=1.0e-12, core=None, active=None):
    r"""Return a function that builds the fermionic dipole moment observable.

    The dipole operator in the second-quantized form is

    .. math::

        \hat{D} = -\sum_{pq} d_{pq} [\hat{c}_{p\uparrow}^\dagger \hat{c}_{q\uparrow} +
        \hat{c}_{p\downarrow}^\dagger \hat{c}_{q\downarrow}] -
        \hat{D}_\mathrm{c} + \hat{D}_\mathrm{n},

    where the matrix elements :math:`d_{pq}` are given by the integral of the position operator
    :math:`\hat{{\bf r}}` over molecular orbitals :math:`\phi`

    .. math::

        d_{pq} = \int \phi_p^*(r) \hat{{\bf r}} \phi_q(r) dr,

    and :math:`\hat{c}^{\dagger}` and :math:`\hat{c}` are the creation and annihilation operators,
    respectively. The contribution of the core orbitals and nuclei are denoted by
    :math:`\hat{D}_\mathrm{c}` and :math:`\hat{D}_\mathrm{n}`, respectively, which are computed as

    .. math::

        \hat{D}_\mathrm{c} = 2 \sum_{i=1}^{N_\mathrm{core}} d_{ii},

    and

    .. math::

        \hat{D}_\mathrm{n} = \sum_{i=1}^{N_\mathrm{atoms}} Z_i {\bf R}_i \hat{I},

    where :math:`Z_i` and :math:`{\bf R}_i` denote, respectively, the atomic number and the
    nuclear coordinates of the :math:`i`-th atom of the molecule.

    Args:
        mol (Molecule): the molecule object
        cutoff (float): cutoff value for discarding the negligible dipole moment integrals
        core (list[int]): indices of the core orbitals
        active (list[int]): indices of the active orbitals

    Returns:
        function: function that builds the fermionic dipole moment observable

    **Example**

    >>> symbols  = ['H', 'H']
    >>> geometry = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], requires_grad = False)
    >>> alpha = np.array([[3.42525091, 0.62391373, 0.1688554],
    >>>                   [3.42525091, 0.62391373, 0.1688554]], requires_grad=True)
    >>> mol = qml.hf.Molecule(symbols, geometry, alpha=alpha)
    >>> args = [alpha]
    >>> coeffs, ops = fermionic_dipole(mol)(*args)[2]
    >>> ops
    [[], [0, 0], [0, 2], [1, 1], [1, 3], [2, 0], [2, 2], [3, 1], [3, 3]]
    """

    def _fermionic_dipole(*args):
        r"""Build the fermionic dipole moment observable.

        Args:
            args (array[array[float]]): initial values of the differentiable parameters

        Returns:
            tuple(array[float], list[list[int]]): the dipole moment coefficients and the indices of
            the spin orbitals the creation and annihilation operators act on
        """
        constants, integrals = dipole_integrals(mol, core, active)(*args)

        nd = [anp.array([0]), anp.array([0]), anp.array([0])]
        for i in range(len(mol.symbols)):  # nuclear contributions
            nd[0] = nd[0] + atomic_numbers[mol.symbols[i]] * mol.coordinates[i][0]
            nd[1] = nd[1] + atomic_numbers[mol.symbols[i]] * mol.coordinates[i][1]
            nd[2] = nd[2] + atomic_numbers[mol.symbols[i]] * mol.coordinates[i][2]

        f = []
        for i in range(3):
            coeffs, ops = fermionic_one(constants[i], integrals[i], cutoff=cutoff)
            f.append((anp.concatenate((nd[i], coeffs * (-1))), [[]] + ops))

        return f

    return _fermionic_dipole


def dipole_moment(mol, cutoff=1.0e-12, core=None, active=None):
    r"""Return a function that computes the qubit dipole moment observable.

    The dipole operator in the second-quantized form is

    .. math::

        \hat{D} = -\sum_{pq} d_{pq} [\hat{c}_{p\uparrow}^\dagger \hat{c}_{q\uparrow} +
        \hat{c}_{p\downarrow}^\dagger \hat{c}_{q\downarrow}] -
        \hat{D}_\mathrm{c} + \hat{D}_\mathrm{n},

    where the matrix elements :math:`d_{pq}` are given by the integral of the position operator
    :math:`\hat{{\bf r}}` over molecular orbitals :math:`\phi`

    .. math::

        d_{pq} = \int \phi_p^*(r) \hat{{\bf r}} \phi_q(r) dr,

    and :math:`\hat{c}^{\dagger}` and :math:`\hat{c}` are the creation and annihilation operators,
    respectively. The contribution of the core orbitals and nuclei are denoted by
    :math:`\hat{D}_\mathrm{c}` and :math:`\hat{D}_\mathrm{n}`, respectively, which are computed as

    .. math::

        \hat{D}_\mathrm{c} = 2 \sum_{i=1}^{N_\mathrm{core}} d_{ii},

    and

    .. math::

        \hat{D}_\mathrm{n} = \sum_{i=1}^{N_\mathrm{atoms}} Z_i {\bf R}_i \hat{I},

    where :math:`Z_i` and :math:`{\bf R}_i` denote, respectively, the atomic number and the
    nuclear coordinates of the :math:`i`-th atom of the molecule.

    The fermonic dipole operator is then transformed to the qubit basis which gives

    .. math::

        \hat{D} = \sum_{j} c_j P_j,

    where :math:`c_j` is a numerical coefficient and :math:`P_j` is a ternsor product of
    single-qubit Pauli operators :math:`X, Y, Z, I`.

    Args:
        mol (Molecule): the molecule object
        cutoff (float): cutoff value for discarding the negligible dipole moment integrals
        core (list[int]): indices of the core orbitals
        active (list[int]): indices of the active orbitals

    Returns:
        function: function that computes the qubit dipole moment observable

    **Example**

    >>> symbols  = ['H', 'H']
    >>> geometry = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], requires_grad = False)
    >>> alpha = np.array([[3.42525091, 0.62391373, 0.1688554],
    >>>                   [3.42525091, 0.62391373, 0.1688554]], requires_grad=True)
    >>> mol = qml.hf.Molecule(symbols, geometry, alpha=alpha)
    >>> args = [alpha]
    >>> dipole_moment(mol)(*args)[2].ops
    [PauliZ(wires=[0]),
     PauliY(wires=[0]) @ PauliZ(wires=[1]) @ PauliY(wires=[2]),
     PauliX(wires=[0]) @ PauliZ(wires=[1]) @ PauliX(wires=[2]),
     PauliZ(wires=[1]),
     PauliY(wires=[1]) @ PauliZ(wires=[2]) @ PauliY(wires=[3]),
     PauliX(wires=[1]) @ PauliZ(wires=[2]) @ PauliX(wires=[3]),
     PauliZ(wires=[2]),
     PauliZ(wires=[3])]
    """

    def _dipole(*args):
        r"""Compute the qubit dipole moment observable.

        Args:
            args (array[array[float]]): initial values of the differentiable parameters

        Returns:
            (list[Hamiltonian]): x, y and z components of the dipole moment observable
        """
        d = []
        d_ferm = fermionic_dipole(mol, cutoff, core, active)(*args)
        for i in d_ferm:
            d.append(qubit_operator(i, cutoff=cutoff))

        return d

    return _dipole


def fermionic_one(constant, integral, cutoff=1.0e-12):
    r"""Create a fermionic operator from one-particle molecular orbital integrals.

    Args:
        constant (array[float]): the contribution of the core orbitals and nuclei
        integral (array[float]): the one-particle molecular orbital integrals
        cutoff (float): cutoff value for discarding the negligible integrals

    Returns:
        tuple(array[float], list[int]): fermionic coefficients and operators

    **Example**

    >>> constant = np.array([1.0])
    >>> integral = np.array([[0.5, -0.8270995], [-0.8270995, 0.5]])
    >>> coeffs, ops = fermionic_one(constant, integral)
    >>> ops
    [[], [0, 0], [0, 2], [1, 1], [1, 3], [2, 0], [2, 2], [3, 1], [3, 3]]
    """
    coeffs = anp.array([])

    if constant != anp.array([0.0]):
        coeffs = anp.concatenate((coeffs, constant))
        operators = [[]]
    else:
        operators = []

    for d in [integral]:
        i = anp.argwhere(abs(d) >= cutoff)
        operators = operators + (i * 2).tolist() + (i * 2 + 1).tolist()  # up-up + down-down terms
        coeffs = anp.concatenate((coeffs, anp.tile(d[abs(d) >= cutoff], 2)))

    indices_sort = [operators.index(i) for i in sorted(operators)]

    return coeffs[indices_sort], sorted(operators)


def qubit_operator(o_ferm, cutoff=1.0e-12):
    r"""Convert a fermionic observable to a PennyLane qubit observable.

    The fermionic operator is a tuple containing the fermionic coefficients and operators. For
    instance, the one-body fermionic operator :math:`a_2^\dagger a_0` is specified as [2, 0] and the
    two-body operator :math:`a_4^\dagger a_3^\dagger a_2 a_1` is specified as [4, 3, 2, 1].

    Args:
        o_ferm tuple(array[float], list[int]): fermionic operator
        cutoff (float): cutoff value for discarding the negligible terms

    Returns:
        Hamiltonian: Simplified PennyLane Hamiltonian

    **Example**

    >>> coeffs = np.array([1.0, 1.0])
    >>> ops = [[0, 0], [0, 0]]
    >>> f = (coeffs, ops)
    >>> print(qubit_operator(f))
    ((-1+0j)) [Z0]
    + ((1+0j)) [I0]
    """
    ops = []
    coeffs = anp.array([])

    for n, t in enumerate(o_ferm[1]):

        if len(t) == 0:
            coeffs = np.concatenate((coeffs, np.array([o_ferm[0][n]]) + 0.0))
            ops = ops + [qml.Identity(0)]

        else:
            op = _generate_qubit_operator(t)
            if op != 0:
                for i, o in enumerate(op[1]):
                    if len(o) == 0:
                        op[1][i] = qml.Identity(0)
                    if len(o) == 1:
                        op[1][i] = _return_pauli(o[0][1])(o[0][0])
                    if len(o) > 1:
                        k = qml.Identity(0)
                        for o_ in o:
                            k = k @ _return_pauli(o_[1])(o_[0])
                        op[1][i] = k
                coeffs = np.concatenate([coeffs, np.array(op[0]) * o_ferm[0][n]])
                ops = ops + op[1]

    o_qubit = simplify(qml.Hamiltonian(coeffs, ops), cutoff=cutoff)

    return o_qubit

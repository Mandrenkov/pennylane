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
"""This module contains a proxy qubit object for spawning multiple instances of a given qubit type for run on a background scheduler.
"""
from typing import List, Union, Tuple, Dict
from contextlib import nullcontext
import pennylane as qml
from pennylane import QubitDevice, DeviceError, QubitStateVector, BasisState
from .default_qubit import DefaultQubit
from .._version import __version__

try:
    import dask
    import dask.distributed as dist
    from distributed import get_client, secede, rejoin
    from distributed.protocol import dask_serialize, dask_deserialize, serialize, deserialize

    @dask_serialize.register(qml.numpy.tensor)
    def serialize(tensor: qml.numpy.tensor) -> Tuple[Dict, List[bytes]]:
        header,frames = dist.protocol.numpy.serialize_numpy_ndarray(tensor)
        header["type"] = "qml.numpy.tensor"
        header["requires_grad"] = tensor.requires_grad
        frames = [tensor.data]
        return header, frames

    @dask_deserialize.register(qml.numpy.tensor)
    def deserialize(header: Dict, frames: List[bytes]) -> qml.numpy.tensor:
        return qml.numpy.tensor(frames[0], requires_grad=header["requires_grad"])

except ImportError as e:  # pragma: no cover
    raise ImportError("default.task requires installing dask and dask.distributed") from e

class DefaultTask(QubitDevice):
    """Proxy simulator plugin written using Dask.Distributed as a task-distribution scheduling backend.

    **Short name:** ``default.task``

    This device provides a pure-state qubit simulator wrapping both ``"default.qubit"`` and ``"lightning.qubit"``, 
    and written to allow batched offloading to a Dask scheduler. 

    To use this device, you will need to install dask and dask.distributed:

    .. code-block:: console

        pip install dask distributed

    **Example**

    >>> dask_scheduler = "localhost:8786"
    >>> dask_backend = "lightning.qubit"
    >>> dev = qml.device("default.qubit.distributed", wires=6, scheduler="localhost:8786", backend=dask_backend)
    >>> @qml.qnode(dev, diff_method="adjoint")
    ... def circuit(x):
    ...     qml.RX(x[0], wires=0)
    ...     qml.RY(x[1], wires=1)
    ...     qml.RZ(x[2], wires=0)
    ...     qml.RZ(x[0], wires=1)
    ...     qml.RX(x[1], wires=0)
    ...     qml.RY(x[2], wires=1)
    ...     qml.Rot(x[0], x[1], x[2], wires=0)
    ...     return qml.expval(qml.PauliZ(0))
    >>> weights = np.array([0.2, 0.5, 0.1])
    >>> tapes = qml.gradients.param_shift(tape)
    >>> print(grad_fn(weights))
    array([-2.2526717e-01 -1.0086454e+00  1.3877788e-17])

    Args:
        wires (int): The number of wires to initialize the device with.
        shots (None, int): How many times the circuit should be evaluated (or sampled) to estimate
            the expectation values. Defaults to ``None`` if not specified, which means that the device
            returns analytical results.
        analytic (bool): Indicates if the device should calculate expectations
            and variances analytically. In non-analytic mode, the ``diff_method="backprop"``
            QNode differentiation method is not supported and it is recommended to consider
            switching device to ``default.qubit`` and using ``diff_method="parameter-shift"``.
        scheduler (None, str): The URL of the dask scheduler, specified as `address:port`. 
            If not specified, dask will initialize a scheduler local to the system running 
            the Python environment. The scheduler is expected to be of the form `dask.distributed`,
            and have workers using the same (or greater) version of Python and PennyLane.
        backend (None, str): Indicates the PennyLane device type to use for offloading 
            computation tasks. Currently  ``default.qubit`` and  ``lightning.qubit`` are the valid options. If not specified, ``default.qubit`` will be used. 
    """
    operations = DefaultQubit.operations
    observables = DefaultQubit.observables

    name = "Task-based qubit PennyLane plugin"
    short_name = "default.task"
    pennylane_requires = __version__
    version = __version__
    author = "Xanadu Inc."

    supported_devices = {"default.qubit", "default.qubit.tf", "default.qubit.jax", "lightning.qubit", }

    def __init__(self, wires, *, shots=None, analytic=None, client=None, backend="default.qubit", gen_report: Union[bool, str] = False, future = False):
        if client != None:
            self.client = client
        else:
            self.client = get_client()

        self._backend = backend
        self._wires = wires
        self._gen_report = gen_report
        self.num_wires = wires if isinstance(wires, int) else len(wires)
        self._shots = None
        self._cache = None
        self._future = future
        self.expand_fn = self.default_expand_fn
        self._shot_vector = None

        if backend not in DefaultTask.supported_devices:
            raise("Unsupported device backend.")

    def batch_execute(self, circuits: Union[List[qml.tape.QuantumTape], qml.beta.QNode], **kwargs):
        if self._gen_report:
            filename = self._gen_report if isinstance(self._gen_report, str) else "dask-report.html"
            from dask.distributed import performance_report
            cm = performance_report(filename=filename)
        else:
            cm = nullcontext()

        with cm:
            results = []
            if isinstance(circuits, qml.beta.QNode):
                results.append(self.client.submit(DefaultTask._execute_wrapper, self._backend, self._wires, circuit))
            elif isinstance(circuits, dask.distributed.client.Future):
                results = self.client.submit(lambda backend, wires, tapes: [DefaultTask._execute_wrapper(backend, wires, i) for i in tapes], self._backend, self._wires, circuits)
            else:
                for idx,circuit in enumerate(circuits):
                    results.append(self.client.submit(DefaultTask._execute_wrapper, self._backend, self._wires, circuit))

            if self._future:
                return results
            else:
                secede()
                res = self.client.gather(results)
                rejoin()
                return res

    def apply():
        pass

    @staticmethod
    def _execute_wrapper(backend: str, wires: int, circuit: Union[qml.QNode, qml.tape.QuantumTape]):
        dev = qml.device(backend, wires=wires)
        return dev.execute(circuit)
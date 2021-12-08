# Copyright 2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Functionality for applying cuts to the circuit graph"""
from pennylane.cut.mark import MeasureNode, PrepareNode, OperationNode, WireCut, GateCut
import networkx as nx
from typing import Tuple, Dict, Sequence, Any
from pennylane.operation import Operator

from networkx import weakly_connected_components
from pennylane.measure import MeasurementProcess
from pennylane.operation import Tensor
from pennylane.circuit_graph import CircuitGraph
from pennylane.operation import Expectation
import itertools
from pennylane.tape import QuantumTape
from pennylane import apply


def disconnect_graph(g: nx.Graph):
    g = g.copy()
    qg = g.copy()
    g_edges = list(g.edges(data="type"))

    meas_prep_on_wire = {}

    for n in nx.topological_sort(g):
        if isinstance(n, (MeasureNode, PrepareNode)):
            wire = n.wires[0]

            if meas_prep_on_wire.get(wire, None) is None:
                meas_prep_on_wire[wire] = [n]
            else:
                meas_prep_on_wire[wire].append(n)

    for node1, node2, t in g_edges:
        if t is None:
            qg.remove_edge(node1, node2)
        else:
            g.remove_edge(node1, node2)

    subgraph_nodes = list(nx.weakly_connected_components(g))
    subgraphs = [nx.subgraph(g, s) for s in subgraph_nodes]

    for s in subgraphs:
        for meas_prep in meas_prep_on_wire.values():
            order = []
            for n in meas_prep:
                try:
                    s[n]
                    order.append(n)
                except KeyError:
                    pass
            for i, o in enumerate(order):
                if isinstance(o, MeasureNode):
                    try:
                        o_next = order[i + 1]
                        g.add_edge(o, o_next)
                    except IndexError:
                        pass

    mapping = {}
    for i, s in enumerate(subgraph_nodes):
        nodes = list(s)
        n1 = nodes[0]

        for n2 in nodes[1:]:
            qg = nx.contracted_nodes(qg, n1, n2)
        mapping[n1] = i

    nx.relabel_nodes(qg, mapping, copy=False)

    return subgraphs, qg


def get_dag(tape):
    g = tape.graph.graph.copy()
    meas = tape.measurements
    assert len(meas) == 1
    meas = meas[0]

    assert meas.return_type is Expectation

    obs = meas.obs

    if isinstance(obs, Tensor):
        terms = obs.obs
        predecessors = list(g.predecessors(obs))

        g.remove_node(obs)
        for t in terms:
            g.add_node(t)
            for wire in t.wires:
                for p in predecessors:
                    if wire in p.wires:
                        g.add_edge(p, t)

    return g


def apply_cuts(g):
    nodes = tuple(g.nodes)

    for n in nodes:
        if isinstance(n, WireCut):
            _remove_wire_cut_node(n, g)

    nodes = tuple(g.nodes)

    for n in nodes:
        if isinstance(n, GateCut):
            _remove_gate_cut_node(n, g)


def find_cuts(g: nx.Graph, wire_capacity: int, gate_capacity: int, **kwargs) -> \
        Tuple[Tuple[Tuple[Operator, Operator, Any]], Tuple[Operator], Dict]: # Tuple[Tuple[Operator]]
    nodes = list(g.nodes)
    # wire_cuts = ((nodes[0], nodes[1], 0),)
    wire_cuts = ()
    gate_cuts = ()# (nodes[3],)
    # partitioned_nodes = ((nodes[0],), (nodes[1],) + tuple(nodes[3:]))
    return wire_cuts, gate_cuts, {} #, partitioned_nodes


def place_cuts(g: nx.Graph, wire_capacity: int, gate_capacity: int, **kwargs):
    wire_cuts, gate_cuts, opt_results = find_cuts(g, wire_capacity, gate_capacity, **kwargs)

    for n in gate_cuts:
        _remove_gate_cut_node(n, g)

    for op1, op2, wire in wire_cuts:
        meas = MeasureNode(wires=wire)
        prep = PrepareNode(wires=wire)
        g.add_node(meas)
        g.add_node(prep)
        g.add_edge(op1, meas)
        g.add_edge(prep, op2)
        g.add_edge(meas, prep, type="wire_cut", pair=(meas, prep))


def _remove_wire_cut_node(n, g):
    predecessors = g.predecessors(n)  # TODO: What if no predecessors or successors?
    successors = g.successors(n)

    g.remove_node(n)

    measure_wires = {}
    prepare_wires = {}

    for p in predecessors:
        for wire in p.wires:
            if wire in n.wires:
                op = MeasureNode(wires=wire)
                g.add_node(op)
                g.add_edge(p, op)
                measure_wires[wire] = op

    for s in successors:
        for wire in s.wires:
            if wire in n.wires:
                op = PrepareNode(wires=wire)
                g.add_node(op)
                g.add_edge(op, s)
                prepare_wires[wire] = op

    for wire in measure_wires.keys():
        measure = measure_wires[wire]
        prepare = prepare_wires[wire]
        g.add_edge(measure, prepare, type="wire_cut", pair=(measure, prepare))


def dag_to_tape(g):

    ops = nx.topological_sort(g)

    with QuantumTape() as tape:
        for o in ops:
            apply(o)

    return tape


def _remove_gate_cut_node(n, g):
    predecessors = list(g.predecessors(n))  # TODO: What if no predecessors or successors?
    successors = list(g.successors(n))

    g.remove_node(n)

    n_wires = n.wires

    op_nodes = []
    for wire in n_wires:
        p_wire = [p for p in predecessors if wire in p.wires][-1]  # TODO: check if ordered
        s_wire = [s for s in successors if wire in s.wires][0]
        op = OperationNode(wires=wire)
        g.add_node(op)
        g.add_edge(p_wire, op)
        g.add_edge(op, s_wire)
        op_nodes.append(op)

    for op1, op2 in itertools.combinations(op_nodes, r=2):
        g.add_edge(op1, op2, type="gate_cut", pair=(op1, op2))
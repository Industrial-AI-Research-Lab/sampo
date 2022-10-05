"""
This file contains high-level functions for calling the resource optimization
"""
from enum import Enum, auto
from functools import partial
from typing import Union, Tuple

from metrics.resources_in_time.binary_search import BinarySearchOptimizationType, BinarySearchOptimizer
from metrics.resources_in_time.newton_conjugate_gradient import NewtonCGOptimizer
from scheduler.base import Scheduler
from schemas.time import Time
from schemas.contractor import AgentsDict, Contractor
from schemas.graph import WorkGraph


class ResourceOptimizationType(Enum):
    """
    Represents resource optimization technique.
    WARNING: Only BinarySearch is currently implemented. Do not Use NewtonCG
    """
    BinarySearch = auto()
    NewtonCG = auto()


def apply_binary_optimization(scheduler: Scheduler, work_graph: WorkGraph, deadline: Time,
                              method: BinarySearchOptimizationType = BinarySearchOptimizationType.ItemByItemFastInit,
                              agents_from_manual_input: AgentsDict = None,
                              dry_resources: bool = False) \
        -> Union[Tuple[Contractor, Time], Tuple[None, None]]:
    """
    Applies resource optimization by means of binary search to the given work graph with the given scheduler
    :param agents_from_manual_input:
    :param scheduler:
    :param work_graph:
    :param deadline: Estimated time of end of work
    :param method: Method of optimization. Can be 'fast', 'item-by-item' or 'item-by-item-fast-init'
    :param dry_resources:
    :return:
    """
    optimizer = BinarySearchOptimizer(scheduler, method)
    return optimizer.optimize(work_graph, deadline, agents_from_manual_input, dry_resources=dry_resources)


def apply_gradient_optimization(scheduler: Scheduler, work_graph: WorkGraph, deadline: Time,
                                agents_from_manual_input: AgentsDict = None,
                                dry_resources: bool = False) \
        -> Union[Tuple[Contractor, Time], Tuple[None, None]]:
    """
    WARNING: Gradient resource optimization has not been implemented properly
    Applies resource optimization by means of gradient methods to the given work graph with the given scheduler
    :param scheduler:
    :param work_graph:
    :param deadline:
    :param agents_from_manual_input:
    :param dry_resources:
    :return:
    """
    raise NotImplementedError('Gradient resource optimization has not been implemented properly')

    optimizer = NewtonCGOptimizer(scheduler)
    return optimizer.optimize(work_graph, deadline, agents=agents_from_manual_input, dry_resources=dry_resources)


def apply_resource_optimization(optimization_type: ResourceOptimizationType, scheduler: Scheduler,
                                work_graph: WorkGraph, deadline: Time,
                                agents_from_manual_input: AgentsDict = None,
                                dry_resources: bool = False) \
        -> Union[Tuple[Contractor, Time], Tuple[None, None]]:
    if optimization_type is ResourceOptimizationType.BinarySearch:
        optimizer = partial(apply_binary_optimization, method=BinarySearchOptimizationType.ItemByItemFastInit)
    elif optimization_type is ResourceOptimizationType.NewtonCG:
        optimizer = apply_gradient_optimization
    else:
        raise Exception(f'Optimization method not implemented: {optimization_type.name}')

    return optimizer(scheduler=scheduler, work_graph=work_graph, deadline=deadline,
                     agents_from_manual_input=agents_from_manual_input, dry_resources=dry_resources)
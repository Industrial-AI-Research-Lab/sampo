from collections import defaultdict
from dataclasses import dataclass, field
from random import Random
from typing import List, Optional, Callable, Set, Dict

from schemas.work_estimator import WorkTimeEstimator
from schemas.identifiable import Identifiable
from schemas.requirements import WorkerReq, EquipmentReq, MaterialReq, ConstructionObjectReq
from schemas.serializable import AutoJSONSerializable
from schemas.time import Time
from schemas.resources import Worker
from utils.serializers import custom_serializer


@dataclass
class WorkUnit(AutoJSONSerializable['WorkUnit'], Identifiable):
    worker_reqs: List[WorkerReq] = field(default_factory=list)
    equipment_reqs: List[EquipmentReq] = field(default_factory=list)
    material_reqs: List[MaterialReq] = field(default_factory=list)
    object_reqs: List[ConstructionObjectReq] = field(default_factory=list)
    group: Optional[str] = "default"
    is_service_unit: Optional[bool] = False
    volume: Optional[float] = 1
    volume_type: Optional[str] = "unit"

    @custom_serializer('worker_reqs')
    def worker_reqs_serializer(self, value):
        return [wr._serialize() for wr in value]

    @classmethod
    @custom_serializer('worker_reqs', deserializer=True)
    def worker_reqs_deserializer(cls, value):
        return [WorkerReq._deserialize(wr) for wr in value]

    # TODO: move this logit to WorkTimeEstimator
    def estimate_static(self, worker_list: List[Worker], work_estimator: WorkTimeEstimator = None) -> Time:
        if work_estimator:
            # TODO What?? We are loosing much performance
            #  when processing worker names EACH estimation
            workers = {w.name.replace("_res_fact", ""): w.count for w in worker_list}
            work_time = work_estimator.estimate_time(self.name.split("_stage_")[0], self.volume, workers)
            if work_time > 0:
                return work_time

        return self._abstract_estimate(worker_list, get_static_by_worker)

    def estimate_stochastic(self, worker_list: List[Worker], rand: Optional[Random] = None) -> Time:
        return self._abstract_estimate(worker_list, get_stochastic_by_worker, rand)

    def _abstract_estimate(self, worker_list: List[Worker],
                           get_productivity: Callable[[Worker, Optional[Random]], float],
                           rand: Optional[Random] = None) -> Time:
        groups = defaultdict(list)
        for w in worker_list:
            groups[w.name].append(w)
        times = [Time(0)]  # if there are no requirements for the work, it is done instantly
        for req in self.worker_reqs:
            if req.min_count == 0:
                continue
            name = req.type
            command = groups[name]
            worker_count = sum([worker.count for worker in command], 0)
            if worker_count < req.min_count:
                return Time.inf()
            productivity = sum([get_productivity(c, rand) for c in command], 0) / worker_count
            productivity *= communication_coefficient(worker_count, req.max_count)
            if productivity == 0:
                return Time.inf()
            times.append(Time(req.volume // productivity))
        return max(times)


def get_static_by_worker(w: Worker, _: Optional[Random] = None):
    return w.get_static_productivity()


def get_stochastic_by_worker(w: Worker, rand: Optional[Random] = None):
    return w.get_stochastic_productivity(rand)


# Function is chosen because it has a quadratic decrease in efficiency as the number of commands on the object
# increases, after the maximum number of commands begins to decrease in efficiency, and its growth rate depends on
# the maximum number of commands.
# sum(1 - ((x-1)^2 / max_groups^2), where x from 1 to groups_count
def communication_coefficient(groups_count: int, max_groups: int) -> float:
    n = groups_count
    m = max_groups
    return 1 / (6 * m ** 2) * (-2 * n ** 3 + 3 * n ** 2 + (6 * m ** 2 - 1) * n)


AdjacencyChildren = Set[str]
AdjacencyMatrix = Dict[str, AdjacencyChildren]
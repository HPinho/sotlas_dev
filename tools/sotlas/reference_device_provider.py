"""Deterministic in-process implementation of the DEVICE provider protocol.

This provider is an executable semantic reference, not a hardware backend.  It
materializes opaque generation-safe lifecycle tokens and rejects invalid reuse,
so a future CUDA/OpenCL/driver provider can be compared against the same
provider contract without treating host memory as a real device transfer.
"""
from __future__ import annotations

from dataclasses import dataclass


class ReferenceDeviceProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReferenceDeviceOwner:
    binding: str
    generation: int


@dataclass(frozen=True)
class ReferenceSubmission:
    binding: str
    generation: int


@dataclass(frozen=True)
class ReferenceCompletion:
    binding: str
    generation: int


@dataclass(frozen=True)
class ReferenceFence:
    generations: tuple[int, ...]


@dataclass(frozen=True)
class ReferenceHostOwner:
    binding: str
    generation: int


class ReferenceDeviceProvider:
    """Immediate provider with generation-safe ownership bookkeeping."""

    name = "sotlas-reference-device-provider"

    def __init__(self) -> None:
        self._next_generation = 1
        self._queue: str | None = None
        self._records: dict[int, dict[str, object]] = {}
        self._bindings: set[str] = set()

    def _check_queue(self, queue: str) -> None:
        if not isinstance(queue, str) or not queue:
            raise ReferenceDeviceProviderError("reference provider requires a queue")
        if self._queue is None:
            self._queue = queue
        elif self._queue != queue:
            raise ReferenceDeviceProviderError("reference provider queue identity changed")

    def submit(self, *, queue: str, binding: str, point_id: str):
        self._check_queue(queue)
        if not isinstance(binding, str) or not binding or binding in self._bindings:
            raise ReferenceDeviceProviderError(
                "reference provider requires one live submission per binding"
            )
        if not isinstance(point_id, str) or not point_id:
            raise ReferenceDeviceProviderError("reference submit requires a point identity")
        generation = self._next_generation
        self._next_generation += 1
        self._bindings.add(binding)
        self._records[generation] = {
            "binding": binding,
            "submit_point": point_id,
            "completed": False,
            "reacquired": False,
        }
        return (
            ReferenceDeviceOwner(binding, generation),
            ReferenceSubmission(binding, generation),
        )

    def complete(
        self,
        *,
        queue: str,
        submission,
        binding: str,
        point_id: str,
        timeout_ms: int | None,
    ):
        self._check_queue(queue)
        if not isinstance(submission, ReferenceSubmission):
            raise ReferenceDeviceProviderError("unknown reference submission token")
        record = self._records.get(submission.generation)
        if record is None or record["binding"] != binding or submission.binding != binding:
            raise ReferenceDeviceProviderError("reference completion binding diverges")
        if record["completed"]:
            raise ReferenceDeviceProviderError("reference submission completed twice")
        if record["reacquired"]:
            raise ReferenceDeviceProviderError("reference submission already reacquired")
        if not isinstance(point_id, str) or not point_id:
            raise ReferenceDeviceProviderError("reference completion requires a point identity")
        record["completed"] = True
        record["completion_point"] = point_id
        return ReferenceCompletion(binding, submission.generation)

    def synchronize(
        self,
        *,
        queue: str,
        completions: tuple[object, ...],
        point_id: str,
        timeout_ms: int | None,
    ):
        self._check_queue(queue)
        if not completions:
            raise ReferenceDeviceProviderError("reference sync requires completions")
        generations: list[int] = []
        for completion in completions:
            if not isinstance(completion, ReferenceCompletion):
                raise ReferenceDeviceProviderError("unknown reference completion token")
            record = self._records.get(completion.generation)
            if (
                record is None
                or record["binding"] != completion.binding
                or not record["completed"]
                or record["reacquired"]
            ):
                raise ReferenceDeviceProviderError("reference completion is not synchronizable")
            if completion.generation in generations:
                raise ReferenceDeviceProviderError("reference sync repeats a completion")
            generations.append(completion.generation)
        if not isinstance(point_id, str) or not point_id:
            raise ReferenceDeviceProviderError("reference sync requires a point identity")
        return ReferenceFence(tuple(generations))

    def reacquire(
        self,
        *,
        queue: str,
        device_owner,
        fence,
        binding: str,
        point_id: str,
    ):
        self._check_queue(queue)
        if not isinstance(device_owner, ReferenceDeviceOwner):
            raise ReferenceDeviceProviderError("unknown reference device owner")
        if not isinstance(fence, ReferenceFence):
            raise ReferenceDeviceProviderError("unknown reference fence")
        record = self._records.get(device_owner.generation)
        if (
            record is None
            or record["binding"] != binding
            or device_owner.binding != binding
            or not record["completed"]
        ):
            raise ReferenceDeviceProviderError("reference owner is not reacquirable")
        if device_owner.generation not in fence.generations:
            raise ReferenceDeviceProviderError("reference fence does not cover owner")
        if record["reacquired"]:
            raise ReferenceDeviceProviderError("reference owner reacquired twice")
        if not isinstance(point_id, str) or not point_id:
            raise ReferenceDeviceProviderError("reference reacquire requires a point identity")
        record["reacquired"] = True
        self._bindings.remove(binding)
        return ReferenceHostOwner(binding, device_owner.generation)

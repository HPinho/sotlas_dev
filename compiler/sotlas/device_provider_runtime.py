"""Backend-neutral execution contract for validated DEVICE provider plans.

This is deliberately *not* a GPU/NPU implementation.  It is the runtime
protocol a concrete provider must satisfy after logical lifecycle and physical
ABI validation have already succeeded.  The executor preserves source-stable
lifecycle point identities, forbids reacquisition before synchronization, and
makes provider failure/timeout explicit rather than silently treating them as
successful completion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .sir.device_runtime_physical_abi import BoundDeviceRuntimePhysicalABIPlan


class DeviceProviderError(RuntimeError):
    """Base class for provider execution failures."""

    def __init__(self, message: str, *, operation: str, point_id: str):
        super().__init__(message)
        self.operation = operation
        self.point_id = point_id


class DeviceProviderTimeout(DeviceProviderError):
    """A provider did not establish the required lifecycle fact in time."""


class DeviceProviderFailure(DeviceProviderError):
    """A provider explicitly failed one lifecycle operation."""


class DeviceProviderContractError(ValueError):
    """A provider result or bound plan violates the DEVICE execution contract."""


@dataclass(frozen=True)
class DeviceSubmission:
    binding: str
    device_owner: Any
    submission: Any
    point_id: str


@dataclass(frozen=True)
class DeviceCompletion:
    binding: str
    completion: Any
    submission_point_id: str
    point_id: str


@dataclass(frozen=True)
class DeviceFence:
    token: Any
    completion_point_ids: tuple[str, ...]
    point_id: str


@dataclass(frozen=True)
class DeviceReacquisition:
    binding: str
    host_owner: Any
    fence_point_id: str
    point_id: str


@dataclass(frozen=True)
class DeviceProviderExecutionResult:
    provider: str
    function: str
    queue: str
    submissions: tuple[DeviceSubmission, ...]
    completions: tuple[DeviceCompletion, ...]
    fence: DeviceFence
    reacquisitions: tuple[DeviceReacquisition, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return (
            *(item.point_id for item in self.submissions),
            *(item.point_id for item in self.completions),
            self.fence.point_id,
            *(item.point_id for item in self.reacquisitions),
        )


@runtime_checkable
class DeviceProvider(Protocol):
    """Protocol implemented by reference or hardware-specific providers."""

    name: str

    def submit(
        self, *, queue: str, binding: str, point_id: str
    ) -> tuple[Any, Any]: ...

    def complete(
        self,
        *,
        queue: str,
        submission: Any,
        binding: str,
        point_id: str,
        timeout_ms: int | None,
    ) -> Any: ...

    def synchronize(
        self,
        *,
        queue: str,
        completions: tuple[Any, ...],
        point_id: str,
        timeout_ms: int | None,
    ) -> Any: ...

    def reacquire(
        self,
        *,
        queue: str,
        device_owner: Any,
        fence: Any,
        binding: str,
        point_id: str,
    ) -> Any: ...


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceProviderContractError(f"{label} requires a non-empty identity")
    return value


def _validate_timeout(timeout_ms: int | None) -> int | None:
    if timeout_ms is None:
        return None
    if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or timeout_ms < 0:
        raise DeviceProviderContractError(
            "DEVICE provider timeout must be a non-negative integer or None"
        )
    return timeout_ms


def _provider_name(provider: DeviceProvider) -> str:
    if not isinstance(provider, DeviceProvider):
        raise DeviceProviderContractError(
            "DEVICE provider does not implement the required execution protocol"
        )
    return _required_text(provider.name, label="DEVICE provider name")


def _raise_provider_error(
    exc: BaseException,
    *,
    operation: str,
    point_id: str,
) -> None:
    if isinstance(exc, DeviceProviderError):
        # Providers may raise a domain error themselves, but they may not lie
        # about which canonical operation/point failed.
        if exc.operation != operation or exc.point_id != point_id:
            raise DeviceProviderContractError(
                "DEVICE provider error identity diverges from the active lifecycle point"
            ) from exc
        raise exc
    if isinstance(exc, TimeoutError):
        raise DeviceProviderTimeout(
            f"DEVICE provider timed out during {operation} at {point_id}",
            operation=operation,
            point_id=point_id,
        ) from exc
    raise DeviceProviderFailure(
        f"DEVICE provider failed during {operation} at {point_id}: {exc}",
        operation=operation,
        point_id=point_id,
    ) from exc


def execute_device_provider_plan(
    plan: BoundDeviceRuntimePhysicalABIPlan,
    provider: DeviceProvider,
    *,
    timeout_ms: int | None = None,
) -> DeviceProviderExecutionResult:
    """Execute the canonical DEVICE lifecycle through one concrete provider.

    The input must already be a bound physical ABI plan.  This function still
    rechecks lifecycle order, binding/dependency identity and returned provider
    values so manually-constructed or mutated plans fail closed.
    """

    if not isinstance(plan, BoundDeviceRuntimePhysicalABIPlan):
        raise DeviceProviderContractError(
            "DEVICE provider execution requires a bound physical ABI plan"
        )
    provider_name = _provider_name(provider)
    timeout = _validate_timeout(timeout_ms)
    function = _required_text(plan.function, label="DEVICE provider function")
    queue = _required_text(plan.queue, label="DEVICE provider queue")
    calls = tuple(plan.calls)
    if not calls:
        raise DeviceProviderContractError("DEVICE provider plan requires lifecycle calls")

    operations = tuple(call.logical.operation for call in calls)
    owner_count = operations.count("submit")
    expected = (
        ("submit",) * owner_count
        + ("complete",) * owner_count
        + ("synchronize",)
        + ("reacquire",) * owner_count
    )
    if owner_count < 1 or operations != expected:
        raise DeviceProviderContractError(
            "DEVICE provider plan diverges from canonical lifecycle order"
        )

    point_ids = tuple(
        _required_text(call.logical.point_id, label="DEVICE provider lifecycle point")
        for call in calls
    )
    if len(set(point_ids)) != len(point_ids):
        raise DeviceProviderContractError(
            "DEVICE provider lifecycle point identities must be unique"
        )

    submission_calls = calls[:owner_count]
    completion_calls = calls[owner_count : owner_count * 2]
    sync_call = calls[owner_count * 2]
    reacquire_calls = calls[owner_count * 2 + 1 :]

    submissions: list[DeviceSubmission] = []
    by_binding: dict[str, DeviceSubmission] = {}
    for call in submission_calls:
        binding = _required_text(
            call.logical.binding, label="DEVICE provider submission binding"
        )
        if call.logical.depends_on or binding in by_binding:
            raise DeviceProviderContractError(
                "DEVICE provider submission dependencies/bindings are invalid"
            )
        try:
            produced = provider.submit(
                queue=queue, binding=binding, point_id=call.logical.point_id
            )
        except BaseException as exc:
            _raise_provider_error(
                exc, operation="submit", point_id=call.logical.point_id
            )
        if not isinstance(produced, tuple) or len(produced) != 2:
            raise DeviceProviderContractError(
                "DEVICE provider submit must return (device_owner, submission)"
            )
        device_owner, submission_token = produced
        if device_owner is None or submission_token is None:
            raise DeviceProviderContractError(
                "DEVICE provider submit returned an empty owner/submission token"
            )
        item = DeviceSubmission(
            binding=binding,
            device_owner=device_owner,
            submission=submission_token,
            point_id=call.logical.point_id,
        )
        submissions.append(item)
        by_binding[binding] = item

    completions: list[DeviceCompletion] = []
    for index, call in enumerate(completion_calls):
        binding = _required_text(
            call.logical.binding, label="DEVICE provider completion binding"
        )
        submission = by_binding.get(binding)
        if submission is None or call.logical.depends_on != (submission.point_id,):
            raise DeviceProviderContractError(
                "DEVICE provider completion diverges from its submission"
            )
        # Canonical ordering also requires the nth completion to correspond to
        # the nth submission, not merely to some valid binding.
        if submission is not submissions[index]:
            raise DeviceProviderContractError(
                "DEVICE provider completion order diverges from submission order"
            )
        try:
            token = provider.complete(
                queue=queue,
                submission=submission.submission,
                binding=binding,
                point_id=call.logical.point_id,
                timeout_ms=timeout,
            )
        except BaseException as exc:
            _raise_provider_error(
                exc, operation="complete", point_id=call.logical.point_id
            )
        if token is None:
            raise DeviceProviderContractError(
                "DEVICE provider completion returned an empty token"
            )
        completions.append(
            DeviceCompletion(
                binding=binding,
                completion=token,
                submission_point_id=submission.point_id,
                point_id=call.logical.point_id,
            )
        )

    expected_completion_points = tuple(item.point_id for item in completions)
    if tuple(sync_call.logical.depends_on) != expected_completion_points:
        raise DeviceProviderContractError(
            "DEVICE provider synchronization dependency set diverges from completions"
        )
    if sync_call.logical.binding is not None:
        raise DeviceProviderContractError(
            "DEVICE provider synchronization cannot bind one owner"
        )
    try:
        fence_token = provider.synchronize(
            queue=queue,
            completions=tuple(item.completion for item in completions),
            point_id=sync_call.logical.point_id,
            timeout_ms=timeout,
        )
    except BaseException as exc:
        _raise_provider_error(
            exc, operation="synchronize", point_id=sync_call.logical.point_id
        )
    if fence_token is None:
        raise DeviceProviderContractError(
            "DEVICE provider synchronization returned an empty fence"
        )
    fence = DeviceFence(
        token=fence_token,
        completion_point_ids=expected_completion_points,
        point_id=sync_call.logical.point_id,
    )

    reacquisitions: list[DeviceReacquisition] = []
    for index, call in enumerate(reacquire_calls):
        binding = _required_text(
            call.logical.binding, label="DEVICE provider reacquisition binding"
        )
        submission = by_binding.get(binding)
        if submission is None or submission is not submissions[index]:
            raise DeviceProviderContractError(
                "DEVICE provider reacquisition order/binding diverges from submission"
            )
        if call.logical.depends_on != (fence.point_id,):
            raise DeviceProviderContractError(
                "DEVICE provider reacquisition is not gated by synchronization"
            )
        try:
            host_owner = provider.reacquire(
                queue=queue,
                device_owner=submission.device_owner,
                fence=fence.token,
                binding=binding,
                point_id=call.logical.point_id,
            )
        except BaseException as exc:
            _raise_provider_error(
                exc, operation="reacquire", point_id=call.logical.point_id
            )
        if host_owner is None:
            raise DeviceProviderContractError(
                "DEVICE provider reacquisition returned an empty host owner"
            )
        reacquisitions.append(
            DeviceReacquisition(
                binding=binding,
                host_owner=host_owner,
                fence_point_id=fence.point_id,
                point_id=call.logical.point_id,
            )
        )

    result = DeviceProviderExecutionResult(
        provider=provider_name,
        function=function,
        queue=queue,
        submissions=tuple(submissions),
        completions=tuple(completions),
        fence=fence,
        reacquisitions=tuple(reacquisitions),
    )
    if result.point_ids != point_ids:
        raise DeviceProviderContractError(
            "DEVICE provider execution changed source-stable lifecycle point order"
        )
    return result

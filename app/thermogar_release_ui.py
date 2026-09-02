"""Fail-closed Streamlit controls for the current SWR development surface."""

from __future__ import annotations

import hashlib
import inspect
from typing import Any, Callable

import streamlit as st

from thermogar_ne04_domain import (
    DECISION_REQUIRED,
    DomainRequest,
    evaluate_domain_request,
)
from thermogar_release_policy import (
    CALCULATIONS_ENABLED,
    CALCULATION_BLOCK_REASON,
    EXPORTS_ENABLED,
    EXPORT_BLOCK_REASON,
    IMPORTS_ENABLED,
    IMPORT_BLOCK_REASON,
    research_result_evidence,
)
from thermogar_verified_loaders import FeatureRequest, RejectedFeatureReceipt
from thermogar_verified_state import VerifiedArtifactRef


def release_download_button(*args: Any, **kwargs: Any) -> bool:
    """Render a visible but disabled download until the NE-06 contract passes."""

    if not EXPORTS_ENABLED:
        # Streamlit marshals ``data`` into its media store before a disabled
        # download widget is rendered. Therefore the frozen path must not call
        # download_button at all or pass artifact bytes across this boundary.
        label = kwargs.get("label", args[0] if args else "Выгрузка недоступна")
        caller = inspect.currentframe().f_back
        try:
            origin = (
                f"{caller.f_code.co_filename}:{caller.f_lineno}"
                if caller is not None
                else "unknown"
            )
        finally:
            del caller
        identity = "|".join(
            (
                origin,
                str(label),
                str(kwargs.get("file_name", "")),
                str(kwargs.get("mime", "")),
            )
        )
        visual_kwargs: dict[str, Any] = {
            "disabled": True,
            "help": EXPORT_BLOCK_REASON,
            "key": kwargs.get("key")
            or "_thermogar_frozen_export_"
            + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20],
        }
        for name in ("type", "use_container_width", "width", "icon"):
            if name in kwargs:
                visual_kwargs[name] = kwargs[name]
        st.button(label, **visual_kwargs)
        return False
    return bool(st.download_button(*args, **kwargs))


def release_calculation_button(
    *args: Any,
    domain_request: DomainRequest | None = None,
    project_root: Any = None,
    **kwargs: Any,
) -> bool:
    """Render the central numerical action with mandatory NE-04 evaluation.

    The current release switch is frozen off. If a later change enables it,
    an omitted, malformed or denied domain request still leaves the widget
    inert; flipping one policy constant can never bypass the NE-04 evaluator.
    """

    if not CALCULATIONS_ENABLED:
        kwargs["disabled"] = True
        kwargs["help"] = CALCULATION_BLOCK_REASON
        # A stale widget state or test double must not be able to cross the
        # policy boundary merely by returning a truthy click value.
        st.button(*args, **kwargs)
        return False

    if not isinstance(domain_request, DomainRequest) or project_root is None:
        kwargs["disabled"] = True
        kwargs["help"] = (
            "NE-04 заблокировал расчёт: " + DECISION_REQUIRED
        )
        st.button(*args, **kwargs)
        return False

    try:
        decision = evaluate_domain_request(project_root, domain_request)
    except Exception:
        # Product UI never turns an evaluator defect into permission.
        kwargs["disabled"] = True
        kwargs["help"] = "NE-04 заблокировал расчёт: NE04_CONFIG_INVALID"
        st.button(*args, **kwargs)
        return False
    if not decision.allowed:
        kwargs["disabled"] = True
        kwargs["help"] = (
            "NE-04 заблокировал расчёт: "
            + ", ".join(decision.reason_codes)
        )
        st.button(*args, **kwargs)
        return False
    return bool(st.button(*args, **kwargs))


def verified_feature_button(
    decision: FeatureRequest | RejectedFeatureReceipt,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Render one capability button from a closed verified-loader decision."""

    if type(decision) is FeatureRequest:
        return bool(st.button(*args, **kwargs))
    if type(decision) is RejectedFeatureReceipt:
        kwargs["disabled"] = True
        kwargs["help"] = (
            f"{decision.reason_code}: {decision.reason_detail}"
        )
        st.button(*args, **kwargs)
        return False
    raise TypeError(
        "verified_feature_button accepts only FeatureRequest or "
        "RejectedFeatureReceipt."
    )


def verified_equilibrium_button(
    decision: FeatureRequest | RejectedFeatureReceipt,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Render a generic B3 equilibrium capability without global policy gates."""

    return verified_feature_button(decision, *args, **kwargs)


def verified_batch_execute_button(
    decision: FeatureRequest | RejectedFeatureReceipt,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Render the B3 batch action solely from its verified capability decision."""

    return verified_feature_button(decision, *args, **kwargs)


def verified_batch_file_uploader(
    decision: FeatureRequest | RejectedFeatureReceipt,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Retained name; B4A delegates all upload authority to StateStore."""

    kwargs["disabled"] = True
    kwargs["help"] = "StateStore owns the verified upload boundary."
    st.button(*args, **kwargs)
    return None


def verified_batch_export_button(
    decision: FeatureRequest | RejectedFeatureReceipt,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Render batch export solely from its prepared capability decision."""

    return verified_feature_button(decision, *args, **kwargs)


def verified_state_uploader(
    decision: FeatureRequest | RejectedFeatureReceipt,
    label: str,
    types: tuple[str, ...],
    key: str,
    render_and_ingest: Callable[
        [str, tuple[str, ...], str],
        VerifiedArtifactRef | RejectedFeatureReceipt,
    ],
) -> VerifiedArtifactRef | RejectedFeatureReceipt:
    """Delegate the only uploader call to the verified state store."""

    if type(decision) is FeatureRequest:
        if not callable(render_and_ingest):
            raise TypeError("render_and_ingest must be callable")
        return render_and_ingest(label, types, key)
    if type(decision) is RejectedFeatureReceipt:
        st.button(
            label,
            disabled=True,
            help=f"{decision.reason_code}: {decision.reason_detail}",
            key=f"{key}_rejected",
        )
        return decision
    raise TypeError(
        "verified_state_uploader accepts only FeatureRequest or "
        "RejectedFeatureReceipt."
    )


def release_file_uploader(*args: Any, **kwargs: Any) -> Any:
    """Retained legacy marker; it never owns an upload widget in B4A."""

    kwargs["disabled"] = True
    kwargs["help"] = IMPORT_BLOCK_REASON
    st.button(*args, **kwargs)
    return None


def render_result_evidence(
    feature_id: str,
    *,
    execution_succeeded: bool,
    software_diagnostic: bool = False,
) -> dict[str, str]:
    """Render the mandatory six-field envelope beside an on-screen result."""

    labels = research_result_evidence(
        execution_succeeded=execution_succeeded,
        software_diagnostic=software_diagnostic,
    )
    st.caption(f"Evidence envelope · feature_id={feature_id}")
    st.code(
        "\n".join(f"{field}={value}" for field, value in labels.items()),
        language="text",
    )
    return labels

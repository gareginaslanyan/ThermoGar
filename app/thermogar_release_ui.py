"""Streamlit controls for the release surface.

The wrappers below stay as thin named call sites so the forty-odd existing
callers keep working, but they no longer carry a policy decision of their
own. Capability decisions that still exist belong to the verified loaders.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator

import streamlit as st

from thermogar_release_policy import research_result_evidence
from thermogar_verified_loaders import FeatureRequest, RejectedFeatureReceipt
from thermogar_verified_state import VerifiedArtifactRef


# Подсказка недоступной кнопки — русская фраза по коду причины (21-Г, раздел
# В; строки 80–81 CSV 21-В). Код и английская деталь на экран не выходят.
REJECTION_HELP_TEXTS = {
    "FEATURE_ID_UNKNOWN": "Это действие недоступно в текущей версии ThermoGar.",
    "FEATURE_REVISION_UNSUPPORTED": "Это действие недоступно в текущей версии ThermoGar.",
    "BINDING_IDENTITY_MISMATCH": "База не подключена. Выберите базу в боковой панели.",
    "GENERATION_STALE": "Выбор базы изменился. Повторите действие.",
    "BINDING_STALE": "Выбор базы изменился. Повторите действие.",
    "INPUT_INVALID": "Введённые значения не проходят проверку.",
    "RAW_PATH_REJECTED": "Введённые значения не проходят проверку.",
    "SCHEMA_INVALID": "Набор фаз задан неверно. Выберите фазы заново.",
    "PHASE_POLICY_MISMATCH": "Набор фаз задан неверно. Выберите фазы заново.",
    "C15_PHASE_REJECTED": "Фаза C15_LAVES для стальной базы исключена. Уберите её из набора фаз.",
    "PHASE_NOT_PRESENT": "Выбранная фаза недоступна для этого состава. Проверьте набор фаз.",
    "PHASE_SET_EMPTY": "Нужно оставить хотя бы одну фазу.",
}
REJECTION_HELP_FALLBACK = "Действие недоступно: исходные данные не прошли проверку."


def rejection_help_text(decision: RejectedFeatureReceipt) -> str:
    """Подсказка недоступной кнопки словами, без кода причины."""

    code = getattr(decision.reason_code, "value", decision.reason_code)
    return REJECTION_HELP_TEXTS.get(str(code), REJECTION_HELP_FALLBACK)


# Решение владельца 25.09.2026, п. 9 (1В): строка основной кнопки — контейнер
# с ключом tg_action_<экран>; style.css прижимает его к нижнему краю окна.
ACTION_ROW_PREFIX = "tg_action_"


@contextmanager
def action_row(screen: str, *, sticky: bool = True) -> Iterator[None]:
    """Строка кнопки: кнопка и причина неактивности под ней."""

    key = f"{ACTION_ROW_PREFIX}{screen}" if sticky else screen
    with st.container(key=key):
        yield


def release_download_button(*args: Any, **kwargs: Any) -> bool:
    """Render a download control."""

    return bool(st.download_button(*args, **kwargs))


def release_calculation_button(
    *args: Any,
    domain_request: Any = None,
    project_root: Any = None,
    **kwargs: Any,
) -> bool:
    """Render a numerical action button.

    ``domain_request`` and ``project_root`` are accepted and ignored so the
    existing call sites keep their signature.
    """

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
        kwargs["help"] = rejection_help_text(decision)
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
            help=rejection_help_text(decision),
            key=f"{key}_rejected",
        )
        return decision
    raise TypeError(
        "verified_state_uploader accepts only FeatureRequest or "
        "RejectedFeatureReceipt."
    )


def release_file_uploader(*args: Any, **kwargs: Any) -> Any:
    """Render a file uploader."""

    return st.file_uploader(*args, **kwargs)


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

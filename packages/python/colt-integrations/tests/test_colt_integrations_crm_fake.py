"""`FakeCRMProvider` — the only `CRMProvider` adapter this milestone builds (CLAUDE.md §30,
§28.1, §93)."""

from __future__ import annotations

import pytest

from colt_integrations.crm.fake import FakeCRMProvider
from colt_integrations.errors import ProviderUnavailableError


async def test_sync_contact_creates_then_updates_the_same_object() -> None:
    provider = FakeCRMProvider()

    created = await provider.sync_contact(external_id="person-1", fields={"email": "a@x.test"})
    assert created.created is True

    updated = await provider.sync_contact(external_id="person-1", fields={"email": "b@x.test"})
    assert updated.created is False
    assert updated.provider_object_id == created.provider_object_id
    assert provider.object_count == 1
    stored = provider.stored_object("CONTACT", "person-1")
    assert stored is not None
    assert stored.fields == {"email": "b@x.test"}


async def test_different_kinds_never_collide_on_the_same_external_id() -> None:
    provider = FakeCRMProvider()

    contact = await provider.sync_contact(external_id="1", fields={})
    company = await provider.sync_company(external_id="1", fields={})
    opportunity = await provider.sync_opportunity(external_id="1", fields={})
    task = await provider.sync_task(external_id="1", fields={})

    object_ids = {
        contact.provider_object_id,
        company.provider_object_id,
        opportunity.provider_object_id,
        task.provider_object_id,
    }
    assert len(object_ids) == 4
    assert provider.object_count == 4


async def test_a_queued_failure_raises_once_then_the_next_call_succeeds() -> None:
    provider = FakeCRMProvider()
    provider.queue_failure("COMPANY", "co-1", ProviderUnavailableError("simulated 500"))

    with pytest.raises(ProviderUnavailableError):
        await provider.sync_company(external_id="co-1", fields={"name": "Acme"})

    result = await provider.sync_company(external_id="co-1", fields={"name": "Acme"})
    assert result.created is True
    assert provider.object_count == 1


async def test_several_queued_failures_are_consumed_in_order() -> None:
    provider = FakeCRMProvider()
    provider.queue_failure("TASK", "t-1", ProviderUnavailableError("first"))
    provider.queue_failure("TASK", "t-1", ProviderUnavailableError("second"))

    with pytest.raises(ProviderUnavailableError, match="first"):
        await provider.sync_task(external_id="t-1", fields={})
    with pytest.raises(ProviderUnavailableError, match="second"):
        await provider.sync_task(external_id="t-1", fields={})

    result = await provider.sync_task(external_id="t-1", fields={})
    assert result.created is True


async def test_authenticate_reflects_the_constructor_flag() -> None:
    assert await FakeCRMProvider(authenticated=True).authenticate() is True
    assert await FakeCRMProvider(authenticated=False).authenticate() is False

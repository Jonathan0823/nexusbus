import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import crud
from app.database.models import PollingTarget, PollingTargetUpdate


@pytest.mark.asyncio
async def test_create_polling_target():
    """Test creating a polling target."""
    mock_session = AsyncMock(spec=AsyncSession)

    target = PollingTarget(
        device_id="test-plc", register_type="holding", address=100, count=5
    )

    result = await crud.create_polling_target(mock_session, target)

    assert result.device_id == "test-plc"
    mock_session.add.assert_called_once_with(target)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_polling_targets_by_device():
    """Test getting targets by device."""
    mock_session = AsyncMock(spec=AsyncSession)

    mock_target = PollingTarget(
        id=1, device_id="test-plc", register_type="holding", address=100
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_target]
    mock_session.execute.return_value = mock_result

    result = await crud.get_polling_targets_by_device(mock_session, "test-plc")

    assert len(result) == 1
    assert result[0].device_id == "test-plc"


@pytest.mark.asyncio
async def test_update_polling_target():
    """Test updating a polling target."""
    mock_session = AsyncMock(spec=AsyncSession)

    existing_target = PollingTarget(id=1, count=1)

    with patch(
        "app.database.crud.get_polling_target",
        new=AsyncMock(return_value=existing_target),
    ):
        update_data = PollingTargetUpdate(count=10)

        result = await crud.update_polling_target(mock_session, 1, update_data)

        assert result.count == 10
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_polling_target():
    """Test deleting a polling target."""
    mock_session = AsyncMock(spec=AsyncSession)

    existing_target = PollingTarget(id=1, is_active=True)

    with patch(
        "app.database.crud.get_polling_target",
        new=AsyncMock(return_value=existing_target),
    ):
        success = await crud.delete_polling_target(mock_session, 1)

        assert success is True
        assert existing_target.is_active is False
        mock_session.commit.assert_awaited_once()

"""
Unit tests for tool_handlers.py
"""

import json
from unittest.mock import AsyncMock

import pytest

from src.tool_handlers import handle_retrieve_attachment
from src.entity_registry import get_entity


def _parse(result):
    """Parse TextContent result to dict."""
    return json.loads(result[0].text)


@pytest.fixture
def mock_client():
    """Create a mock AgiloftClient."""
    return AsyncMock()


@pytest.fixture
def attachment_entity():
    """Get the attachment entity config."""
    return get_entity("attachment")


class TestHandleRetrieveAttachment:
    """Tests for the retrieve_attachment handler."""

    @pytest.mark.asyncio
    async def test_successful_download(self, mock_client, attachment_entity):
        """Should return file metadata on success."""
        mock_client.retrieve_attachment.return_value = {
            "file_path": "/Users/test/Downloads/agiloft/contract.docx",
            "file_name": "contract.docx",
            "file_size_bytes": 12345,
            "content_type": "application/octet-stream",
            "record_id": 612,
            "field": "attached_file",
        }

        result = await handle_retrieve_attachment(
            attachment_entity,
            {"record_id": 612, "field": "attached_file"},
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is True
        assert data["operation"] == "retrieve_attachment"
        assert data["data"]["file_path"] == "/Users/test/Downloads/agiloft/contract.docx"
        assert data["data"]["file_size_bytes"] == 12345

    @pytest.mark.asyncio
    async def test_sandbox_path_rejected(self, mock_client, attachment_entity):
        """Should reject sandbox save_dir with a helpful message."""
        result = await handle_retrieve_attachment(
            attachment_entity,
            {
                "record_id": 612,
                "field": "attached_file",
                "save_dir": "/mnt/user-data/downloads",
            },
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "sandbox" in data["error"].lower()
        # Should not have called the client at all
        mock_client.retrieve_attachment.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_error(self, mock_client, attachment_entity):
        """Should return error on API failure."""
        mock_client.retrieve_attachment.side_effect = Exception("API down")

        result = await handle_retrieve_attachment(
            attachment_entity,
            {"record_id": 612, "field": "attached_file"},
            mock_client,
        )
        data = _parse(result)

        assert data["success"] is False
        assert "API down" in data["error"]

    @pytest.mark.asyncio
    async def test_passes_save_dir(self, mock_client, attachment_entity):
        """Should pass save_dir through to the client."""
        mock_client.retrieve_attachment.return_value = {
            "file_path": "/Users/test/custom/contract.docx",
            "file_name": "contract.docx",
            "file_size_bytes": 100,
            "content_type": "application/pdf",
            "record_id": 612,
            "field": "attached_file",
        }

        await handle_retrieve_attachment(
            attachment_entity,
            {
                "record_id": 612,
                "field": "attached_file",
                "save_dir": "/Users/test/custom",
            },
            mock_client,
        )

        call_kwargs = mock_client.retrieve_attachment.call_args
        assert call_kwargs[1]["save_dir"] == "/Users/test/custom"

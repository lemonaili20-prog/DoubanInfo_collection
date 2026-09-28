from unittest.mock import Mock, patch

from app.doubaninfo import DoubanInfoClient


def test_client_uses_api_key_header():
    client = DoubanInfoClient(
        api_key="test-key",
        base_url="https://example.com/api",
    )

    assert client.session.headers["X-API-KEY"] == "test-key"


@patch("app.doubaninfo.requests.Session.get")
def test_search(mock_get):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "success": True,
        "title": "Test Movie",
        "year": 2026,
    }
    mock_get.return_value = response

    client = DoubanInfoClient(
        api_key="test-key",
        base_url="https://example.com/api",
    )

    result = client.search("Test Movie 2026")

    assert result["success"] is True
    assert result["title"] == "Test Movie"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["params"]["url"] == "Test Movie 2026"

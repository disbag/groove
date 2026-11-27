from unittest.mock import Mock, patch

import pytest
import requests

from pipeline.discogs import Discogs, DiscogsAuthError


@pytest.mark.parametrize("status", [401, 403])
def test_access_denied_stops_requests(status):
    client = Discogs()
    with patch.object(client.session, "get", return_value=Mock(status_code=status)) as get:
        with pytest.raises(DiscogsAuthError):
            client.release(1)
        get.assert_called_once()


def test_rate_limit_uses_retry_after():
    client = Discogs()
    limited = requests.Response()
    limited.status_code = 429
    limited.headers["Retry-After"] = "7"
    ok = Mock(status_code=200, headers={})
    ok.json.return_value = {"id": 1}
    with patch.object(client.session, "get", side_effect=[limited, ok]), patch("pipeline.discogs.time.sleep") as sleep:
        assert client.release(1) == {"id": 1}
        sleep.assert_any_call(7)

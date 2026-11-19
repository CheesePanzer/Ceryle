import pytest
from fastapi import HTTPException

from middlewares import verify_api_key


async def test_verify_api_key_accepts_exact_key():
    await verify_api_key("test-api-key")


@pytest.mark.parametrize("api_key", [None, "", "test", "test-api-key-extra"])
async def test_verify_api_key_rejects_missing_or_partial_key(api_key):
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(api_key)

    assert exc_info.value.status_code == 401

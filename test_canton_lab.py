import asyncio
import json
import os
from decimal import Decimal

import httpx

os.environ.setdefault("CANTOR8_CLIENT_ID", "test-client")
os.environ.setdefault("CANTOR8_CLIENT_SECRET", "test-secret")

import canton_lab


async def verify() -> None:
    """Verify authentication, string offsets, response shape, and CC summation."""
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL(canton_lab.AUTH_URL):
            return httpx.Response(200, json={"access_token": "test-token"})

        if request.url.path.endswith("/v2/state/ledger-end"):
            return httpx.Response(200, json={"offset": "42"})

        if request.url.path.endswith("/v2/state/active-contracts"):
            captured_request["authorization"] = request.headers["Authorization"]
            captured_request["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json=[
                    {
                        "contractEntry": {
                            "activeContract": {
                                "templateId": (
                                    "package-id:Splice.Api.Token.HoldingV1:Holding"
                                ),
                                "createArguments": {"amount": "1.25"},
                            }
                        }
                    },
                    {
                        "contractEntry": {
                            "activeContract": {
                                "templateId": (
                                    "package-id:Splice.Api.Token.HoldingV1:Holding"
                                ),
                                "createArguments": {"amount": "2.75"},
                            }
                        }
                    },
                    {
                        "contractEntry": {
                            "activeContract": {
                                "templateId": "package-id:Other:Contract",
                                "createArguments": {"amount": "999"},
                            }
                        }
                    },
                ],
            )

        return httpx.Response(404, text=f"Unexpected test URL: {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        token = await canton_lab.get_auth_token(client)
        active_at_offset = await canton_lab.get_ledger_end(client, token)
        balance = await canton_lab.get_cc_balance(
            client, token, active_at_offset
        )

    expected_payload = {
        "eventFormat": {
            "filtersByParty": {
                canton_lab.PARTY_ID: {
                    "cumulative": [
                        {
                            "identifierFilter": {
                                "WildcardFilter": {
                                    "value": {"includeCreatedEventBlob": True}
                                }
                            }
                        }
                    ]
                }
            },
            "verbose": False,
        },
        "activeAtOffset": "42",
    }

    assert active_at_offset == "42"
    assert captured_request["authorization"] == "Bearer test-token"
    assert captured_request["payload"] == expected_payload
    assert balance == Decimal("4.00")

    print("Mock verification passed.")


if __name__ == "__main__":
    asyncio.run(verify())

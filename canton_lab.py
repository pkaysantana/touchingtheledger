import asyncio
import os
from decimal import Decimal, InvalidOperation

import httpx
from dotenv import load_dotenv

# Load credentials from the local .env file.
load_dotenv()

AUTH_URL = (
    "https://auth.dev.digik.cantor8.tech/realms/master/"
    "protocol/openid-connect/token"
)
CLIENT_ID = os.getenv("CANTOR8_CLIENT_ID")
CLIENT_SECRET = os.getenv("CANTOR8_CLIENT_SECRET")

LEDGER_API_BASE = "https://api.validator.dev.digik.cantor8.tech/api/ledger"
PARTY_ID = (
    "don::1220446bb4f24a1da5f217a07c5501bf1da0173911d16669d9a81932ab5e186ed457"
)

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError(
        "Critical Security Error: Missing Identity Provider credentials in .env"
    )


async def get_auth_token(client: httpx.AsyncClient) -> str:
    """Obtain a fresh JWT access token from the Keycloak identity provider."""
    response = await client.post(
        AUTH_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    response.raise_for_status()

    body = response.json()
    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Identity Provider response did not contain an access_token")
    return token


def extract_active_contract(entry: dict) -> dict | None:
    """Accept the requested response shape and Canton's documented V2 wrapper."""
    active_contract = entry.get("activeContract")
    if isinstance(active_contract, dict):
        return active_contract

    contract_entry = entry.get("contractEntry")
    if not isinstance(contract_entry, dict):
        return None

    wrapped_contract = contract_entry.get("JsActiveContract")
    if not isinstance(wrapped_contract, dict):
        return None

    created_event = wrapped_contract.get("createdEvent")
    if not isinstance(created_event, dict):
        return None

    return {
        "templateId": created_event.get("templateId"),
        "createArguments": created_event.get(
            "createArguments", created_event.get("createArgument")
        ),
    }


def parse_amount(create_arguments: dict, contract_index: int) -> Decimal:
    """Read a Holding amount without introducing floating-point rounding."""
    amount = create_arguments.get("amount")
    if amount is None:
        raise ValueError(
            f"Holding contract entry {contract_index} has no createArguments.amount"
        )

    try:
        return Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Holding contract entry {contract_index} has invalid amount: {amount!r}"
        ) from exc


async def get_cc_balance(client: httpx.AsyncClient, token: str) -> Decimal:
    """Query active Holding contracts and return their total Canton Coin amount."""
    url = f"{LEDGER_API_BASE}/v2/state/active-contracts"
    payload = {
        "eventFormat": {
            "filtersByParty": {
                PARTY_ID: {
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
        "activeAtOffset": "",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = await client.post(url, headers=headers, json=payload)
    if response.is_error:
        print(
            f"Ledger API error {response.status_code} "
            f"{response.reason_phrase}:\n{response.text}"
        )
    response.raise_for_status()

    entries = response.json()
    if not isinstance(entries, list):
        raise ValueError(
            "Ledger API response must be a list of active contract entries"
        )

    balance = Decimal("0")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue

        active_contract = extract_active_contract(entry)
        if active_contract is None:
            continue

        template_id = active_contract.get("templateId")
        if not isinstance(template_id, str) or "Holding" not in template_id:
            continue

        create_arguments = active_contract.get("createArguments")
        if not isinstance(create_arguments, dict):
            raise ValueError(
                f"Holding contract entry {index} has invalid createArguments"
            )

        balance += parse_amount(create_arguments, index)

    return balance


async def main() -> None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await get_auth_token(client)
            balance = await get_cc_balance(client, token)
            print(f"Final CC balance: {balance}")
    except httpx.HTTPStatusError as exc:
        print(
            f"HTTP Error: {exc.response.status_code} - {exc.response.text}"
        )
    except httpx.RequestError as exc:
        print(f"Network Error: {exc}")
    except Exception as exc:
        print(f"An unexpected error occurred: {exc}")


if __name__ == "__main__":
    asyncio.run(main())

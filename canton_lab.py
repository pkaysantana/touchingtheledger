import asyncio
import json
import os
from collections.abc import Callable

import httpx
from dotenv import load_dotenv

# Load credentials from the .env file
load_dotenv()

AUTH_URL = "https://auth.dev.digik.cantor8.tech/realms/master/protocol/openid-connect/token"
CLIENT_ID = os.getenv("CANTOR8_CLIENT_ID")
CLIENT_SECRET = os.getenv("CANTOR8_CLIENT_SECRET")

ADMIN_API_BASE = "https://api.validator.dev.digik.cantor8.tech/api/validator"
LEDGER_API_BASE = "https://api.validator.dev.digik.cantor8.tech/api/ledger"

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError(
        "Critical Security Error: Missing Identity Provider credentials in .env"
    )


async def get_auth_token() -> str:
    """Obtains a fresh JWT access token from the Keycloak IdP."""
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        print("Requesting token from IdP...")
        response = await client.post(AUTH_URL, data=data)
        response.raise_for_status()
        body = response.json()
        print("Successfully authenticated!")
        return body["access_token"]


def prompt_for_signature(topology_hash: str) -> str:
    """Prompts for an Ed25519 signature produced by the external party's key."""
    print(
        "\nSign the decoded bytes of this hex topology hash with the "
        "external party's Ed25519 private key:"
    )
    print(topology_hash)
    return input("Paste the 64-byte signature as 128 hex characters: ").strip()


async def post_json_with_diagnostics(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    payload: dict,
    stage: str,
) -> dict:
    """Posts JSON and prints the complete response body when the API rejects it."""
    try:
        response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        print(f"\n{stage} failed before an HTTP response was received.")
        print(f"Request: {exc.request.method} {exc.request.url}")
        print(f"Transport error: {exc!r}")
        raise

    if response.is_error:
        print(f"\n{stage} failed.")
        print(f"Request: {response.request.method} {response.request.url}")
        print(f"Request JSON:\n{json.dumps(payload, indent=2)}")
        print(f"HTTP status: {response.status_code} {response.reason_phrase}")
        print("Response body (verbatim):")
        print(response.text if response.text else "<empty response body>")

        try:
            error_json = response.json()
        except (json.JSONDecodeError, ValueError):
            pass
        else:
            print("Response body (formatted JSON):")
            print(json.dumps(error_json, indent=2, ensure_ascii=False))

    response.raise_for_status()

    try:
        return response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"\n{stage} returned HTTP {response.status_code}, but not valid JSON.")
        print("Response body (verbatim):")
        print(response.text if response.text else "<empty response body>")
        raise RuntimeError(f"{stage} returned invalid JSON") from exc


async def allocate_party(
    headers: dict,
    party_hint: str,
    public_key: str,
    sign_hash: Callable[[str], str] = prompt_for_signature,
) -> str:
    """Generates, signs, and submits topology for an externally controlled party."""
    if not party_hint:
        raise ValueError("party_hint must not be empty")
    if len(public_key) != 64:
        raise ValueError(
            "public_key must be a 32-byte Ed25519 public key encoded as 64 hex characters"
        )
    try:
        bytes.fromhex(public_key)
    except ValueError as exc:
        raise ValueError("public_key must contain only hexadecimal characters") from exc

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Step 2a: Generating topology transaction...")
        gen_url = f"{ADMIN_API_BASE}/v0/admin/external-party/topology/generate"
        generate_payload = {
            "party_hint": party_hint,
            "public_key": public_key,
        }
        generated = await post_json_with_diagnostics(
            client,
            gen_url,
            headers,
            generate_payload,
            "Topology generation",
        )

        party_id = generated.get("party_id")
        topology_txs = generated.get("topology_txs")
        if not isinstance(party_id, str) or not isinstance(topology_txs, list):
            print("Unexpected generate response:")
            print(json.dumps(generated, indent=2, ensure_ascii=False))
            raise ValueError(
                "Generate response must contain string 'party_id' and list 'topology_txs'"
            )

        signed_topology_txs = []
        for index, topology_tx in enumerate(topology_txs):
            if not isinstance(topology_tx, dict):
                raise ValueError(f"topology_txs[{index}] must be a JSON object")

            encoded_tx = topology_tx.get("topology_tx")
            topology_hash = topology_tx.get("hash")
            if not isinstance(encoded_tx, str) or not isinstance(topology_hash, str):
                print("Unexpected topology transaction:")
                print(json.dumps(topology_tx, indent=2, ensure_ascii=False))
                raise ValueError(
                    f"topology_txs[{index}] must contain 'topology_tx' and 'hash'"
                )

            signed_hash = sign_hash(topology_hash)
            if len(signed_hash) != 128:
                raise ValueError(
                    f"Signature {index + 1} must be 64 bytes encoded as 128 hex characters"
                )
            try:
                bytes.fromhex(signed_hash)
            except ValueError as exc:
                raise ValueError(
                    f"Signature {index + 1} must contain only hexadecimal characters"
                ) from exc

            signed_topology_txs.append(
                {
                    "topology_tx": encoded_tx,
                    "signed_hash": signed_hash,
                }
            )

        print("Step 2b: Submitting topology transaction...")
        submit_url = f"{ADMIN_API_BASE}/v0/admin/external-party/topology/submit"
        submit_payload = {
            "public_key": public_key,
            "signed_topology_txs": signed_topology_txs,
        }
        submitted = await post_json_with_diagnostics(
            client,
            submit_url,
            headers,
            submit_payload,
            "Topology submission",
        )

        submitted_party_id = submitted.get("party_id")
        if not isinstance(submitted_party_id, str):
            print("Unexpected submit response:")
            print(json.dumps(submitted, indent=2, ensure_ascii=False))
            raise ValueError("Submit response must contain string 'party_id'")
        if submitted_party_id != party_id:
            raise ValueError(
                "Submit response party_id does not match the generated party_id"
            )

        print(f"\nSuccess! Your allocated Party ID is:\n{submitted_party_id}\n")
        return submitted_party_id


async def main():
    try:
        # Step 1: Secure access token
        token = await get_auth_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        print("Successfully authenticated!\n")

        # Step 2: Allocate the new externally controlled party
        party_hint = input("Party hint: ").strip()
        public_key = input(
            "Ed25519 public key (32 bytes, encoded as 64 hex characters): "
        ).strip()
        party_id = await allocate_party(headers, party_hint, public_key)

        # (Next: We will use this party_id to create the PreApproval DAML contract)

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())

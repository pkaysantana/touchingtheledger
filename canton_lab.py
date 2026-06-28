import asyncio
import httpx

# Coordinates from your lab brief
AUTH_URL = "https://auth.dev.digik.cantor8.tech/realms/master/protocol/openid-connect/token"
CLIENT_ID = "hackathon"
CLIENT_SECRET = "0JElLeAZK7fcRF4ngghM2s7XWxPgDYSD"

ADMIN_API_BASE = "https://api.validator.dev.digik.cantor8.tech/api/validator"
LEDGER_API_BASE = "https://api.validator.dev.digik.cantor8.tech/api/ledger"


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


async def allocate_party(headers: dict) -> str:
    """Generates and submits the topology to allocate a new internal party."""
    async with httpx.AsyncClient() as client:
        print("Step 2a: Generating topology transaction...")
        gen_url = f"{ADMIN_API_BASE}/v0/admin/external-party/topology/generate"

        # Sending an empty payload is standard for generating a new party without a specific hint
        gen_response = await client.post(gen_url, headers=headers, json={})
        gen_response.raise_for_status()
        topology_tx = gen_response.json()

        print("Step 2b: Submitting topology transaction...")
        submit_url = f"{ADMIN_API_BASE}/v0/admin/external-party/topology/submit"

        submit_response = await client.post(
            submit_url, headers=headers, json=topology_tx
        )
        submit_response.raise_for_status()

        # Canton's topology submit response contains the assigned Party ID
        result = submit_response.json()
        party_id = result.get("partyId")

        print(f"\n Success! Your allocated Party ID is:\n{party_id}\n")
        return party_id


async def main():
    try:
        # Step 1: Secure access token
        token = await get_auth_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        print("Successfully authenticated!\n")

        # Step 2: Allocate the new party
        party_id = await allocate_party(headers)

        # (Next: We will use this party_id to create the PreApproval DAML contract)

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())

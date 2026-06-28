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


async def main():
    try:
        # Step 1: Secure your access token
        token = await get_auth_token()

        # This header dictionary will be reused for all subsequent API requests
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        print(f"\nYour JWT is ready (truncated): {token[:30]}...")

        # Next step will go here (Registering the internal party)

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())

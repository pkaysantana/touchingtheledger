# Touching the Ledger

Python lab client for querying the Canton Coin balance of the configured party
through the Cantor8 V2 JSON Ledger API.

## Requirements

- Python 3.10 or newer
- Access to the Cantor8 hackathon validator

## Setup

Create and activate a project-local virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For Bash:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Copy the environment template and provide the assigned credentials:

```powershell
Copy-Item .env.example .env
```

```dotenv
CANTOR8_CLIENT_ID="hackathon"
CANTOR8_CLIENT_SECRET="your-assigned-client-secret"
```

The application stops before making a network request when either credential
is missing.

## Run

```powershell
python canton_lab.py
```

The script:

1. Obtains a short-lived JWT from Keycloak.
2. Gets the current string offset from `/v2/state/ledger-end`.
3. Queries `/v2/state/active-contracts` at that offset for the configured
   Canton Party ID.
4. Selects active contracts whose template ID contains `Holding`.
5. Adds their `createArguments.amount` values using decimal arithmetic.
6. Prints the final Canton Coin balance.

## Security

The following paths are intentionally excluded from Git:

- `.env`
- `.venv/`
- `secrets/`
- `topology_tx.json`

Never commit OAuth credentials or the external party's Ed25519 private key.
Moving a previously committed credential into `.env` does not remove it from
Git history; rotate any credential that was previously committed or shared.

## API behavior

The active-contract endpoint returns a point-in-time ledger snapshot. Each
item is read from `contractEntry.activeContract`, and offsets remain strings
end-to-end to avoid 64-bit precision loss.

The query is read-only. It does not create, archive, exercise, or transfer any
ledger contracts.

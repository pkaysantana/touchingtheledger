# Touching the Ledger

Python lab client for authenticating with the Cantor8 Keycloak identity
provider and onboarding an externally controlled party through the Canton
Validator Admin API.

## Requirements

- Python 3.10 or newer
- OpenSSL with Ed25519 support for external-party signatures
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
2. Requests external-party topology transactions using a party hint and a
   hex-encoded Ed25519 public key.
3. Prompts for a signature over each returned topology hash.
4. Submits the unchanged topology transactions with their signatures.
5. Prints the allocated Canton Party ID.

## Secret handling

The following paths are intentionally excluded from Git:

- `.env`
- `.venv/`
- `secrets/`
- `topology_tx.json`

Never commit the OAuth client secret or Ed25519 private key. On Windows, the
`secrets` directory and private key should have NTFS access restricted to the
owning user. Back up the private key in secure encrypted storage; losing it
removes the ability to sign as the external party.

Moving a previously committed credential into `.env` does not remove it from
Git history. Rotate any credential that was previously committed or shared.

## API notes

The validator endpoints under
`/v0/admin/external-party/` onboard an externally controlled party. They are
not the same as allocating a participant-managed internal party through the
Ledger API.

The topology submit request requires the original generated topology
transactions and an Ed25519 signature for every returned hash. The private key
must remain local and must never be sent to the validator.

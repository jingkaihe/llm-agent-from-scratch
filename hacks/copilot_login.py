import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import requests

COPILOT_CLIENT_ID = "Iv1.b507a08c87ecfe98"
COPILOT_DEVICE_URL = "https://github.com/login/device/code"
COPILOT_TOKEN_URL = "https://github.com/login/oauth/access_token"
COPILOT_EXCHANGE_URL = "https://api.github.com/copilot_internal/v2/token"
COPILOT_SCOPES = ["read:user", "user:email", "copilot"]


class CopilotAuthError(Exception):
    """Raised when Copilot authentication fails"""

    pass


@contextmanager
def error_handler(operation: str):
    """Context manager for consistent error handling"""
    try:
        yield
    except requests.RequestException as e:
        raise CopilotAuthError(f"Failed to {operation}: {e}") from e
    except KeyError as e:
        raise CopilotAuthError(
            f"Invalid response during {operation}: missing {e}"
        ) from e
    except Exception as e:
        raise CopilotAuthError(f"Unexpected error during {operation}: {e}") from e


def generate_device_flow() -> dict:
    """Initiate GitHub device authorization flow for Copilot"""
    with error_handler("generate device code"):
        response = requests.post(
            COPILOT_DEVICE_URL,
            data={
                "client_id": COPILOT_CLIENT_ID,
                "scope": " ".join(COPILOT_SCOPES),
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "llm-agent-from-scratch",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def poll_for_token(device_code: str, interval: int, expires_in: int) -> dict:
    """Poll GitHub OAuth endpoint for user authorization"""
    timeout = time.time() + expires_in
    current_interval = interval

    while time.time() < timeout:
        time.sleep(current_interval)

        with error_handler("poll for token"):
            response = requests.post(
                COPILOT_TOKEN_URL,
                data={
                    "client_id": COPILOT_CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            error = data.get("error")
            if not error:
                return data
            elif error == "authorization_pending":
                continue
            elif error == "slow_down":
                current_interval += 5
                continue
            elif error in ("expired_token", "access_denied"):
                raise CopilotAuthError(
                    f"Authentication failed: {error} - {data.get('error_description', '')}"
                )

    raise CopilotAuthError("Authentication timed out")


def exchange_for_copilot_token(access_token: str) -> dict:
    """Exchange GitHub OAuth token for Copilot-specific token"""
    with error_handler("exchange for Copilot token"):
        response = requests.get(
            COPILOT_EXCHANGE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Editor-Version": "vscode/1.102.0",
                "Copilot-Integration-Id": "vscode-chat",
                "Accept": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def save_credentials(credentials: dict, output_path: Path) -> None:
    """Save credentials to JSON file"""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(credentials, f, indent=2)
        print(f"✓ Credentials saved to: {output_path}")
    except Exception as e:
        raise CopilotAuthError(f"Failed to save credentials: {e}") from e


def copilot_login(output_path: Optional[Path] = None) -> dict:
    """
    Perform GitHub Copilot OAuth device flow authentication.

    Returns:
        Dictionary containing authentication credentials
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent / ".copilot.json"

    print("=" * 60)
    print("GitHub Copilot OAuth Login")
    print("=" * 60)
    print("\nStarting GitHub Copilot OAuth device flow...\n")

    device_response = generate_device_flow()

    verification_uri = device_response["verification_uri"]
    user_code = device_response["user_code"]
    device_code = device_response["device_code"]
    interval = device_response["interval"]
    expires_in = device_response["expires_in"]

    print("To authenticate with GitHub Copilot:")
    print(f"  1. Open this URL in your browser: {verification_uri}")
    print(f"  2. Enter this code when prompted: {user_code}")
    print()
    print("Waiting for authentication to complete...")
    print("(This may take a few moments...)\n")

    token_response = poll_for_token(device_code, interval, expires_in)

    access_token = token_response["access_token"]
    scope = token_response.get("scope", "")

    print("Exchanging token for Copilot access...")
    copilot_response = exchange_for_copilot_token(access_token)

    copilot_token = copilot_response["token"]
    copilot_expires_at = copilot_response["expires_at"]

    credentials = {
        "access_token": access_token,
        "copilot_token": copilot_token,
        "scope": scope,
        "copilot_expires_at": copilot_expires_at,
    }

    save_credentials(credentials, output_path)

    print("\n" + "=" * 60)
    print("✓ Authentication successful!")
    print("=" * 60)
    print("\nYou can now use GitHub Copilot subscription-based models.")
    print()

    return credentials


if __name__ == "__main__":
    try:
        copilot_login()
    except CopilotAuthError as e:
        print(f"\n❌ Error: {e}")
        exit(1)
    except KeyboardInterrupt:
        print("\n\n❌ Authentication cancelled by user")
        exit(1)

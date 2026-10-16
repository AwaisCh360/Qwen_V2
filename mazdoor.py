import requests
import time
import re
import urllib.parse
import logging
import config

logger = logging.getLogger("mazdoor")

class MazdoorMail:
    """Wrapper for Mazdoor temporary email service (berozgaar.mazdoor.me)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.MAZDOOR_API_KEY
        self.session_id = None
        self.email = None
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        if self.api_key:
            self.http.headers["x-api-key"] = self.api_key

    def create_inbox(self) -> str | None:
        """
        Creates an inbox on Mazdoor API. Uses x-api-key if available,
        otherwise falls back to anonymous session token.
        """
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            else:
                # Fallback: GET /api/session
                res = self.http.get(f"{config.MAZDOOR_BASE_URL}/session", timeout=config.REQUEST_TIMEOUT)
                if res.status_code != 200:
                    logger.error(f"Failed to get Mazdoor session: {res.status_code} - {res.text}")
                    return None
                data = res.json()
                self.session_id = data.get("sessionId")
                if not self.session_id:
                    return None
                headers["x-session-id"] = self.session_id

            # POST /api/inboxes
            res2 = self.http.post(f"{config.MAZDOOR_BASE_URL}/inboxes", headers=headers, json={}, timeout=config.REQUEST_TIMEOUT)
            if res2.status_code not in (200, 201):
                logger.error(f"Failed to create Mazdoor inbox: {res2.status_code} - {res2.text}")
                return None
            inbox_data = res2.json()
            self.email = inbox_data.get("address")
            return self.email
        except Exception as e:
            logger.error(f"Exception creating Mazdoor inbox: {e}")
            return None

    def get_otp_code(self, timeout: int = 90) -> str | None:
        """
        Polls GET /api/inboxes/:address/messages for incoming Qwen verification OTP.
        Filters out hex colors and extracts the 6-digit verification code.
        """
        if not self.email:
            logger.error("Inbox not initialized")
            return None

        encoded_email = urllib.parse.quote(self.email)
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        elif self.session_id:
            headers["x-session-id"] = self.session_id

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                res = self.http.get(
                    f"{config.MAZDOOR_BASE_URL}/inboxes/{encoded_email}/messages",
                    headers=headers,
                    timeout=config.REQUEST_TIMEOUT
                )
                if res.status_code == 200:
                    messages = res.json()
                    if isinstance(messages, list) and len(messages) > 0:
                        for msg in messages:
                            content = msg.get("html") or msg.get("body") or msg.get("subject", "")
                            # Remove hex color codes like #ffffff or #123456
                            clean_text = re.sub(r'#[0-9a-fA-F]{3,8}\b', '', str(content))
                            # Search for 6-digit numerical OTP
                            codes = re.findall(r'\b([0-9]{6})\b', clean_text)
                            if codes:
                                return codes[0]
            except Exception:
                pass
            time.sleep(1.0)

        return None

    def list_inboxes(self) -> list:
        """Fetch all inboxes linked with this API key."""
        try:
            headers = {"x-api-key": self.api_key} if self.api_key else {}
            res = self.http.get(f"{config.MAZDOOR_BASE_URL}/inboxes", headers=headers, timeout=config.REQUEST_TIMEOUT)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"Error listing inboxes: {e}")
        return []

    def get_messages(self, email: str | None = None) -> list:
        """Fetch all raw messages for a given inbox address."""
        target_email = email or self.email
        if not target_email:
            return []
        try:
            encoded_email = urllib.parse.quote(target_email)
            headers = {"x-api-key": self.api_key} if self.api_key else {}
            res = self.http.get(
                f"{config.MAZDOOR_BASE_URL}/inboxes/{encoded_email}/messages",
                headers=headers,
                timeout=config.REQUEST_TIMEOUT
            )
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"Error fetching messages for {target_email}: {e}")
        return []

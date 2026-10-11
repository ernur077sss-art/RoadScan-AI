from dataclasses import dataclass, field
from pathlib import Path
import os
import secrets


@dataclass
class Settings:
    environment: str = field(default_factory=lambda: os.getenv('ROADSCAN_ENV', 'development'))
    database_url: str = field(default_factory=lambda: os.getenv('ROADSCAN_DATABASE_URL', 'sqlite:///./.data/roadscan.db'))
    origin: str = field(default_factory=lambda: os.getenv('ROADSCAN_ORIGIN', 'http://localhost:3000'))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv('ROADSCAN_DATA_DIR', '.data')))
    secret: str = field(default_factory=lambda: os.getenv('ROADSCAN_SECRET', ''))
    auth_mode: str = field(default_factory=lambda: os.getenv('ROADSCAN_AUTH_MODE', 'password'))
    sms_mode: str = field(default_factory=lambda: os.getenv('ROADSCAN_SMS_MODE', 'development'))
    sms_url: str = field(default_factory=lambda: os.getenv('ROADSCAN_SMS_URL', ''))
    sms_token: str = field(default_factory=lambda: os.getenv('ROADSCAN_SMS_TOKEN', ''))
    integration_mode: str = field(default_factory=lambda: os.getenv('ROADSCAN_109_MODE', 'disabled'))
    storage: str = field(default_factory=lambda: os.getenv('ROADSCAN_STORAGE', 'local'))
    s3_endpoint: str = field(default_factory=lambda: os.getenv('ROADSCAN_S3_ENDPOINT', ''))
    s3_bucket: str = field(default_factory=lambda: os.getenv('ROADSCAN_S3_BUCKET', ''))
    max_upload: int = 25 * 1024 * 1024

    def prepare(self):
        if self.environment not in {'development', 'test', 'production'}:
            raise ValueError('Unknown ROADSCAN_ENV')
        if self.sms_mode not in {'development', 'bridge'}:
            raise ValueError('Unknown SMS mode')
        if self.auth_mode not in {'password', 'otp'}:
            raise ValueError('Unknown authentication mode')
        if self.integration_mode not in {'disabled', 'simulator'}:
            raise ValueError('Real 109 adapter requires the official API contract')
        if self.storage not in {'local', 's3'}:
            raise ValueError('Unknown storage backend')
        if self.environment == 'production':
            if len(self.secret) < 32 or not self.origin.startswith('https://'):
                raise ValueError('Production requires HTTPS origin and a strong ROADSCAN_SECRET')
            if self.auth_mode == 'otp' and (self.sms_mode != 'bridge' or not self.sms_url.startswith('https://') or not self.sms_token):
                raise ValueError('Production requires a configured HTTPS SMS bridge')
            if not self.database_url.startswith('postgresql') or self.storage != 's3':
                raise ValueError('Production requires PostgreSQL and private S3 storage')
            if self.integration_mode == 'simulator':
                raise ValueError('109 simulator is forbidden in production')
        if self.storage == 's3' and not self.s3_bucket:
            raise ValueError('ROADSCAN_S3_BUCKET is required')
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.secret:
            secret_file = self.data_dir / 'session-key'
            try:
                with secret_file.open('x') as f:
                    secret_file.chmod(0o600)
                    f.write(secrets.token_urlsafe(48))
            except FileExistsError:
                pass
            self.secret = secret_file.read_text().strip()
        return self

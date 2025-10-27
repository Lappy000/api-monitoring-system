"""Configuration management with Pydantic settings."""

import os
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import yaml


class EndpointConfig(BaseModel):
    """Configuration for a single endpoint."""
    name: str
    url: str
    method: str = "GET"
    interval: int = 60
    timeout: int = 5
    expected_status: int = 200
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    is_active: bool = True


class EmailConfig(BaseModel):
    """Email notification configuration."""
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    from_addr: str = ""
    from_name: str = "API Monitor"
    to_addrs: List[str] = Field(default_factory=list)
    subject_template: str = "🚨 Alert: {endpoint_name} is DOWN"
    body_template: str = "Endpoint {endpoint_name} is unreachable. Error: {error}"


class WebhookConfig(BaseModel):
    """Webhook notification configuration."""
    enabled: bool = False
    url: str = ""
    method: str = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    retry_count: int = 3
    retry_delay: int = 5
    timeout: int = 10
    payload_template: str = '{{"text": "Alert: {endpoint_name} is DOWN"}}'


class TelegramConfig(BaseModel):
    """Telegram notification configuration."""
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    message_template: str = "🚨 *{endpoint_name}* is DOWN\nError: {error}"
    parse_mode: str = "Markdown"


class NotificationsConfig(BaseModel):
    """Notifications configuration."""
    enabled: bool = True
    cooldown_seconds: int = 300
    send_recovery: bool = True
    email: EmailConfig = Field(default_factory=EmailConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class DatabaseConfig(BaseModel):
    """Database configuration."""
    type: str = "sqlite"
    url: str = "sqlite+aiosqlite:///./data/api_monitor.db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_pre_ping: bool = True
    echo: bool = False


class MonitoringConfig(BaseModel):
    """Monitoring settings."""
    check_history_days: int = 90
    cleanup_interval: int = 86400
    max_concurrent_checks: int = 20


class RetryConfig(BaseModel):
    """Retry configuration."""
    enabled: bool = True
    max_attempts: int = 3
    base_delay: int = 1
    multiplier: int = 2
    max_delay: int = 60
    jitter: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/api_monitor.log"
    console: bool = True


class PrometheusConfig(BaseModel):
    """Prometheus metrics configuration."""
    enabled: bool = False
    port: int = 9090
    path: str = "/metrics"


class CORSConfig(BaseModel):
    """CORS configuration."""
    enabled: bool = True
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: List[str] = Field(default_factory=lambda: ["*"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])


class AuthConfig(BaseModel):
    """API authentication configuration."""
    enabled: bool = False
    api_key: str = ""
    header_name: str = "X-API-Key"


class APIConfig(BaseModel):
    """API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    cors: CORSConfig = Field(default_factory=CORSConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)


class Config(BaseModel):
    """Main configuration class."""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    endpoints: List[EndpointConfig] = Field(default_factory=list)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    api: APIConfig = Field(default_factory=APIConfig)


class Settings(BaseSettings):
    """Environment-based settings."""
    app_env: str = Field(default="development", alias="APP_ENV")
    config_path: str = Field(default="config/config.yaml", alias="CONFIG_PATH")
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    log_level: Optional[str] = Field(default=None, alias="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def load_config() -> Config:
    """
    Load configuration from YAML file and environment variables.
    
    Returns:
        Config: Loaded configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    settings = Settings()
    
    # Load from YAML file
    config_path = settings.config_path
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}
    else:
        config_data = {}
    
    # Create config from YAML
    config = Config(**config_data)
    
    # Override with environment variables
    if settings.database_url:
        config.database.url = settings.database_url
    
    if settings.log_level:
        config.logging.level = settings.log_level
    
    return config


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance (singleton pattern).
    
    Returns:
        Config: Configuration instance
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config
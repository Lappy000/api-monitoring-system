"""Configuration management with Pydantic settings."""

import os
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
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
    
    @field_validator('interval')
    @classmethod
    def interval_must_be_positive(cls, v):
        if v < 10:
            raise ValueError('interval must be at least 10 seconds')
        return v
    
    @field_validator('timeout')
    @classmethod
    def timeout_must_be_positive(cls, v):
        if v < 1:
            raise ValueError('timeout must be at least 1 second')
        return v
    
    @field_validator('expected_status')
    @classmethod
    def status_code_must_be_valid(cls, v):
        if not (100 <= v <= 599):
            raise ValueError('status code must be between 100 and 599')
        return v


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
    
    @field_validator('smtp_port')
    @classmethod
    def smtp_port_must_be_valid(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('SMTP port must be between 1 and 65535')
        return v
    
    @field_validator('smtp_user', 'smtp_password', 'from_addr')
    @classmethod
    def required_if_enabled(cls, v, info):
        if info.data.get('enabled') and not v:
            field_name = info.field_name
            raise ValueError(f'{field_name} must be set when email notifications are enabled')
        return v


class WebhookConfig(BaseModel):
    """Webhook notification configuration."""
    enabled: bool = False
    url: str = ""
    method: str = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    retry_count: int = 3
    retry_delay: int = 5
    timeout: int = 10
    payload_template: str = '{"text": "🚨 API Monitor Alert: {endpoint_name} is DOWN"}'
    
    @field_validator('retry_count')
    @classmethod
    def retry_count_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('retry_count must be non-negative')
        return v
    
    @field_validator('url')
    @classmethod
    def url_must_be_set_if_enabled(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('url must be set when webhook notifications are enabled')
        return v


class TelegramConfig(BaseModel):
    """Telegram notification configuration."""
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    message_template: str = "🚨 *{endpoint_name}* is DOWN\\nError: {error}"
    parse_mode: str = "Markdown"
    
    @field_validator('bot_token', 'chat_id')
    @classmethod
    def required_if_enabled(cls, v, info):
        if info.data.get('enabled') and not v:
            field_name = info.field_name
            raise ValueError(f'{field_name} must be set when Telegram notifications are enabled')
        return v


class NotificationsConfig(BaseModel):
    """Notifications configuration."""
    enabled: bool = True
    cooldown_seconds: int = 300
    send_recovery: bool = True
    email: EmailConfig = Field(default_factory=EmailConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    
    @field_validator('cooldown_seconds')
    @classmethod
    def cooldown_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('cooldown_seconds must be non-negative')
        return v


class DatabaseConfig(BaseModel):
    """Database configuration."""
    type: str = "sqlite"
    url: str = "sqlite+aiosqlite:///./data/api_monitor.db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_pre_ping: bool = True
    echo: bool = False
    
    @field_validator('type')
    @classmethod
    def database_type_must_be_supported(cls, v):
        supported = ['sqlite', 'postgresql', 'mysql']
        if v not in supported:
            raise ValueError(f'database type must be one of {supported}')
        return v


class MonitoringConfig(BaseModel):
    """Monitoring settings."""
    check_history_days: int = 90
    cleanup_interval: int = 86400
    max_concurrent_checks: int = 20
    
    @field_validator('max_concurrent_checks')
    @classmethod
    def max_concurrent_must_be_positive(cls, v):
        if v < 1:
            raise ValueError('max_concurrent_checks must be at least 1')
        return v


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
    
    @field_validator('level')
    @classmethod
    def log_level_must_be_valid(cls, v):
        if isinstance(v, str):
            v = v.upper()
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v not in valid_levels:
            raise ValueError(f'log level must be one of {valid_levels}')
        return v


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
    secret_key: str = ""  # For JWT token signing
    algorithm: str = "HS256"  # JWT algorithm
    access_token_expire_minutes: int = 30  # Token expiration
    
    @field_validator('api_key')
    @classmethod
    def api_key_must_be_set_if_enabled(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('API key must be set when authentication is enabled')
        return v


class APIConfig(BaseModel):
    """API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    cors: CORSConfig = Field(default_factory=CORSConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    
    @field_validator('port')
    @classmethod
    def port_must_be_valid(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('port must be between 1 and 65535')
        return v


class RedisConfig(BaseModel):
    """Redis configuration."""
    enabled: bool = False
    url: str = "redis://localhost:6379/0"
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


class Config(BaseModel):
    """Main configuration class."""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    endpoints: List[EndpointConfig] = Field(default_factory=list)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    
    @field_validator('api')
    @classmethod
    def validate_api_config(cls, v):
        if v.auth.enabled and not v.auth.api_key:
            raise ValueError('API key must be set when authentication is enabled')
        return v


def load_config() -> Config:
    """
    Load configuration from YAML file and environment variables.
    
    Returns:
        Config: Loaded configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
        ValidationError: If configuration is invalid
    """
    # Load .env file manually if it exists
    # This avoids Pydantic validation issues with extra fields
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
        except Exception as e:
            print(f"Warning: Could not load .env file: {e}")
    
    # Get configuration loading parameters from environment
    app_env = os.getenv("APP_ENV", "development")
    config_path = os.getenv("CONFIG_PATH", "config/config.yaml")
    database_url = os.getenv("DATABASE_URL")
    log_level = os.getenv("LOG_LEVEL")
    
    # Load from YAML file
    config_data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {config_path}: {e}")
    else:
        # For development, allow missing config file
        if app_env != "development":
            raise FileNotFoundError(f"Config file not found: {config_path}")
    
    # Create config from YAML and validate
    try:
        config = Config(**config_data)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")
    
    # Override with environment variables
    if database_url:
        config.database.url = database_url
    
    if log_level:
        config.logging.level = log_level
    
    # Manually read Redis settings from environment for better control
    redis_enabled = os.getenv("REDIS_ENABLED")
    if redis_enabled is not None:
        # Convert string to boolean
        config.redis.enabled = redis_enabled.lower() in ("true", "1", "yes", "on")
    
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        config.redis.url = redis_url
    
    # Manually read API auth settings from environment
    api_auth_enabled = os.getenv("API_AUTH_ENABLED")
    if api_auth_enabled is not None:
        config.api.auth.enabled = api_auth_enabled.lower() in ("true", "1", "yes", "on")
    
    api_auth_api_key = os.getenv("API_AUTH_API_KEY")
    if api_auth_api_key:
        config.api.auth.api_key = api_auth_api_key
    
    # Read JWT settings from environment
    api_auth_secret_key = os.getenv("API_AUTH_SECRET_KEY")
    if api_auth_secret_key:
        config.api.auth.secret_key = api_auth_secret_key
    
    api_auth_algorithm = os.getenv("API_AUTH_ALGORITHM")
    if api_auth_algorithm:
        config.api.auth.algorithm = api_auth_algorithm
    
    # Final validation
    if config.api.auth.enabled and not config.api.auth.api_key:
        raise ValueError("API authentication is enabled but no API key is set")
    
    if config.notifications.email.enabled and not config.notifications.email.smtp_password:
        raise ValueError("Email notifications are enabled but SMTP password is not set")
    
    if config.redis.enabled and not config.redis.url:
        raise ValueError("Redis is enabled but URL is not set")
    
    return config


# Remove singleton pattern - config should be loaded once and passed around
# Global config instance is an anti-pattern that causes race conditions
# Instead, load config in main.py and pass it to components that need it
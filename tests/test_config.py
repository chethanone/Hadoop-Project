"""
Unit tests for application configuration.
"""
from src.app.config import Config, DevelopmentConfig, TestingConfig, config_by_name


def test_base_config_defaults():
    config = Config()
    assert config.WSL_DISTRO == "Ubuntu"
    assert config.HDFS_URI == "hdfs://localhost:9000"
    assert config.NAMENODE_HTTP_URL == "http://localhost:9870"
    assert config.YARN_RM_HTTP_URL == "http://localhost:8088"
    assert "astro.localdomain" in config.ALLOWED_REDIRECT_HOSTS
    assert config.REDIRECT_REWRITE_MAP.get("astro.localdomain") == "127.0.0.1"
    assert config.SUBPROCESS_TIMEOUT_SECONDS > 0
    assert config.HTTP_TIMEOUT_SECONDS > 0


def test_config_environments():
    assert config_by_name["development"] == DevelopmentConfig
    assert config_by_name["testing"] == TestingConfig
    test_conf = TestingConfig()
    assert test_conf.TESTING is True

"""
Configuration module for Hadoop Management & MapReduce Visualization System.
Provides strongly-typed, environment-aware configuration with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key-hadoop-visualizer-2026")

    # Windows & WSL Environment Settings
    WSL_DISTRO = os.getenv("WSL_DISTRO", "Ubuntu")
    WIN_WORKSPACE = os.getenv("WIN_WORKSPACE", str(BASE_DIR))
    WSL_WORKSPACE = os.getenv("WSL_WORKSPACE", "/mnt/c/hadoop_proj")

    # Hadoop WSL Paths
    HADOOP_HOME_WSL = os.getenv("HADOOP_HOME_WSL", "/home/chethan/hadoop-3.5.0")
    HADOOP_BIN_WSL = f"{HADOOP_HOME_WSL}/bin/hadoop"
    HDFS_BIN_WSL = f"{HADOOP_HOME_WSL}/bin/hdfs"
    JAVA_HOME_WSL = os.getenv("JAVA_HOME_WSL", "/usr/lib/jvm/java-17-openjdk-amd64")

    # Hadoop Cluster Endpoints
    HDFS_URI = os.getenv("HDFS_URI", "hdfs://localhost:9000")
    NAMENODE_HTTP_URL = os.getenv("NAMENODE_HTTP_URL", "http://localhost:9870")
    NAMENODE_JMX_URL = f"{NAMENODE_HTTP_URL}/jmx"
    DATANODE_HTTP_URL = os.getenv("DATANODE_HTTP_URL", "http://localhost:9864")

    # YARN Cluster Endpoints
    YARN_RM_HTTP_URL = os.getenv("YARN_RM_HTTP_URL", "http://localhost:8088")
    YARN_CLUSTER_INFO_URL = f"{YARN_RM_HTTP_URL}/ws/v1/cluster/info"
    YARN_CLUSTER_APPS_URL = f"{YARN_RM_HTTP_URL}/ws/v1/cluster/apps"
    YARN_CLUSTER_METRICS_URL = f"{YARN_RM_HTTP_URL}/ws/v1/cluster/metrics"

    # WebHDFS Redirect Host Normalization
    # Only normalize specifically verified hostnames to prevent SSRF
    ALLOWED_REDIRECT_HOSTS = ("astro.localdomain", "localhost", "127.0.0.1")
    REDIRECT_REWRITE_MAP = {
        "astro.localdomain": "127.0.0.1"
    }

    # Bounded Timeouts
    SUBPROCESS_TIMEOUT_SECONDS = int(os.getenv("SUBPROCESS_TIMEOUT_SECONDS", "20"))
    HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "5"))

    # Application Settings
    DEFAULT_HDFS_USER_DIR = "/user/chethan"
    MAX_PREVIEW_BYTES = 1024 * 1024  # 1 MB preview ceiling
    MAX_PREVIEW_LINES = 500

    TESTING = False
    DEBUG = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SUBPROCESS_TIMEOUT_SECONDS = 5
    HTTP_TIMEOUT_SECONDS = 2


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": Config,
    "default": DevelopmentConfig,
}

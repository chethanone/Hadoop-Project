"""
Routes package initialization.
"""
from .diagnostics import diagnostics_bp
from .file_manager import file_manager_bp
from .mapreduce import mapreduce_bp
from .dashboard import dashboard_bp

__all__ = ["diagnostics_bp", "file_manager_bp", "mapreduce_bp", "dashboard_bp"]

import importlib
import os
from pathlib import Path
from typing import List
from loguru import logger

from src.plugins.base import BasePlugin

class PluginManager:
    _instance = None
    _plugins: List[BasePlugin] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PluginManager, cls).__new__(cls)
        return cls._instance

    def load_plugins(self):
        """
        Scans src/plugins/ directory for subfolders containing plugin implementations
        and loads them.
        """
        self._plugins = []
        plugins_dir = Path(__file__).resolve().parent
        
        for item in plugins_dir.iterdir():
            if item.is_dir() and not item.name.startswith("__"):
                try:
                    # Dynamically import plugin module
                    module_name = f"src.plugins.{item.name}.main"
                    module = importlib.import_module(module_name)
                    
                    # Find class inheriting from BasePlugin
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                            plugin_instance = attr()
                            self._plugins.append(plugin_instance)
                            logger.info(f"Loaded plugin: {plugin_instance.name} - {plugin_instance.description}")
                except Exception as e:
                    logger.error(f"Failed to load plugin {item.name}: {e}")

    def dispatch_attendance(self, student_id: int, status: str, check_in_time):
        for plugin in self._plugins:
            try:
                plugin.on_attendance_marked(student_id, status, check_in_time)
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed on_attendance_marked: {e}")

    def dispatch_leave(self, leave_id: int, applicant_type: str, start_date: str):
        for plugin in self._plugins:
            try:
                plugin.on_leave_submitted(leave_id, applicant_type, start_date)
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed on_leave_submitted: {e}")

    def dispatch_holiday(self, holiday_id: int, holiday_name: str, date_str: str):
        for plugin in self._plugins:
            try:
                plugin.on_holiday_created(holiday_id, holiday_name, date_str)
            except Exception as e:
                logger.error(f"Plugin {plugin.name} failed on_holiday_created: {e}")

plugin_manager = PluginManager()

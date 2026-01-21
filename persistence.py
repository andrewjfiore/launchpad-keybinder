#!/usr/bin/env python3
"""
Persistence layer for Launchpad Mapper.
Handles saving/loading profiles and configuration to disk.
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from launchpad_mapper import Profile

# Default persistence directory
def get_persistence_dir() -> Path:
    """Get the persistence directory, creating it if necessary."""
    # Use platform-appropriate config directory
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', Path.home()))
    else:  # Linux/macOS
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))

    persist_dir = base / 'launchpad-mapper'
    persist_dir.mkdir(parents=True, exist_ok=True)
    return persist_dir


# File paths
PROFILES_FILE = 'profiles.json'
CONFIG_FILE = 'config.json'


class PersistenceManager:
    """Manages persistence of profiles and configuration."""

    def __init__(self, persistence_dir: Optional[Path] = None):
        self.persistence_dir = persistence_dir or get_persistence_dir()
        self.profiles_path = self.persistence_dir / PROFILES_FILE
        self.config_path = self.persistence_dir / CONFIG_FILE

        # Thread safety
        self._lock = threading.RLock()

        # Auto-save debouncing
        self._save_timer: Optional[threading.Timer] = None
        self._save_delay = 1.0  # Debounce saves by 1 second
        self._pending_save = False

        # Callbacks for persistence events
        self._on_load_callbacks: List[Callable] = []
        self._on_save_callbacks: List[Callable] = []

    def add_load_callback(self, callback: Callable):
        """Register a callback for when data is loaded."""
        self._on_load_callbacks.append(callback)

    def add_save_callback(self, callback: Callable):
        """Register a callback for when data is saved."""
        self._on_save_callbacks.append(callback)

    def _notify_load(self, data_type: str):
        """Notify callbacks that data was loaded."""
        for cb in self._on_load_callbacks:
            try:
                cb(data_type)
            except Exception as e:
                print(f"Error in load callback: {e}")

    def _notify_save(self, data_type: str):
        """Notify callbacks that data was saved."""
        for cb in self._on_save_callbacks:
            try:
                cb(data_type)
            except Exception as e:
                print(f"Error in save callback: {e}")

    # =========================================================================
    # PROFILES PERSISTENCE
    # =========================================================================

    def save_profiles(self, profiles: Dict[str, Any], active_profile: str) -> bool:
        """
        Save all profiles to disk.

        Args:
            profiles: Dictionary of profile name -> Profile object or dict
            active_profile: Name of the currently active profile

        Returns:
            True if save succeeded, False otherwise
        """
        with self._lock:
            try:
                # Convert profiles to serializable format
                profiles_data = {}
                for name, profile in profiles.items():
                    if hasattr(profile, 'to_dict'):
                        profiles_data[name] = profile.to_dict()
                    else:
                        profiles_data[name] = profile

                data = {
                    'version': 1,
                    'active_profile': active_profile,
                    'profiles': profiles_data,
                    'saved_at': time.time()
                }

                # Write atomically using temp file
                temp_path = self.profiles_path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                temp_path.replace(self.profiles_path)

                self._notify_save('profiles')
                print(f"Profiles saved to {self.profiles_path}")
                return True

            except Exception as e:
                print(f"Error saving profiles: {e}")
                return False

    def load_profiles(self) -> Optional[Dict[str, Any]]:
        """
        Load all profiles from disk.

        Returns:
            Dictionary with 'profiles' and 'active_profile' keys, or None if not found
        """
        with self._lock:
            if not self.profiles_path.exists():
                return None

            try:
                with open(self.profiles_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self._notify_load('profiles')
                print(f"Profiles loaded from {self.profiles_path}")
                return data

            except Exception as e:
                print(f"Error loading profiles: {e}")
                return None

    def schedule_save_profiles(self, profiles: Dict[str, Any], active_profile: str):
        """
        Schedule a debounced save of profiles.
        Multiple rapid changes will be batched into a single save.
        """
        with self._lock:
            # Cancel any pending save
            if self._save_timer:
                self._save_timer.cancel()

            # Schedule new save
            self._save_timer = threading.Timer(
                self._save_delay,
                self._do_scheduled_save,
                args=(profiles, active_profile)
            )
            self._save_timer.daemon = True
            self._save_timer.start()
            self._pending_save = True

    def _do_scheduled_save(self, profiles: Dict[str, Any], active_profile: str):
        """Execute the scheduled save."""
        with self._lock:
            self._pending_save = False
            self._save_timer = None
        self.save_profiles(profiles, active_profile)

    def flush_pending_saves(self):
        """Force any pending saves to complete immediately."""
        with self._lock:
            if self._save_timer:
                self._save_timer.cancel()
                self._save_timer = None
            # The actual save was already scheduled with specific data,
            # so we just need to wait for any in-progress saves

    # =========================================================================
    # CONFIG PERSISTENCE
    # =========================================================================

    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration to disk.

        Config includes:
        - Last used MIDI ports
        - MIDI backend preference
        - Auto-reconnect settings
        - Auto-switch rules
        - UI preferences
        """
        with self._lock:
            try:
                data = {
                    'version': 1,
                    'saved_at': time.time(),
                    **config
                }

                temp_path = self.config_path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                temp_path.replace(self.config_path)

                self._notify_save('config')
                print(f"Config saved to {self.config_path}")
                return True

            except Exception as e:
                print(f"Error saving config: {e}")
                return False

    def load_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from disk."""
        with self._lock:
            if not self.config_path.exists():
                return None

            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self._notify_load('config')
                print(f"Config loaded from {self.config_path}")
                return data

            except Exception as e:
                print(f"Error loading config: {e}")
                return None

    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update specific config values, preserving others."""
        with self._lock:
            config = self.load_config() or {}
            config.update(updates)
            return self.save_config(config)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_last_midi_ports(self) -> Optional[Dict[str, str]]:
        """Get the last used MIDI port names."""
        config = self.load_config()
        if not config:
            return None
        return {
            'input_port': config.get('last_input_port'),
            'output_port': config.get('last_output_port')
        }

    def save_last_midi_ports(self, input_port: Optional[str], output_port: Optional[str]):
        """Save the last used MIDI port names."""
        self.update_config({
            'last_input_port': input_port,
            'last_output_port': output_port
        })

    def get_auto_switch_rules(self) -> Optional[List[Dict[str, str]]]:
        """Get saved auto-switch rules."""
        config = self.load_config()
        if not config:
            return None
        return config.get('auto_switch_rules')

    def save_auto_switch_rules(self, rules: List[Dict[str, str]], enabled: bool):
        """Save auto-switch rules."""
        self.update_config({
            'auto_switch_rules': rules,
            'auto_switch_enabled': enabled
        })

    def export_backup(self, backup_path: Path) -> bool:
        """Export all data to a backup file."""
        with self._lock:
            try:
                profiles_data = self.load_profiles()
                config_data = self.load_config()

                backup = {
                    'version': 1,
                    'exported_at': time.time(),
                    'profiles': profiles_data,
                    'config': config_data
                }

                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(backup, f, indent=2)

                print(f"Backup exported to {backup_path}")
                return True

            except Exception as e:
                print(f"Error exporting backup: {e}")
                return False

    def import_backup(self, backup_path: Path) -> bool:
        """Import data from a backup file."""
        with self._lock:
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup = json.load(f)

                # Restore profiles if present
                if backup.get('profiles'):
                    profiles_data = backup['profiles']
                    if isinstance(profiles_data, dict) and 'profiles' in profiles_data:
                        with open(self.profiles_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, indent=2)

                # Restore config if present
                if backup.get('config'):
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(backup['config'], f, indent=2)

                print(f"Backup imported from {backup_path}")
                return True

            except Exception as e:
                print(f"Error importing backup: {e}")
                return False

    def clear_all(self):
        """Clear all persisted data (for testing)."""
        with self._lock:
            if self.profiles_path.exists():
                self.profiles_path.unlink()
            if self.config_path.exists():
                self.config_path.unlink()


# Global persistence manager instance
_persistence_manager: Optional[PersistenceManager] = None


def get_persistence_manager() -> PersistenceManager:
    """Get the global persistence manager instance."""
    global _persistence_manager
    if _persistence_manager is None:
        _persistence_manager = PersistenceManager()
    return _persistence_manager

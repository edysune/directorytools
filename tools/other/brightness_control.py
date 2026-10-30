#!/usr/bin/env python3
"""
Screen Brightness Controller

This script allows you to adjust screen brightness across different platforms.
Supports Linux (xrandr, sysfs), Windows (WMI), and macOS (brightness).

Usage:
    python brightness_control.py set 50          # Set brightness to 50%
    python brightness_control.py get             # Get current brightness
    python brightness_control.py inc 10           # Increase by 10%
    python brightness_control.py dec 10           # Decrease by 10%
    python brightness_control.py list            # List available displays
"""

import argparse
import os
import subprocess
import sys
import platform
from typing import List, Optional, Tuple


class BrightnessController:
    def __init__(self):
        self.system = platform.system().lower()
        self.controller = self._get_controller()
    
    def _get_controller(self):
        """Get the appropriate controller for the current system."""
        if self.system == "linux":
            return LinuxBrightnessController()
        elif self.system == "windows":
            return WindowsBrightnessController()
        elif self.system == "darwin":
            return MacOSBrightnessController()
        else:
            raise RuntimeError(f"Unsupported system: {self.system}")
    
    def set_brightness(self, value: int, display: Optional[str] = None) -> bool:
        """Set brightness to a specific value (0-100)."""
        if not 0 <= value <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        return self.controller.set_brightness(value, display)
    
    def get_brightness(self, display: Optional[str] = None) -> Optional[int]:
        """Get current brightness value."""
        return self.controller.get_brightness(display)
    
    def adjust_brightness(self, delta: int, display: Optional[str] = None) -> bool:
        """Adjust brightness by delta value."""
        current = self.get_brightness(display)
        if current is None:
            return False
        new_value = max(0, min(100, current + delta))
        return self.set_brightness(new_value, display)
    
    def list_displays(self) -> List[str]:
        """List available displays."""
        return self.controller.list_displays()


class LinuxBrightnessController:
    def __init__(self):
        self.method = self._detect_method()
    
    def _detect_method(self) -> str:
        """Detect the best method for Linux brightness control."""
        # Try xrandr first (for X11)
        try:
            subprocess.run(['xrandr', '--version'], capture_output=True, check=True)
            return 'xrandr'
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Try sysfs backlight (for laptops)
        backlight_dirs = [
            '/sys/class/backlight/intel_backlight',
            '/sys/class/backlight/acpi_video0',
            '/sys/class/backlight/radeon_bl0',
            '/sys/class/backlight/amdgpu_bl0'
        ]
        
        for backlight_dir in backlight_dirs:
            if os.path.exists(backlight_dir):
                if os.path.exists(f"{backlight_dir}/brightness") and \
                   os.path.exists(f"{backlight_dir}/max_brightness"):
                    return 'sysfs'
        
        return 'none'
    
    def set_brightness(self, value: int, display: Optional[str] = None) -> bool:
        """Set brightness using the detected method."""
        if self.method == 'xrandr':
            return self._set_brightness_xrandr(value, display)
        elif self.method == 'sysfs':
            return self._set_brightness_sysfs(value)
        else:
            print("No suitable brightness control method found")
            return False
    
    def get_brightness(self, display: Optional[str] = None) -> Optional[int]:
        """Get current brightness."""
        if self.method == 'xrandr':
            return self._get_brightness_xrandr(display)
        elif self.method == 'sysfs':
            return self._get_brightness_sysfs()
        else:
            return None
    
    def list_displays(self) -> List[str]:
        """List available displays."""
        if self.method == 'xrandr':
            return self._list_xrandr_displays()
        elif self.method == 'sysfs':
            return ['system']  # sysfs controls system backlight
        else:
            return []
    
    def _set_brightness_xrandr(self, value: int, display: Optional[str] = None) -> bool:
        """Set brightness using xrandr."""
        try:
            if display:
                cmd = ['xrandr', '--output', display, '--brightness', str(value / 100.0)]
            else:
                # Get the first connected display
                displays = self._list_xrandr_displays()
                if not displays:
                    print("No connected displays found")
                    return False
                cmd = ['xrandr', '--output', displays[0], '--brightness', str(value / 100.0)]
            
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"xrandr failed: {e}")
            return False
    
    def _get_brightness_xrandr(self, display: Optional[str] = None) -> Optional[int]:
        """Get brightness using xrandr."""
        try:
            cmd = ['xrandr', '--verbose']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse xrandr output for brightness
            lines = result.stdout.split('\n')
            current_display = None
            
            for line in lines:
                if ' connected' in line:
                    current_display = line.split()[0]
                    continue
                
                if current_display and 'Brightness:' in line:
                    if display is None or current_display == display:
                        brightness_str = line.split('Brightness:')[1].strip()
                        brightness = float(brightness_str)
                        return int(brightness * 100)
            
            return None
        except (subprocess.CalledProcessError, ValueError) as e:
            print(f"Debug: Error parsing xrandr output: {e}")
            return None
    
    def _list_xrandr_displays(self) -> List[str]:
        """List connected displays using xrandr."""
        try:
            cmd = ['xrandr']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            displays = []
            for line in result.stdout.split('\n'):
                if ' connected' in line:
                    display_name = line.split()[0]
                    displays.append(display_name)
            
            return displays
        except subprocess.CalledProcessError:
            return []
    
    def _set_brightness_sysfs(self, value: int) -> bool:
        """Set brightness using sysfs."""
        backlight_dirs = [
            '/sys/class/backlight/intel_backlight',
            '/sys/class/backlight/acpi_video0',
            '/sys/class/backlight/radeon_bl0',
            '/sys/class/backlight/amdgpu_bl0'
        ]
        
        for backlight_dir in backlight_dirs:
            if os.path.exists(backlight_dir):
                try:
                    max_brightness_file = f"{backlight_dir}/max_brightness"
                    brightness_file = f"{backlight_dir}/brightness"
                    
                    with open(max_brightness_file, 'r') as f:
                        max_brightness = int(f.read().strip())
                    
                    new_brightness = int(max_brightness * value / 100)
                    
                    # Need sudo to write to sysfs
                    cmd = ['sudo', 'tee', brightness_file]
                    subprocess.run(cmd, input=str(new_brightness).encode(), check=True)
                    
                    return True
                except (OSError, subprocess.CalledProcessError) as e:
                    print(f"Failed to set brightness via sysfs: {e}")
                    continue
        
        return False
    
    def _get_brightness_sysfs(self) -> Optional[int]:
        """Get brightness using sysfs."""
        backlight_dirs = [
            '/sys/class/backlight/intel_backlight',
            '/sys/class/backlight/acpi_video0',
            '/sys/class/backlight/radeon_bl0',
            '/sys/class/backlight/amdgpu_bl0'
        ]
        
        for backlight_dir in backlight_dirs:
            if os.path.exists(backlight_dir):
                try:
                    max_brightness_file = f"{backlight_dir}/max_brightness"
                    brightness_file = f"{backlight_dir}/brightness"
                    
                    with open(max_brightness_file, 'r') as f:
                        max_brightness = int(f.read().strip())
                    
                    with open(brightness_file, 'r') as f:
                        current_brightness = int(f.read().strip())
                    
                    return int(current_brightness * 100 / max_brightness)
                except (OSError, ValueError):
                    continue
        
        return None


class WindowsBrightnessController:
    def set_brightness(self, value: int, display: Optional[str] = None) -> bool:
        """Set brightness using Windows WMI."""
        try:
            import wmi
            c = wmi.WMI()
            
            # Get all monitors
            monitors = c.WmiMonitorBrightnessMethods()
            
            if not monitors:
                print("No WMI-compatible monitors found")
                return False
            
            # Set brightness on first monitor
            monitors[0].WmiSetBrightness(value, 0)
            return True
        except ImportError:
            print("WMI module not available. Install with: pip install wmi")
            return False
        except Exception as e:
            print(f"Failed to set brightness: {e}")
            return False
    
    def get_brightness(self, display: Optional[str] = None) -> Optional[int]:
        """Get current brightness using Windows WMI."""
        try:
            import wmi
            c = wmi.WMI()
            
            # Get current brightness
            brightness = c.WmiMonitorBrightness()[0].CurrentBrightness
            return brightness
        except (ImportError, Exception):
            return None
    
    def list_displays(self) -> List[str]:
        """List available displays."""
        try:
            import wmi
            c = wmi.WMI()
            monitors = c.Win32_DesktopMonitor()
            return [f"Monitor_{i}" for i in range(len(monitors))]
        except ImportError:
            return []


class MacOSBrightnessController:
    def set_brightness(self, value: int, display: Optional[str] = None) -> bool:
        """Set brightness using macOS brightness command."""
        try:
            # Try using brightness command (requires installation)
            cmd = ['brightness', str(value)]
            subprocess.run(cmd, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to osascript
            try:
                brightness = value / 100.0
                script = f'tell application "System Events" to set brightness to {brightness}'
                subprocess.run(['osascript', '-e', script], check=True)
                return True
            except subprocess.CalledProcessError:
                print("No suitable brightness control method found")
                return False
    
    def get_brightness(self, display: Optional[str] = None) -> Optional[int]:
        """Get current brightness on macOS."""
        try:
            script = 'tell application "System Events" to get brightness'
            result = subprocess.run(['osascript', '-e', script], 
                                  capture_output=True, text=True, check=True)
            brightness = float(result.stdout.strip())
            return int(brightness * 100)
        except (subprocess.CalledProcessError, ValueError):
            return None
    
    def list_displays(self) -> List[str]:
        """List available displays on macOS."""
        try:
            script = 'tell application "System Events" to get name of displays'
            result = subprocess.run(['osascript', '-e', script], 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip().split(', ')
        except subprocess.CalledProcessError:
            return ['main']


def main():
    parser = argparse.ArgumentParser(
        description="Control screen brightness across platforms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python brightness_control.py set 50          # Set brightness to 50%
    python brightness_control.py get             # Get current brightness
    python brightness_control.py inc 10           # Increase by 10%
    python brightness_control.py dec 10           # Decrease by 10%
    python brightness_control.py list            # List available displays
        """
    )
    
    parser.add_argument('action', choices=['set', 'get', 'inc', 'dec', 'list'],
                       help='Action to perform')
    parser.add_argument('value', nargs='?', type=int,
                       help='Brightness value (0-100) or adjustment amount')
    parser.add_argument('-d', '--display', help='Display name (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    try:
        controller = BrightnessController()
        
        if args.action == 'set':
            if args.value is None:
                print("Error: set command requires a brightness value")
                sys.exit(1)
            
            success = controller.set_brightness(args.value, args.display)
            if success:
                print(f"Brightness set to {args.value}%")
            else:
                print("Failed to set brightness")
                sys.exit(1)
        
        elif args.action == 'get':
            brightness = controller.get_brightness(args.display)
            if brightness is not None:
                print(f"Current brightness: {brightness}%")
            else:
                print("Could not get brightness")
                sys.exit(1)
        
        elif args.action == 'inc':
            if args.value is None:
                print("Error: inc command requires an adjustment value")
                sys.exit(1)
            
            success = controller.adjust_brightness(args.value, args.display)
            if success:
                current = controller.get_brightness(args.display)
                print(f"Brightness increased by {args.value}% to {current}%")
            else:
                print("Failed to adjust brightness")
                sys.exit(1)
        
        elif args.action == 'dec':
            if args.value is None:
                print("Error: dec command requires an adjustment value")
                sys.exit(1)
            
            success = controller.adjust_brightness(-args.value, args.display)
            if success:
                current = controller.get_brightness(args.display)
                print(f"Brightness decreased by {args.value}% to {current}%")
            else:
                print("Failed to adjust brightness")
                sys.exit(1)
        
        elif args.action == 'list':
            displays = controller.list_displays()
            if displays:
                print("Available displays:")
                for display in displays:
                    print(f"  - {display}")
            else:
                print("No displays found")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

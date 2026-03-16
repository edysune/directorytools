#!/usr/bin/env python3
"""
Brightness Control GUI

A tkinter GUI application for controlling screen brightness across multiple displays.
Features real-time brightness adjustment with sliders and text input fallbacks.

Usage:
    python brightness_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import Dict, List, Optional
import sys
import os

# Import the brightness controller from our existing script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from brightness_control import BrightnessController


class BrightnessGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Brightness Control")
        self.root.geometry("600x400")
        self.root.resizable(True, True)
        
        # Initialize brightness controller
        try:
            self.controller = BrightnessController()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize brightness controller: {e}")
            self.root.destroy()
            return
        
        # Store display widgets and current values
        self.display_widgets = {}
        self.current_brightness = {}
        self.updating = False
        
        # Create GUI
        self.create_widgets()
        
        # Start display detection
        self.detect_displays()
        
        # Start auto-update thread
        self.start_auto_update()
    
    def create_widgets(self):
        """Create the main GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Display Brightness Control", 
                               font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Refresh button
        refresh_btn = ttk.Button(main_frame, text="Refresh Displays", 
                               command=self.detect_displays)
        refresh_btn.grid(row=0, column=2, pady=(0, 20), sticky=tk.E)
        
        # Scrollable frame for displays
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.displays_frame = ttk.Frame(canvas)
        
        self.displays_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.displays_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=3, sticky=(tk.N, tk.S))
        
        main_frame.rowconfigure(1, weight=1)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def detect_displays(self):
        """Detect available displays and create controls for them."""
        self.status_var.set("Detecting displays...")
        self.root.update()
        
        # Clear existing display widgets
        for widget in self.displays_frame.winfo_children():
            widget.destroy()
        self.display_widgets.clear()
        self.current_brightness.clear()
        
        # Get displays
        try:
            displays = self.controller.list_displays()
            
            if not displays:
                self.show_no_displays()
                return
            
            # Create controls for each display
            for i, display in enumerate(displays):
                self.create_display_control(display, i)
            
            self.status_var.set(f"Found {len(displays)} display(s)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to detect displays: {e}")
            self.status_var.set("Error detecting displays")
    
    def show_no_displays(self):
        """Show message when no displays are found."""
        no_displays_label = ttk.Label(self.displays_frame, 
                                     text="No displays found. Make sure brightness control is available.",
                                     foreground="red")
        no_displays_label.grid(row=0, column=0, pady=50)
        self.status_var.set("No displays found")
    
    def create_display_control(self, display_name: str, row: int):
        """Create control widgets for a single display."""
        # Display frame
        display_frame = ttk.LabelFrame(self.displays_frame, text=display_name, padding="10")
        display_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)
        self.displays_frame.columnconfigure(0, weight=1)
        
        # Get current brightness
        current_brightness = self.get_display_brightness(display_name)
        self.current_brightness[display_name] = current_brightness or 0
        
        # Display info
        info_frame = ttk.Frame(display_frame)
        info_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        current_label = ttk.Label(info_frame, text=f"Current: {self.current_brightness[display_name]}%")
        current_label.grid(row=0, column=0, sticky=tk.W)
        
        # Create slider
        slider_frame = ttk.Frame(display_frame)
        slider_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        slider_frame.columnconfigure(0, weight=1)
        
        brightness_var = tk.IntVar(value=self.current_brightness[display_name])
        
        slider = ttk.Scale(slider_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                          variable=brightness_var, command=lambda v, d=display_name: self.on_slider_change(d, v))
        slider.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Percentage label
        percent_label = ttk.Label(slider_frame, text=f"{self.current_brightness[display_name]}%")
        percent_label.grid(row=0, column=1, padx=(10, 0))
        
        # Text input fallback
        text_frame = ttk.Frame(display_frame)
        text_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        ttk.Label(text_frame, text="Or enter value (0-100):").grid(row=0, column=0, sticky=tk.W)
        
        text_var = tk.StringVar(value=str(self.current_brightness[display_name]))
        text_entry = ttk.Entry(text_frame, textvariable=text_var, width=10)
        text_entry.grid(row=0, column=1, padx=(10, 0))
        
        set_btn = ttk.Button(text_frame, text="Set", 
                           command=lambda d=display_name, v=text_var: self.set_brightness_text(d, v))
        set_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Store widgets
        self.display_widgets[display_name] = {
            'frame': display_frame,
            'slider': slider,
            'brightness_var': brightness_var,
            'text_var': text_var,
            'current_label': current_label,
            'percent_label': percent_label
        }
    
    def get_display_brightness(self, display_name: str) -> Optional[int]:
        """Get current brightness for a display."""
        try:
            return self.controller.get_brightness(display_name)
        except Exception:
            return None
    
    def on_slider_change(self, display_name: str, value: str):
        """Handle slider value change."""
        if self.updating:
            return
        
        try:
            brightness = int(float(value))
            self.set_brightness(display_name, brightness)
        except (ValueError, TypeError):
            pass
    
    def set_brightness_text(self, display_name: str, text_var):
        """Set brightness from text input."""
        try:
            brightness = int(text_var.get())
            if 0 <= brightness <= 100:
                self.set_brightness(display_name, brightness)
                # Update slider
                if display_name in self.display_widgets:
                    self.display_widgets[display_name]['brightness_var'].set(brightness)
            else:
                messagebox.showwarning("Invalid Value", "Brightness must be between 0 and 100")
        except ValueError:
            messagebox.showwarning("Invalid Value", "Please enter a valid number")
    
    def set_brightness(self, display_name: str, brightness: int):
        """Set brightness for a display."""
        try:
            success = self.controller.set_brightness(brightness, display_name)
            
            if success:
                self.current_brightness[display_name] = brightness
                self.update_display_info(display_name)
                self.status_var.set(f"Set {display_name} brightness to {brightness}%")
            else:
                self.status_var.set(f"Failed to set {display_name} brightness")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set brightness: {e}")
            self.status_var.set(f"Error setting {display_name} brightness")
    
    def update_display_info(self, display_name: str):
        """Update display information widgets."""
        if display_name not in self.display_widgets:
            return
        
        widgets = self.display_widgets[display_name]
        brightness = self.current_brightness[display_name]
        
        # Update labels
        widgets['current_label'].config(text=f"Current: {brightness}%")
        widgets['percent_label'].config(text=f"{brightness}%")
        widgets['text_var'].set(str(brightness))
    
    def start_auto_update(self):
        """Start background thread to auto-update brightness values."""
        def update_loop():
            while True:
                try:
                    if not self.updating:
                        self.root.after(0, self.update_all_displays)
                    time.sleep(2)  # Update every 2 seconds
                except Exception:
                    break
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
    
    def update_all_displays(self):
        """Update brightness values for all displays."""
        self.updating = True
        
        try:
            for display_name in self.current_brightness.keys():
                current = self.get_display_brightness(display_name)
                if current is not None and current != self.current_brightness.get(display_name):
                    self.current_brightness[display_name] = current
                    self.update_display_info(display_name)
                    
                    # Update slider without triggering callback
                    if display_name in self.display_widgets:
                        self.display_widgets[display_name]['brightness_var'].set(current)
        finally:
            self.updating = False


def main():
    root = tk.Tk()
    app = BrightnessGUI(root)
    
    # Handle window closing
    def on_closing():
        root.quit()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        on_closing()


if __name__ == "__main__":
    main()

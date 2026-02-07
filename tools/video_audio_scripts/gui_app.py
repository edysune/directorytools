#!/usr/bin/env python3
"""GUI Application for Video Audio Scripts.

Provides a graphical interface to scan, analyze, and fix video metadata.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Import scan and analyze functionality
from scanVideoMetadata import walk_and_scan, walk_and_scan_subtitles, is_video_file
from analyzeVideoMetadata import (
    analyze, find_latest_scan_file, load_scan, write_output,
    analyze_subtitle_whitelist, analyze_allowed_subtitle_types,
    analyze_default_audio, analyze_audio_whitelist, analyze_non_embedded_subtitles
)
from fixVideoMetadata import (
    load_json, attempt_set_default_audio, attempt_identify_unknown, backup_file_before_fix,
    attempt_remove_non_whitelisted_audio, attempt_remove_non_whitelisted_subs
)


def attempt_convert_subtitle_formats(item: dict, keep_backup=True):
    """Convert incompatible subtitle formats to SRT."""
    import subprocess
    import shutil
    import re
    import tempfile
    from pathlib import Path
    
    path = item.get("path")
    incompatible_subs = item.get("incompatible_subtitles") or []
    
    if not incompatible_subs:
        return False  # No changes needed
    
    # Check if any are text-based formats that can be converted
    text_based_codecs = ['ass', 'ssa']
    image_based_codecs = ['hdmv_pgs_subtitle', 'dvd_subtitle', 'dvdsub']
    
    # Separate text-based from image-based
    text_based_subs = [sub for sub in incompatible_subs if sub['codec'] in text_based_codecs]
    image_based_subs = [sub for sub in incompatible_subs if sub['codec'] in image_based_codecs]
    
    # If there are no text-based subtitles to convert, skip
    if not text_based_subs:
        if image_based_subs:
            print(f"SKIP: {path} only has image-based subtitles (PGS/DVD) that cannot be converted to text.")
        return False  # No convertible formats
    
    # Create backup BEFORE modifying if requested
    if keep_backup:
        backup_file_before_fix(path)

    # Convert text-based incompatible formats (ASS/SSA) to SRT with cleanup
    try:
        path_obj = Path(path)
        tmp = str(path_obj.parent / (path_obj.stem + ".tmp" + path_obj.suffix))
        
        # First, extract subtitles to temporary SRT files and clean them
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            cleaned_subs = []
            
            # Extract each text-based subtitle to SRT and clean it
            for idx, sub in enumerate(text_based_subs):
                sub_index = sub['index']
                temp_srt = tmpdir_path / f"sub_{idx}.srt"
                
                # Try to extract using absolute stream index first (0:3 means stream 3)
                # This is the correct approach for ffmpeg
                extract_cmd = [
                    "ffmpeg", "-y", "-i", path,
                    "-map", f"0:{sub_index}",
                    "-c:s", "srt",
                    str(temp_srt)
                ]
                result = subprocess.run(extract_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    # If it fails, try alternative approaches
                    # Sometimes the index needs adjustment
                    print(f"Warning: Failed to extract stream 0:{sub_index}. Trying alternative methods...")
                    # Try without specifying stream - extract all subtitles and pick by order
                    try:
                        extract_cmd = [
                            "ffmpeg", "-y", "-i", path,
                            "-c:s", "srt",
                            str(temp_srt)
                        ]
                        subprocess.run(extract_cmd, check=True, capture_output=True, text=True)
                    except Exception as extract_err:
                        print(f"Failed to extract subtitle {idx}: {extract_err}")
                        continue
                
                # Clean the SRT file of ASS/SSA artifacts
                if temp_srt.exists():
                    with open(temp_srt, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Remove common ASS/SSA formatting tags
                    # Remove style overrides: {\...}
                    content = re.sub(r'\{[^}]*\}', '', content)
                    # Remove drawing commands: {\p...}...{\p0}
                    content = re.sub(r'\{\\p\d+\}.*?\{\\p0\}', '', content)
                    # Clean up multiple spaces
                    content = re.sub(r'  +', ' ', content)
                    # Remove lines that are now empty after cleaning
                    lines = content.split('\n')
                    cleaned_lines = []
                    skip_entry = False
                    for line in lines:
                        stripped = line.strip()
                        # Check if this is a subtitle text line (not number, not timestamp)
                        if stripped and not stripped.isdigit() and '-->' not in stripped:
                            # If the line is now empty or just whitespace after cleaning, skip this entry
                            if not line.strip():
                                skip_entry = True
                                continue
                        if stripped == '' and skip_entry:
                            skip_entry = False
                            continue
                        cleaned_lines.append(line)
                    content = '\n'.join(cleaned_lines)
                    
                    # Write cleaned content back
                    with open(temp_srt, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    cleaned_subs.append((sub_index, str(temp_srt)))
            
            # Build ffmpeg command to remux with cleaned subtitles
            # Map all streams from source except subtitles we're replacing
            cmd = ["ffmpeg", "-y", "-i", path]
            
            # Add cleaned subtitle inputs
            for _, srt_path in cleaned_subs:
                cmd.extend(["-i", srt_path])
            
            # Map video and audio from original
            cmd.extend(["-map", "0:v?", "-map", "0:a?"])
            
            # Map cleaned subtitle streams
            for idx, (_, _) in enumerate(cleaned_subs, start=1):
                cmd.extend(["-map", f"{idx}:s"])
            
            # Map any subtitle streams that weren't converted (already SRT, or image-based we're keeping)
            subtitle_streams = item.get("subtitle_streams") or []
            converted_indices = {sub['index'] for sub in text_based_subs}
            for sub_stream in subtitle_streams:
                if sub_stream['index'] not in converted_indices:
                    cmd.extend(["-map", f"0:{sub_stream['index']}"])
            
            # Copy video and audio, convert subtitles to srt
            cmd.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "srt", tmp])
            
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        shutil.move(tmp, path)
        print(f"Converted and cleaned subtitle formats to SRT for {path}")
        return True  # Changes made successfully
    except Exception as e:
        print(f"Failed to convert subtitles via ffmpeg: {e}")
        # Clean up temp file if it exists
        if Path(tmp).exists():
            Path(tmp).unlink()
        raise  # Re-raise to count as failure


def find_original_files(directory: str) -> list:
    """Recursively find all files with -original suffix in the directory."""
    original_files = []
    try:
        for root, dirs, files in os.walk(directory):
            for fname in files:
                if "-original" in fname:
                    original_files.append(os.path.join(root, fname))
    except Exception as e:
        print(f"Error searching for original files: {e}")
    return original_files


def count_original_files(directory: str) -> int:
    """Count -original backup files without modifying them."""
    original_files = find_original_files(directory)
    return len(original_files)


def revert_files(directory: str) -> tuple:
    """
    Revert files by restoring from -original backups.
    Returns (total_affected, success_count, error_list)
    """
    original_files = find_original_files(directory)
    
    if not original_files:
        return 0, 0, []
    
    success_count = 0
    error_list = []
    
    for original_path in original_files:
        try:
            # Generate the target name by removing -original suffix
            path_obj = Path(original_path)
            name_parts = path_obj.name.rsplit("-original", 1)
            if len(name_parts) == 2:
                target_name = name_parts[0] + name_parts[1]
            else:
                continue  # Skip if we can't parse it correctly
            
            target_path = path_obj.parent / target_name
            
            # Delete the non-original file if it exists
            if target_path.exists():
                target_path.unlink()
            
            # Rename the original file to remove -original suffix
            path_obj.rename(target_path)
            success_count += 1
        except Exception as e:
            error_list.append((original_path, str(e)))
    
    return len(original_files), success_count, error_list


def clean_files(directory: str) -> tuple:
    """
    Delete all -original backup files.
    Returns (total_to_delete, success_count, error_list)
    """
    original_files = find_original_files(directory)
    
    if not original_files:
        return 0, 0, []
    
    success_count = 0
    error_list = []
    
    for original_path in original_files:
        try:
            Path(original_path).unlink()
            success_count += 1
        except Exception as e:
            error_list.append((original_path, str(e)))
    
    return len(original_files), success_count, error_list


class MultiSelectListbox:
    """A custom multiselect listbox widget."""
    def __init__(self, parent, items, selected=None, colors=None, height=5):
        self.parent = parent
        self.items = items
        # Normalize selected items - strip whitespace and match case-insensitively
        self.selected = set()
        if selected:
            for sel_item in selected:
                sel_normalized = sel_item.strip()
                # Find exact match in items (case-sensitive after normalization)
                for item in items:
                    if item.strip() == sel_normalized:
                        self.selected.add(item)
                        break
        
        self.colors = colors or {}
        self.height = height
        
        # Create frame
        self.frame = tk.Frame(parent)
        
        # Create scrollbar
        scrollbar = tk.Scrollbar(self.frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create listbox
        self.listbox = tk.Listbox(
            self.frame,
            selectmode=tk.MULTIPLE,
            yscrollcommand=scrollbar.set,
            height=height,
            bg=self.colors.get('entry_bg', '#3c3c3c'),
            fg=self.colors.get('fg', '#e0e0e0'),
            selectbackground=self.colors.get('highlight', '#4a6fa5'),
            highlightthickness=0,
            borderwidth=1,
            relief=tk.SOLID,
            exportselection=False
        )
        scrollbar.config(command=self.listbox.yview)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Populate listbox
        for i, item in enumerate(self.items):
            self.listbox.insert(tk.END, item)
            if item in self.selected:
                self.listbox.selection_set(i)
    
    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
    
    def get_selected(self):
        """Get list of selected items."""
        return [self.items[i] for i in self.listbox.curselection()]


class VideoAudioGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Audio Metadata Tool")
        self.root.geometry("700x500")
        
        # Dark mode color scheme
        self.colors = {
            'bg': '#2b2b2b',           # Dark background
            'fg': '#e0e0e0',           # Light text
            'select_bg': '#404040',     # Selected item background
            'button_bg': '#3c3c3c',     # Button background
            'button_fg': '#ffffff',     # Button text
            'entry_bg': '#3c3c3c',      # Entry background
            'entry_fg': '#e0e0e0',      # Entry text
            'frame_bg': '#2b2b2b',      # Frame background
            'highlight': '#4a6fa5',     # Accent color (blue)
            'border': '#404040',        # Border color
            'text': '#e0e0e0',          # Text color (same as fg)
        }
        
        # Apply dark theme
        self.apply_dark_theme()
        
        # Setup config directory
        self.script_dir = Path(__file__).resolve().parent
        self.config_dir = self.script_dir / "gui_configs"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "gui_config.json"
        
        # Setup output directory
        self.output_dir = self.script_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Track last scan result
        self.last_scan_file = None
        
        # Initialize setting variables
        self.keep_original_files = tk.BooleanVar(value=True)
        self.delete_previous_output_auto = tk.BooleanVar(value=False)
        self.attempt_identify_unknown_audio = tk.BooleanVar(value=False)
        
        # Language and format lists
        self.language_list = ["English", "Spanish", "French", "German", "Italian", "Portuguese", "Russian", "Japanese", "Chinese", "Korean"]
        self.subtitle_formats = ["SRT", "ASS", "SSA", "VTT", "SUB", "SBV", "JSON"]
        
        # Subtitle Settings
        self.subtitle_whitelist = tk.StringVar(value="English")
        self.allowed_subtitle_types = tk.StringVar(value="SRT")
        
        # Audio Settings
        self.default_audio_language = tk.StringVar(value="English")
        self.audio_whitelist = tk.StringVar(value="English")
        
        # Directory Management Settings
        self.ignore_directories = tk.StringVar(value="")
        
        # Create widgets first (needed for log_message)
        self.create_widgets()
        
        # Load existing config after widgets are created
        self.config = self.load_config()
        
        # Update menu visibility based on backup setting
        self.update_file_management_menu_visibility()
        
        # Selected directory
        if self.config.get("last_directory"):
            self.selected_directory.set(self.config.get("last_directory", ""))
            self.update_button_states()
            self.update_cleanup_buttons()
    
    def apply_dark_theme(self):
        """Apply dark theme styling to the application."""
        style = ttk.Style()
        
        # Try to use 'clam' theme as base (works well for dark mode)
        try:
            style.theme_use('clam')
        except:
            pass
        
        # Configure ttk styles
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('TLabel', background=self.colors['bg'], foreground=self.colors['fg'])
        style.configure('TButton', 
                       background=self.colors['button_bg'], 
                       foreground=self.colors['button_fg'],
                       borderwidth=1)
        style.map('TButton',
                 background=[('active', self.colors['highlight'])],
                 foreground=[('active', self.colors['button_fg'])])
        
        style.configure('TLabelframe', background=self.colors['bg'], foreground=self.colors['fg'])
        style.configure('TLabelframe.Label', background=self.colors['bg'], foreground=self.colors['fg'])
        
        # Configure root window
        self.root.configure(bg=self.colors['bg'])
        
    def create_widgets(self):
        """Create the GUI widgets."""
        # Create menu bar with dark mode colors
        menubar = tk.Menu(
            self.root,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            activebackground=self.colors['highlight'],
            activeforeground=self.colors['button_fg']
        )
        self.root.config(menu=menubar)
        
        # Settings menu
        settings_menu = tk.Menu(
            menubar,
            tearoff=0,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            activebackground=self.colors['highlight'],
            activeforeground=self.colors['button_fg']
        )
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Open Settings", command=self.open_settings_dialog)
        
        # Additional Scripts menu
        self.file_mgmt_menu = tk.Menu(
            menubar,
            tearoff=0,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            activebackground=self.colors['highlight'],
            activeforeground=self.colors['button_fg']
        )
        self.file_mgmt_menu_index = menubar.add_cascade(label="Additional Scripts", menu=self.file_mgmt_menu)
        self.file_mgmt_menu.add_command(label="Revert to Originals", command=self.revert_originals)
        self.file_mgmt_menu.add_command(label="Clean Backups", command=self.clean_backups)
        self.file_mgmt_menu.add_separator()
        self.file_mgmt_menu.add_command(label="Clear Output", command=self.clear_output_files)
        self.menubar = menubar
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Initialize selected directory variable
        self.selected_directory = tk.StringVar(value="")
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="Video Audio Metadata Tool", 
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Directory selection section
        dir_frame = ttk.LabelFrame(main_frame, text="Directory Selection", padding="10")
        dir_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W+tk.E, pady=(0, 20))
        dir_frame.columnconfigure(1, weight=1)
        
        ttk.Label(dir_frame, text="Selected Directory:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        dir_entry = ttk.Entry(dir_frame, textvariable=self.selected_directory, state="readonly")
        dir_entry.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        browse_btn = ttk.Button(dir_frame, text="Browse...", command=self.browse_directory)
        browse_btn.grid(row=0, column=2, sticky=tk.W, pady=5, padx=(0, 5))
        
        open_dir_btn = tk.Button(
            dir_frame, 
            text="⬆", 
            command=self.open_directory,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            width=1,
            height=1,
            font=("Arial", 12)
        )
        open_dir_btn.grid(row=0, column=3, sticky=tk.W, pady=1, padx=(1, 0))
        self.open_dir_btn = open_dir_btn
        
        # Action buttons section
        action_frame = ttk.LabelFrame(main_frame, text="Actions", padding="10")
        action_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W+tk.E, pady=(0, 20))
        
        analyze_btn = ttk.Button(
            action_frame, 
            text="Scan & Analyze", 
            command=self.scan_and_analyze,
            state=tk.DISABLED
        )
        analyze_btn.grid(row=0, column=0, padx=5, pady=5)
        self.analyze_btn = analyze_btn
        
        fix_btn = ttk.Button(
            action_frame, 
            text="Fix Issues", 
            command=self.fix_issues,
            state=tk.DISABLED
        )
        fix_btn.grid(row=0, column=2, padx=5, pady=5)
        self.fix_btn = fix_btn
        
        # Log output section with custom header
        log_container = tk.Frame(main_frame, bg=self.colors['bg'])
        log_container.grid(row=3, column=0, columnspan=3, sticky=tk.W+tk.E+tk.N+tk.S, pady=(10, 10))
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Header frame with title and save button
        log_header_frame = tk.Frame(log_container, bg=self.colors['bg'])
        log_header_frame.grid(row=0, column=0, sticky=tk.W+tk.E, pady=(0, 5))
        log_header_frame.columnconfigure(0, weight=1)
        
        # Output Log title
        log_title = tk.Label(
            log_header_frame,
            text="Output Log",
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            font=("Arial", 10, "bold")
        )
        log_title.grid(row=0, column=0, sticky=tk.W)
        
        # Save Log button (floated to right)
        save_log_btn = tk.Button(
            log_header_frame,
            text="💾 Save Log",
            command=self.save_log_to_file,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            font=("Arial", 9),
            padx=10,
            pady=2
        )
        save_log_btn.grid(row=0, column=1, sticky=tk.E, padx=5)
        
        # Log frame for text widget
        log_frame = tk.Frame(log_container, bg=self.colors['entry_bg'])
        log_frame.grid(row=1, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        
        # Text widget with scrollbar (dark mode styling)
        self.log_text = tk.Text(
            log_frame, 
            height=15, 
            wrap=tk.WORD, 
            state=tk.DISABLED,
            bg=self.colors['entry_bg'],
            fg=self.colors['entry_fg'],
            insertbackground=self.colors['fg'],
            selectbackground=self.colors['highlight'],
            selectforeground=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        scrollbar.grid(row=0, column=1, sticky=tk.N+tk.S)
        
        # Status bar with progress bar
        self.status_var = tk.StringVar(value="Ready")
        self.progress_percentage = 0
        
        # Create canvas for visual progress bar
        status_canvas = tk.Canvas(
            main_frame, 
            height=25, 
            bg=self.colors['bg'], 
            highlightthickness=0
        )
        status_canvas.grid(row=4, column=0, columnspan=3, sticky=tk.W+tk.E)
        self.status_canvas = status_canvas
        
        # Bind to canvas resize to redraw progress bar
        status_canvas.bind("<Configure>", self._on_status_canvas_resize)
    
    def _on_status_canvas_resize(self, event=None):
        """Redraw progress bar when canvas is resized."""
        self._update_progress_bar_display()
    
    def _update_progress_bar_display(self):
        """Update the visual progress bar on the canvas."""
        self.status_canvas.delete("all")
        
        width = self.status_canvas.winfo_width()
        height = self.status_canvas.winfo_height()
        
        if width <= 1:  # Canvas not yet rendered
            return
        
        # Draw background (dark)
        self.status_canvas.create_rectangle(
            0, 0, width, height,
            fill=self.colors['bg'],
            outline=self.colors['border'],
            width=1
        )
        
        # Draw filled progress rectangle (green)
        if self.progress_percentage > 0:
            filled_width = (width * self.progress_percentage) / 100
            self.status_canvas.create_rectangle(
                0, 0, filled_width, height,
                fill="#4CAF50",  # Green
                outline="",
                width=0
            )
        
        # Draw text centered
        text = self.status_var.get()
        self.status_canvas.create_text(
            width / 2, height / 2,
            text=text,
            fill=self.colors['text'],
            font=("Arial", 10),
            anchor=tk.CENTER
        )

    
    def browse_directory(self):
        """Open directory browser dialog."""
        initial_dir = self.selected_directory.get() or os.path.expanduser("~")
        
        directory = filedialog.askdirectory(
            title="Select Directory to Scan",
            initialdir=initial_dir
        )
        
        if directory:
            self.selected_directory.set(directory)
            self.save_config()
            self.log_message(f"Directory selected: {directory}")
            self.update_button_states()
            self.update_cleanup_buttons()
    
    def update_button_states(self):
        """Enable/disable buttons based on selected directory."""
        has_directory = bool(self.selected_directory.get())
        
        if has_directory:
            self.analyze_btn.config(state=tk.NORMAL)
            self.fix_btn.config(state=tk.NORMAL)
            self._set_status("Ready - Directory: " + self.selected_directory.get(), 0)
        else:
            self.analyze_btn.config(state=tk.DISABLED)
            self.fix_btn.config(state=tk.DISABLED)
            self._set_status("Ready - No directory selected", 0)
    
    def _set_status(self, message: str, percentage: int = 0):
        """Set status message and progress percentage."""
        self.status_var.set(message)
        self.progress_percentage = min(100, max(0, percentage))
        self._update_progress_bar_display()
    
    def show_dark_info(self, title: str, message: str):
        """Show info dialog with dark theme styling."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configure dark background
        dialog.configure(bg=self.colors['bg'])
        
        # Message frame
        msg_frame = tk.Frame(dialog, bg=self.colors['bg'])
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        msg_label = tk.Label(
            msg_frame,
            text=message,
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            wraplength=360,
            justify=tk.LEFT
        )
        msg_label.pack(pady=10)
        
        # Button frame
        btn_frame = tk.Frame(dialog, bg=self.colors['bg'])
        btn_frame.pack(pady=(0, 10))
        
        ok_btn = tk.Button(
            btn_frame,
            text="OK",
            command=dialog.destroy,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            width=10
        )
        ok_btn.pack()
        
        dialog.focus()
    
    def show_dark_warning(self, title: str, message: str):
        """Show warning dialog with dark theme styling."""
        self.show_dark_info(title, message)
    
    def show_dark_error(self, title: str, message: str):
        """Show error dialog with dark theme styling."""
        self.show_dark_info(title, message)
    
    def show_dark_confirm(self, title: str, message: str) -> bool:
        """Show confirmation dialog with dark theme styling. Returns True if OK clicked."""
        result = [False]
        
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configure dark background
        dialog.configure(bg=self.colors['bg'])
        
        # Message frame
        msg_frame = tk.Frame(dialog, bg=self.colors['bg'])
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        msg_label = tk.Label(
            msg_frame,
            text=message,
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            wraplength=360,
            justify=tk.LEFT
        )
        msg_label.pack(pady=10)
        
        # Button frame
        btn_frame = tk.Frame(dialog, bg=self.colors['bg'])
        btn_frame.pack(pady=(0, 10))
        
        def on_ok():
            result[0] = True
            dialog.destroy()
        
        ok_btn = tk.Button(
            btn_frame,
            text="OK",
            command=on_ok,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            width=8
        )
        ok_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            width=8
        )
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        dialog.focus()
        self.root.wait_window(dialog)
        return result[0]
    
    def find_latest_analyze(self, prefix: str):
        """Find the latest analyze file with given prefix in output directory."""
        pattern = f"analyze_{prefix}*"
        candidates = list(self.output_dir.glob(pattern + ".json"))
        if not candidates:
            # Fallback to broader pattern
            pattern = f"analyze*{prefix}*"
            candidates = list(self.output_dir.glob(pattern + ".json"))
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]
    
    def _file_has_results(self, file_path):
        """Check if an analysis file contains actual results."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                results = data.get("results", [])
                return len(results) > 0
        except Exception:
            return False
    
    def _file_has_results_non_embedded(self, file_path):
        """Check if a non-embedded subtitles analysis file contains actual results."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                linked = data.get("linked_results", [])
                unlinked = data.get("unlinked_results", [])
                return len(linked) > 0 or len(unlinked) > 0
        except Exception:
            return False
    
    def update_file_management_menu_visibility(self):
        """Additional Scripts menu is always enabled."""
        # Menu is always enabled, no conditional logic needed
        pass
    
    def load_config(self):
        """Load configuration from JSON file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.log_message("Configuration loaded")
                    
                    # Load settings
                    self.keep_original_files.set(config.get("keep_original_files", True))
                    
                    # Load subtitle settings - store as comma-separated strings
                    subtitle_whitelist = config.get("subtitle_whitelist", "English")
                    if subtitle_whitelist:
                        self.subtitle_whitelist.set(subtitle_whitelist)
                    
                    allowed_types = config.get("allowed_subtitle_types", "SRT")
                    if allowed_types:
                        self.allowed_subtitle_types.set(allowed_types)
                    
                    # Load audio settings - store as comma-separated strings
                    default_audio = config.get("default_audio_language", "English")
                    if default_audio:
                        self.default_audio_language.set(default_audio)
                    
                    audio_whitelist = config.get("audio_whitelist", "English")
                    if audio_whitelist:
                        self.audio_whitelist.set(audio_whitelist)
                    
                    # Load audio analysis settings
                    self.attempt_identify_unknown_audio.set(config.get("attempt_identify_unknown_audio", False))
                    
                    # Load backup settings
                    self.delete_previous_output_auto.set(config.get("delete_previous_output_auto", False))
                    
                    # Load directory management settings (raw text)
                    ignore_dirs = config.get("ignore_directories", "")
                    if ignore_dirs:
                        self.ignore_directories.set(ignore_dirs)
                    
                    return config
            except Exception as e:
                self.log_message(f"Error loading config: {e}")
                return {}
        return {}
    
    def save_config(self):
        """Save configuration to JSON file."""
        try:
            config_data = {
                "last_directory": self.selected_directory.get(),
                "keep_original_files": self.keep_original_files.get(),
                "delete_previous_output_auto": self.delete_previous_output_auto.get(),
                "subtitle_whitelist": self.subtitle_whitelist.get(),
                "allowed_subtitle_types": self.allowed_subtitle_types.get(),
                "default_audio_language": self.default_audio_language.get(),
                "audio_whitelist": self.audio_whitelist.get(),
                "attempt_identify_unknown_audio": self.attempt_identify_unknown_audio.get(),
                "ignore_directories": self.ignore_directories.get(),
                "last_updated": datetime.now().isoformat(),
            }
            
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            
            self.log_message(f"Configuration saved to {self.config_file}")
            self.status_var.set("Configuration saved")
        except Exception as e:
            error_msg = f"Error saving config: {e}"
            self.log_message(error_msg)
            messagebox.showerror("Save Error", error_msg)
    
    def update_cleanup_buttons(self):
        """Update cleanup button states (now only used for logging)."""
        # Buttons are now in a dialog, so this just logs the check
        directory = self.selected_directory.get()
        if directory:
            original_count = count_original_files(directory)
            if original_count > 0:
                self.log_message(f"Found {original_count} backup file(s)")
    
    def revert_originals(self):
        """Revert files from -original backups."""
        directory = self.selected_directory.get()
        if not directory:
            messagebox.showwarning("No Directory", "Please select a directory first")
            return
        
        # Count files WITHOUT modifying them
        total_files = count_original_files(directory)
        
        if total_files == 0:
            messagebox.showinfo("No Backups", "No -original backup files found")
            return
        
        # Show confirmation dialog
        response = messagebox.askokcancel(
            "Revert Backups",
            f"This will restore {total_files} file(s) from their -original backups:\n\n"
            f"- Delete the current modified file\n"
            f"- Rename the -original file to replace it\n\n"
            f"Are you sure you want to proceed?"
        )
        
        if not response:
            return
        
        # Actually perform the revert
        self.log_message("Starting file revert process...")
        try:
            total, success, errors = revert_files(directory)
            self.log_message(f"Revert complete: {success}/{total} files restored")
            
            if errors:
                error_msg = "Errors occurred during revert:\n" + "\n".join(f"{f}: {e}" for f, e in errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors) - 5} more errors"
                messagebox.showwarning("Revert Errors", error_msg)
            
            self.update_cleanup_buttons()
        except Exception as e:
            messagebox.showerror("Revert Error", f"Failed to revert files: {e}")
    
    def clean_backups(self):
        """Delete all -original backup files."""
        directory = self.selected_directory.get()
        if not directory:
            messagebox.showwarning("No Directory", "Please select a directory first")
            return
        
        # Count files WITHOUT modifying them
        total_files = count_original_files(directory)
        
        if total_files == 0:
            messagebox.showinfo("No Backups", "No -original backup files found")
            return
        
        # Show confirmation dialog
        response = messagebox.askokcancel(
            "Clean Backups",
            f"This will permanently delete {total_files} backup file(s):\n\n"
            f"- All files with -original in their name will be deleted\n"
            f"- This cannot be undone\n\n"
            f"Are you sure you want to proceed?"
        )
        
        if not response:
            return
        
        # Actually perform the clean
        self.log_message("Starting backup cleanup process...")
        try:
            total, success, errors = clean_files(directory)
            self.log_message(f"Cleanup complete: {success}/{total} backup files deleted")
            
            if errors:
                error_msg = "Errors occurred during cleanup:\n" + "\n".join(f"{f}: {e}" for f, e in errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors) - 5} more errors"
                messagebox.showwarning("Cleanup Errors", error_msg)
            
            self.update_cleanup_buttons()
        except Exception as e:
            messagebox.showerror("Cleanup Error", f"Failed to clean backups: {e}")
    
    def clear_output_files(self):
        """Clear all JSON files from the output folder."""
        # Show confirmation dialog
        response = messagebox.askokcancel(
            "Clear Output Files",
            f"This will delete all JSON files in the output folder:\n\n"
            f"- {self.output_dir}\n"
            f"- This cannot be undone\n"
            f"- Fix Issues will be disabled until new analysis is run\n\n"
            f"Are you sure you want to proceed?"
        )
        
        if not response:
            return
        
        self.log_message("Clearing output files...")
        try:
            json_files = list(self.output_dir.glob("*.json"))
            if not json_files:
                messagebox.showinfo("No Output Files", "No JSON files found in output folder")
                self.log_message("No output files to clear")
                return
            
            # Delete all JSON files
            deleted_count = 0
            errors = []
            for json_file in json_files:
                try:
                    json_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    errors.append((json_file.name, str(e)))
            
            # Log results
            self.log_message(f"Removed {deleted_count} output file(s)")
            
            # Disable Fix Issues button since analysis files are gone
            self.fix_btn.config(state=tk.DISABLED)
            self._set_status("Output cleared - Analysis needed", 0)
            
            if errors:
                error_msg = "Errors occurred while deleting files:\n" + "\n".join(f"{f}: {e}" for f, e in errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors) - 5} more errors"
                messagebox.showwarning("Deletion Errors", error_msg)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear output files: {e}")
    
    def log_message(self, message):
        """Add a message to the log output."""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def save_log_to_file(self):
        """Save the current output log to a file."""
        try:
            # Get current log content
            log_content = self.log_text.get("1.0", tk.END)
            
            # Check if log is empty
            if not log_content.strip():
                messagebox.showinfo("Empty Log", "The output log is empty. Nothing to save.")
                return
            
            # Create filename with timestamp
            timestamp = datetime.now().isoformat().replace(":", "-")
            filename = f"output_log_{timestamp}.txt"
            output_path = self.output_dir / filename
            
            # Save to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(log_content)
            
            self.log_message(f"Log saved to: {output_path.name}")
            
        except Exception as e:
            error_msg = f"Failed to save log: {e}"
            messagebox.showerror("Save Error", error_msg)
            self.log_message(f"ERROR: {error_msg}")
    
    def open_directory(self):
        """Open the selected directory in the default file explorer."""
        directory = self.selected_directory.get()
        if not directory:
            messagebox.showwarning("No Directory", "Please select a directory first.")
            return
        
        dir_path = Path(directory)
        if not dir_path.exists():
            messagebox.showerror("Invalid Directory", f"Directory does not exist: {directory}")
            return
        
        try:
            import platform
            import subprocess
            
            system = platform.system()
            if system == "Windows":
                os.startfile(directory)
            elif system == "Darwin":  # macOS
                subprocess.Popen(["open", directory])
            else:  # Linux and other Unix-like
                subprocess.Popen(["xdg-open", directory])
            
            self.log_message(f"Opened directory: {directory}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open directory: {e}")
            self.log_message(f"Error opening directory: {e}")
    
    def scan_directory(self):
        """Scan the selected directory for video files."""
        directory = self.selected_directory.get()
        if not directory:
            messagebox.showwarning("No Directory", "Please select a directory first.")
            return
        
        dir_path = Path(directory)
        if not dir_path.exists():
            messagebox.showerror("Invalid Directory", f"Directory does not exist: {directory}")
            return
        
        # Check if ffprobe is available
        if not shutil.which("ffprobe"):
            messagebox.showerror("FFprobe Not Found",
                "FFprobe (part of FFmpeg) is required but not found.\n\n"
                "To install on Ubuntu/Debian:\n"
                "  sudo apt-get install ffmpeg\n\n"
                "To install on other systems:\n"
                "  Visit: https://ffmpeg.org/download.html")
            return
        
        # Disable buttons during scan
        self.set_buttons_enabled(False)
        self.log_message(f"Starting scan of: {directory}")
        self.status_var.set("Scanning... Please wait")
        
        # Run scan in separate thread to keep GUI responsive
        scan_thread = threading.Thread(target=self._run_scan, args=(dir_path,), daemon=True)
        scan_thread.start()
    
    def _run_scan(self, dir_path):
        """Run the scan operation in a background thread."""
        try:
            self.root.after(0, lambda: self._set_status("Scanning 0 files - please wait", 0))
            self.log_message("Discovering video files...")
            
            # Parse ignore directories from config
            ignore_dirs_text = self.ignore_directories.get()
            ignore_dirs = set()
            if ignore_dirs_text:
                for line in ignore_dirs_text.split('\n'):
                    line = line.strip()
                    if line:  # Skip empty lines
                        ignore_dirs.add(line)
                if ignore_dirs:
                    self.log_message(f"Ignoring {len(ignore_dirs)} director{'y' if len(ignore_dirs) == 1 else 'ies'}")
            
            # Track scan progress with a progress callback
            def scan_progress(current_count, file_path):
                """Callback to update scan progress."""
                # Update every 50 files to reduce UI updates
                if current_count % 50 == 0 or current_count < 10:
                    self.root.after(0, lambda c=current_count: self._set_status(f"Scanning {c} files - please wait", 0))
            
            results = walk_and_scan(dir_path, progress_callback=scan_progress, ignore_dirs=ignore_dirs, log_callback=self.log_message)
            
            if not results:
                self.root.after(0, lambda: self._scan_complete([], dir_path, "No video files found"))
                return
            
            # Save results to JSON
            self.root.after(0, lambda r=len(results): self._set_status(f"Saving {r} scanned files - please wait", 50))
            timestamp = datetime.now().isoformat().replace(":", "-")
            out_name = f"scan_{dir_path.name}_{timestamp}.json"
            out_path = self.output_dir / out_name
            
            payload = {
                "scanned_path": str(dir_path),
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "file_count": len(results),
                "results": results,
            }
            
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            
            self.last_scan_file = out_path
            
            # Update UI in main thread
            self.root.after(0, lambda: self._set_status("Finalizing - please wait", 95))
            self.root.after(0, lambda: self._scan_complete(results, dir_path, str(out_path)))
            
        except Exception as e:
            error_msg = f"Scan failed: {e}"
            self.root.after(0, lambda: self._scan_error(error_msg))
    
    def _scan_complete(self, results, dir_path, output_file):
        """Handle scan completion (called in main thread)."""
        self.log_message(f"Scan complete! Found {len(results)} video files")
        self.log_message(f"Results saved to: {output_file}")
        
        # Summary of findings
        if results:
            audio_issues = sum(1 for r in results if not r.get("audio_streams"))
            subtitle_issues = sum(1 for r in results if not r.get("subtitle_streams"))
            self.log_message(f"Summary: {len(results)} videos, {audio_issues} without audio, {subtitle_issues} without subtitles")
        
        self._set_status(f"Scan complete - {len(results)} video files found", 100)
        self.set_buttons_enabled(True)
    
    def _scan_error(self, error_msg):
        """Handle scan error (called in main thread)."""
        self.log_message(f"ERROR: {error_msg}")
        self.status_var.set("Scan failed")
        self.set_buttons_enabled(True)
        messagebox.showerror("Scan Error", error_msg)
    
    def set_buttons_enabled(self, enabled):
        """Enable or disable action buttons."""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.analyze_btn.config(state=state)
        self.fix_btn.config(state=state)
    
    def open_settings_dialog(self):
        """Open settings dialog window with multiple sections."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("600x850")
        dialog.resizable(False, False)
        
        # Center dialog on parent window
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configure dark background
        dialog.configure(bg=self.colors['bg'])
        
        # Create main scrollable frame
        main_frame = tk.Frame(dialog, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scroll canvas
        canvas = tk.Canvas(main_frame, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create local copies of settings for the dialog
        keep_backup_var = tk.BooleanVar(value=self.keep_original_files.get())
        delete_output_var = tk.BooleanVar(value=self.delete_previous_output_auto.get())
        
        # Parse multiselect values - strip whitespace from each item
        def parse_multiselect(value_str):
            """Parse comma-separated string into list of stripped values."""
            if not value_str or not value_str.strip():
                return []
            return [item.strip() for item in value_str.split(",")]
        
        subtitle_whitelist_selected = parse_multiselect(self.subtitle_whitelist.get())
        if not subtitle_whitelist_selected:
            subtitle_whitelist_selected = ["English"]
            
        allowed_types_selected = parse_multiselect(self.allowed_subtitle_types.get())
        if not allowed_types_selected:
            allowed_types_selected = ["SRT"]
            
        audio_whitelist_selected = parse_multiselect(self.audio_whitelist.get())
        if not audio_whitelist_selected:
            audio_whitelist_selected = ["English"]
        
        # ===== SUBTITLE SETTINGS SECTION =====
        subtitle_label = tk.Label(
            scrollable_frame,
            text="Subtitle Settings",
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            font=("Arial", 11, "bold")
        )
        subtitle_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        subtitle_frame = tk.Frame(scrollable_frame, bg=self.colors['frame_bg'], relief=tk.FLAT, borderwidth=1)
        subtitle_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        
        # Subtitle Whitelist
        sub_wl_label = tk.Label(
            subtitle_frame,
            text="Subtitle Whitelist (Languages to Keep):",
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            font=("Arial", 9)
        )
        sub_wl_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        sub_wl_listbox = MultiSelectListbox(
            subtitle_frame,
            self.language_list,
            selected=subtitle_whitelist_selected,
            colors=self.colors,
            height=3
        )
        sub_wl_listbox.pack(fill=tk.BOTH, padx=10, pady=(0, 10))
        
        # Allowed Subtitle Types
        sub_types_label = tk.Label(
            subtitle_frame,
            text="Allowed Subtitle Types:",
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            font=("Arial", 9)
        )
        sub_types_label.pack(anchor=tk.W, padx=10, pady=(0, 5))
        
        sub_types_listbox = MultiSelectListbox(
            subtitle_frame,
            self.subtitle_formats,
            selected=allowed_types_selected,
            colors=self.colors,
            height=3
        )
        sub_types_listbox.pack(fill=tk.BOTH, padx=10, pady=(0, 10))
        
        # ===== AUDIO SETTINGS SECTION =====
        audio_label = tk.Label(
            scrollable_frame,
            text="Audio Settings",
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            font=("Arial", 11, "bold")
        )
        audio_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        audio_frame = tk.Frame(scrollable_frame, bg=self.colors['frame_bg'], relief=tk.FLAT, borderwidth=1)
        audio_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        
        # Default Audio Language (single select)
        default_audio_label = tk.Label(
            audio_frame,
            text="Default Audio Language:",
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            font=("Arial", 9)
        )
        default_audio_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        default_audio_var = tk.StringVar(value=self.default_audio_language.get())
        default_audio_combo = ttk.Combobox(
            audio_frame,
            textvariable=default_audio_var,
            values=self.language_list,
            state="readonly",
            width=30
        )
        default_audio_combo.pack(anchor=tk.W, padx=10, pady=(0, 10))
        
        # Audio Whitelist
        audio_wl_label = tk.Label(
            audio_frame,
            text="Audio Whitelist (Languages to Keep):",
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            font=("Arial", 9)
        )
        audio_wl_label.pack(anchor=tk.W, padx=10, pady=(0, 5))
        
        audio_wl_listbox = MultiSelectListbox(
            audio_frame,
            self.language_list,
            selected=audio_whitelist_selected,
            colors=self.colors,
            height=3
        )
        audio_wl_listbox.pack(fill=tk.BOTH, padx=10, pady=(0, 10))
        
        # Attempt to Identify Unknown Audio Streams
        attempt_identify_var = tk.BooleanVar(value=self.attempt_identify_unknown_audio.get())
        attempt_identify_check = tk.Checkbutton(
            audio_frame,
            text="Attempt to Identify Unknown Audio Streams",
            variable=attempt_identify_var,
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            selectcolor=self.colors['frame_bg'],
            activebackground=self.colors['frame_bg'],
            activeforeground=self.colors['fg']
        )
        attempt_identify_check.pack(anchor=tk.W, padx=10, pady=(0, 10))
        
        # ===== BACKUP SETTINGS SECTION =====
        backup_label = tk.Label(
            scrollable_frame,
            text="Backup Settings",
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            font=("Arial", 11, "bold")
        )
        backup_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        backup_frame = tk.Frame(scrollable_frame, bg=self.colors['frame_bg'], relief=tk.FLAT, borderwidth=1)
        backup_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        
        cb_keep_backup = tk.Checkbutton(
            backup_frame,
            text="Keep Original Files (Create Backups)",
            variable=keep_backup_var,
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            selectcolor=self.colors['highlight'],
            activebackground=self.colors['frame_bg'],
            activeforeground=self.colors['fg']
        )
        cb_keep_backup.pack(anchor=tk.W, padx=10, pady=10)
        
        cb_delete_output = tk.Checkbutton(
            backup_frame,
            text="Delete Previous Output Automatically",
            variable=delete_output_var,
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            selectcolor=self.colors['highlight'],
            activebackground=self.colors['frame_bg'],
            activeforeground=self.colors['fg']
        )
        cb_delete_output.pack(anchor=tk.W, padx=10, pady=(0, 10))
        
        # ===== DIRECTORY MANAGEMENT SECTION =====
        dir_mgmt_label = tk.Label(
            scrollable_frame,
            text="Directory Management",
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            font=("Arial", 11, "bold")
        )
        dir_mgmt_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        dir_mgmt_frame = tk.Frame(scrollable_frame, bg=self.colors['frame_bg'], relief=tk.FLAT, borderwidth=1)
        dir_mgmt_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 10))
        
        # Ignore Directory label with tooltip
        ignore_dir_header_frame = tk.Frame(dir_mgmt_frame, bg=self.colors['frame_bg'])
        ignore_dir_header_frame.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        ignore_dir_label = tk.Label(
            ignore_dir_header_frame,
            text="Ignore Directory:",
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            font=("Arial", 9)
        )
        ignore_dir_label.pack(side=tk.LEFT)
        
        # Tooltip icon
        tooltip_label = tk.Label(
            ignore_dir_header_frame,
            text=" ⓘ",
            bg=self.colors['frame_bg'],
            fg=self.colors['highlight'],
            font=("Arial", 10, "bold"),
            cursor="question_arrow"
        )
        tooltip_label.pack(side=tk.LEFT)
        
        # Create tooltip
        def create_tooltip(widget, text):
            """Create a tooltip for a widget."""
            tooltip = None
            
            def on_enter(event):
                nonlocal tooltip
                x, y, _, _ = widget.bbox("insert")
                x += widget.winfo_rootx() + 20
                y += widget.winfo_rooty() + 20
                
                tooltip = tk.Toplevel(widget)
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{x}+{y}")
                
                label = tk.Label(
                    tooltip,
                    text=text,
                    background="#ffffe0",
                    foreground="#000000",
                    relief=tk.SOLID,
                    borderwidth=1,
                    font=("Arial", 9),
                    padx=5,
                    pady=3
                )
                label.pack()
            
            def on_leave(event):
                nonlocal tooltip
                if tooltip:
                    tooltip.destroy()
                    tooltip = None
            
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
        
        create_tooltip(tooltip_label, "Add absolute directory path to ignore - 1 path per line")
        
        # Multi-line text widget for ignore directories
        ignore_dir_text_frame = tk.Frame(dir_mgmt_frame, bg=self.colors['frame_bg'])
        ignore_dir_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        ignore_dir_text = tk.Text(
            ignore_dir_text_frame,
            height=5,
            width=50,
            bg=self.colors['entry_bg'],
            fg=self.colors['entry_fg'],
            insertbackground=self.colors['entry_fg'],
            wrap=tk.NONE,
            font=("Arial", 9)
        )
        ignore_dir_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar for text widget
        ignore_dir_scrollbar = tk.Scrollbar(ignore_dir_text_frame, command=ignore_dir_text.yview)
        ignore_dir_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        ignore_dir_text.config(yscrollcommand=ignore_dir_scrollbar.set)
        
        # Load current value
        current_ignore_dirs = self.ignore_directories.get()
        if current_ignore_dirs:
            ignore_dir_text.insert("1.0", current_ignore_dirs)
        
        # ===== BUTTON FRAME =====
        button_frame = tk.Frame(dialog, bg=self.colors['bg'])
        button_frame.pack(pady=(0, 10))
        
        def save_settings():
            # Save basic settings
            self.keep_original_files.set(keep_backup_var.get())
            self.delete_previous_output_auto.set(delete_output_var.get())
            
            # Save multiselect settings
            subtitle_wl = sub_wl_listbox.get_selected()
            self.subtitle_whitelist.set(", ".join(subtitle_wl) if subtitle_wl else "English")
            
            allowed_types = sub_types_listbox.get_selected()
            self.allowed_subtitle_types.set(", ".join(allowed_types) if allowed_types else "SRT")
            
            self.default_audio_language.set(default_audio_var.get())
            
            audio_wl = audio_wl_listbox.get_selected()
            self.audio_whitelist.set(", ".join(audio_wl) if audio_wl else "English")
            
            self.attempt_identify_unknown_audio.set(attempt_identify_var.get())
            
            # Save ignore directories (raw text)
            ignore_dirs_text = ignore_dir_text.get("1.0", tk.END).rstrip("\n")
            self.ignore_directories.set(ignore_dirs_text)
            
            # Save to config file
            self.save_config()
            
            # Update menu visibility based on new backup setting
            self.update_file_management_menu_visibility()
            
            self.log_message("Settings saved")
            dialog.destroy()
        
        def cancel_settings():
            dialog.destroy()
        
        save_btn = tk.Button(
            button_frame,
            text="Save",
            command=save_settings,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            width=10
        )
        save_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=cancel_settings,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            width=10
        )
        cancel_btn.pack(side=tk.LEFT, padx=5)
    
    def open_file_management_dialog(self):
        """Open backup management dialog window."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Backup Management")
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        
        # Center dialog on parent window
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configure dark background
        dialog.configure(bg=self.colors['bg'])
        
        # Backup management frame with dark mode
        mgmt_frame = tk.Frame(dialog, bg=self.colors['frame_bg'], relief=tk.FLAT, borderwidth=1)
        mgmt_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        mgmt_label = tk.Label(
            mgmt_frame,
            text="Backup Management",
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            font=("Arial", 10, "bold")
        )
        mgmt_label.pack(anchor=tk.W, padx=10, pady=(5, 0))
        
        # Determine if buttons should be enabled
        directory = self.selected_directory.get()
        has_backups = False
        if directory:
            has_backups = count_original_files(directory) > 0
        
        buttons_frame = tk.Frame(mgmt_frame, bg=self.colors['frame_bg'])
        buttons_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        revert_btn = tk.Button(
            buttons_frame,
            text="Revert to Originals",
            command=self.revert_originals,
            state=tk.NORMAL if has_backups else tk.DISABLED,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2" if has_backups else "arrow"
        )
        revert_btn.pack(pady=5, fill=tk.X)
        
        clean_btn = tk.Button(
            buttons_frame,
            text="Clean Backups",
            command=self.clean_backups,
            state=tk.NORMAL if has_backups else tk.DISABLED,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2" if has_backups else "arrow"
        )
        clean_btn.pack(pady=5, fill=tk.X)
        
        # Close button
        button_frame = tk.Frame(dialog, bg=self.colors['bg'])
        button_frame.pack(pady=(0, 10))
        
        close_btn = tk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy,
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            borderwidth=1,
            relief=tk.FLAT,
            cursor="hand2",
            width=10
        )
        close_btn.pack(padx=5)
    
    def scan_and_analyze(self):
        """Run scan and then analyze in sequence."""
        directory = self.selected_directory.get()
        if not directory:
            messagebox.showwarning("No Directory", "Please select a directory first.")
            return
        
        dir_path = Path(directory)
        if not dir_path.exists():
            messagebox.showerror("Invalid Directory", f"Directory does not exist: {directory}")
            return
        
        # Check if ffprobe is available
        if not shutil.which("ffprobe"):
            messagebox.showerror("FFprobe Not Found",
                "FFprobe (part of FFmpeg) is required but not found.\n\n"
                "To install on Ubuntu/Debian:\n"
                "  sudo apt-get install ffmpeg\n\n"
                "To install on other systems:\n"
                "  Visit: https://ffmpeg.org/download.html")
            return
        
        # Disable buttons during scan & analyze
        self.set_buttons_enabled(False)
        self.log_message(f"Starting scan and analysis of: {directory}")
        self._set_status("Scanning and analyzing... Please wait", 0)
        
        # Run scan and analyze in separate thread
        thread = threading.Thread(target=self._run_scan_and_analyze, args=(dir_path,), daemon=True)
        thread.start()
    
    def _run_scan_and_analyze(self, dir_path):
        """Run scan and analyze in background thread."""
        try:
            # Clear previous output files if setting is enabled
            if self.delete_previous_output_auto.get():
                json_files = list(self.output_dir.glob("*.json"))
                if json_files:
                    deleted_count = 0
                    for json_file in json_files:
                        try:
                            json_file.unlink()
                            deleted_count += 1
                        except Exception:
                            pass
                    if deleted_count > 0:
                        self.root.after(0, lambda d=deleted_count: self.log_message(f"Cleared {d} previous output file(s)"))
            
            # === SCAN PHASE ===
            self.log_message("Discovering video files...")
            self.root.after(0, lambda: self._set_status("Scanning 0 files - please wait", 0))
            
            # Parse ignore directories from config
            ignore_dirs_text = self.ignore_directories.get()
            ignore_dirs = set()
            if ignore_dirs_text:
                for line in ignore_dirs_text.split('\n'):
                    line = line.strip()
                    if line:  # Skip empty lines
                        ignore_dirs.add(line)
                if ignore_dirs:
                    self.root.after(0, lambda c=len(ignore_dirs): self.log_message(f"Ignoring {c} director{'y' if c == 1 else 'ies'}"))
            
            # Track scan progress with callback
            def scan_progress(current_count, file_path):
                """Callback to update scan progress."""
                # Update every 50 files to reduce UI updates
                if current_count % 50 == 0 or current_count < 10:
                    self.root.after(0, lambda c=current_count: self._set_status(f"Scanning {c} files - please wait", 0))
            
            results = walk_and_scan(dir_path, progress_callback=scan_progress, ignore_dirs=ignore_dirs, log_callback=self.log_message)
            
            if not results:
                self.root.after(0, lambda: self._scan_and_analyze_complete([], None, None))
                return
            
            # Save scan results to JSON
            timestamp = datetime.now().isoformat().replace(":", "-")
            scan_out_name = f"scan_{dir_path.name}_{timestamp}.json"
            scan_out_path = self.output_dir / scan_out_name
            
            payload = {
                "scanned_path": str(dir_path),
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "file_count": len(results),
                "results": results,
            }
            
            with open(scan_out_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            
            self.last_scan_file = scan_out_path
            
            # Log scan results
            self.root.after(0, lambda: self.log_message(f"Scan complete! Found {len(results)} video files"))
            if results:
                audio_issues = sum(1 for r in results if not r.get("audio_streams"))
                subtitle_issues = sum(1 for r in results if not r.get("subtitle_streams"))
                summary_msg = f"Scan Summary: {len(results)} videos, {audio_issues} without audio, {subtitle_issues} without subtitles"
                self.root.after(0, lambda: self.log_message(summary_msg))
                
                # If there are files without audio, list them
                if audio_issues > 0:
                    no_audio_files = [r.get("path") for r in results if not r.get("audio_streams")]
                    for file_path in no_audio_files:
                        self.root.after(0, lambda fp=file_path: self.log_message(f"  No audio: {fp}"))
            
            # === SCAN NON-EMBEDDED SUBTITLES ===
            self.root.after(0, lambda: self.log_message("Scanning for non-embedded subtitle files..."))
            subtitle_results = walk_and_scan_subtitles(dir_path, progress_callback=None, ignore_dirs=ignore_dirs, log_callback=self.log_message)
            
            subtitle_scan_path = None
            if subtitle_results:
                self.root.after(0, lambda: self.log_message(f"Found {len(subtitle_results)} non-embedded subtitle files"))
                
                # Save subtitle scan results to separate JSON
                subtitle_scan_out_name = f"scan_subtitles_{dir_path.name}_{timestamp}.json"
                subtitle_scan_path = self.output_dir / subtitle_scan_out_name
                
                subtitle_payload = {
                    "scanned_path": str(dir_path),
                    "generated_utc": datetime.utcnow().isoformat() + "Z",
                    "file_count": len(subtitle_results),
                    "results": subtitle_results,
                }
                
                with open(subtitle_scan_path, "w", encoding="utf-8") as fh:
                    json.dump(subtitle_payload, fh, indent=2, ensure_ascii=False)
            else:
                self.root.after(0, lambda: self.log_message("No non-embedded subtitle files found"))
            
            # === ANALYZE PHASE ===
            self.root.after(0, lambda: self._set_status("Analyzing - please wait", 0))
            
            try:
                # Load scan data
                self.root.after(0, lambda: self.log_message("Loading scan data..."))
                scan_data = load_scan(scan_out_path)
                
                self.root.after(0, lambda: self.log_message("Running focused analyses..."))
                outputs = []
                total_analyses = 4
                
                # 1. Analyze subtitle whitelist
                self.root.after(0, lambda: self._set_status("Analyzing subtitles... (1/4)", 25))
                subtitle_whitelist_issues = analyze_subtitle_whitelist(
                    scan_data,
                    subtitle_whitelist=self.subtitle_whitelist.get()
                )
                payload = {
                    "source": str(scan_out_path),
                    "generated_utc": datetime.utcnow().isoformat() + "Z",
                    "count": len(subtitle_whitelist_issues),
                    "results": subtitle_whitelist_issues,
                }
                out = write_output("analyze_subtitle_whitelist", scan_out_path, payload)
                if len(subtitle_whitelist_issues) > 0:
                    outputs.append(("Subtitle Whitelist Issues", len(subtitle_whitelist_issues), out))
                
                # 2. Analyze allowed subtitle types
                self.root.after(0, lambda: self._set_status("Analyzing subtitle formats... (2/4)", 50))
                allowed_types_issues = analyze_allowed_subtitle_types(
                    scan_data,
                    allowed_subtitle_types=self.allowed_subtitle_types.get()
                )
                payload = {
                    "source": str(scan_out_path),
                    "generated_utc": datetime.utcnow().isoformat() + "Z",
                    "count": len(allowed_types_issues),
                    "results": allowed_types_issues,
                }
                out = write_output("analyze_allowed_subtitle_types", scan_out_path, payload)
                if len(allowed_types_issues) > 0:
                    outputs.append(("Incompatible Subtitle Formats", len(allowed_types_issues), out))
                
                # 3. Analyze default audio language
                self.root.after(0, lambda: self._set_status("Analyzing default audio... (3/4)", 75))
                default_audio_issues = analyze_default_audio(
                    scan_data,
                    default_audio_language=self.default_audio_language.get()
                )
                payload = {
                    "source": str(scan_out_path),
                    "generated_utc": datetime.utcnow().isoformat() + "Z",
                    "count": len(default_audio_issues),
                    "results": default_audio_issues,
                }
                out = write_output("analyze_default_audio", scan_out_path, payload)
                if len(default_audio_issues) > 0:
                    outputs.append(("Default Audio Issues", len(default_audio_issues), out))
                
                # 4. Analyze audio whitelist
                self.root.after(0, lambda: self._set_status("Analyzing audio streams... (4/4)", 90))
                audio_whitelist_issues = analyze_audio_whitelist(
                    scan_data,
                    audio_whitelist=self.audio_whitelist.get()
                )
                payload = {
                    "source": str(scan_out_path),
                    "generated_utc": datetime.utcnow().isoformat() + "Z",
                    "count": len(audio_whitelist_issues),
                    "results": audio_whitelist_issues,
                }
                out = write_output("analyze_audio_whitelist", scan_out_path, payload)
                if len(audio_whitelist_issues) > 0:
                    outputs.append(("Audio Whitelist Issues", len(audio_whitelist_issues), out))
                
                # 5. Analyze non-embedded subtitle files (if found)
                if subtitle_scan_path:
                    self.root.after(0, lambda: self._set_status("Analyzing non-embedded subtitles...", 92))
                    self.root.after(0, lambda: self.log_message("Analyzing non-embedded subtitle files..."))
                    
                    subtitle_scan_data = load_scan(subtitle_scan_path)
                    linked_subtitles, unlinked_subtitles = analyze_non_embedded_subtitles(
                        subtitle_scan_data, scan_data
                    )
                    
                    if linked_subtitles or unlinked_subtitles:
                        payload = {
                            "source": str(subtitle_scan_path),
                            "generated_utc": datetime.utcnow().isoformat() + "Z",
                            "linked_count": len(linked_subtitles),
                            "unlinked_count": len(unlinked_subtitles),
                            "linked_results": linked_subtitles,
                            "unlinked_results": unlinked_subtitles,
                        }
                        out = write_output("analyze_non_embedded_subtitles", subtitle_scan_path, payload)
                        if len(linked_subtitles) > 0 or len(unlinked_subtitles) > 0:
                            outputs.append((
                                f"Non-Embedded Subtitles ({len(linked_subtitles)} linked, {len(unlinked_subtitles)} unlinked)",
                                len(linked_subtitles) + len(unlinked_subtitles),
                                out
                            ))
                
                self.root.after(0, lambda: self.log_message("Analysis complete, processing results..."))
                
                # Keep original analyze call for remaining analyses (only if needed)
                if self.attempt_identify_unknown_audio.get():
                    default_audio_issues_full, subtitle_issues_full, unknown_issues, timing_issues = analyze(
                        scan_data,
                        subtitle_whitelist=self.subtitle_whitelist.get(),
                        default_audio_language=self.default_audio_language.get(),
                        audio_whitelist=self.audio_whitelist.get()
                    )
                else:
                    unknown_issues = []
                
                # Additional analysis: Check for incompatible subtitle formats (deprecated - now handled by analyze_allowed_subtitle_types)

                # Note: incompatible subtitle formats are now handled by analyze_allowed_subtitle_types
                
                # Also generate output for unknown and timing issues (if setting enabled)
                if self.attempt_identify_unknown_audio.get():
                    payload = {
                        "source": str(scan_out_path),
                        "generated_utc": datetime.utcnow().isoformat() + "Z",
                        "count": len(unknown_issues),
                        "results": unknown_issues,
                    }
                    out = write_output("analyze_unknown", scan_out_path, payload)
                    if len(unknown_issues) > 0:
                        outputs.append(("Unknown Language Issues", len(unknown_issues), out))
                
                self.root.after(0, lambda: self._scan_and_analyze_complete(results, outputs, str(scan_out_path)))
                
            except Exception as analyze_err:
                import traceback
                error_traceback = traceback.format_exc()
                self.root.after(0, lambda err=analyze_err, tb=error_traceback: (
                    self.log_message(f"Analysis error: {err}"),
                    self.log_message(f"Traceback: {tb}")
                ))
                self.root.after(0, lambda: self._scan_and_analyze_complete(results, None, str(scan_out_path)))
                
        except Exception as e:
            error_msg = f"Scan and analyze failed: {e}"
            self.root.after(0, lambda: self._scan_and_analyze_error(error_msg))
    
    def _scan_and_analyze_complete(self, scan_results, analysis_outputs, scan_file):
        """Handle scan and analyze completion."""
        if analysis_outputs:
            self.log_message(f"✓ Scan and Analysis Complete!")
            self.log_message(f"  Total Files Found: {len(scan_results)}")
            self.log_message(f"  Issue Types Found: {len(analysis_outputs)}")
            for issue_type, count, out_path in analysis_outputs:
                self.log_message(f"    - {issue_type}: {count} files")
        else:
            self.log_message(f"✓ Scan Complete - No issues found!")
            self.log_message(f"  Total Files Found: {len(scan_results)}")
        
        self._set_status(f"Ready - {len(scan_results)} files analyzed", 100)
        self.set_buttons_enabled(True)
        self.update_cleanup_buttons()
    
    def _scan_and_analyze_error(self, error_msg):
        """Handle scan and analyze error."""
        self.log_message(f"ERROR: {error_msg}")
        self._set_status("Scan and Analyze failed", 0)
        self.set_buttons_enabled(True)
        self.show_dark_error("Scan & Analyze Error", error_msg)
    
    def analyze_results(self):
        """Analyze the scan results."""
        # Try to use last scan file, or find latest
        scan_file = self.last_scan_file
        if not scan_file or not Path(scan_file).exists():
            scan_file = find_latest_scan_file(self.output_dir)
        
        if not scan_file:
            messagebox.showwarning("No Scan File", 
                "No scan results found. Please run a scan first.")
            return
        
        # Disable buttons during analysis
        self.set_buttons_enabled(False)
        self.log_message(f"Starting analysis of: {Path(scan_file).name}")
        self.status_var.set("Analyzing... Please wait")
        
        # Run analysis in separate thread
        analyze_thread = threading.Thread(
            target=self._run_analyze, 
            args=(Path(scan_file),), 
            daemon=True
        )
        analyze_thread.start()
    
    def _run_analyze(self, scan_file):
        """Run the analysis operation in a background thread."""
        try:
            self.root.after(0, lambda: self._set_status("Analyzing - please wait", 0))
            self.root.after(0, lambda: self.log_message("Loading scan data..."))
            scan_data = load_scan(scan_file)
            
            self.root.after(0, lambda: self.log_message("Analyzing for issues..."))
            self.root.after(0, lambda: self._set_status("Analyzing... (1/5)", 20))
            
            # Run analysis with configuration-based rules
            default_audio_issues, subtitle_issues, unknown_issues, timing_issues = analyze(
                scan_data, 
                ignore_patterns=None, 
                require_default_english=False,
                subtitle_whitelist=self.subtitle_whitelist.get(),
                default_audio_language=self.default_audio_language.get(),
                audio_whitelist=self.audio_whitelist.get()
            )
            
            # Additional analysis: Check for incompatible subtitle formats
            self.root.after(0, lambda: self._set_status("Analyzing... (2/5)", 40))
            incompatible_sub_issues = self._analyze_subtitle_formats(scan_data)
            
            # Save results - always create files even if empty, so Fix button can detect no issues
            outputs = []
            
            # Always create output files, even with 0 results
            self.root.after(0, lambda: self._set_status("Saving results... (3/5)", 60))
            payload = {
                "source": str(scan_file),
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "count": len(default_audio_issues),
                "results": default_audio_issues,
            }
            out = write_output("analyze_default_audio", scan_file, payload)
            if len(default_audio_issues) > 0:
                outputs.append(("Default Audio Issues", len(default_audio_issues), out))
            
            self.root.after(0, lambda: self._set_status("Saving results... (4/5)", 70))
            payload = {
                "source": str(scan_file),
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "count": len(subtitle_issues),
                "results": subtitle_issues,
            }
            out = write_output("analyze_subtitle", scan_file, payload)
            if len(subtitle_issues) > 0:
                outputs.append(("Subtitle Issues", len(subtitle_issues), out))
            
            payload = {
                "source": str(scan_file),
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "count": len(unknown_issues),
                "results": unknown_issues,
            }
            out = write_output("analyze_unknown", scan_file, payload)
            if len(unknown_issues) > 0:
                outputs.append(("Unknown Language Issues", len(unknown_issues), out))
            
            payload = {
                "source": str(scan_file),
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "count": len(incompatible_sub_issues),
                "results": incompatible_sub_issues,
            }
            out = write_output("analyze_incompatible_subtitles", scan_file, payload)
            if len(incompatible_sub_issues) > 0:
                outputs.append(("Incompatible Subtitle Formats", len(incompatible_sub_issues), out))
            
            payload = {
                "source": str(scan_file),
                "generated_utc": datetime.utcnow().isoformat() + "Z",
                "count": len(timing_issues),
                "results": timing_issues,
            }
            out = write_output("analyze_timing", scan_file, payload)
            if len(timing_issues) > 0:
                outputs.append(("Subtitle Timing Issues", len(timing_issues), out))
            
            # Update UI in main thread
            self.root.after(0, lambda: self._set_status("Finalizing results... (5/5)", 95))
            self.root.after(0, lambda: self._analyze_complete(outputs))
            
        except Exception as e:
            error_msg = f"Analysis failed: {e}"
            self.root.after(0, lambda: self._analyze_error(error_msg))
    
    def _analyze_complete(self, outputs):
        """Handle analysis completion (called in main thread)."""
        if outputs:
            self.log_message("Analysis complete! Issues found:")
            for issue_type, count, out_path in outputs:
                self.log_message(f"  - {issue_type}: {count} files")
                self.log_message(f"    Saved to: {Path(out_path).name}")
            
            self._set_status(f"Analysis complete - {len(outputs)} issue types found", 100)
        else:
            self.log_message("Analysis complete! No issues found.")
            self._set_status("Analysis complete - No issues found", 100)
        
        self.set_buttons_enabled(True)
    
    def _analyze_error(self, error_msg):
        """Handle analysis error (called in main thread)."""
        self.log_message(f"ERROR: {error_msg}")
        self.status_var.set("Analysis failed")
        self.set_buttons_enabled(True)
        messagebox.showerror("Analysis Error", error_msg)
    
    def _analyze_subtitle_formats(self, scan_data):
        """Analyze subtitle formats based on allowed_subtitle_types setting."""
        # Map codec names to format types
        codec_to_format = {
            'subrip': 'SRT',
            'ass': 'ASS',
            'ssa': 'SSA',
            'webvtt': 'VTT',
            'microdvd': 'SUB',
            'subviewer': 'SBV',
            'json': 'JSON',
            'hdmv_pgs_subtitle': 'PGS',
            'dvd_subtitle': 'DVD',
            'dvdsub': 'DVD',
        }
        
        # Parse allowed subtitle types from config (case-insensitive)
        allowed_types_str = self.allowed_subtitle_types.get()
        allowed_types = {t.strip().upper() for t in allowed_types_str.split(",")}
        
        # Build incompatible codecs list - codecs NOT in allowed types
        incompatible_codecs = {}
        for codec, fmt_type in codec_to_format.items():
            if fmt_type not in allowed_types:
                incompatible_codecs[codec] = fmt_type
        
        results = scan_data.get("results") or []
        issues = []
        
        for item in results:
            subtitle_streams = item.get("subtitle_streams") or []
            incompatible_subs = []
            
            for sub in subtitle_streams:
                codec = sub.get("codec", "").lower()
                if codec in incompatible_codecs:
                    incompatible_subs.append({
                        "index": sub.get("index"),
                        "codec": codec,
                        "codec_name": incompatible_codecs[codec],
                        "language": sub.get("language"),
                    })
            
            if incompatible_subs:
                e = dict(item)
                e["analyze_issue"] = "incompatible_subtitle_format"
                e["incompatible_subtitles"] = incompatible_subs
                issues.append(e)
        
        return issues
    
    def _analyze_error(self, error_msg):
        """Handle analysis error (called in main thread)."""
        self.log_message(f"ERROR: {error_msg}")
        self.status_var.set("Analysis failed")
        self.set_buttons_enabled(True)
        messagebox.showerror("Analysis Error", error_msg)
    
    def fix_issues(self):
        """Fix issues found in the analysis."""
        # Check if any analyze files exist with new naming convention
        subtitle_whitelist_file = self.find_latest_analyze("subtitle_whitelist")
        allowed_types_file = self.find_latest_analyze("allowed_subtitle_types")
        default_audio_file = self.find_latest_analyze("default_audio")
        audio_whitelist_file = self.find_latest_analyze("audio_whitelist")
        unknown_file = self.find_latest_analyze("unknown")
        non_embedded_subtitles_file = self.find_latest_analyze("non_embedded_subtitles")
        
        # Check if any of these files have actual issues
        has_issues = False
        if subtitle_whitelist_file and self._file_has_results(subtitle_whitelist_file):
            has_issues = True
        if allowed_types_file and self._file_has_results(allowed_types_file):
            has_issues = True
        if default_audio_file and self._file_has_results(default_audio_file):
            has_issues = True
        if audio_whitelist_file and self._file_has_results(audio_whitelist_file):
            has_issues = True
        if unknown_file and self._file_has_results(unknown_file):
            has_issues = True
        if non_embedded_subtitles_file and self._file_has_results_non_embedded(non_embedded_subtitles_file):
            has_issues = True
        
        if not has_issues:
            # No issues found - nothing to fix
            messagebox.showinfo(
                "No Issues Found",
                "Analysis found no issues that need fixing.\n\n"
                "Your video files are correctly configured!"
            )
            return
        
        # Check if analysis files are stale (older than latest scan)
        scan_file = self.last_scan_file or find_latest_scan_file(self.output_dir)
        if scan_file and Path(scan_file).exists():
            scan_mtime = Path(scan_file).stat().st_mtime
            
            # Check if any analyze files are older than the scan
            analyze_files = [f for f in [subtitle_whitelist_file, allowed_types_file, default_audio_file, audio_whitelist_file, unknown_file] if f]
            stale_files = []
            for af in analyze_files:
                if Path(af).stat().st_mtime < scan_mtime:
                    stale_files.append(af)
            
            if stale_files:
                response = messagebox.askyesno(
                    "Stale Analysis Detected",
                    f"Your analysis files are older than the latest scan.\n\n"
                    f"This usually happens after fixing issues and re-scanning.\n"
                    f"The analysis may contain outdated information.\n\n"
                    f"Would you like to re-analyze first to ensure accuracy?"
                )
                if response:
                    self.analyze_results()
                    return
        
        # Show confirmation dialog with available fix options
        fix_options = {}
        if subtitle_whitelist_file and self._file_has_results(subtitle_whitelist_file):
            fix_options['subtitle_whitelist'] = {
                'label': 'Remove non-whitelisted subtitles',
                'file': subtitle_whitelist_file
            }
        if allowed_types_file and self._file_has_results(allowed_types_file):
            fix_options['allowed_types'] = {
                'label': 'Convert incompatible subtitle formats',
                'file': allowed_types_file
            }
        if default_audio_file and self._file_has_results(default_audio_file):
            fix_options['default_audio'] = {
                'label': 'Set preferred audio as default',
                'file': default_audio_file
            }
        if audio_whitelist_file and self._file_has_results(audio_whitelist_file):
            fix_options['audio_whitelist'] = {
                'label': 'Remove non-whitelisted audio streams',
                'file': audio_whitelist_file
            }
        if unknown_file and self._file_has_results(unknown_file):
            fix_options['unknown'] = {
                'label': 'Identify unknown languages',
                'file': unknown_file
            }
        if non_embedded_subtitles_file and self._file_has_results_non_embedded(non_embedded_subtitles_file):
            fix_options['non_embedded_subtitles'] = {
                'label': 'Process non-embedded subtitle files',
                'file': non_embedded_subtitles_file
            }
        
        # Show custom dialog with checkboxes
        selected_fixes = self._show_fix_selection_dialog(fix_options)
        if not selected_fixes:
            return
        
        # Disable buttons during fix
        self.set_buttons_enabled(False)
        self.log_message("Starting fix process...")
        self.status_var.set("Fixing issues... Please wait")
        
        # Run fixes in separate thread
        fix_thread = threading.Thread(
            target=self._run_fixes,
            args=(selected_fixes,),
            daemon=True
        )
        fix_thread.start()
    
    def _show_fix_selection_dialog(self, fix_options):
        """Show a custom dialog with checkboxes for selecting which fixes to apply."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Fixes to Apply")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Apply dark theme to dialog
        dialog.configure(bg='#2b2b2b')
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Result storage
        result = {}
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title - combined message
        title_label = ttk.Label(
            main_frame,
            text="Select which fixes you want to apply:",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Checkboxes frame
        check_frame = ttk.Frame(main_frame)
        check_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create checkboxes for each fix option
        check_vars = {}
        for key, option_data in fix_options.items():
            var = tk.BooleanVar(value=True)  # All checked by default
            check_vars[key] = var
            
            cb = ttk.Checkbutton(
                check_frame,
                text=option_data['label'],
                variable=var
            )
            cb.pack(anchor=tk.W, pady=5, padx=10)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(15, 0))
        
        def on_apply():
            # Collect selected fixes
            for key, var in check_vars.items():
                if var.get():
                    result[key] = fix_options[key]['file']
            dialog.destroy()
        
        def on_cancel():
            result.clear()
            dialog.destroy()
        
        apply_btn = ttk.Button(button_frame, text="Apply Selected", command=on_apply)
        apply_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return result
    
    def _run_fixes(self, selected_fixes):
        """Run the fix operations in a background thread."""
        try:
            total_fixed = 0
            total_failed = 0
            
            # Fix subtitle whitelist issues (remove non-whitelisted subtitles)
            if 'subtitle_whitelist' in selected_fixes:
                self.root.after(0, lambda: self.log_message("Processing subtitle whitelist fixes..."))
                data = load_json(selected_fixes['subtitle_whitelist'])
                results = data.get("results") or []
                
                for idx, item in enumerate(results, 1):
                    path = item.get("path")
                    pct = int(((idx - 1) / len(results)) * 100) if results else 0
                    self.root.after(0, lambda i=idx, t=len(results), p=pct: self._set_status(f"Fixing issues... ({i}/{t})", p))
                    try:
                        result = attempt_remove_non_whitelisted_subs(item, subtitle_whitelist=self.subtitle_whitelist.get(), keep_backup=self.keep_original_files.get())
                        if result.get("success"):
                            self.root.after(0, lambda p=path: self.log_message(f"  Fixed S: {Path(p).name}"))
                            removed = result.get("removed", [])
                            remaining = result.get("remaining", [])
                            if removed:
                                self.root.after(0, lambda r=removed: self.log_message(f"     Removed  [{len(r)}]: {', '.join(r)}"))
                            if remaining:
                                self.root.after(0, lambda r=remaining: self.log_message(f"     Remaining [{len(r)}]: {', '.join(r)}"))
                            total_fixed += 1
                        else:
                            self.root.after(0, lambda p=path: self.log_message(f"  Skipped: {Path(p).name}"))
                    except Exception as e:
                        self.root.after(0, lambda p=path, err=e: self.log_message(f"  Failed: {Path(p).name} - {err}"))
                        total_failed += 1
            
            # Fix allowed subtitle types (convert incompatible formats)
            if 'allowed_types' in selected_fixes:
                self.root.after(0, lambda: self.log_message("Processing subtitle format conversions..."))
                data = load_json(selected_fixes['allowed_types'])
                results = data.get("results") or []
                
                for idx, item in enumerate(results, 1):
                    path = item.get("path")
                    pct = int(((idx - 1) / len(results)) * 100) if results else 0
                    self.root.after(0, lambda i=idx, t=len(results), p=pct: self._set_status(f"Fixing issues... ({i}/{t})", p))
                    try:
                        changed = attempt_convert_subtitle_formats(item, keep_backup=self.keep_original_files.get())
                        if changed:
                            self.root.after(0, lambda p=path: self.log_message(f"  Fixed S: {Path(p).name}"))
                            total_fixed += 1
                        else:
                            self.root.after(0, lambda p=path: self.log_message(f"  Skipped (cannot convert or no changes): {Path(p).name}"))
                    except Exception as e:
                        self.root.after(0, lambda p=path, err=e: self.log_message(f"  Failed: {Path(p).name} - {err}"))
                        total_failed += 1
            
            # Fix default audio issues
            if 'default_audio' in selected_fixes:
                self.root.after(0, lambda: self.log_message("Processing default audio fixes..."))
                data = load_json(selected_fixes['default_audio'])
                results = data.get("results") or []
                
                for idx, item in enumerate(results, 1):
                    path = item.get("path")
                    pct = int(((idx - 1) / len(results)) * 100) if results else 0
                    self.root.after(0, lambda i=idx, t=len(results), p=pct: self._set_status(f"Fixing issues... ({i}/{t})", p))
                    try:
                        result = attempt_set_default_audio(item, default_audio_language=self.default_audio_language.get(), keep_backup=self.keep_original_files.get())
                        if result.get("success"):
                            self.root.after(0, lambda p=path: self.log_message(f"  Fixed A: {Path(p).name}"))
                            previous = result.get("previous", "unknown")
                            new = result.get("new", "unknown")
                            self.root.after(0, lambda p=previous, n=new: self.log_message(f"     Changed default audio: {p} → {n}"))
                            total_fixed += 1
                        else:
                            self.root.after(0, lambda p=path: self.log_message(f"  Skipped: {Path(p).name}"))
                    except Exception as e:
                        self.root.after(0, lambda p=path, err=e: self.log_message(f"  Failed: {Path(p).name} - {err}"))
                        total_failed += 1
            
            # Fix audio whitelist issues (remove non-whitelisted audio streams)
            if 'audio_whitelist' in selected_fixes:
                self.root.after(0, lambda: self.log_message("Processing audio whitelist fixes..."))
                data = load_json(selected_fixes['audio_whitelist'])
                results = data.get("results") or []
                
                for idx, item in enumerate(results, 1):
                    path = item.get("path")
                    pct = int(((idx - 1) / len(results)) * 100) if results else 0
                    self.root.after(0, lambda i=idx, t=len(results), p=pct: self._set_status(f"Fixing issues... ({i}/{t})", p))
                    try:
                        result = attempt_remove_non_whitelisted_audio(item, audio_whitelist=self.audio_whitelist.get(), keep_backup=self.keep_original_files.get())
                        if result.get("success"):
                            self.root.after(0, lambda p=path: self.log_message(f"  Fixed A: {Path(p).name}"))
                            removed = result.get("removed", [])
                            remaining = result.get("remaining", [])
                            if removed:
                                self.root.after(0, lambda r=removed: self.log_message(f"     Removed  [{len(r)}]: {', '.join(r)}"))
                            if remaining:
                                self.root.after(0, lambda r=remaining: self.log_message(f"     Remaining [{len(r)}]: {', '.join(r)}"))
                            total_fixed += 1
                        else:
                            self.root.after(0, lambda p=path: self.log_message(f"  Skipped: {Path(p).name}"))
                    except Exception as e:
                        self.root.after(0, lambda p=path, err=e: self.log_message(f"  Failed: {Path(p).name} - {err}"))
                        total_failed += 1
            
            # Fix unknown language issues (with simple heuristic)
            if 'unknown' in selected_fixes:
                self.root.after(0, lambda: self.log_message("Processing unknown language fixes..."))
                data = load_json(selected_fixes['unknown'])
                results = data.get("results") or []
                
                for idx, item in enumerate(results, 1):
                    path = item.get("path")
                    pct = int(((idx - 1) / len(results)) * 100) if results else 0
                    self.root.after(0, lambda i=idx, t=len(results), p=pct: self._set_status(f"Fixing issues... ({i}/{t})", p))
                    try:
                        self.root.after(0, lambda p=path: self.log_message(f"  Checking: {Path(p).name}"))
                        attempt_identify_unknown(item)
                        total_fixed += 1
                    except Exception as e:
                        self.root.after(0, lambda p=path, err=e: self.log_message(f"  Failed: {Path(p).name} - {err}"))
                        total_failed += 1
            
            # Fix non-embedded subtitles (merge into video files)
            if 'non_embedded_subtitles' in selected_fixes:
                self.root.after(0, lambda: self.log_message("Processing non-embedded subtitle files..."))
                data = load_json(selected_fixes['non_embedded_subtitles'])
                linked_results = data.get("linked_results") or []
                unlinked_results = data.get("unlinked_results") or []
                
                # Only process linked subtitles
                for idx, item in enumerate(linked_results, 1):
                    subtitle_path = item.get("path")
                    subtitle_name = Path(subtitle_path).name
                    linked_video = item.get("linked_video")
                    
                    pct = int(((idx - 1) / len(linked_results)) * 100) if linked_results else 0
                    self.root.after(0, lambda i=idx, t=len(linked_results), p=pct: self._set_status(f"Processing subtitles... ({i}/{t})", p))
                    
                    if not linked_video:
                        continue
                    
                    self.root.after(0, lambda s=subtitle_name, v=Path(linked_video).name: 
                        self.log_message(f"  Found: {s} -> linked to {v}"))
                    
                    # Validate subtitle filename pattern: {file_name}.{language}.{extension}
                    subtitle_path_obj = Path(subtitle_path)
                    subtitle_stem = subtitle_path_obj.stem  # filename without extension
                    subtitle_ext = subtitle_path_obj.suffix.lower()
                    
                    # Extract potential language from subtitle filename
                    # Pattern: base_name.language.ext
                    parts = subtitle_stem.split('.')
                    if len(parts) < 2:
                        self.root.after(0, lambda s=subtitle_name: 
                            self.log_message(f"     Skipped: Invalid naming pattern (no language detected)"))
                        continue
                    
                    potential_language = parts[-1]  # Last part before extension
                    
                    # Validate against language list (case-insensitive)
                    language_map = {lang.lower(): lang for lang in self.language_list}
                    if potential_language.lower() not in language_map:
                        self.root.after(0, lambda s=subtitle_name, lang=potential_language: 
                            self.log_message(f"     Skipped: Invalid language '{lang}' (not in whitelist)"))
                        continue
                    
                    # Get properly capitalized language name
                    language = language_map[potential_language.lower()]
                    
                    try:
                        # Merge subtitle into video file
                        video_path = Path(linked_video)
                        
                        # Create backup if enabled
                        if self.keep_original_files.get():
                            backup_file_before_fix(str(video_path))
                            self.root.after(0, lambda: self.log_message(f"     Created backup"))
                        
                        # Create temporary output file
                        temp_output = video_path.parent / (video_path.stem + ".tmp" + video_path.suffix)
                        
                        # Use ffmpeg to merge subtitle with language metadata
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", str(video_path),
                            "-i", str(subtitle_path),
                            "-c", "copy",
                            "-c:s", "copy",
                            "-metadata:s:s:0", f"language={language.lower()[:3]}",
                            "-metadata:s:s:0", f"title={language}",
                            str(temp_output)
                        ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                        
                        if result.returncode == 0:
                            # Replace original with merged file
                            shutil.move(str(temp_output), str(video_path))
                            
                            # Remove external subtitle file
                            Path(subtitle_path).unlink()
                            
                            self.root.after(0, lambda lang=language: 
                                self.log_message(f"     ✓ Merged and removed external subtitle (language: {lang})"))
                            total_fixed += 1
                        else:
                            # Clean up temp file if it exists
                            if temp_output.exists():
                                temp_output.unlink()
                            
                            error = result.stderr[:200] if result.stderr else "Unknown error"
                            self.root.after(0, lambda e=error: 
                                self.log_message(f"     Failed: ffmpeg error - {e}"))
                            total_failed += 1
                            
                    except subprocess.TimeoutExpired:
                        self.root.after(0, lambda: 
                            self.log_message(f"     Failed: ffmpeg timeout (>120s)"))
                        total_failed += 1
                    except Exception as e:
                        self.root.after(0, lambda err=str(e): 
                            self.log_message(f"     Failed: {err}"))
                        total_failed += 1
                
                # Log unlinked subtitles
                if unlinked_results:
                    self.root.after(0, lambda c=len(unlinked_results): 
                        self.log_message(f"  Skipped {c} unlinked subtitle file(s)"))
            
            # Update UI in main thread
            self.root.after(0, lambda: self._fix_complete(total_fixed, total_failed))
            
        except Exception as e:
            error_msg = f"Fix process failed: {e}"
            self.root.after(0, lambda: self._fix_error(error_msg))
    
    def _fix_complete(self, total_fixed, total_failed):
        """Handle fix completion (called in main thread)."""
        self.log_message(f"Fix process complete!")
        self.log_message(f"  Successfully fixed: {total_fixed} files")
        if total_failed > 0:
            self.log_message(f"  Failed: {total_failed} files")
        
        self._set_status(f"Fixes complete - {total_fixed} successful, {total_failed} failed", 100)
        self.set_buttons_enabled(True)
        self.update_cleanup_buttons()
    
    def _fix_error(self, error_msg):
        """Handle fix error (called in main thread)."""
        self.log_message(f"ERROR: {error_msg}")
        self._set_status("Fix process failed", 0)
        self.set_buttons_enabled(True)
        messagebox.showerror("Fix Error", error_msg)


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = VideoAudioGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

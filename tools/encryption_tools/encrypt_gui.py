#!/usr/bin/env python3
"""
GUI wrapper for the secure AES-256 encryption tool
Provides easy-to-use interface for file encryption/decryption
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import base64
import threading
from pathlib import Path
from encrypt import SecureEncryptor, generate_master_key, derive_master_key_from_password


class EncryptionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure AES-256 File Encryption")
        self.root.geometry("700x600")
        
        self.master_key = None
        self.encryptor = None
        
        # Bulk encryption variables
        self.bulk_folder_path = None
        self.bulk_file_vars = {}  # Dictionary to store checkbox variables
        self.bulk_files = []  # List of files/folders in the selected directory
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Secure AES-256 File Encryption", 
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(1, weight=1)
        
        # Create tabs
        self.create_single_file_tab()
        self.create_bulk_encrypt_tab()
        self.create_bulk_decrypt_tab()
        
        # Status bar at bottom
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def create_single_file_tab(self):
        """Create the single file encryption/decryption tab"""
        single_frame = ttk.Frame(self.notebook)
        self.notebook.add(single_frame, text="Single File")
        
        # Master Key Section
        key_frame = ttk.LabelFrame(single_frame, text="Master Key Management", padding="10")
        key_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        key_frame.columnconfigure(1, weight=1)
        
        ttk.Label(key_frame, text="Master Key Status:").grid(row=0, column=0, sticky=tk.W)
        self.key_status_label = ttk.Label(key_frame, text="Not Set", foreground="red")
        self.key_status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Button(key_frame, text="Generate New Key", 
                  command=self.generate_key).grid(row=1, column=0, pady=5)
        ttk.Button(key_frame, text="Use Password", 
                  command=self.use_password).grid(row=1, column=1, pady=5, padx=(10, 0))
        ttk.Button(key_frame, text="Enter Key (Hex)", 
                  command=self.enter_key).grid(row=1, column=2, pady=5, padx=(10, 0))
        
        # File Selection Section
        self.file_frame = ttk.LabelFrame(single_frame, text="File Selection", padding="10")
        self.file_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        self.file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(self.file_frame, text="Input File/Folder:").grid(row=0, column=0, sticky=tk.W)
        self.input_entry = ttk.Entry(self.file_frame, width=50)
        self.input_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        ttk.Button(self.file_frame, text="Browse", 
                  command=self.browse_input).grid(row=0, column=2, padx=(10, 0))
        
        ttk.Label(self.file_frame, text="Output File/Folder:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.output_entry = ttk.Entry(self.file_frame, width=50)
        self.output_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))
        ttk.Button(self.file_frame, text="Browse", 
                  command=self.browse_output).grid(row=1, column=2, padx=(10, 0), pady=(10, 0))
        
        # Action Section
        action_frame = ttk.LabelFrame(single_frame, text="Action", padding="10")
        action_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.action_var = tk.StringVar(value="encrypt")
        ttk.Radiobutton(action_frame, text="Encrypt", variable=self.action_var, 
                       value="encrypt", command=self.on_action_change).grid(row=0, column=0, padx=(0, 20))
        ttk.Radiobutton(action_frame, text="Decrypt", variable=self.action_var, 
                       value="decrypt", command=self.on_action_change).grid(row=0, column=1)
        
        # GUID Filename Option (only for encryption)
        self.use_guid_var = tk.BooleanVar(value=False)
        self.guid_checkbox = ttk.Checkbutton(action_frame, text="Use Random GUID Filename", 
                                        variable=self.use_guid_var,
                                        command=self.on_guid_checkbox_change)
        self.guid_checkbox.grid(row=1, column=0, columnspan=2, pady=(5, 10), sticky=tk.W)
        
        ttk.Button(action_frame, text="Execute", 
                  command=self.execute_action).grid(row=2, column=0, columnspan=2, pady=(10, 0))
        
        # Log Section
        log_frame = ttk.LabelFrame(single_frame, text="Activity Log", padding="10")
        log_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        single_frame.rowconfigure(3, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=70)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure single frame grid weights
        single_frame.columnconfigure(0, weight=1)
    
    def create_bulk_encrypt_tab(self):
        """Create the bulk encryption tab"""
        bulk_frame = ttk.Frame(self.notebook)
        self.notebook.add(bulk_frame, text="Bulk Encrypt")
        
        # Folder Selection Section
        folder_frame = ttk.LabelFrame(bulk_frame, text="Folder Selection", padding="10")
        folder_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        folder_frame.columnconfigure(1, weight=1)
        
        ttk.Label(folder_frame, text="Select Folder:").grid(row=0, column=0, sticky=tk.W)
        self.bulk_folder_entry = ttk.Entry(folder_frame, width=50)
        self.bulk_folder_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        ttk.Button(folder_frame, text="Browse", 
                  command=self.browse_bulk_folder).grid(row=0, column=2, padx=(10, 0))
        
        # Files List Section
        files_frame = ttk.LabelFrame(bulk_frame, text="Files and Folders", padding="10")
        files_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)
        bulk_frame.rowconfigure(1, weight=1)
        
        # Create scrollable frame for file list
        self.bulk_canvas = tk.Canvas(files_frame)
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.bulk_canvas.yview)
        self.bulk_scrollable_frame = ttk.Frame(self.bulk_canvas)
        
        self.bulk_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.bulk_canvas.configure(scrollregion=self.bulk_canvas.bbox("all"))
        )
        
        self.bulk_canvas.create_window((0, 0), window=self.bulk_scrollable_frame, anchor="nw")
        self.bulk_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.bulk_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Control Section
        control_frame = ttk.LabelFrame(bulk_frame, text="Controls", padding="10")
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.bulk_encrypt_button = ttk.Button(control_frame, text="Encrypt Selected", 
                                             command=self.bulk_encrypt_selected, state="disabled")
        self.bulk_encrypt_button.grid(row=0, column=0, padx=(0, 10))
        
        ttk.Button(control_frame, text="Select All", 
                  command=self.bulk_select_all).grid(row=0, column=1, padx=(0, 10))
        ttk.Button(control_frame, text="Deselect All", 
                  command=self.bulk_deselect_all).grid(row=0, column=2, padx=(0, 10))
        
        # Progress Section
        progress_frame = ttk.LabelFrame(bulk_frame, text="Progress", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.bulk_progress_var = tk.StringVar(value="No files selected")
        progress_label = ttk.Label(progress_frame, textvariable=self.bulk_progress_var)
        progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.bulk_progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.bulk_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Configure bulk frame grid weights
        bulk_frame.columnconfigure(0, weight=1)
    
    def create_bulk_decrypt_tab(self):
        """Create the bulk decryption tab"""
        decrypt_frame = ttk.Frame(self.notebook)
        self.notebook.add(decrypt_frame, text="Bulk Decrypt")
        
        # Manifest Selection Section
        manifest_frame = ttk.LabelFrame(decrypt_frame, text="Manifest Selection", padding="10")
        manifest_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        manifest_frame.columnconfigure(1, weight=1)
        
        ttk.Label(manifest_frame, text="Select enc.manifest file:").grid(row=0, column=0, sticky=tk.W)
        self.manifest_entry = ttk.Entry(manifest_frame, width=50)
        self.manifest_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        ttk.Button(manifest_frame, text="Browse", 
                  command=self.browse_manifest).grid(row=0, column=2, padx=(10, 0))
        
        # Output Section
        output_frame = ttk.LabelFrame(decrypt_frame, text="Output Folder", padding="10")
        output_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        output_frame.columnconfigure(1, weight=1)
        
        ttk.Label(output_frame, text="Output to:").grid(row=0, column=0, sticky=tk.W)
        self.decrypt_output_entry = ttk.Entry(output_frame, width=50)
        self.decrypt_output_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        ttk.Button(output_frame, text="Browse", 
                  command=self.browse_decrypt_output).grid(row=0, column=2, padx=(10, 0))
        
        # Control Section
        control_frame = ttk.LabelFrame(decrypt_frame, text="Controls", padding="10")
        control_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.bulk_decrypt_button = ttk.Button(control_frame, text="Decrypt All", 
                                             command=self.bulk_decrypt_all, state="disabled")
        self.bulk_decrypt_button.grid(row=0, column=0, padx=(0, 10))
        
        # Progress Section
        progress_frame = ttk.LabelFrame(decrypt_frame, text="Progress", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.decrypt_progress_var = tk.StringVar(value="No manifest selected")
        progress_label = ttk.Label(progress_frame, textvariable=self.decrypt_progress_var)
        progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.decrypt_progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.decrypt_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Log Section
        log_frame = ttk.LabelFrame(decrypt_frame, text="Decryption Log", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        decrypt_frame.rowconfigure(4, weight=1)
        
        self.decrypt_log_text = scrolledtext.ScrolledText(log_frame, height=10, width=70)
        self.decrypt_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure decrypt frame grid weights
        decrypt_frame.columnconfigure(0, weight=1)
    
    # Bulk encryption methods
    def browse_bulk_folder(self):
        """Browse for folder to encrypt"""
        folder_path = filedialog.askdirectory(title="Select Folder to Encrypt")
        if folder_path:
            self.bulk_folder_entry.delete(0, tk.END)
            self.bulk_folder_entry.insert(0, folder_path)
            self.load_bulk_files(folder_path)
    
    def load_bulk_files(self, folder_path):
        """Load files and folders from selected directory"""
        self.bulk_folder_path = Path(folder_path)
        self.bulk_files = []
        self.bulk_file_vars = {}
        
        # Clear existing widgets
        for widget in self.bulk_scrollable_frame.winfo_children():
            widget.destroy()
        
        # Get all files and folders in the directory (non-recursive)
        try:
            items = []
            for item in self.bulk_folder_path.iterdir():
                items.append(item)
            
            # Sort alphanumerically
            items.sort(key=lambda x: x.name.lower())
            
            # Create checkbox for each item
            for i, item in enumerate(items):
                var = tk.BooleanVar()
                self.bulk_file_vars[item.name] = var
                
                # Create frame for checkbox and label
                item_frame = ttk.Frame(self.bulk_scrollable_frame)
                item_frame.grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
                
                # Checkbox
                checkbox = ttk.Checkbutton(item_frame, variable=var, 
                                         command=self.update_encrypt_button)
                checkbox.grid(row=0, column=0, padx=(0, 5))
                
                # Icon and label
                icon = "📁" if item.is_dir() else "📄"
                label = ttk.Label(item_frame, text=f"{icon} {item.name}")
                label.grid(row=0, column=1, sticky=tk.W)
                
                self.bulk_files.append(item)
            
            self.bulk_progress_var.set(f"Found {len(self.bulk_files)} items")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load folder: {e}")
    
    def update_encrypt_button(self):
        """Update encrypt button state based on selections"""
        selected_count = sum(1 for var in self.bulk_file_vars.values() if var.get())
        if selected_count > 0:
            self.bulk_encrypt_button.config(state="normal")
            self.bulk_progress_var.set(f"{selected_count} of {len(self.bulk_files)} items selected")
        else:
            self.bulk_encrypt_button.config(state="disabled")
            self.bulk_progress_var.set(f"No files selected ({len(self.bulk_files)} items available)")
    
    def bulk_select_all(self):
        """Select all files and folders"""
        for var in self.bulk_file_vars.values():
            var.set(True)
        self.update_encrypt_button()
    
    def bulk_deselect_all(self):
        """Deselect all files and folders"""
        for var in self.bulk_file_vars.values():
            var.set(False)
        self.update_encrypt_button()
    
    def bulk_encrypt_selected(self):
        """Encrypt selected files and folders"""
        if not self.encryptor:
            messagebox.showerror("Error", "Please set a master key first")
            return
        
        # Get selected items
        selected_items = []
        for item in self.bulk_files:
            if self.bulk_file_vars[item.name].get():
                selected_items.append(item)
        
        if not selected_items:
            messagebox.showerror("Error", "No items selected")
            return
        
        # Create output folder
        output_folder = self.bulk_folder_path.parent / f"{self.bulk_folder_path.name}_enc"
        output_folder.mkdir(exist_ok=True)
        
        # Start encryption in background thread
        thread = threading.Thread(target=self._bulk_encrypt_worker, 
                                args=(selected_items, output_folder))
        thread.daemon = True
        thread.start()
    
    def _bulk_encrypt_worker(self, items, output_folder):
        """Worker thread for bulk encryption"""
        try:
            # Generate manifest master key
            manifest_master_key = generate_master_key()
            manifest_master_key_b64 = base64.b64encode(manifest_master_key.hex().encode()).decode()
            
            # Create manifest encryptor
            manifest_encryptor = SecureEncryptor(manifest_master_key)
            
            # Initialize manifest file
            manifest_path = output_folder / "enc.manifest"
            with open(manifest_path, 'w') as f:
                f.write(manifest_master_key_b64 + '\n')
            
            total_items = len(items)
            for i, item in enumerate(items):
                # Update progress
                progress = (i / total_items) * 100
                self.bulk_progress_bar['value'] = progress
                self.bulk_progress_var.set(f"Encrypting {item.name} ({i+1}/{total_items})")
                
                try:
                    # Generate individual master key for this item
                    individual_key = generate_master_key()
                    individual_key_b64 = base64.b64encode(individual_key.hex().encode()).decode()
                    
                    # Encrypt original filename with manifest master key
                    original_name_b64 = base64.b64encode(item.name.encode()).decode()
                    encrypted_name = manifest_encryptor._encrypt_string(original_name_b64)
                    encrypted_name_b64 = base64.b64encode(encrypted_name.encode()).decode()
                    
                    # Encrypt individual key with manifest master key
                    encrypted_individual_key = manifest_encryptor._encrypt_string(individual_key_b64)
                    encrypted_individual_key_b64 = base64.b64encode(encrypted_individual_key.encode()).decode()
                    
                    # Encrypt the file/folder with individual key
                    individual_encryptor = SecureEncryptor(individual_key)
                    encrypted_filename = individual_encryptor.generate_guid_filename(item)
                    output_path = output_folder / encrypted_filename
                    
                    if item.is_dir():
                        # Encrypt folder (will be zipped first)
                        individual_encryptor.encrypt_file(item, output_path, use_guid_filename=True)
                    else:
                        # Encrypt file
                        individual_encryptor.encrypt_file(item, output_path, use_guid_filename=True)
                    
                    # Add to manifest
                    manifest_line = f"{encrypted_individual_key_b64},{encrypted_name_b64},{encrypted_filename}\n"
                    with open(manifest_path, 'a') as f:
                        f.write(manifest_line)
                    
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to encrypt {item.name}: {e}"))
            
            # Complete
            self.bulk_progress_bar['value'] = 100
            self.bulk_progress_var.set(f"Completed! Encrypted {total_items} items")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Bulk encryption completed!\nOutput: {output_folder}"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Bulk encryption failed: {e}"))
    
    def browse_manifest(self):
        """Browse for manifest file"""
        manifest_path = filedialog.askopenfilename(
            title="Select enc.manifest file",
            filetypes=[("Manifest files", "enc.manifest"), ("All files", "*.*")]
        )
        if manifest_path:
            self.manifest_entry.delete(0, tk.END)
            self.manifest_entry.insert(0, manifest_path)
            self.bulk_decrypt_button.config(state="normal")
            self.decrypt_progress_var.set("Manifest loaded - ready to decrypt")
    
    def browse_decrypt_output(self):
        """Browse for output folder"""
        output_path = filedialog.askdirectory(title="Select Output Folder")
        if output_path:
            self.decrypt_output_entry.delete(0, tk.END)
            self.decrypt_output_entry.insert(0, output_path)
    
    def bulk_decrypt_all(self):
        """Decrypt all items from manifest"""
        manifest_path = self.manifest_entry.get().strip()
        output_path = self.decrypt_output_entry.get().strip()
        
        if not manifest_path or not output_path:
            messagebox.showerror("Error", "Please select manifest file and output folder")
            return
        
        # Start decryption in background thread
        thread = threading.Thread(target=self._bulk_decrypt_worker, 
                                args=(manifest_path, output_path))
        thread.daemon = True
        thread.start()
    
    def _bulk_decrypt_worker(self, manifest_path, output_path):
        """Worker thread for bulk decryption"""
        try:
            manifest_path = Path(manifest_path)
            output_path = Path(output_path)
            output_path.mkdir(exist_ok=True)
            
            # Read manifest
            with open(manifest_path, 'r') as f:
                lines = f.readlines()
            
            if not lines:
                raise ValueError("Manifest file is empty")
            
            # Get manifest master key
            manifest_master_key_b64 = lines[0].strip()
            manifest_master_key_hex = base64.b64decode(manifest_master_key_b64).decode()
            manifest_master_key = bytes.fromhex(manifest_master_key_hex)
            manifest_encryptor = SecureEncryptor(manifest_master_key)
            
            total_items = len(lines) - 1  # Exclude header line
            
            for i, line in enumerate(lines[1:], 1):
                # Update progress
                progress = (i / total_items) * 100
                self.decrypt_progress_bar['value'] = progress
                self.decrypt_progress_var.set(f"Decrypting item {i}/{total_items}")
                
                try:
                    # Parse manifest line
                    parts = line.strip().split(',')
                    if len(parts) != 3:
                        continue
                    
                    encrypted_individual_key_b64, encrypted_name_b64, encrypted_filename = parts
                    
                    # Decrypt individual key
                    encrypted_individual_key = base64.b64decode(encrypted_individual_key_b64).decode()
                    individual_key_b64 = manifest_encryptor._decrypt_string(encrypted_individual_key)
                    individual_key_hex = base64.b64decode(individual_key_b64).decode()
                    individual_key = bytes.fromhex(individual_key_hex)
                    
                    # Decrypt original name
                    encrypted_name = base64.b64decode(encrypted_name_b64).decode()
                    original_name_b64 = manifest_encryptor._decrypt_string(encrypted_name)
                    original_name = base64.b64decode(original_name_b64).decode()
                    
                    # Decrypt the file/folder
                    individual_encryptor = SecureEncryptor(individual_key)
                    encrypted_file_path = manifest_path.parent / encrypted_filename
                    decrypted_output_path = output_path / original_name
                    
                    individual_encryptor.decrypt_file(encrypted_file_path, decrypted_output_path)
                    
                    self.root.after(0, lambda name=original_name: self._log_decrypt(f"Decrypted: {name}"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self._log_decrypt(f"Error decrypting item {i}: {e}"))
            
            # Complete
            self.decrypt_progress_bar['value'] = 100
            self.decrypt_progress_var.set(f"Completed! Decrypted {total_items} items")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Bulk decryption completed!\nOutput: {output_path}"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Bulk decryption failed: {e}"))
    
    def _log_decrypt(self, message):
        """Add message to decrypt log"""
        self.decrypt_log_text.insert(tk.END, f"{message}\n")
        self.decrypt_log_text.see(tk.END)
        self.root.update_idletasks()
    
    def log(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """Clear the log"""
        self.log_text.delete(1.0, tk.END)
    
    def on_action_change(self):
        """Handle action radio button change"""
        self.toggle_guid_option()
    
    def toggle_guid_option(self):
        """Enable/disable GUID option based on action"""
        if self.action_var.get() == "decrypt":
            # Disable GUID option for decryption
            self.use_guid_var.set(False)
            self.guid_checkbox.config(state="disabled")
            # Enable output field for decryption
            self.output_entry.config(state="normal")
            self.output_entry.delete(0, tk.END)
            # Show browse button for output
            for widget in self.file_frame.grid_slaves(row=1, column=2):
                widget.grid()
        else:
            # Enable GUID option for encryption
            self.guid_checkbox.config(state="normal")
            
            # Check if GUID is selected
            if self.use_guid_var.get():
                # Disable output field when GUID is selected (filename auto-generated)
                self.output_entry.config(state="disabled")
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, "(Auto-generated as GUID.enc)")
                # Hide browse button for output
                for widget in self.file_frame.grid_slaves(row=1, column=2):
                    widget.grid_remove()
            else:
                # Enable output field when GUID is not selected
                self.output_entry.config(state="normal")
                self.output_entry.delete(0, tk.END)
                # Show browse button for output
                for widget in self.file_frame.grid_slaves(row=1, column=2):
                    widget.grid()
    
    def on_guid_checkbox_change(self):
        """Handle GUID checkbox state change"""
        if self.action_var.get() == "encrypt":
            if self.use_guid_var.get():
                # Disable output field when GUID is selected
                self.output_entry.config(state="disabled")
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, "(Auto-generated as GUID.enc)")
                # Hide browse button for output
                for widget in self.file_frame.grid_slaves(row=1, column=2):
                    widget.grid_remove()
            else:
                # Enable output field when GUID is not selected
                self.output_entry.config(state="normal")
                self.output_entry.delete(0, tk.END)
                # Show browse button for output
                for widget in self.file_frame.grid_slaves(row=1, column=2):
                    widget.grid()
    
    def generate_key(self):
        """Generate a new master key"""
        try:
            self.master_key = generate_master_key()
            self.encryptor = SecureEncryptor(self.master_key)
            self.key_status_label.config(text="Generated (Random)", foreground="green")
            
            key_hex = self.master_key.hex()
            self.log(f"Generated new master key: {key_hex}")
            self.log("IMPORTANT: Save this key securely! You'll need it for decryption.")
            
            messagebox.showinfo("Key Generated", 
                              f"New master key generated:\n\n{key_hex}\n\n"
                              "Save this key securely! You'll need it for decryption.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate key: {e}")
    
    def use_password(self):
        """Create master key from password"""
        dialog = PasswordDialog(self.root)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                password, salt = dialog.result
                self.master_key = salt
                self.encryptor = SecureEncryptor(self.master_key)
                self.key_status_label.config(text="Password-Based", foreground="green")
                
                self.log("Master key derived from password")
                self.log(f"Password salt: {salt.hex()}")
                self.log("IMPORTANT: Save the salt with your password!")
                
                messagebox.showinfo("Password Set", 
                                  "Master key derived from password.\n\n"
                                  f"Save this salt securely: {salt.hex()}\n"
                                  "You'll need both the password and salt for decryption.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set password: {e}")
    
    def enter_key(self):
        """Enter master key in hex format"""
        dialog = KeyEntryDialog(self.root)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                key_hex = dialog.result
                self.master_key = bytes.fromhex(key_hex)
                self.encryptor = SecureEncryptor(self.master_key)
                self.key_status_label.config(text="Manual Entry", foreground="green")
                
                self.log(f"Master key set manually: {key_hex}")
            except ValueError:
                messagebox.showerror("Error", "Invalid hex format for master key")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set key: {e}")
    
    def browse_input(self):
        """Browse for input file or folder"""
        if self.action_var.get() == "encrypt":
            # Allow both files and folders for encryption
            choice = messagebox.askyesno("Select Type", "Select a folder? (No for file)")
            if choice:
                foldername = filedialog.askdirectory(title="Select Input Folder")
                if foldername:
                    self.input_entry.delete(0, tk.END)
                    self.input_entry.insert(0, foldername)
                    
                    # Auto-generate output filename (folder -> .enc file)
                    input_path = Path(foldername)
                    output_path = input_path.with_suffix(input_path.suffix + ".enc")
                    self.output_entry.delete(0, tk.END)
                    self.output_entry.insert(0, str(output_path))
            else:
                filename = filedialog.askopenfilename(
                    title="Select Input File",
                    filetypes=[("All Files", "*.*")]
                )
                if filename:
                    self.input_entry.delete(0, tk.END)
                    self.input_entry.insert(0, filename)
                    
                    # Auto-generate output filename
                    input_path = Path(filename)
                    output_path = input_path.with_suffix(input_path.suffix + ".enc")
                    self.output_entry.delete(0, tk.END)
                    self.output_entry.insert(0, str(output_path))
        else:
            # For decryption, expect encrypted files
            filename = filedialog.askopenfilename(
                title="Select Encrypted File",
                filetypes=[("Encrypted Files", "*.enc"), ("All Files", "*.*")]
            )
            if filename:
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, filename)
                
                # Auto-generate output filename (remove .enc)
                input_path = Path(filename)
                output_path = input_path.with_suffix("")
                if output_path.suffix == ".enc":
                    output_path = output_path.with_suffix("")
                
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, str(output_path))
    
    def browse_output(self):
        """Browse for output file or folder"""
        if self.action_var.get() == "encrypt":
            # Output is always a file for encryption
            filetypes = [("Encrypted Files", "*.enc"), ("All Files", "*.*")]
            defaultext = ".enc"
            filename = filedialog.asksaveasfilename(
                title="Select Output File",
                filetypes=filetypes,
                defaultextension=defaultext
            )
        else:
            # For decryption, ask if user wants to extract to folder
            choice = messagebox.askyesno("Output Type", "Extract to folder? (No for file)")
            if choice:
                foldername = filedialog.askdirectory(title="Select Output Folder")
                if foldername:
                    self.output_entry.delete(0, tk.END)
                    self.output_entry.insert(0, foldername)
                    return
            else:
                filetypes = [("All Files", "*.*")]
                defaultext = ""
                filename = filedialog.asksaveasfilename(
                    title="Select Output File",
                    filetypes=filetypes,
                    defaultextension=defaultext
                )
        
        if filename:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, filename)
    
    def execute_action(self):
        """Execute encryption or decryption"""
        if not self.encryptor:
            messagebox.showerror("Error", "Please set a master key first")
            return
        
        input_path = self.input_entry.get().strip()
        output_path = self.output_entry.get().strip()
        action = self.action_var.get()
        
        # Validation logic
        if not input_path:
            messagebox.showerror("Error", "Please select an input path")
            return
        
        if not Path(input_path).exists():
            messagebox.showerror("Error", f"Input path does not exist: {input_path}")
            return
        
        # For GUID mode, output path is auto-generated, so don't require it
        if action == "encrypt" and self.use_guid_var.get():
            # Output will be generated in same directory as input
            pass
        elif not output_path:
            messagebox.showerror("Error", "Please select both input and output paths")
            return
        
        try:
            self.status_var.set(f"{action.capitalize()}ing...")
            self.log(f"Starting {action} of {input_path}")
            
            input_file = Path(input_path)
            
            if action == "encrypt":
                use_guid = self.use_guid_var.get()
                if use_guid:
                    # For GUID mode, generate output path in same directory as input
                    output_file = input_file.parent / "guid_output.enc"
                else:
                    output_file = Path(output_path)
                
                self.encryptor.encrypt_file(input_file, output_file, use_guid_filename=use_guid)
                if use_guid:
                    self.log(f"Successfully encrypted with GUID filename")
                else:
                    self.log(f"Successfully encrypted to {output_path}")
            else:  # decrypt
                output_file = Path(output_path)
                self.encryptor.decrypt_file(input_file, output_file)
                self.log(f"Successfully decrypted to {output_path}")
            
            self.status_var.set("Completed successfully")
            messagebox.showinfo("Success", f"{action.capitalize()} completed successfully!")
            
        except Exception as e:
            self.status_var.set("Error")
            self.log(f"Error during {action}: {e}")
            messagebox.showerror("Error", f"{action.capitalize()} failed: {e}")


class PasswordDialog:
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Set Master Password")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (250 // 2)
        self.dialog.geometry(f"400x250+{x}+{y}")
        
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="Enter master password:", 
                 font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.password_entry = ttk.Entry(main_frame, show="*", width=30)
        self.password_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(main_frame, text="Confirm password:", 
                 font=('Arial', 10)).grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        self.confirm_entry = ttk.Entry(main_frame, show="*", width=30)
        self.confirm_entry.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, sticky=(tk.W, tk.E))
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).grid(row=0, column=1)
        
        self.password_entry.focus()
        main_frame.columnconfigure(0, weight=1)
        
        # Bind Enter key
        self.dialog.bind('<Return>', lambda e: self.ok_clicked())
    
    def ok_clicked(self):
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()
        
        if not password:
            messagebox.showerror("Error", "Please enter a password")
            return
        
        if password != confirm:
            messagebox.showerror("Error", "Passwords don't match")
            return
        
        if len(password) < 8:
            messagebox.showerror("Error", "Password should be at least 8 characters")
            return
        
        # Derive master key from password
        master_key, salt = derive_master_key_from_password(password)
        self.result = (master_key, salt)
        self.dialog.destroy()
    
    def cancel_clicked(self):
        self.dialog.destroy()


class KeyEntryDialog:
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Enter Master Key")
        self.dialog.geometry("500x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (200 // 2)
        self.dialog.geometry(f"500x200+{x}+{y}")
        
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="Enter master key (64 hex characters):", 
                 font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.key_entry = ttk.Entry(main_frame, width=60)
        self.key_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).grid(row=0, column=1)
        
        self.key_entry.focus()
        main_frame.columnconfigure(0, weight=1)
        
        # Bind Enter key
        self.dialog.bind('<Return>', lambda e: self.ok_clicked())
    
    def ok_clicked(self):
        key_hex = self.key_entry.get().strip()
        
        if not key_hex:
            messagebox.showerror("Error", "Please enter a master key")
            return
        
        if len(key_hex) != 64:
            messagebox.showerror("Error", "Master key must be exactly 64 hex characters (32 bytes)")
            return
        
        try:
            # Validate hex format
            bytes.fromhex(key_hex)
            self.result = key_hex
            self.dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid hex format")
    
    def cancel_clicked(self):
        self.dialog.destroy()


def main():
    root = tk.Tk()
    app = EncryptionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

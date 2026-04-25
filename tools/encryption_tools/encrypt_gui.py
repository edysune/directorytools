#!/usr/bin/env python3
"""
GUI wrapper for the secure AES-256 encryption tool
Provides easy-to-use interface for file encryption/decryption
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
from pathlib import Path
from encrypt import SecureEncryptor, generate_master_key, derive_master_key_from_password


class EncryptionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure AES-256 File Encryption")
        self.root.geometry("700x600")
        
        self.master_key = None
        self.encryptor = None
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Secure AES-256 File Encryption", 
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Master Key Section
        key_frame = ttk.LabelFrame(main_frame, text="Master Key Management", padding="10")
        key_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
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
        self.file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        self.file_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
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
        action_frame = ttk.LabelFrame(main_frame, text="Action", padding="10")
        action_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
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
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=70)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Button(log_frame, text="Clear Log", 
                  command=self.clear_log).grid(row=1, column=0, pady=(5, 0))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    
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

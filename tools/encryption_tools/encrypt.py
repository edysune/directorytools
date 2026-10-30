#!/usr/bin/env python3
"""
Secure AES-256 File Encryption Tool
Uses HKDF for key derivation from a master key
Supports both CLI and GUI interfaces
"""

import os
import sys
import argparse
import getpass
import hashlib
import zipfile
import tempfile
import shutil
import uuid
import base64
from pathlib import Path
from typing import Tuple, Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag


class SecureEncryptor:
    """Handles AES-256-GCM encryption with HKDF key derivation"""
    
    def __init__(self, master_key: bytes):
        """Initialize with master key (32 bytes for AES-256)"""
        if len(master_key) != 32:
            raise ValueError("Master key must be 32 bytes (256 bits)")
        self.master_key = master_key
        self.backend = default_backend()
    
    def derive_key(self, salt: bytes, info: bytes) -> bytes:
        """Derive unique encryption key using HKDF"""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit AES key
            salt=salt,
            info=info,
            backend=self.backend
        )
        return hkdf.derive(self.master_key)
    
    def generate_guid_filename(self, original_path: Path) -> str:
        """Generate a GUID-based filename with .enc extension"""
        guid = str(uuid.uuid4())
        return f"{guid}.enc"
    
    def resolve_filename_conflict(self, output_path: Path, original_name: str) -> Path:
        """Resolve filename conflicts by adding (X) suffix"""
        base_path = output_path.parent / original_name
        
        if not base_path.exists():
            return base_path
        
        # If conflict exists, add (1), (2), etc.
        counter = 1
        stem = base_path.stem
        suffix = base_path.suffix
        
        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = output_path.parent / new_name
            
            if not new_path.exists():
                return new_path
            
            counter += 1
    
    def _encrypt_string(self, plaintext: str) -> str:
        """Encrypt a string using AES-256-GCM"""
        # Generate salt and nonce
        salt = os.urandom(16)
        nonce = os.urandom(12)
        
        # Derive key for string encryption
        info = b"string-encryption"
        key = self.derive_key(salt, info)
        
        # Encrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        
        # Return base64 encoded: [salt][nonce][ciphertext][auth_tag]
        encrypted_data = salt + nonce + ciphertext + encryptor.tag
        return base64.b64encode(encrypted_data).decode()
    
    def _decrypt_string(self, encrypted_b64: str) -> str:
        """Decrypt a string using AES-256-GCM"""
        # Decode base64
        encrypted_data = base64.b64decode(encrypted_b64)
        
        # Extract components
        salt = encrypted_data[:16]
        nonce = encrypted_data[16:28]
        ciphertext = encrypted_data[28:-16]
        auth_tag = encrypted_data[-16:]
        
        # Derive key
        info = b"string-encryption"
        key = self.derive_key(salt, info)
        
        # Decrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce, auth_tag),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        
        try:
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode()
        except InvalidTag:
            raise ValueError("String decryption failed: Invalid authentication tag")
    
    def encrypt_file(self, input_path: Path, output_path: Path, use_guid_filename: bool = False) -> None:
        """Encrypt a file or folder using AES-256-GCM"""
        # Handle folder encryption by zipping first
        if input_path.is_dir():
            temp_zip_path = None
            try:
                # Create temporary zip file
                temp_zip_path = Path(tempfile.mktemp(suffix='.zip'))
                self._zip_folder(input_path, temp_zip_path)
                
                # Generate GUID filename if requested
                if use_guid_filename:
                    guid_filename = self.generate_guid_filename(input_path)
                    actual_output_path = output_path.parent / guid_filename
                else:
                    actual_output_path = output_path
                
                # Encrypt the zip file
                self._encrypt_file_internal(temp_zip_path, actual_output_path, input_path.name)
                
                print(f"Folder '{input_path}' zipped and encrypted to '{actual_output_path}'")
            finally:
                # Clean up temporary zip file
                if temp_zip_path and temp_zip_path.exists():
                    temp_zip_path.unlink()
        else:
            # Generate GUID filename if requested
            if use_guid_filename:
                guid_filename = self.generate_guid_filename(input_path)
                actual_output_path = output_path.parent / guid_filename
            else:
                actual_output_path = output_path
            
            # Encrypt single file
            self._encrypt_file_internal(input_path, actual_output_path, input_path.name)
    
    def _encrypt_file_internal(self, input_path: Path, output_path: Path, original_name: str) -> None:
        """Internal method to encrypt a single file using AES-256-GCM"""
        # Generate unique salt and nonce for this file
        salt = os.urandom(16)  # 128-bit salt
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        
        # Derive unique key for this file
        file_info = f"file-encryption-{input_path.name}".encode()
        encryption_key = self.derive_key(salt, file_info)
        
        # Read plaintext
        plaintext = input_path.read_bytes()
        
        # Encrypt
        cipher = Cipher(
            algorithms.AES(encryption_key),
            modes.GCM(nonce),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # Store metadata: original filename length and original filename
        original_name_bytes = original_name.encode('utf-8')
        original_name_len = len(original_name_bytes).to_bytes(4, byteorder='big')
        file_info_len = len(file_info).to_bytes(2, byteorder='big')
        
        # Write encrypted file: [salt][nonce][file_info_len][file_info][orig_name_len][orig_name][ciphertext][auth_tag]
        with open(output_path, 'wb') as f:
            f.write(salt)
            f.write(nonce)
            f.write(file_info_len)
            f.write(file_info)
            f.write(original_name_len)
            f.write(original_name_bytes)
            f.write(ciphertext)
            f.write(encryptor.tag)  # 16-byte authentication tag
    
    def decrypt_file(self, input_path: Path, output_path: Path) -> None:
        """Decrypt a file or folder using AES-256-GCM"""
        # Create temporary file for decrypted content
        temp_decrypted_path = None
        try:
            # Create temp file path
            temp_decrypted_path = Path(tempfile.mktemp())
            
            # Decrypt to temporary file first and get original name
            temp_decrypted_path, original_name = self._decrypt_file_internal(input_path, temp_decrypted_path)
            
            # Resolve filename conflicts
            final_output_path = self.resolve_filename_conflict(output_path, original_name)
            
            # Check if decrypted content is a zip file
            if self._is_zip_file(temp_decrypted_path):
                # Extract zip to output directory
                if final_output_path.exists():
                    if final_output_path.is_file():
                        final_output_path.unlink()
                    else:
                        shutil.rmtree(final_output_path)
                
                final_output_path.mkdir(parents=True, exist_ok=True)
                self._unzip_folder(temp_decrypted_path, final_output_path)
                print(f"Decrypted and extracted folder to '{final_output_path}'")
            else:
                # Move decrypted file to final location
                if final_output_path.exists():
                    final_output_path.unlink()
                shutil.move(str(temp_decrypted_path), str(final_output_path))
                
        finally:
            # Clean up temporary file
            if temp_decrypted_path and temp_decrypted_path.exists():
                temp_decrypted_path.unlink()
    
    def _decrypt_file_internal(self, input_path: Path, output_path: Path) -> Tuple[Path, str]:
        """Internal method to decrypt a single file using AES-256-GCM"""
        # Read encrypted file
        data = input_path.read_bytes()
        
        # Extract components
        salt = data[:16]
        nonce = data[16:28]
        file_info_len = int.from_bytes(data[28:30], byteorder='big')
        file_info = data[30:30+file_info_len]
        original_name_len = int.from_bytes(data[30+file_info_len:34+file_info_len], byteorder='big')
        original_name_bytes = data[34+file_info_len:34+file_info_len+original_name_len]
        original_name = original_name_bytes.decode('utf-8')
        ciphertext = data[34+file_info_len+original_name_len:-16]
        auth_tag = data[-16:]
        
        # Derive key using stored salt and file info
        encryption_key = self.derive_key(salt, file_info)
        
        # Decrypt
        cipher = Cipher(
            algorithms.AES(encryption_key),
            modes.GCM(nonce, auth_tag),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        
        try:
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        except InvalidTag:
            raise ValueError("Decryption failed: Invalid authentication tag (wrong key or corrupted file)")
        
        # Write decrypted file
        output_path.write_bytes(plaintext)
        return output_path, original_name
    
    def _zip_folder(self, folder_path: Path, zip_path: Path) -> None:
        """Zip a folder recursively"""
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in folder_path.rglob('*'):
                if file_path.is_file():
                    # Calculate relative path from folder
                    arcname = file_path.relative_to(folder_path)
                    zipf.write(file_path, arcname)
    
    def _unzip_folder(self, zip_path: Path, extract_path: Path) -> None:
        """Extract a zip file to a folder"""
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_path)
    
    def _is_zip_file(self, file_path: Path) -> bool:
        """Check if a file is a valid zip file"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zipf:
                zipf.testzip()  # Test zip file integrity
            return True
        except (zipfile.BadZipFile, zipfile.LargeZipFile):
            return False


def generate_master_key() -> bytes:
    """Generate a cryptographically secure random master key"""
    return os.urandom(32)


def derive_master_key_from_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Derive master key from password using PBKDF2"""
    if salt is None:
        salt = os.urandom(16)
    
    kdf = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return kdf, salt


def get_master_key_interactive() -> bytes:
    """Get master key from user (generate new or derive from password)"""
    print("Master Key Options:")
    print("1. Generate new random master key")
    print("2. Derive from password")
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        master_key = generate_master_key()
        print(f"\nGenerated master key: {master_key.hex()}")
        print("Save this key securely! You'll need it for decryption.")
        return master_key
    elif choice == "2":
        password = getpass.getpass("Enter master password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            raise ValueError("Passwords don't match")
        
        master_key, salt = derive_master_key_from_password(password)
        print(f"\nMaster key salt: {salt.hex()}")
        print("Save this salt with your password! You'll need both for decryption.")
        return master_key
    else:
        raise ValueError("Invalid choice")


def cli_main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(description="Secure AES-256 File and Folder Encryption")
    parser.add_argument("action", choices=["encrypt", "decrypt"], help="Action to perform")
    parser.add_argument("input", help="Input file or folder path")
    parser.add_argument("output", help="Output file or folder path")
    parser.add_argument("--key", help="Master key in hex (32 bytes)")
    parser.add_argument("--password", action="store_true", help="Use password instead of key")
    parser.add_argument("--guid", action="store_true", help="Use random GUID filename for encryption")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"Error: Input path {input_path} does not exist")
        sys.exit(1)
    
    # Get master key
    if args.key:
        try:
            master_key = bytes.fromhex(args.key)
        except ValueError:
            print("Error: Invalid hex format for master key")
            sys.exit(1)
    elif args.password:
        password = getpass.getpass("Enter master password: ")
        master_key, _ = derive_master_key_from_password(password)
    else:
        master_key = get_master_key_interactive()
    
    # Initialize encryptor
    encryptor = SecureEncryptor(master_key)
    
    # Perform action
    try:
        if args.action == "encrypt":
            use_guid = args.guid if hasattr(args, 'guid') else False
            encryptor.encrypt_file(input_path, output_path, use_guid_filename=use_guid)
            if use_guid:
                print(f"Encrypted {input_path} -> {output_path} (with GUID filename)")
            else:
                print(f"Encrypted {input_path} -> {output_path}")
        else:  # decrypt
            encryptor.decrypt_file(input_path, output_path)
            print(f"Decrypted {input_path} -> {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
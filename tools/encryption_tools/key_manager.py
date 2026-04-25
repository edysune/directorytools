#!/usr/bin/env python3
"""
Master Key Management Utilities
Provides tools for secure key storage and retrieval
"""

import os
import json
import getpass
from pathlib import Path
from typing import Dict, Optional, Tuple
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

from encrypt import generate_master_key, derive_master_key_from_password


class KeyManager:
    """Manages secure storage and retrieval of master keys"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize key manager with storage path"""
        if storage_path is None:
            storage_path = Path.home() / ".encrypt_keys"
        
        self.storage_path = storage_path
        self.storage_path.mkdir(exist_ok=True)
        self.keys_file = self.storage_path / "keys.json"
        self.keys_data = self._load_keys()
    
    def _load_keys(self) -> Dict:
        """Load keys from storage file"""
        if self.keys_file.exists():
            try:
                with open(self.keys_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_keys(self):
        """Save keys to storage file"""
        try:
            with open(self.keys_file, 'w') as f:
                json.dump(self.keys_data, f, indent=2)
            # Set restrictive permissions
            os.chmod(self.keys_file, 0o600)
        except IOError as e:
            raise Exception(f"Failed to save keys: {e}")
    
    def store_key(self, name: str, key: bytes, password: Optional[str] = None) -> None:
        """Store a master key with optional password protection"""
        if password:
            # Encrypt the key with password
            encrypted_key = self._encrypt_key(key, password)
            key_data = {
                "encrypted_key": encrypted_key.decode(),
                "salt": derive_master_key_from_password(password)[1].hex(),
                "protected": True
            }
        else:
            # Store plaintext (not recommended for production)
            key_data = {
                "key": key.hex(),
                "protected": False
            }
        
        self.keys_data[name] = key_data
        self._save_keys()
    
    def retrieve_key(self, name: str, password: Optional[str] = None) -> bytes:
        """Retrieve a master key by name"""
        if name not in self.keys_data:
            raise KeyError(f"Key '{name}' not found")
        
        key_data = self.keys_data[name]
        
        if key_data["protected"]:
            if not password:
                raise ValueError("Password required for this key")
            return self._decrypt_key(key_data["encrypted_key"], password)
        else:
            return bytes.fromhex(key_data["key"])
    
    def _encrypt_key(self, key: bytes, password: str) -> bytes:
        """Encrypt a key with a password using Fernet"""
        # Derive encryption key from password
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        encryption_key = kdf.derive(password.encode())
        
        # Encrypt the master key
        fernet = Fernet(Fernet(encryption_key))
        encrypted_key = fernet.encrypt(key)
        
        # Store salt with encrypted key
        return salt + encrypted_key
    
    def _decrypt_key(self, encrypted_data: str, password: str) -> bytes:
        """Decrypt a key with a password"""
        encrypted_data = bytes.fromhex(encrypted_data)
        salt = encrypted_data[:16]
        encrypted_key = encrypted_data[16:]
        
        # Derive encryption key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        encryption_key = kdf.derive(password.encode())
        
        # Decrypt the master key
        fernet = Fernet(encryption_key)
        return fernet.decrypt(encrypted_key)
    
    def list_keys(self) -> Dict[str, bool]:
        """List all stored keys and their protection status"""
        return {name: data["protected"] for name, data in self.keys_data.items()}
    
    def delete_key(self, name: str) -> None:
        """Delete a stored key"""
        if name in self.keys_data:
            del self.keys_data[name]
            self._save_keys()
        else:
            raise KeyError(f"Key '{name}' not found")
    
    def generate_and_store_key(self, name: str, password: Optional[str] = None) -> bytes:
        """Generate a new master key and store it"""
        key = generate_master_key()
        self.store_key(name, key, password)
        return key


def cli_main():
    """Command-line interface for key management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Master Key Management")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate and store a new key')
    gen_parser.add_argument('name', help='Key name')
    gen_parser.add_argument('--password', action='store_true', help='Protect with password')
    
    # Retrieve command
    ret_parser = subparsers.add_parser('retrieve', help='Retrieve a stored key')
    ret_parser.add_argument('name', help='Key name')
    ret_parser.add_argument('--password', action='store_true', help='Key is password protected')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all stored keys')
    
    # Delete command
    del_parser = subparsers.add_parser('delete', help='Delete a stored key')
    del_parser.add_argument('name', help='Key name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    km = KeyManager()
    
    try:
        if args.command == 'generate':
            password = None
            if args.password:
                password = getpass.getpass("Enter protection password: ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    print("Error: Passwords don't match")
                    return
            
            key = km.generate_and_store_key(args.name, password)
            print(f"Generated and stored key '{args.name}'")
            print(f"Key value: {key.hex()}")
            if password:
                print("Key is password protected")
        
        elif args.command == 'retrieve':
            password = None
            if args.password:
                password = getpass.getpass("Enter password: ")
            
            try:
                key = km.retrieve_key(args.name, password)
                print(f"Key '{args.name}': {key.hex()}")
            except KeyError:
                print(f"Error: Key '{args.name}' not found")
            except ValueError as e:
                print(f"Error: {e}")
        
        elif args.command == 'list':
            keys = km.list_keys()
            if keys:
                print("Stored keys:")
                for name, protected in keys.items():
                    status = "protected" if protected else "unprotected"
                    print(f"  {name} ({status})")
            else:
                print("No keys stored")
        
        elif args.command == 'delete':
            km.delete_key(args.name)
            print(f"Deleted key '{args.name}'")
    
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    cli_main()

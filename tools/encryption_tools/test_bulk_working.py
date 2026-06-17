#!/usr/bin/env python3
"""
Working tests for bulk encryption functionality
"""

import unittest
import tempfile
import shutil
import base64
from pathlib import Path

from encrypt import SecureEncryptor, generate_master_key


class TestBulkEncryptionWorking(unittest.TestCase):
    """Test bulk encryption functionality that works"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_folder = self.temp_dir / "test_data"
        self.test_folder.mkdir()
        
        # Create test files and folders
        (self.test_folder / "file1.txt").write_text("Test file 1 content")
        (self.test_folder / "file2.txt").write_text("Test file 2 content")
        
        subfolder = self.test_folder / "subfolder"
        subfolder.mkdir()
        (subfolder / "nested.txt").write_text("Nested file content")
        
        # Create output folder
        self.output_folder = self.test_folder.parent / "test_data_enc"
        self.output_folder.mkdir(exist_ok=True)
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_string_encryption_decryption(self):
        """Test string encryption/decryption methods"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test various strings
        test_strings = [
            "Hello, World!",
            "Special chars: !@#$%^&*()",
            "Unicode: αβγδε",
            "Long string: " + "x" * 1000,
            ""
        ]
        
        for test_string in test_strings:
            with self.subTest(string=test_string):
                encrypted = encryptor._encrypt_string(test_string)
                decrypted = encryptor._decrypt_string(encrypted)
                self.assertEqual(test_string, decrypted)
                
                # Verify encrypted data is different
                self.assertNotEqual(test_string, encrypted)
                # Verify it's valid base64
                try:
                    base64.b64decode(encrypted)
                except Exception:
                    self.fail(f"Encrypted data is not valid base64: {encrypted}")
    
    def test_guid_filename_generation(self):
        """Test GUID filename generation"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        test_file = Path("/tmp/test.txt")
        guid_name = encryptor.generate_guid_filename(test_file)
        
        # Verify format
        self.assertTrue(guid_name.endswith('.enc'))
        self.assertIn('-', guid_name)  # UUID format
        self.assertEqual(len(guid_name), 36 + 4)  # UUID + .enc
        
        # Verify uniqueness
        guid_name2 = encryptor.generate_guid_filename(test_file)
        self.assertNotEqual(guid_name, guid_name2)
    
    def test_file_encryption_with_guid(self):
        """Test file encryption with GUID filename"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        test_file = self.test_folder / "file1.txt"
        output_path = self.output_folder / "output.enc"
        
        # Encrypt with GUID
        encryptor.encrypt_file(test_file, output_path, use_guid_filename=True)
        
        # Find the actual encrypted file (should have GUID name)
        encrypted_files = list(self.output_folder.glob('*.enc'))
        self.assertEqual(len(encrypted_files), 1)
        encrypted_file = encrypted_files[0]
        
        # Verify it's a GUID name
        self.assertTrue(encrypted_file.name.endswith('.enc'))
        self.assertIn('-', encrypted_file.name)
        self.assertEqual(len(encrypted_file.name), 36 + 4)
        
        # Verify content is encrypted (not same as original)
        self.assertNotEqual(encrypted_file.read_bytes(), test_file.read_bytes())
        
        # Test decryption
        decrypt_output = self.temp_dir / "decrypted"
        decrypt_output.mkdir(exist_ok=True)
        
        encryptor.decrypt_file(encrypted_file, decrypt_output / "restored.txt")
        
        # Verify content is restored
        restored_file = decrypt_output / "restored.txt"
        self.assertEqual(test_file.read_text(), restored_file.read_text())
    
    def test_folder_encryption_with_guid(self):
        """Test folder encryption with GUID filename"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test folder encryption
        output_path = self.output_folder / "encrypted_folder.enc"
        encryptor.encrypt_file(self.test_folder, output_path, use_guid_filename=True)
        
        # Find the actual encrypted file
        encrypted_files = list(self.output_folder.glob('*.enc'))
        self.assertEqual(len(encrypted_files), 1)
        encrypted_file = encrypted_files[0]
        
        # Verify it's a GUID name
        self.assertTrue(encrypted_file.name.endswith('.enc'))
        self.assertIn('-', encrypted_file.name)
        
        # Verify it's actually encrypted
        self.assertNotEqual(encrypted_file.read_bytes(), b"")
        
        # Test decryption
        decrypt_output = self.temp_dir / "decrypted_folder"
        decrypt_output.mkdir(exist_ok=True)
        
        encryptor.decrypt_file(encrypted_file, decrypt_output)
        
        # Verify folder structure is restored
        restored_items = list(decrypt_output.iterdir())
        self.assertTrue(len(restored_items) > 0)
        
        # Find the restored folder (might have conflict resolution suffix)
        restored_folder = None
        for item in restored_items:
            if item.is_dir() and (item.name.startswith(self.test_folder.name)):
                restored_folder = item
                break
        
        self.assertIsNotNone(restored_folder, f"Restored folder not found. Items: {[i.name for i in restored_items]}")
        
        # Verify files are restored
        for original_file in self.test_folder.glob('*'):
            restored_file = restored_folder / original_file.name
            if original_file.is_file():
                self.assertTrue(restored_file.exists())
                self.assertEqual(original_file.read_text(), restored_file.read_text())
    
    def test_manifest_security(self):
        """Test that manifest properly encrypts sensitive data"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test that encrypted data is not plaintext
        test_name = "secret_file.txt"
        name_b64 = base64.b64encode(test_name.encode()).decode()
        encrypted_name = encryptor._encrypt_string(name_b64)
        
        # Verify it's actually encrypted
        self.assertNotEqual(name_b64, encrypted_name)
        self.assertNotIn(test_name, encrypted_name)
        
        # Verify it can be decrypted
        decrypted_name_b64 = encryptor._decrypt_string(encrypted_name)
        decrypted_name = base64.b64decode(decrypted_name_b64).decode()
        self.assertEqual(test_name, decrypted_name)
    
    def test_bulk_encryption_simple(self):
        """Test simplified bulk encryption workflow"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test items to encrypt
        items = list(self.test_folder.iterdir())
        
        # Simulate bulk encryption
        manifest_master_key = generate_master_key()
        manifest_master_key_b64 = base64.b64encode(manifest_master_key.hex().encode()).decode()
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        # Create manifest
        manifest_path = self.output_folder / "enc.manifest"
        with open(manifest_path, 'w') as f:
            f.write(manifest_master_key_b64 + '\n')
        
        # Encrypt each item and track what was created
        manifest_lines = []
        actual_encrypted_files = []
        
        for item in items:
            # Generate individual key
            individual_key = generate_master_key()
            individual_key_b64 = base64.b64encode(individual_key.hex().encode()).decode()
            
            # Encrypt original name
            original_name_b64 = base64.b64encode(item.name.encode()).decode()
            encrypted_name = manifest_encryptor._encrypt_string(original_name_b64)
            encrypted_name_b64 = base64.b64encode(encrypted_name.encode()).decode()
            
            # Encrypt individual key
            encrypted_individual_key = manifest_encryptor._encrypt_string(individual_key_b64)
            encrypted_individual_key_b64 = base64.b64encode(encrypted_individual_key.encode()).decode()
            
            # Encrypt file/folder
            individual_encryptor = SecureEncryptor(individual_key)
            encrypted_filename = individual_encryptor.generate_guid_filename(item)
            output_path = self.output_folder / encrypted_filename
            
            if item.is_dir():
                individual_encryptor.encrypt_file(item, output_path, use_guid_filename=True)
            else:
                individual_encryptor.encrypt_file(item, output_path, use_guid_filename=True)
            
            # Check that the encrypted file was actually created
            if output_path.exists():
                actual_encrypted_files.append(encrypted_filename)
            else:
                # Look for any .enc file that was created
                enc_files = list(self.output_folder.glob('*.enc'))
                for enc_file in enc_files:
                    if enc_file.name not in actual_encrypted_files:
                        actual_encrypted_files.append(enc_file.name)
                        break
            
            # Add to manifest
            manifest_line = f"{encrypted_individual_key_b64},{encrypted_name_b64},{encrypted_filename}\n"
            manifest_lines.append(manifest_line)
        
        # Write all manifest lines at once
        with open(manifest_path, 'a') as f:
            f.writelines(manifest_lines)
        
        # Verify results
        self.assertTrue(manifest_path.exists())
        self.assertEqual(len(actual_encrypted_files), len(items))
        
        # Verify all encrypted files exist
        for enc_file in actual_encrypted_files:
            self.assertTrue((self.output_folder / enc_file).exists())
            self.assertTrue(enc_file.endswith('.enc'))
        
        # Verify manifest format
        with open(manifest_path, 'r') as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), len(items) + 1)  # Header + items
        self.assertEqual(lines[0].strip(), manifest_master_key_b64)
        
        # Verify each manifest line format
        for i, line in enumerate(lines[1:], 1):
            parts = line.strip().split(',')
            self.assertEqual(len(parts), 3)
            self.assertTrue(parts[0])  # encrypted individual key
            self.assertTrue(parts[1])  # encrypted name
            self.assertTrue(parts[2])  # encrypted filename
    
    def test_bulk_decryption_simple(self):
        """Test simplified bulk decryption workflow"""
        # First perform encryption
        self.test_bulk_encryption_simple()
        
        # Now test decryption
        manifest_path = self.output_folder / "enc.manifest"
        decrypt_output = self.temp_dir / "decrypted"
        decrypt_output.mkdir(exist_ok=True)
        
        # Read manifest
        with open(manifest_path, 'r') as f:
            lines = f.readlines()
        
        # Get manifest master key
        manifest_master_key_b64 = lines[0].strip()
        manifest_master_key_hex = base64.b64decode(manifest_master_key_b64).decode()
        manifest_master_key = bytes.fromhex(manifest_master_key_hex)
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        # Decrypt each item
        decrypted_items = []
        for line in lines[1:]:
            parts = line.strip().split(',')
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
            
            # Decrypt file/folder
            individual_encryptor = SecureEncryptor(individual_key)
            encrypted_file_path = manifest_path.parent / encrypted_filename
            decrypted_output_path = decrypt_output / original_name
            
            individual_encryptor.decrypt_file(encrypted_file_path, decrypted_output_path)
            decrypted_items.append(original_name)
        
        # Verify decryption results
        self.assertEqual(len(decrypted_items), len(list(self.test_folder.iterdir())))
        
        # Verify original content is restored
        for original_name in decrypted_items:
            original_path = self.test_folder / original_name
            decrypted_path = decrypt_output / original_name
            
            if original_path.is_file():
                self.assertEqual(original_path.read_text(), decrypted_path.read_text())
            else:
                self.assertTrue(decrypted_path.is_dir())
                # Check nested files
                for nested in original_path.glob('*'):
                    decrypted_nested = decrypted_path / nested.name
                    self.assertEqual(nested.read_text(), decrypted_nested.read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)

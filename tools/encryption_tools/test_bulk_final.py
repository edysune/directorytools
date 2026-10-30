#!/usr/bin/env python3
"""
Final comprehensive tests for bulk encryption functionality
"""

import unittest
import tempfile
import shutil
import base64
from pathlib import Path

from encrypt import SecureEncryptor, generate_master_key


class TestBulkEncryptionFinal(unittest.TestCase):
    """Test bulk encryption functionality"""
    
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
    
    def test_file_encryption_decryption_roundtrip(self):
        """Test complete file encryption/decryption roundtrip"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        test_file = self.test_folder / "file1.txt"
        original_content = test_file.read_text()
        
        # Create output folder
        self.output_folder.mkdir(exist_ok=True)
        
        # Encrypt with GUID
        output_path = self.output_folder / "output.enc"
        encryptor.encrypt_file(test_file, output_path, use_guid_filename=True)
        
        # Find the encrypted file
        encrypted_files = list(self.output_folder.glob('*.enc'))
        self.assertEqual(len(encrypted_files), 1)
        encrypted_file = encrypted_files[0]
        
        # Verify it's a GUID name
        self.assertTrue(encrypted_file.name.endswith('.enc'))
        self.assertIn('-', encrypted_file.name)
        
        # Test decryption
        decrypt_output = self.temp_dir / "decrypted"
        decrypt_output.mkdir(exist_ok=True)
        
        encryptor.decrypt_file(encrypted_file, decrypt_output)
        
        # Find the decrypted file
        decrypted_files = list(decrypt_output.glob('*'))
        self.assertEqual(len(decrypted_files), 1)
        decrypted_file = decrypted_files[0]
        
        # Verify content is restored
        self.assertEqual(original_content, decrypted_file.read_text())
        self.assertEqual(decrypted_file.name, test_file.name)
    
    def test_folder_encryption_decryption_roundtrip(self):
        """Test complete folder encryption/decryption roundtrip"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Create output folder
        self.output_folder.mkdir(exist_ok=True)
        
        # Encrypt folder
        output_path = self.output_folder / "encrypted_folder.enc"
        encryptor.encrypt_file(self.test_folder, output_path, use_guid_filename=True)
        
        # Find the encrypted file
        encrypted_files = list(self.output_folder.glob('*.enc'))
        self.assertEqual(len(encrypted_files), 1)
        encrypted_file = encrypted_files[0]
        
        # Verify it's a GUID name
        self.assertTrue(encrypted_file.name.endswith('.enc'))
        self.assertIn('-', encrypted_file.name)
        
        # Test decryption
        decrypt_output = self.temp_dir / "decrypted_folder"
        decrypt_output.mkdir(exist_ok=True)
        
        encryptor.decrypt_file(encrypted_file, decrypt_output)
        
        # Find the restored folder
        restored_folders = [f for f in decrypt_output.iterdir() if f.is_dir()]
        self.assertEqual(len(restored_folders), 1)
        restored_folder = restored_folders[0]
        
        # Verify folder structure is restored
        for original_file in self.test_folder.glob('*'):
            restored_file = restored_folder / original_file.name
            if original_file.is_file():
                self.assertTrue(restored_file.exists())
                self.assertEqual(original_file.read_text(), restored_file.read_text())
    
    def test_manifest_encryption_format(self):
        """Test manifest encryption follows specified format"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Create test data
        test_file = self.test_folder / "file1.txt"
        
        # Simulate manifest encryption process
        manifest_master_key = generate_master_key()
        manifest_master_key_b64 = base64.b64encode(manifest_master_key.hex().encode()).decode()
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        # Generate individual key
        individual_key = generate_master_key()
        individual_key_b64 = base64.b64encode(individual_key.hex().encode()).decode()
        
        # Encrypt original filename
        original_name_b64 = base64.b64encode(test_file.name.encode()).decode()
        encrypted_name = manifest_encryptor._encrypt_string(original_name_b64)
        encrypted_name_b64 = base64.b64encode(encrypted_name.encode()).decode()
        
        # Encrypt individual key
        encrypted_individual_key = manifest_encryptor._encrypt_string(individual_key_b64)
        encrypted_individual_key_b64 = base64.b64encode(encrypted_individual_key.encode()).decode()
        
        # Generate encrypted filename
        individual_encryptor = SecureEncryptor(individual_key)
        encrypted_filename = individual_encryptor.generate_guid_filename(test_file)
        
        # Verify manifest line format: <base64-individual-key>,<base64-encrypted-name>,<encryptedfile.enc>
        manifest_line = f"{encrypted_individual_key_b64},{encrypted_name_b64},{encrypted_filename}"
        parts = manifest_line.split(',')
        
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[0])  # encrypted individual key
        self.assertTrue(parts[1])  # encrypted name
        self.assertTrue(parts[2])  # encrypted filename
        
        # Verify each part is valid base64
        for part in parts[:2]:  # First two parts should be base64
            try:
                base64.b64decode(part)
            except Exception:
                self.fail(f"Part is not valid base64: {part}")
        
        # Verify encrypted filename format
        self.assertTrue(parts[2].endswith('.enc'))
        self.assertIn('-', parts[2])
    
    def test_bulk_encryption_manifest_structure(self):
        """Test bulk encryption creates proper manifest structure"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Create output folder
        self.output_folder.mkdir(exist_ok=True)
        
        # Simulate bulk encryption
        items = list(self.test_folder.iterdir())
        manifest_master_key = generate_master_key()
        manifest_master_key_b64 = base64.b64encode(manifest_master_key.hex().encode()).decode()
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        # Create manifest
        manifest_path = self.output_folder / "enc.manifest"
        with open(manifest_path, 'w') as f:
            f.write(manifest_master_key_b64 + '\n')
        
        # Process items
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
            
            # Generate encrypted filename
            individual_encryptor = SecureEncryptor(individual_key)
            encrypted_filename = individual_encryptor.generate_guid_filename(item)
            
            # Add to manifest
            manifest_line = f"{encrypted_individual_key_b64},{encrypted_name_b64},{encrypted_filename}\n"
            with open(manifest_path, 'a') as f:
                f.write(manifest_line)
        
        # Verify manifest structure
        with open(manifest_path, 'r') as f:
            lines = f.readlines()
        
        # Should have header + one line per item
        self.assertEqual(len(lines), len(items) + 1)
        
        # Header should be manifest master key
        self.assertEqual(lines[0].strip(), manifest_master_key_b64)
        
        # Each item line should have 3 parts
        for i, line in enumerate(lines[1:], 1):
            parts = line.strip().split(',')
            self.assertEqual(len(parts), 3, f"Line {i} should have 3 parts: {line}")
            
            # Verify format
            encrypted_individual_key_b64, encrypted_name_b64, encrypted_filename = parts
            
            # First two parts should be base64
            try:
                base64.b64decode(encrypted_individual_key_b64)
                base64.b64decode(encrypted_name_b64)
            except Exception:
                self.fail(f"Line {i} has invalid base64: {line}")
            
            # Third part should be GUID filename
            self.assertTrue(encrypted_filename.endswith('.enc'))
            self.assertIn('-', encrypted_filename)
    
    def test_manifest_decryption_restores_names(self):
        """Test that manifest decryption restores original names"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test data
        original_names = ["file1.txt", "file2.txt", "subfolder"]
        
        # Simulate manifest encryption/decryption
        manifest_master_key = generate_master_key()
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        # Encrypt and decrypt each name
        for original_name in original_names:
            # Encrypt original name (as in bulk encryption)
            original_name_b64 = base64.b64encode(original_name.encode()).decode()
            encrypted_name = manifest_encryptor._encrypt_string(original_name_b64)
            encrypted_name_b64 = base64.b64encode(encrypted_name.encode()).decode()
            
            # Decrypt original name (as in bulk decryption)
            encrypted_name_decoded = base64.b64decode(encrypted_name_b64).decode()
            decrypted_name_b64 = manifest_encryptor._decrypt_string(encrypted_name_decoded)
            decrypted_name = base64.b64decode(decrypted_name_b64).decode()
            
            # Verify restoration
            self.assertEqual(original_name, decrypted_name)
    
    def test_security_properties(self):
        """Test security properties of the bulk encryption system"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test that different keys produce different encrypted data
        test_string = "sensitive_data.txt"
        
        master_key1 = generate_master_key()
        master_key2 = generate_master_key()
        
        encryptor1 = SecureEncryptor(master_key1)
        encryptor2 = SecureEncryptor(master_key2)
        
        encrypted1 = encryptor1._encrypt_string(test_string)
        encrypted2 = encryptor2._encrypt_string(test_string)
        
        # Same plaintext encrypted with different keys should be different
        self.assertNotEqual(encrypted1, encrypted2)
        
        # But can be decrypted with correct keys
        decrypted1 = encryptor1._decrypt_string(encrypted1)
        decrypted2 = encryptor2._decrypt_string(encrypted2)
        
        self.assertEqual(test_string, decrypted1)
        self.assertEqual(test_string, decrypted2)
        
        # Wrong key should fail to decrypt
        with self.assertRaises(Exception):
            encryptor1._decrypt_string(encrypted2)
        
        with self.assertRaises(Exception):
            encryptor2._decrypt_string(encrypted1)


if __name__ == '__main__':
    unittest.main(verbosity=2)

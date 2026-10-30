#!/usr/bin/env python3
"""
Comprehensive unit tests for bulk encryption functionality
"""

import unittest
import tempfile
import shutil
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock

from encrypt import SecureEncryptor, generate_master_key
from encrypt_gui import EncryptionGUI


class TestBulkEncryption(unittest.TestCase):
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
                self.assertIn("=", encrypted)  # Base64 padding
    
    def test_bulk_encryption_workflow(self):
        """Test complete bulk encryption workflow"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test items to encrypt
        items = list(self.test_folder.iterdir())
        
        # Simulate bulk encryption
        manifest_master_key = generate_master_key()
        manifest_master_key_b64 = base64.b64encode(manifest_master_key.hex().encode()).decode()
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        # Create output folder and manifest
        self.output_folder.mkdir(exist_ok=True)
        manifest_path = self.output_folder / "enc.manifest"
        
        # Write manifest header
        with open(manifest_path, 'w') as f:
            f.write(manifest_master_key_b64 + '\n')
        
        # Encrypt each item
        encrypted_files = []
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
            
            encrypted_files.append(encrypted_filename)
            
            # Add to manifest
            manifest_line = f"{encrypted_individual_key_b64},{encrypted_name_b64},{encrypted_filename}\n"
            with open(manifest_path, 'a') as f:
                f.write(manifest_line)
        
        # Verify results
        self.assertTrue(manifest_path.exists())
        self.assertEqual(len(encrypted_files), len(items))
        
        # Verify all encrypted files exist
        for enc_file in encrypted_files:
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
    
    def test_bulk_decryption_workflow(self):
        """Test complete bulk decryption workflow"""
        # First perform encryption
        self.test_bulk_encryption_workflow()
        
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
    
    def test_folder_zip_encryption(self):
        """Test folder zipping before encryption"""
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test folder encryption
        output_path = self.temp_dir / "encrypted_folder.enc"
        encryptor.encrypt_file(self.test_folder, output_path, use_guid_filename=True)
        
        # Verify encrypted file exists
        self.assertTrue(output_path.exists())
        
        # Verify it's different from original
        self.assertNotEqual(output_path.read_bytes(), b"")
        
        # Test decryption
        decrypt_output = self.temp_dir / "decrypted_folder"
        decrypt_output.mkdir(exist_ok=True)
        
        encryptor.decrypt_file(output_path, decrypt_output)
        
        # Verify folder structure is restored
        restored_folder = decrypt_output / self.test_folder.name
        self.assertTrue(restored_folder.is_dir())
        
        # Verify files are restored
        for original_file in self.test_folder.glob('*'):
            restored_file = restored_folder / original_file.name
            if original_file.is_file():
                self.assertTrue(restored_file.exists())
                self.assertEqual(original_file.read_text(), restored_file.read_text())


class TestBulkEncryptionGUI(unittest.TestCase):
    """Test bulk encryption GUI components"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create test folder with files
        self.test_folder = self.temp_dir / "gui_test"
        self.test_folder.mkdir()
        
        (self.test_folder / "file1.txt").write_text("Test content")
        (self.test_folder / "file2.txt").write_text("More content")
        
        subfolder = self.test_folder / "subfolder"
        subfolder.mkdir()
        (subfolder / "nested.txt").write_text("Nested content")
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('tkinter.Tk')
    def test_gui_initialization(self, mock_tk):
        """Test GUI initialization"""
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        gui = EncryptionGUI(mock_root)
        
        # Verify notebook is created
        self.assertTrue(hasattr(gui, 'notebook'))
        
        # Verify bulk encryption variables
        self.assertTrue(hasattr(gui, 'bulk_folder_path'))
        self.assertTrue(hasattr(gui, 'bulk_file_vars'))
        self.assertTrue(hasattr(gui, 'bulk_files'))
    
    @patch('tkinter.Tk')
    @patch('tkinter.filedialog.askdirectory')
    def test_browse_bulk_folder(self, mock_askdirectory, mock_tk):
        """Test folder browsing functionality"""
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        mock_askdirectory.return_value = str(self.test_folder)
        
        gui = EncryptionGUI(mock_root)
        gui.bulk_folder_entry = MagicMock()
        gui.load_bulk_files = MagicMock()
        
        gui.browse_bulk_folder()
        
        # Verify folder was selected and files loaded
        gui.bulk_folder_entry.delete.assert_called()
        gui.bulk_folder_entry.insert.assert_called_with(0, str(self.test_folder))
        gui.load_bulk_files.assert_called_with(str(self.test_folder))
    
    @patch('tkinter.Tk')
    def test_load_bulk_files(self, mock_tk):
        """Test loading files from folder"""
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        gui = EncryptionGUI(mock_root)
        gui.bulk_scrollable_frame = MagicMock()
        gui.bulk_progress_var = MagicMock()
        
        gui.load_bulk_files(str(self.test_folder))
        
        # Verify folder path is set
        self.assertEqual(gui.bulk_folder_path, self.test_folder)
        
        # Verify files are loaded
        self.assertEqual(len(gui.bulk_files), 3)  # 2 files + 1 folder
        
        # Verify alphanumeric sorting
        names = [item.name for item in gui.bulk_files]
        self.assertEqual(names, sorted(names, key=str.lower))
        
        # Verify progress is updated
        gui.bulk_progress_var.set.assert_called_with("Found 3 items")
    
    @patch('tkinter.Tk')
    def test_update_encrypt_button(self, mock_tk):
        """Test encrypt button state updates"""
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        gui = EncryptionGUI(mock_root)
        gui.bulk_encrypt_button = MagicMock()
        gui.bulk_progress_var = MagicMock()
        
        # Mock file variables
        gui.bulk_file_vars = {
            'file1.txt': MagicMock(get=lambda: True),
            'file2.txt': MagicMock(get=lambda: False),
            'subfolder': MagicMock(get=lambda: True)
        }
        gui.bulk_files = [MagicMock(name=name) for name in ['file1.txt', 'file2.txt', 'subfolder']]
        
        gui.update_encrypt_button()
        
        # Verify button is enabled when items selected
        gui.bulk_encrypt_button.config.assert_called_with(state="normal")
        gui.bulk_progress_var.set.assert_called_with("2 of 3 items selected")
        
        # Test with no selections
        for var in gui.bulk_file_vars.values():
            var.get = lambda: False
        
        gui.update_encrypt_button()
        gui.bulk_encrypt_button.config.assert_called_with(state="disabled")
        gui.bulk_progress_var.set.assert_called_with("No files selected (3 items available)")
    
    @patch('tkinter.Tk')
    def test_select_all_deselect_all(self, mock_tk):
        """Test select all and deselect all functionality"""
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        gui = EncryptionGUI(mock_root)
        gui.bulk_file_vars = {
            'file1.txt': MagicMock(),
            'file2.txt': MagicMock(),
            'subfolder': MagicMock()
        }
        gui.update_encrypt_button = MagicMock()
        
        # Test select all
        gui.bulk_select_all()
        for var in gui.bulk_file_vars.values():
            var.set.assert_called_with(True)
        gui.update_encrypt_button.assert_called()
        
        # Test deselect all
        gui.bulk_deselect_all()
        for var in gui.bulk_file_vars.values():
            var.set.assert_called_with(False)
        gui.update_encrypt_button.assert_called()


class TestBulkEncryptionIntegration(unittest.TestCase):
    """Integration tests for bulk encryption"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create realistic test data
        self.source_folder = self.temp_dir / "documents"
        self.source_folder.mkdir()
        
        # Create various file types
        files_content = {
            "report.pdf": "PDF content here",
            "presentation.pptx": "PowerPoint content",
            "data.csv": "col1,col2\nval1,val2",
            "notes.txt": "Meeting notes",
            "image.jpg": "JPEG binary data simulation"
        }
        
        for filename, content in files_content.items():
            (self.source_folder / filename).write_text(content)
        
        # Create subfolders
        projects = self.source_folder / "projects"
        projects.mkdir()
        (projects / "project1.docx").write_text("Document content")
        (projects / "project2.xlsx").write_text("Spreadsheet content")
        
        finance = self.source_folder / "finance"
        finance.mkdir()
        (finance / "budget.xlsx").write_text("Budget data")
        (finance / "expenses.csv").write_text("date,amount\n2024-01-01,100")
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_bulk_encryption_decryption(self):
        """Test complete end-to-end workflow"""
        # Setup
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        output_folder = self.source_folder.parent / "documents_enc"
        output_folder.mkdir(exist_ok=True)
        
        # Bulk encryption
        manifest_master_key = generate_master_key()
        manifest_master_key_b64 = base64.b64encode(manifest_master_key.hex().encode()).decode()
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        manifest_path = output_folder / "enc.manifest"
        with open(manifest_path, 'w') as f:
            f.write(manifest_master_key_b64 + '\n')
        
        # Encrypt all items
        items = sorted(self.source_folder.iterdir(), key=lambda x: x.name.lower())
        encrypted_mapping = {}
        
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
            output_path = output_folder / encrypted_filename
            
            if item.is_dir():
                individual_encryptor.encrypt_file(item, output_path, use_guid_filename=True)
            else:
                individual_encryptor.encrypt_file(item, output_path, use_guid_filename=True)
            
            encrypted_mapping[item.name] = encrypted_filename
            
            # Add to manifest
            manifest_line = f"{encrypted_individual_key_b64},{encrypted_name_b64},{encrypted_filename}\n"
            with open(manifest_path, 'a') as f:
                f.write(manifest_line)
        
        # Verify encryption
        self.assertTrue(manifest_path.exists())
        self.assertEqual(len(encrypted_mapping), len(items))
        
        for original_name, encrypted_name in encrypted_mapping.items():
            self.assertTrue((output_folder / encrypted_name).exists())
        
        # Bulk decryption
        decrypt_output = self.temp_dir / "restored_documents"
        decrypt_output.mkdir(exist_ok=True)
        
        with open(manifest_path, 'r') as f:
            lines = f.readlines()
        
        manifest_master_key_hex = base64.b64decode(lines[0].strip()).decode()
        manifest_master_key = bytes.fromhex(manifest_master_key_hex)
        manifest_encryptor = SecureEncryptor(manifest_master_key)
        
        restored_items = []
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
            restored_items.append(original_name)
        
        # Verify complete restoration
        self.assertEqual(set(restored_items), set([item.name for item in items]))
        
        # Verify content integrity
        for original_name in restored_items:
            original_path = self.source_folder / original_name
            restored_path = decrypt_output / original_name
            
            if original_path.is_file():
                self.assertEqual(original_path.read_text(), restored_path.read_text())
            else:
                self.assertTrue(restored_path.is_dir())
                # Verify subfolder contents
                for sub_item in original_path.glob('*'):
                    restored_sub = restored_path / sub_item.name
                    self.assertEqual(sub_item.read_text(), restored_sub.read_text())
        
        # Verify folder structure is identical
        original_structure = self._get_folder_structure(self.source_folder)
        restored_structure = self._get_folder_structure(decrypt_output)
        self.assertEqual(original_structure, restored_structure)
    
    def _get_folder_structure(self, path):
        """Get recursive folder structure for comparison"""
        structure = {}
        for item in path.glob('*'):
            if item.is_file():
                structure[item.name] = item.read_text()
            else:
                structure[item.name] = self._get_folder_structure(item)
        return structure


if __name__ == '__main__':
    unittest.main(verbosity=2)

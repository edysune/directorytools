#!/usr/bin/env python3
"""
Test script for folder encryption functionality
Verifies folder zipping and encryption workflows
"""

import os
import tempfile
import shutil
from pathlib import Path
from encrypt import SecureEncryptor, generate_master_key


def create_test_folder(folder_path: Path) -> None:
    """Create a test folder with various files and subfolders"""
    folder_path.mkdir(parents=True, exist_ok=True)
    
    # Create some test files
    (folder_path / "file1.txt").write_text("This is file 1 content")
    (folder_path / "file2.txt").write_text("This is file 2 content with more text")
    
    # Create subfolder
    subfolder = folder_path / "subfolder"
    subfolder.mkdir()
    
    (subfolder / "nested_file.txt").write_text("This is a nested file")
    
    # Create another subfolder
    subfolder2 = folder_path / "another_subfolder"
    subfolder2.mkdir()
    
    (subfolder2 / "deep_file.txt").write_text("This file is in another subfolder")


def verify_folder_structure(original_folder: Path, extracted_folder: Path) -> bool:
    """Verify that the extracted folder matches the original structure"""
    try:
        # Check same files exist
        original_files = set(original_folder.rglob('*'))
        extracted_files = set(extracted_folder.rglob('*'))
        
        if len(original_files) != len(extracted_files):
            print(f"File count mismatch: {len(original_files)} vs {len(extracted_files)}")
            return False
        
        # Check file contents match
        for original_file in original_files:
            if original_file.is_file():
                # Calculate relative path
                rel_path = original_file.relative_to(original_folder)
                extracted_file = extracted_folder / rel_path
                
                if not extracted_file.exists():
                    print(f"Missing file: {rel_path}")
                    return False
                
                if original_file.read_bytes() != extracted_file.read_bytes():
                    print(f"Content mismatch: {rel_path}")
                    return False
        
        return True
    
    except Exception as e:
        print(f"Error during verification: {e}")
        return False


def test_folder_encryption():
    """Test folder encryption and decryption"""
    print("Testing folder encryption/decryption...")
    
    # Create temporary test folder
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_folder = temp_path / "test_folder"
        encrypted_file = temp_path / "test_folder.enc"
        extracted_folder = temp_path / "extracted_folder"
        
        try:
            # Create test folder structure
            create_test_folder(test_folder)
            
            # Generate master key and encrypt folder
            master_key = generate_master_key()
            encryptor = SecureEncryptor(master_key)
            
            print(f"Created test folder with {len(list(test_folder.rglob('*')))} items")
            
            # Encrypt folder
            encryptor.encrypt_file(test_folder, encrypted_file)
            assert encrypted_file.exists(), "Encrypted file not created"
            
            print(f"Encrypted folder to {encrypted_file}")
            print(f"Encrypted file size: {encrypted_file.stat().st_size} bytes")
            
            # Decrypt folder
            encryptor.decrypt_file(encrypted_file, extracted_folder)
            assert extracted_folder.exists(), "Extracted folder not created"
            
            print(f"Decrypted to {extracted_folder}")
            
            # Verify folder structure and contents
            if verify_folder_structure(test_folder, extracted_folder):
                print("Folder structure and contents verified successfully")
            else:
                raise AssertionError("Folder verification failed")
            
            print("Folder encryption/decryption test passed")
            return True
            
        except Exception as e:
            print(f"Folder encryption test failed: {e}")
            return False


def test_mixed_file_folder():
    """Test that regular files still work alongside folder encryption"""
    print("Testing mixed file and folder operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test_file.txt"
        test_folder = temp_path / "test_folder"
        encrypted_file = temp_path / "test_file.enc"
        encrypted_folder = temp_path / "test_folder.enc"
        decrypted_file = temp_path / "decrypted_file.txt"
        decrypted_folder = temp_path / "decrypted_folder"
        
        try:
            # Create test file and folder
            test_file.write_text("This is a test file")
            create_test_folder(test_folder)
            
            # Generate master key
            master_key = generate_master_key()
            encryptor = SecureEncryptor(master_key)
            
            # Encrypt file
            encryptor.encrypt_file(test_file, encrypted_file)
            
            # Encrypt folder
            encryptor.encrypt_file(test_folder, encrypted_folder)
            
            # Decrypt file
            encryptor.decrypt_file(encrypted_file, decrypted_file)
            
            # Decrypt folder
            encryptor.decrypt_file(encrypted_folder, decrypted_folder)
            
            # Verify file content
            if test_file.read_text() != decrypted_file.read_text():
                raise AssertionError("File content mismatch")
            
            # Verify folder structure
            if not verify_folder_structure(test_folder, decrypted_folder):
                raise AssertionError("Folder structure mismatch")
            
            print("Mixed file and folder operations test passed")
            return True
            
        except Exception as e:
            print(f"Mixed operations test failed: {e}")
            return False


def test_large_folder():
    """Test encryption of a folder with many files"""
    print("Testing large folder encryption...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        large_folder = temp_path / "large_folder"
        encrypted_file = temp_path / "large_folder.enc"
        extracted_folder = temp_path / "extracted_large"
        
        try:
            # Create folder with many files
            large_folder.mkdir()
            
            # Create 50 test files
            for i in range(50):
                file_path = large_folder / f"file_{i:03d}.txt"
                file_path.write_text(f"Content of file {i}\n" * 100)  # Larger content
            
            # Create subfolders with files
            for subfolder_num in range(5):
                subfolder = large_folder / f"subfolder_{subfolder_num}"
                subfolder.mkdir()
                
                for file_num in range(10):
                    file_path = subfolder / f"subfile_{file_num:03d}.txt"
                    file_path.write_text(f"Subfolder {subfolder_num} file {file_num}\n" * 50)
            
            total_files = len(list(large_folder.rglob('*')))
            print(f"Created large folder with {total_files} items")
            
            # Encrypt and decrypt
            master_key = generate_master_key()
            encryptor = SecureEncryptor(master_key)
            
            encryptor.encrypt_file(large_folder, encrypted_file)
            encryptor.decrypt_file(encrypted_file, extracted_folder)
            
            # Verify
            if verify_folder_structure(large_folder, extracted_folder):
                print("Large folder encryption test passed")
                return True
            else:
                raise AssertionError("Large folder verification failed")
                
        except Exception as e:
            print(f"Large folder test failed: {e}")
            return False


def run_all_folder_tests():
    """Run all folder-related tests"""
    print("Running folder encryption tests...\n")
    
    tests = [
        test_folder_encryption,
        test_mixed_file_folder,
        test_large_folder
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"Failed: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"Exception in {test.__name__}: {e}")
        
        print()  # Add spacing between tests
    
    print(f"Folder Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All folder tests passed! The tool now supports folder encryption.")
        return True
    else:
        print("Some folder tests failed!")
        return False


if __name__ == "__main__":
    success = run_all_folder_tests()
    exit(0 if success else 1)

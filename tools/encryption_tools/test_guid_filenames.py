#!/usr/bin/env python3
"""
Test script for GUID filename functionality
Verifies GUID generation, filename storage, and restoration with conflict handling
"""

import os
import tempfile
from pathlib import Path
from encrypt import SecureEncryptor, generate_master_key


def test_guid_filename_generation():
    """Test GUID filename generation"""
    print("Testing GUID filename generation...")
    
    # Create test file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
        temp_file.write(b"Test content for GUID filename")
        input_path = Path(temp_file.name)
    
    output_path = None
    decrypt_output = None
    
    try:
        # Generate master key and encrypt with GUID
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        # Test GUID generation
        guid_filename = encryptor.generate_guid_filename(input_path)
        print(f"Generated GUID filename: {guid_filename}")
        
        # Verify GUID format (should be UUID + original extension)
        if len(guid_filename) > 30 and guid_filename.count('-') == 4 and guid_filename.endswith('.txt'):
            print("✓ GUID filename format is correct")
        else:
            print("✗ GUID filename format is incorrect")
            return False
        
        # Test encryption with GUID
        output_path = input_path.parent / "test_output.enc"
        encryptor.encrypt_file(input_path, output_path, use_guid_filename=True)
        
        # When using GUID, the actual file is created with GUID name in same directory
        actual_encrypted_path = input_path.parent / guid_filename
        if actual_encrypted_path.exists():
            print("✓ Encrypted file created with GUID filename")
        else:
            print("✗ Encrypted file not created")
            return False
        
        # Test decryption restores original name
        decrypt_output = input_path.parent / "decrypted_test.txt"
        encryptor.decrypt_file(actual_encrypted_path, decrypt_output)
        
        if decrypt_output.exists():
            print("✓ Decrypted file restored with original name")
        else:
            print("✗ Decrypted file not restored")
            return False
        
        # Verify content
        if decrypt_output.read_bytes() == b"Test content for GUID filename":
            print("✓ File content matches original")
        else:
            print("✗ File content mismatch")
            return False
        
        return True
        
    finally:
        # Cleanup
        actual_encrypted_path = input_path.parent / encryptor.generate_guid_filename(input_path)
        for path in [input_path, actual_encrypted_path, decrypt_output]:
            if path and path.exists():
                path.unlink()


def test_filename_conflict_handling():
    """Test filename conflict resolution with (X) suffix"""
    print("\nTesting filename conflict handling...")
    
    master_key = generate_master_key()
    encryptor = SecureEncryptor(master_key)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create original file
        original_file = temp_path / "test_file.txt"
        original_file.write_text("Original content")
        
        # Encrypt and decrypt first time
        encrypted_file = temp_path / "encrypted.enc"
        encryptor.encrypt_file(original_file, encrypted_file, use_guid_filename=True)
        
        # When using GUID, the actual file has GUID name
        actual_encrypted_file = temp_path / encryptor.generate_guid_filename(original_file)
        
        # Decrypt first time (should create original name)
        first_decrypted = temp_path / "output"
        encryptor.decrypt_file(actual_encrypted_file, first_decrypted)
        
        expected_file = temp_path / "test_file.txt"
        if expected_file.exists():
            print("✓ First decryption created original filename")
        else:
            print("✗ First decryption failed")
            return False
        
        # Create conflict by manually creating file with same name
        conflict_file = temp_path / "test_file.txt"
        conflict_file.write_text("Conflict content")
        
        # Decrypt second time (should add (1) suffix)
        second_decrypted = temp_path / "output2"
        encryptor.decrypt_file(actual_encrypted_file, second_decrypted)
        
        conflict_resolved = temp_path / "test_file (1).txt"
        if conflict_resolved.exists():
            print("✓ Filename conflict resolved with (1) suffix")
        else:
            print("✗ Filename conflict not resolved")
            return False
        
        # Test multiple conflicts
        conflict_file2 = temp_path / "test_file (1).txt"
        conflict_file2.write_text("Another conflict")
        
        third_decrypted = temp_path / "output3"
        encryptor.decrypt_file(encrypted_file, third_decrypted)
        
        conflict_resolved2 = temp_path / "test_file (2).txt"
        if conflict_resolved2.exists():
            print("✓ Multiple conflicts resolved with (2) suffix")
        else:
            print("✗ Multiple conflicts not resolved")
            return False
        
        return True


def test_folder_guid_filenames():
    """Test GUID filenames with folders"""
    print("\nTesting GUID filenames with folders...")
    
    master_key = generate_master_key()
    encryptor = SecureEncryptor(master_key)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test folder
        test_folder = temp_path / "test_folder"
        test_folder.mkdir()
        
        (test_folder / "file1.txt").write_text("File 1 content")
        (test_folder / "file2.txt").write_text("File 2 content")
        
        subfolder = test_folder / "subfolder"
        subfolder.mkdir()
        (subfolder / "nested.txt").write_text("Nested content")
        
        # Encrypt folder with GUID filename
        encrypted_file = temp_path / "folder_output.enc"
        encryptor.encrypt_file(test_folder, encrypted_file, use_guid_filename=True)
        
        if encrypted_file.exists():
            print("✓ Folder encrypted with GUID filename")
        else:
            print("✗ Folder encryption failed")
            return False
        
        # Decrypt folder (should restore original name)
        decrypt_output = temp_path / "output_folder"
        encryptor.decrypt_file(encrypted_file, decrypt_output)
        
        restored_folder = decrypt_output / "test_folder"
        if restored_folder.exists() and restored_folder.is_dir():
            print("✓ Folder decrypted with original name")
        else:
            print("✗ Folder decryption failed")
            return False
        
        # Verify folder structure
        restored_files = list(restored_folder.rglob('*'))
        expected_files = [
            restored_folder / "file1.txt",
            restored_folder / "file2.txt", 
            restored_folder / "subfolder" / "nested.txt"
        ]
        
        if all(path.exists() for path in expected_files):
            print("✓ Folder structure preserved")
        else:
            print("✗ Folder structure not preserved")
            return False
        
        return True


def test_mixed_operations():
    """Test mixed operations with and without GUID"""
    print("\nTesting mixed operations...")
    
    master_key = generate_master_key()
    encryptor = SecureEncryptor(master_key)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test files
        file1 = temp_path / "normal_file.txt"
        file1.write_text("Normal encryption")
        
        file2 = temp_path / "guid_file.txt"
        file2.write_text("GUID encryption")
        
        # Encrypt one normally, one with GUID
        normal_encrypted = temp_path / "normal_encrypted.enc"
        guid_encrypted = temp_path / "guid_encrypted.enc"
        
        encryptor.encrypt_file(file1, normal_encrypted, use_guid_filename=False)
        encryptor.encrypt_file(file2, guid_encrypted, use_guid_filename=True)
        
        if normal_encrypted.exists() and guid_encrypted.exists():
            print("✓ Both encryption methods worked")
        else:
            print("✗ Mixed encryption failed")
            return False
        
        # Decrypt both
        decrypt_dir = temp_path / "decrypted"
        decrypt_dir.mkdir()
        
        encryptor.decrypt_file(normal_encrypted, decrypt_dir)
        encryptor.decrypt_file(guid_encrypted, decrypt_dir)
        
        restored_normal = decrypt_dir / "normal_file.txt"
        restored_guid = decrypt_dir / "guid_file.txt"
        
        if restored_normal.exists() and restored_guid.exists():
            print("✓ Both files restored correctly")
        else:
            print("✗ File restoration failed")
            return False
        
        return True


def run_all_guid_tests():
    """Run all GUID filename tests"""
    print("Running GUID filename tests...\n")
    
    tests = [
        test_guid_filename_generation,
        test_filename_conflict_handling,
        test_folder_guid_filenames,
        test_mixed_operations
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
    
    print(f"GUID Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All GUID tests passed! The feature works correctly.")
        return True
    else:
        print("Some GUID tests failed!")
        return False


if __name__ == "__main__":
    success = run_all_guid_tests()
    exit(0 if success else 1)

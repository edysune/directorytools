#!/usr/bin/env python3
"""
Test script for the encryption tool
Verifies encrypt/decrypt workflows
"""

import os
import tempfile
from pathlib import Path
from encrypt import SecureEncryptor, generate_master_key, derive_master_key_from_password


def test_basic_encryption():
    """Test basic encryption/decryption workflow"""
    print("Testing basic encryption/decryption...")
    
    # Generate test data
    test_data = b"This is a test file with some sensitive data."
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(delete=False) as temp_input:
        temp_input.write(test_data)
        input_path = Path(temp_input.name)
    
    output_path = Path(temp_input.name + ".enc")
    decrypted_path = Path(temp_input.name + ".dec")
    
    try:
        # Generate master key and encrypt
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        
        encryptor.encrypt_file(input_path, output_path)
        assert output_path.exists(), "Encrypted file not created"
        
        # Decrypt and verify
        encryptor.decrypt_file(output_path, decrypted_path)
        assert decrypted_path.exists(), "Decrypted file not created"
        
        # Verify content matches
        decrypted_data = decrypted_path.read_bytes()
        assert decrypted_data == test_data, "Decrypted data doesn't match original"
        
        print("✓ Basic encryption/decryption test passed")
        
    finally:
        # Cleanup
        for path in [input_path, output_path, decrypted_path]:
            if path.exists():
                path.unlink()
    
    return True


def test_password_derived_key():
    """Test password-derived master key"""
    print("Testing password-derived key...")
    
    # Generate test data
    test_data = b"Password-protected test data."
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(delete=False) as temp_input:
        temp_input.write(test_data)
        input_path = Path(temp_input.name)
    
    output_path = Path(temp_input.name + ".enc")
    decrypted_path = Path(temp_input.name + ".dec")
    
    try:
        # Use password-derived key
        password = "test_password_123"
        master_key, salt = derive_master_key_from_password(password)
        
        encryptor = SecureEncryptor(master_key)
        encryptor.encrypt_file(input_path, output_path)
        
        # Decrypt with same derived key
        encryptor.decrypt_file(output_path, decrypted_path)
        
        # Verify content
        decrypted_data = decrypted_path.read_bytes()
        assert decrypted_data == test_data, "Password-derived key test failed"
        
        print("✓ Password-derived key test passed")
        
    finally:
        # Cleanup
        for path in [input_path, output_path, decrypted_path]:
            if path.exists():
                path.unlink()
    
    return True


def test_multiple_files():
    """Test encrypting multiple files with same master key"""
    print("Testing multiple files with same master key...")
    
    master_key = generate_master_key()
    encryptor = SecureEncryptor(master_key)
    
    # Create test files with different content
    test_files = []
    for i in range(3):
        test_data = f"Test file {i} content: {os.urandom(16).hex()}".encode()
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_input:
            temp_input.write(test_data)
            input_path = Path(temp_input.name)
        
        output_path = Path(temp_input.name + ".enc")
        decrypted_path = Path(temp_input.name + ".dec")
        
        # Encrypt
        encryptor.encrypt_file(input_path, output_path)
        
        # Decrypt
        encryptor.decrypt_file(output_path, decrypted_path)
        
        # Verify
        decrypted_data = decrypted_path.read_bytes()
        assert decrypted_data == test_data, f"File {i} decryption failed"
        
        test_files.extend([input_path, output_path, decrypted_path])
    
    print("✓ Multiple files test passed")
    
    # Cleanup
    for path in test_files:
        if path.exists():
            path.unlink()
    
    return True


def test_wrong_key():
    """Test that wrong master key fails decryption"""
    print("Testing wrong key detection...")
    
    test_data = b"Data that should not decrypt with wrong key"
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_input:
        temp_input.write(test_data)
        input_path = Path(temp_input.name)
    
    output_path = Path(temp_input.name + ".enc")
    decrypted_path = Path(temp_input.name + ".dec")
    
    try:
        # Encrypt with one key
        master_key1 = generate_master_key()
        encryptor1 = SecureEncryptor(master_key1)
        encryptor1.encrypt_file(input_path, output_path)
        
        # Try to decrypt with different key
        master_key2 = generate_master_key()
        encryptor2 = SecureEncryptor(master_key2)
        
        try:
            encryptor2.decrypt_file(output_path, decrypted_path)
            assert False, "Decryption should have failed with wrong key"
        except ValueError as e:
            assert "Invalid authentication tag" in str(e), "Expected authentication error"
        
        print("✓ Wrong key detection test passed")
        
    finally:
        # Cleanup
        for path in [input_path, output_path, decrypted_path]:
            if path.exists():
                path.unlink()
    
    return True


def test_file_tampering():
    """Test detection of file tampering"""
    print("Testing file tampering detection...")
    
    test_data = b"Original data"
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_input:
        temp_input.write(test_data)
        input_path = Path(temp_input.name)
    
    output_path = Path(temp_input.name + ".enc")
    decrypted_path = Path(temp_input.name + ".dec")
    
    try:
        # Encrypt
        master_key = generate_master_key()
        encryptor = SecureEncryptor(master_key)
        encryptor.encrypt_file(input_path, output_path)
        
        # Tamper with encrypted file (flip a bit in ciphertext)
        encrypted_data = output_path.read_bytes()
        # Find ciphertext part (after salt+nonce=28 bytes)
        if len(encrypted_data) > 28:
            tampered_data = bytearray(encrypted_data)
            # Flip a bit in the ciphertext
            tampered_data[30] ^= 0x01
            output_path.write_bytes(tampered_data)
        
        # Try to decrypt tampered file
        try:
            encryptor.decrypt_file(output_path, decrypted_path)
            assert False, "Decryption should have failed with tampered file"
        except ValueError as e:
            assert "Invalid authentication tag" in str(e), "Expected authentication error"
        
        print("✓ File tampering detection test passed")
        
    finally:
        # Cleanup
        for path in [input_path, output_path, decrypted_path]:
            if path.exists():
                path.unlink()
    
    return True


def run_all_tests():
    """Run all tests"""
    print("Running encryption tool tests...\n")
    
    tests = [
        test_basic_encryption,
        test_password_derived_key,
        test_multiple_files,
        test_wrong_key,
        test_file_tampering
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} failed with exception: {e}")
    
    print(f"\nTest Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests passed! ✓")
        return True
    else:
        print("Some tests failed! ✗")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

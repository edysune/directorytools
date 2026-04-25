#!/usr/bin/env python3
"""
Simple test to verify GUID functionality works
"""

import tempfile
from pathlib import Path
from encrypt import SecureEncryptor, generate_master_key

def simple_test():
    print("Simple GUID functionality test...")
    
    # Create test file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
        temp_file.write(b"Test content")
        input_path = Path(temp_file.name)
    
    master_key = generate_master_key()
    encryptor = SecureEncryptor(master_key)
    
    try:
        # Test GUID generation
        guid_filename = encryptor.generate_guid_filename(input_path)
        print(f"✓ Generated GUID: {guid_filename}")
        
        # Test encryption with GUID
        output_path = input_path.parent / "test.enc"
        encryptor.encrypt_file(input_path, output_path, use_guid_filename=True)
        
        # Check actual encrypted file (use same GUID generation logic)
        actual_encrypted = input_path.parent / guid_filename
        if actual_encrypted.exists():
            print("✓ Encrypted file created with GUID name")
        else:
            print("✗ Encrypted file not found")
            # List all GUID files in directory
            guid_files = [f for f in input_path.parent.glob('*.txt') if '-' in f.name and len(f.name) > 30]
            print(f"Available GUID files: {guid_files}")
            return False
        
        # Test decryption
        decrypt_output = input_path.parent / "decrypted.txt"
        encryptor.decrypt_file(actual_encrypted, decrypt_output)
        
        if decrypt_output.exists():
            print("✓ File decrypted with original name")
        else:
            print("✗ Decrypted file not found")
            return False
        
        # Verify content
        if decrypt_output.read_bytes() == b"Test content":
            print("✓ Content matches original")
        else:
            print("✗ Content mismatch")
            return False
        
        print("✓ All tests passed!")
        return True
        
    finally:
        # Cleanup
        for path in [input_path, input_path.parent / "test.enc", 
                    input_path.parent / guid_filename, 
                    input_path.parent / "decrypted.txt"]:
            if path.exists():
                path.unlink()

if __name__ == "__main__":
    success = simple_test()
    exit(0 if success else 1)

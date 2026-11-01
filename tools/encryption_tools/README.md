# Secure AES-256 File Encryption Tool

A secure file encryption tool that uses AES-256-GCM with HKDF key derivation for maximum security. Supports both command-line and GUI interfaces.

## Features

- **AES-256-GCM Encryption**: Authenticated encryption prevents tampering
- **HKDF Key Derivation**: Each file gets a cryptographically unique key from one master key
- **Multiple Interfaces**: Both CLI and GUI for different use cases
- **Key Management**: Secure storage and retrieval of master keys
- **Password Support**: Option to derive master key from strong passwords

## Security Architecture

### Key Management Strategy
The tool uses a **master key + HKDF** approach:

1. **Single Master Key**: Generate one 256-bit master key (or derive from password)
2. **Unique Per-File Keys**: HKDF derives unique keys for each file using:
   - Master key (32 bytes)
   - Random salt (16 bytes per file)  
   - File-specific context info
3. **Authenticated Encryption**: AES-256-GCM provides confidentiality + integrity

### Benefits
- Only need to remember **one master key** for unlimited files
- Compromise of one file's key doesn't affect others
- No password brute-forcing (random master key option)
- Industry-standard cryptographic primitives

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make scripts executable
chmod +x encrypt.py encrypt_gui.py key_manager.py
```

## Usage

### Command Line Interface

#### Basic Usage
```bash
# Encrypt a file (will prompt for master key options)
python encrypt.py encrypt document.pdf document.pdf.enc

# Decrypt a file
python encrypt.py decrypt document.pdf.enc document.pdf

# Use password instead of random key
python encrypt.py encrypt document.pdf document.pdf.enc --password

# Provide master key directly (hex format)
python encrypt.py encrypt document.pdf document.pdf.enc --key <64-char-hex>
```

#### Key Management
```bash
# Generate and store a named key
python key_manager.py generate mykey --password

# List stored keys
python key_manager.py list

# Retrieve a stored key
python key_manager.py retrieve mykey --password

# Delete a stored key
python key_manager.py delete mykey
```

### GUI Interface

```bash
# Launch the GUI
python encrypt_gui.py
```

The GUI provides:
- Master key generation/entry
- File selection with browse dialogs
- Encrypt/decrypt operations
- Activity logging
- Status indicators

## File Format

Encrypted files use this format:
```
[salt(16)][nonce(12)][ciphertext][auth_tag(16)]
```

- **Salt**: Random per-file salt for HKDF
- **Nonce**: Random nonce for AES-GCM
- **Ciphertext**: Encrypted data
- **Auth Tag**: GCM authentication tag (16 bytes)

## Security Best Practices

### Master Key Security
1. **Random Keys**: Use generated random keys when possible
2. **Secure Storage**: Store keys in password managers or hardware tokens
3. **Backup**: Keep secure backups of master keys
4. **Rotation**: Consider periodic key rotation for long-term use

### Password Security (if used)
1. **Strong Passwords**: Use passwords with high entropy (12+ chars, mixed types)
2. **Unique Salts**: Each password derivation uses unique salt
3. **Memory Hard**: PBKDF2 with 100,000 iterations

### Operational Security
1. **Secure Deletion**: Securely delete original files after encryption
2. **File Permissions**: Use restrictive file permissions (600)
3. **Audit Logging**: Monitor encryption/decryption activities

## Examples

### Encrypting Multiple Files
```bash
# Generate master key once
MASTER_KEY=$(python -c "from encrypt import generate_master_key; print(generate_master_key().hex())")

# Encrypt multiple files with same master key
python encrypt.py encrypt file1.txt file1.txt.enc --key $MASTER_KEY
python encrypt.py encrypt file2.txt file2.txt.enc --key $MASTER_KEY
python encrypt.py encrypt file3.txt file3.txt.enc --key $MASTER_KEY

# Decrypt files
python encrypt.py decrypt file1.txt.enc file1.txt --key $MASTER_KEY
python encrypt.py decrypt file2.txt.enc file2.txt --key $MASTER_KEY
python encrypt.py decrypt file3.txt.enc file3.txt --key $MASTER_KEY
```

### Password-Based Workflow
```bash
# Encrypt with password
python encrypt.py encrypt sensitive.pdf sensitive.pdf.enc --password
# (enter password when prompted)

# Decrypt with password  
python encrypt.py decrypt sensitive.pdf.enc sensitive.pdf --password
# (enter same password)
```

## Dependencies

- **cryptography**: Cryptographic operations (AES, HKDF, PBKDF2)
- **tkinter**: GUI interface (usually included with Python)

## Security Notes

- This tool uses industry-standard cryptographic primitives
- AES-256-GCM provides authenticated encryption (confidentiality + integrity)
- HKDF ensures proper key separation between files
- Master key is never directly used for encryption
- Each file uses unique salt and nonce
- No key reuse vulnerabilities

## Limitations

- Not designed for streaming large files (loads entire file into memory)
- GUI requires tkinter (usually available with Python)
- Key storage uses local filesystem encryption (consider hardware security modules for high-value keys)

## License

This tool is provided for educational and legitimate security purposes only. Users are responsible for complying with applicable laws and regulations.

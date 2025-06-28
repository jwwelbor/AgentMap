---
sidebar_position: 4
title: Security Best Practices
description: Comprehensive security guidelines for AgentMap deployments including authentication, data protection, API security, and threat mitigation.
keywords: [AgentMap security, API security, authentication, data protection, secure agents, security best practices, threat mitigation]
---

# Security Best Practices for AgentMap

Security is paramount when deploying AI agent systems in production environments. This guide covers comprehensive security measures for protecting AgentMap deployments, data, and agent communications.

## Authentication and Authorization

### 1. API Key Management

```python
import os
import secrets
import hashlib
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import jwt

class SecureAPIKeyManager:
    def __init__(self):
        self.encryption_key = self.get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        self.api_keys = {}  # In production, use secure database
        
    def get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for API keys"""
        key_file = os.path.join(os.path.expanduser('~'), '.agentmap', 'encryption.key')
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Create new key
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            key = Fernet.generate_key()
            
            # Store securely with appropriate permissions
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Read/write for owner only
            
            return key
    
    def generate_api_key(self, user_id: str, permissions: list = None, expires_days: int = 90) -> str:
        """Generate secure API key with metadata"""
        
        # Generate cryptographically secure random key
        raw_key = secrets.token_urlsafe(32)
        
        # Create key metadata
        key_metadata = {
            'user_id': user_id,
            'permissions': permissions or ['read'],
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=expires_days)).isoformat(),
            'active': True
        }
        
        # Store encrypted metadata
        encrypted_metadata = self.cipher_suite.encrypt(
            json.dumps(key_metadata).encode()
        )
        
        # Hash the key for storage (never store raw keys)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        self.api_keys[key_hash] = encrypted_metadata
        
        return raw_key
    
    def validate_api_key(self, api_key: str) -> dict:
        """Validate API key and return metadata"""
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        encrypted_metadata = self.api_keys.get(key_hash)
        
        if not encrypted_metadata:
            raise ValueError("Invalid API key")
        
        # Decrypt metadata
        try:
            metadata_json = self.cipher_suite.decrypt(encrypted_metadata)
            metadata = json.loads(metadata_json.decode())
        except Exception:
            raise ValueError("Invalid API key metadata")
        
        # Check if key is active
        if not metadata.get('active', False):
            raise ValueError("API key has been revoked")
        
        # Check expiration
        expires_at = datetime.fromisoformat(metadata['expires_at'])
        if datetime.now() > expires_at:
            raise ValueError("API key has expired")
        
        return metadata
    
    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key"""
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        encrypted_metadata = self.api_keys.get(key_hash)
        
        if not encrypted_metadata:
            return False
        
        # Decrypt, modify, and re-encrypt metadata
        try:
            metadata_json = self.cipher_suite.decrypt(encrypted_metadata)
            metadata = json.loads(metadata_json.decode())
            metadata['active'] = False
            metadata['revoked_at'] = datetime.now().isoformat()
            
            new_encrypted_metadata = self.cipher_suite.encrypt(
                json.dumps(metadata).encode()
            )
            self.api_keys[key_hash] = new_encrypted_metadata
            
            return True
        except Exception:
            return False

class SecureAuthenticationAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.api_key_manager = SecureAPIKeyManager()
        self.jwt_secret = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key')
        self.session_timeout = 3600  # 1 hour
    
    def execute(self, input_data, context=None):
        """Authenticate requests and manage sessions"""
        
        auth_method = context.get('auth_method', 'api_key')
        
        if auth_method == 'api_key':
            return self.authenticate_with_api_key(input_data, context)
        elif auth_method == 'jwt':
            return self.authenticate_with_jwt(input_data, context)
        elif auth_method == 'oauth':
            return self.authenticate_with_oauth(input_data, context)
        else:
            return {'error': 'Unsupported authentication method', 'authenticated': False}
    
    def authenticate_with_api_key(self, input_data, context):
        """Authenticate using API key"""
        
        api_key = input_data.get('api_key') or context.get('api_key')
        
        if not api_key:
            return {'error': 'API key required', 'authenticated': False}
        
        try:
            metadata = self.api_key_manager.validate_api_key(api_key)
            
            return {
                'authenticated': True,
                'user_id': metadata['user_id'],
                'permissions': metadata['permissions'],
                'auth_method': 'api_key',
                'session_token': self.create_session_token(metadata['user_id'])
            }
            
        except ValueError as e:
            return {'error': str(e), 'authenticated': False}
    
    def authenticate_with_jwt(self, input_data, context):
        """Authenticate using JWT token"""
        
        token = input_data.get('token') or context.get('authorization', '').replace('Bearer ', '')
        
        if not token:
            return {'error': 'JWT token required', 'authenticated': False}
        
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            # Check token expiration
            if payload.get('exp', 0) < datetime.now().timestamp():
                return {'error': 'Token expired', 'authenticated': False}
            
            return {
                'authenticated': True,
                'user_id': payload.get('user_id'),
                'permissions': payload.get('permissions', []),
                'auth_method': 'jwt',
                'token_payload': payload
            }
            
        except jwt.InvalidTokenError as e:
            return {'error': f'Invalid token: {str(e)}', 'authenticated': False}
    
    def create_session_token(self, user_id: str) -> str:
        """Create session JWT token"""
        
        payload = {
            'user_id': user_id,
            'iat': datetime.now().timestamp(),
            'exp': (datetime.now() + timedelta(seconds=self.session_timeout)).timestamp(),
            'session_id': secrets.token_urlsafe(16)
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
```

### 2. Role-Based Access Control (RBAC)

```python
from enum import Enum
from typing import Set, Dict, List

class Permission(Enum):
    READ_AGENTS = "read_agents"
    WRITE_AGENTS = "write_agents"
    EXECUTE_WORKFLOWS = "execute_workflows"
    MANAGE_USERS = "manage_users"
    VIEW_LOGS = "view_logs"
    ADMIN_ACCESS = "admin_access"
    CREATE_API_KEYS = "create_api_keys"
    DELETE_DATA = "delete_data"

class Role:
    def __init__(self, name: str, permissions: Set[Permission]):
        self.name = name
        self.permissions = permissions
    
    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

class RBACManager:
    def __init__(self):
        self.roles = self._initialize_default_roles()
        self.user_roles = {}  # user_id -> set of role names
        
    def _initialize_default_roles(self) -> Dict[str, Role]:
        """Initialize default roles with permissions"""
        
        return {
            'viewer': Role('viewer', {
                Permission.READ_AGENTS,
                Permission.VIEW_LOGS
            }),
            'user': Role('user', {
                Permission.READ_AGENTS,
                Permission.EXECUTE_WORKFLOWS,
                Permission.VIEW_LOGS
            }),
            'developer': Role('developer', {
                Permission.READ_AGENTS,
                Permission.WRITE_AGENTS,
                Permission.EXECUTE_WORKFLOWS,
                Permission.VIEW_LOGS
            }),
            'admin': Role('admin', {
                Permission.READ_AGENTS,
                Permission.WRITE_AGENTS,
                Permission.EXECUTE_WORKFLOWS,
                Permission.MANAGE_USERS,
                Permission.VIEW_LOGS,
                Permission.ADMIN_ACCESS,
                Permission.CREATE_API_KEYS,
                Permission.DELETE_DATA
            })
        }
    
    def assign_role(self, user_id: str, role_name: str):
        """Assign role to user"""
        if role_name not in self.roles:
            raise ValueError(f"Role '{role_name}' does not exist")
        
        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()
        
        self.user_roles[user_id].add(role_name)
    
    def remove_role(self, user_id: str, role_name: str):
        """Remove role from user"""
        if user_id in self.user_roles:
            self.user_roles[user_id].discard(role_name)
    
    def user_has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has specific permission"""
        user_role_names = self.user_roles.get(user_id, set())
        
        for role_name in user_role_names:
            role = self.roles.get(role_name)
            if role and role.has_permission(permission):
                return True
        
        return False
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """Get all permissions for user"""
        permissions = set()
        user_role_names = self.user_roles.get(user_id, set())
        
        for role_name in user_role_names:
            role = self.roles.get(role_name)
            if role:
                permissions.update(role.permissions)
        
        return permissions

class SecureAuthorizationAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.rbac_manager = RBACManager()
    
    def execute(self, input_data, context=None):
        """Check authorization for requested action"""
        
        user_id = input_data.get('user_id')
        required_permission = input_data.get('permission')
        action = input_data.get('action')
        
        if not user_id or not required_permission:
            return {'authorized': False, 'error': 'Missing user_id or permission'}
        
        try:
            permission_enum = Permission(required_permission)
            has_permission = self.rbac_manager.user_has_permission(user_id, permission_enum)
            
            # Log authorization attempt
            self.log_authorization_attempt(user_id, action, required_permission, has_permission)
            
            return {
                'authorized': has_permission,
                'user_id': user_id,
                'permission': required_permission,
                'action': action
            }
            
        except ValueError:
            return {'authorized': False, 'error': f'Invalid permission: {required_permission}'}
    
    def log_authorization_attempt(self, user_id: str, action: str, permission: str, success: bool):
        """Log authorization attempts for security monitoring"""
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'action': action,
            'permission': permission,
            'authorized': success,
            'ip_address': self.get_client_ip(),
            'user_agent': self.get_user_agent()
        }
        
        # In production, send to security monitoring system
        self.logger.info(f"Authorization attempt: {log_entry}")
    
    def get_client_ip(self) -> str:
        """Get client IP address from request context"""
        # Implementation depends on your web framework
        return "127.0.0.1"  # Placeholder
    
    def get_user_agent(self) -> str:
        """Get client user agent from request context"""
        # Implementation depends on your web framework
        return "AgentMap-Client/1.0"  # Placeholder
```

## Data Protection and Encryption

### 1. Data Encryption

```python
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import secrets

class DataEncryptionService:
    def __init__(self):
        self.key_size = 32  # 256-bit key
        self.iv_size = 16   # 128-bit IV
        
    def generate_key(self, password: str, salt: bytes = None) -> bytes:
        """Generate encryption key from password"""
        
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.key_size,
            salt=salt,
            iterations=100000,
        )
        
        key = kdf.derive(password.encode())
        return key, salt
    
    def encrypt_data(self, data: str, password: str) -> dict:
        """Encrypt data using AES-256-GCM"""
        
        # Generate key and salt
        key, salt = self.generate_key(password)
        
        # Generate random IV
        iv = secrets.token_bytes(self.iv_size)
        
        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        
        # Encrypt data
        data_bytes = data.encode('utf-8')
        ciphertext = encryptor.update(data_bytes) + encryptor.finalize()
        
        # Get authentication tag
        auth_tag = encryptor.tag
        
        # Return encrypted data with metadata
        return {
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'iv': base64.b64encode(iv).decode(),
            'salt': base64.b64encode(salt).decode(),
            'auth_tag': base64.b64encode(auth_tag).decode(),
            'algorithm': 'AES-256-GCM'
        }
    
    def decrypt_data(self, encrypted_data: dict, password: str) -> str:
        """Decrypt AES-256-GCM encrypted data"""
        
        # Extract components
        ciphertext = base64.b64decode(encrypted_data['ciphertext'])
        iv = base64.b64decode(encrypted_data['iv'])
        salt = base64.b64decode(encrypted_data['salt'])
        auth_tag = base64.b64decode(encrypted_data['auth_tag'])
        
        # Regenerate key
        key, _ = self.generate_key(password, salt)
        
        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, auth_tag))
        decryptor = cipher.decryptor()
        
        # Decrypt data
        try:
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")

class AsymmetricEncryptionService:
    def __init__(self):
        self.key_size = 2048
        
    def generate_key_pair(self) -> tuple:
        """Generate RSA key pair"""
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size
        )
        
        public_key = private_key.public_key()
        
        return private_key, public_key
    
    def serialize_keys(self, private_key, public_key, password: str = None) -> dict:
        """Serialize keys to PEM format"""
        
        # Serialize private key
        if password:
            encryption_algorithm = serialization.BestAvailableEncryption(password.encode())
        else:
            encryption_algorithm = serialization.NoEncryption()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption_algorithm
        )
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return {
            'private_key': private_pem.decode(),
            'public_key': public_pem.decode()
        }
    
    def encrypt_with_public_key(self, data: str, public_key_pem: str) -> str:
        """Encrypt data with public key"""
        
        # Load public key
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        
        # Encrypt data
        ciphertext = public_key.encrypt(
            data.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return base64.b64encode(ciphertext).decode()
    
    def decrypt_with_private_key(self, encrypted_data: str, private_key_pem: str, password: str = None) -> str:
        """Decrypt data with private key"""
        
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=password.encode() if password else None
        )
        
        # Decrypt data
        ciphertext = base64.b64decode(encrypted_data)
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return plaintext.decode()

class SecureDataAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.encryption_service = DataEncryptionService()
        self.asymmetric_service = AsymmetricEncryptionService()
    
    def execute(self, input_data, context=None):
        """Handle secure data operations"""
        
        operation = context.get('operation', 'encrypt')
        
        if operation == 'encrypt':
            return self.encrypt_data(input_data, context)
        elif operation == 'decrypt':
            return self.decrypt_data(input_data, context)
        elif operation == 'generate_keys':
            return self.generate_encryption_keys(context)
        else:
            return {'error': f'Unknown operation: {operation}'}
    
    def encrypt_data(self, input_data, context):
        """Encrypt sensitive data"""
        
        data = input_data.get('data')
        password = context.get('password') or input_data.get('password')
        encryption_type = context.get('encryption_type', 'symmetric')
        
        if not data or not password:
            return {'error': 'Data and password required for encryption'}
        
        try:
            if encryption_type == 'symmetric':
                result = self.encryption_service.encrypt_data(data, password)
                return {'encrypted_data': result, 'encryption_type': 'symmetric'}
            
            elif encryption_type == 'asymmetric':
                public_key = context.get('public_key')
                if not public_key:
                    return {'error': 'Public key required for asymmetric encryption'}
                
                encrypted = self.asymmetric_service.encrypt_with_public_key(data, public_key)
                return {'encrypted_data': encrypted, 'encryption_type': 'asymmetric'}
            
            else:
                return {'error': f'Unknown encryption type: {encryption_type}'}
                
        except Exception as e:
            return {'error': f'Encryption failed: {str(e)}'}
    
    def decrypt_data(self, input_data, context):
        """Decrypt sensitive data"""
        
        encrypted_data = input_data.get('encrypted_data')
        password = context.get('password') or input_data.get('password')
        encryption_type = context.get('encryption_type', 'symmetric')
        
        if not encrypted_data:
            return {'error': 'Encrypted data required for decryption'}
        
        try:
            if encryption_type == 'symmetric':
                if not password:
                    return {'error': 'Password required for symmetric decryption'}
                
                decrypted = self.encryption_service.decrypt_data(encrypted_data, password)
                return {'decrypted_data': decrypted}
            
            elif encryption_type == 'asymmetric':
                private_key = context.get('private_key')
                if not private_key:
                    return {'error': 'Private key required for asymmetric decryption'}
                
                decrypted = self.asymmetric_service.decrypt_with_private_key(
                    encrypted_data, private_key, password
                )
                return {'decrypted_data': decrypted}
            
            else:
                return {'error': f'Unknown encryption type: {encryption_type}'}
                
        except Exception as e:
            return {'error': f'Decryption failed: {str(e)}'}
    
    def generate_encryption_keys(self, context):
        """Generate encryption key pairs"""
        
        key_type = context.get('key_type', 'asymmetric')
        password = context.get('password')
        
        try:
            if key_type == 'asymmetric':
                private_key, public_key = self.asymmetric_service.generate_key_pair()
                serialized_keys = self.asymmetric_service.serialize_keys(
                    private_key, public_key, password
                )
                
                return {
                    'key_type': 'asymmetric',
                    'private_key': serialized_keys['private_key'],
                    'public_key': serialized_keys['public_key'],
                    'protected': bool(password)
                }
            
            else:
                return {'error': f'Unsupported key type: {key_type}'}
                
        except Exception as e:
            return {'error': f'Key generation failed: {str(e)}'}
```

### 2. Secure Data Storage

```python
import sqlite3
import hashlib
from pathlib import Path

class SecureDataStorage:
    def __init__(self, database_path: str = None):
        self.db_path = database_path or str(Path.home() / '.agentmap' / 'secure.db')
        self.encryption_service = DataEncryptionService()
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize secure database with proper permissions"""
        
        # Create directory if it doesn't exist
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # Set restrictive permissions on directory
        db_dir.chmod(0o700)  # rwx for owner only
        
        # Initialize database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS secure_data (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    encrypted_data TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_id ON secure_data(user_id)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_data_type ON secure_data(data_type)
            ''')
        
        # Set restrictive permissions on database file
        Path(self.db_path).chmod(0o600)  # rw for owner only
    
    def store_encrypted_data(self, user_id: str, data_type: str, data: str, password: str, metadata: dict = None) -> str:
        """Store encrypted data in secure database"""
        
        # Generate unique ID
        data_id = hashlib.sha256(f"{user_id}:{data_type}:{datetime.now().isoformat()}".encode()).hexdigest()
        
        # Encrypt data
        encrypted_data = self.encryption_service.encrypt_data(data, password)
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO secure_data (id, user_id, data_type, encrypted_data, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                data_id,
                user_id,
                data_type,
                json.dumps(encrypted_data),
                json.dumps(metadata) if metadata else None
            ))
        
        return data_id
    
    def retrieve_decrypted_data(self, data_id: str, user_id: str, password: str) -> dict:
        """Retrieve and decrypt data from secure database"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT encrypted_data, data_type, metadata, created_at
                FROM secure_data
                WHERE id = ? AND user_id = ?
            ''', (data_id, user_id))
            
            row = cursor.fetchone()
            
            if not row:
                raise ValueError("Data not found or access denied")
            
            encrypted_data_json, data_type, metadata_json, created_at = row
            
            # Decrypt data
            encrypted_data = json.loads(encrypted_data_json)
            decrypted_data = self.encryption_service.decrypt_data(encrypted_data, password)
            
            return {
                'data': decrypted_data,
                'data_type': data_type,
                'metadata': json.loads(metadata_json) if metadata_json else None,
                'created_at': created_at
            }
    
    def delete_data(self, data_id: str, user_id: str) -> bool:
        """Securely delete data from database"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                DELETE FROM secure_data
                WHERE id = ? AND user_id = ?
            ''', (data_id, user_id))
            
            return cursor.rowcount > 0
    
    def list_user_data(self, user_id: str) -> list:
        """List data items for user (without decrypting)"""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, data_type, metadata, created_at, updated_at
                FROM secure_data
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'data_type': row[1],
                    'metadata': json.loads(row[2]) if row[2] else None,
                    'created_at': row[3],
                    'updated_at': row[4]
                }
                for row in rows
            ]
```

## Network Security

### 1. Secure Communications

```python
import ssl
import socket
import certifi
import requests
from urllib3.util.ssl_ import create_urllib3_context

class SecureNetworkAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.setup_secure_session()
        
    def setup_secure_session(self):
        """Setup secure HTTP session with proper TLS configuration"""
        
        self.session = requests.Session()
        
        # Create secure SSL context
        ssl_context = create_urllib3_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        # Disable weak ciphers
        ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        # Configure session adapter
        from requests.adapters import HTTPAdapter
        from urllib3.poolmanager import PoolManager
        
        class SecureHTTPAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs['ssl_context'] = ssl_context
                return super().init_poolmanager(*args, **kwargs)
        
        self.session.mount('https://', SecureHTTPAdapter())
        
        # Set security headers
        self.session.headers.update({
            'User-Agent': 'AgentMap-SecureClient/1.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def execute(self, input_data, context=None):
        """Make secure HTTP requests"""
        
        url = input_data.get('url')
        method = input_data.get('method', 'GET').upper()
        headers = input_data.get('headers', {})
        data = input_data.get('data')
        
        # Validate URL
        if not self.is_safe_url(url):
            return {'error': 'Unsafe URL detected', 'url': url}
        
        # Add security headers
        secure_headers = self.get_security_headers(context)
        headers.update(secure_headers)
        
        try:
            # Make secure request
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if method in ['POST', 'PUT', 'PATCH'] else None,
                timeout=context.get('timeout', 30),
                verify=True  # Always verify SSL certificates
            )
            
            response.raise_for_status()
            
            # Log successful request
            self.log_network_request(url, method, response.status_code, True)
            
            return {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'data': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                'secure': True
            }
            
        except requests.exceptions.SSLError as e:
            self.log_network_request(url, method, None, False, f"SSL Error: {str(e)}")
            return {'error': f'SSL verification failed: {str(e)}', 'secure': False}
        
        except requests.exceptions.RequestException as e:
            self.log_network_request(url, method, None, False, str(e))
            return {'error': f'Request failed: {str(e)}', 'secure': False}
    
    def is_safe_url(self, url: str) -> bool:
        """Validate URL for security"""
        
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        
        # Only allow HTTPS
        if parsed.scheme != 'https':
            return False
        
        # Block private IP ranges
        import ipaddress
        
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # Not an IP address, check domain
            pass
        
        # Block suspicious domains
        suspicious_domains = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            '192.168.',
            '10.',
            '172.16.',
            '172.17.',
            '172.18.',
            '172.19.',
            '172.20.',
            '172.21.',
            '172.22.',
            '172.23.',
            '172.24.',
            '172.25.',
            '172.26.',
            '172.27.',
            '172.28.',
            '172.29.',
            '172.30.',
            '172.31.'
        ]
        
        for suspicious in suspicious_domains:
            if parsed.hostname and suspicious in parsed.hostname:
                return False
        
        return True
    
    def get_security_headers(self, context: dict) -> dict:
        """Get security headers for requests"""
        
        headers = {}
        
        # Add API key if provided
        api_key = context.get('api_key')
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        # Add request ID for tracking
        headers['X-Request-ID'] = secrets.token_urlsafe(16)
        
        # Add timestamp
        headers['X-Timestamp'] = str(int(datetime.now().timestamp()))
        
        return headers
    
    def log_network_request(self, url: str, method: str, status_code: int, success: bool, error: str = None):
        """Log network requests for security monitoring"""
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'method': method,
            'status_code': status_code,
            'success': success,
            'error': error,
            'agent': self.__class__.__name__
        }
        
        if success:
            self.logger.info(f"Secure request: {log_entry}")
        else:
            self.logger.warning(f"Failed request: {log_entry}")
```

### 2. Input Validation and Sanitization

```python
import re
import html
import bleach
from typing import Any, Dict, List

class InputValidationAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.setup_validation_rules()
    
    def setup_validation_rules(self):
        """Setup input validation rules"""
        
        self.validation_rules = {
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'phone': r'^\+?1?[0-9]{10,15}$',
            'url': r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$',
            'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            'alphanumeric': r'^[a-zA-Z0-9]+$',
            'safe_filename': r'^[a-zA-Z0-9._-]+$'
        }
        
        # XSS prevention - allowed HTML tags and attributes
        self.allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
        ]
        
        self.allowed_attributes = {
            '*': ['class'],
            'a': ['href', 'title'],
        }
    
    def execute(self, input_data, context=None):
        """Validate and sanitize input data"""
        
        validation_type = context.get('validation_type', 'general')
        
        if validation_type == 'validate':
            return self.validate_data(input_data, context)
        elif validation_type == 'sanitize':
            return self.sanitize_data(input_data, context)
        elif validation_type == 'both':
            validation_result = self.validate_data(input_data, context)
            if validation_result['valid']:
                sanitization_result = self.sanitize_data(input_data, context)
                return {
                    'valid': True,
                    'sanitized_data': sanitization_result['sanitized_data'],
                    'validation_results': validation_result['validation_results']
                }
            else:
                return validation_result
        else:
            return {'error': f'Unknown validation type: {validation_type}'}
    
    def validate_data(self, input_data: Dict, context: Dict) -> Dict:
        """Validate input data against rules"""
        
        validation_schema = context.get('validation_schema', {})
        results = {}
        all_valid = True
        
        for field_name, field_value in input_data.items():
            field_schema = validation_schema.get(field_name, {})
            field_result = self.validate_field(field_name, field_value, field_schema)
            results[field_name] = field_result
            
            if not field_result['valid']:
                all_valid = False
        
        return {
            'valid': all_valid,
            'validation_results': results,
            'input_data': input_data
        }
    
    def validate_field(self, field_name: str, field_value: Any, schema: Dict) -> Dict:
        """Validate individual field"""
        
        result = {
            'valid': True,
            'errors': [],
            'value': field_value
        }
        
        # Check required fields
        if schema.get('required', False) and (field_value is None or field_value == ''):
            result['valid'] = False
            result['errors'].append('Field is required')
            return result
        
        # Skip validation if field is optional and empty
        if field_value is None or field_value == '':
            return result
        
        # Type validation
        expected_type = schema.get('type')
        if expected_type and not isinstance(field_value, expected_type):
            result['valid'] = False
            result['errors'].append(f'Expected type {expected_type.__name__}, got {type(field_value).__name__}')
        
        # Length validation for strings
        if isinstance(field_value, str):
            min_length = schema.get('min_length')
            max_length = schema.get('max_length')
            
            if min_length and len(field_value) < min_length:
                result['valid'] = False
                result['errors'].append(f'Minimum length is {min_length}')
            
            if max_length and len(field_value) > max_length:
                result['valid'] = False
                result['errors'].append(f'Maximum length is {max_length}')
        
        # Pattern validation
        pattern = schema.get('pattern')
        if pattern and isinstance(field_value, str):
            if pattern in self.validation_rules:
                regex_pattern = self.validation_rules[pattern]
            else:
                regex_pattern = pattern
            
            if not re.match(regex_pattern, field_value):
                result['valid'] = False
                result['errors'].append(f'Does not match required pattern')
        
        # Range validation for numbers
        if isinstance(field_value, (int, float)):
            min_value = schema.get('min_value')
            max_value = schema.get('max_value')
            
            if min_value is not None and field_value < min_value:
                result['valid'] = False
                result['errors'].append(f'Minimum value is {min_value}')
            
            if max_value is not None and field_value > max_value:
                result['valid'] = False
                result['errors'].append(f'Maximum value is {max_value}')
        
        # Enum validation
        allowed_values = schema.get('allowed_values')
        if allowed_values and field_value not in allowed_values:
            result['valid'] = False
            result['errors'].append(f'Value must be one of: {allowed_values}')
        
        return result
    
    def sanitize_data(self, input_data: Dict, context: Dict) -> Dict:
        """Sanitize input data to prevent injection attacks"""
        
        sanitization_options = context.get('sanitization_options', {})
        sanitized_data = {}
        
        for field_name, field_value in input_data.items():
            if isinstance(field_value, str):
                sanitized_value = self.sanitize_string(field_value, sanitization_options)
            elif isinstance(field_value, dict):
                sanitized_value = self.sanitize_data(field_value, context)['sanitized_data']
            elif isinstance(field_value, list):
                sanitized_value = [
                    self.sanitize_string(item, sanitization_options) if isinstance(item, str) else item
                    for item in field_value
                ]
            else:
                sanitized_value = field_value
            
            sanitized_data[field_name] = sanitized_value
        
        return {
            'sanitized_data': sanitized_data,
            'original_data': input_data
        }
    
    def sanitize_string(self, text: str, options: Dict) -> str:
        """Sanitize string input"""
        
        # HTML escape by default
        if options.get('html_escape', True):
            text = html.escape(text)
        
        # Remove HTML tags (use bleach for safe HTML)
        if options.get('strip_html', False):
            text = bleach.clean(text, tags=[], strip=True)
        
        # Clean HTML with allowed tags
        if options.get('clean_html', False):
            text = bleach.clean(
                text,
                tags=self.allowed_tags,
                attributes=self.allowed_attributes,
                strip=True
            )
        
        # SQL injection prevention (basic)
        if options.get('sql_escape', True):
            text = text.replace("'", "''").replace('"', '""')
        
        # Remove null bytes
        if options.get('remove_null_bytes', True):
            text = text.replace('\x00', '')
        
        # Normalize unicode
        if options.get('normalize_unicode', True):
            import unicodedata
            text = unicodedata.normalize('NFKC', text)
        
        # Trim whitespace
        if options.get('trim_whitespace', True):
            text = text.strip()
        
        return text
    
    def detect_malicious_patterns(self, text: str) -> List[str]:
        """Detect potentially malicious patterns in text"""
        
        malicious_patterns = [
            (r'<script.*?>.*?</script>', 'XSS Script Tag'),
            (r'javascript:', 'JavaScript Protocol'),
            (r'on\w+\s*=', 'Event Handler'),
            (r'union\s+select', 'SQL Union Injection'),
            (r'drop\s+table', 'SQL Drop Statement'),
            (r'insert\s+into', 'SQL Insert Statement'),
            (r'delete\s+from', 'SQL Delete Statement'),
            (r'update\s+.*\s+set', 'SQL Update Statement'),
            (r'../|..\\', 'Path Traversal'),
            (r'exec\s*\(', 'Code Execution'),
            (r'eval\s*\(', 'Code Evaluation'),
            (r'cmd\s*=', 'Command Injection'),
            (r'system\s*\(', 'System Command')
        ]
        
        detected_threats = []
        
        for pattern, threat_name in malicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected_threats.append(threat_name)
        
        return detected_threats
```

This comprehensive security guide provides essential security measures for AgentMap deployments. Remember to regularly update security practices and monitor for new threats.

For performance optimization while maintaining security, see the [Performance Guide](/docs/guides/advanced/performance).

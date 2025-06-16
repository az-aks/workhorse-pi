#!/usr/bin/env python3
"""
Generate a self-signed certificate for HTTPS development
"""

from datetime import datetime, timedelta
from pathlib import Path
import os
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_self_signed_cert(cert_path="ssl/cert.pem", key_path="ssl/key.pem"):
    """Generate a self-signed certificate for development purposes."""
    # Create output directory if it doesn't exist
    cert_dir = os.path.dirname(cert_path)
    key_dir = os.path.dirname(key_path)
    
    if cert_dir and not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
    if key_dir and not os.path.exists(key_dir):
        os.makedirs(key_dir)
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Generate self-signed certificate with modern settings
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Workhorse Bot - Development"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Development"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow() - timedelta(days=1)  # Start 1 day ago for clock skew
    ).not_valid_after(
        # Certificate valid for 2 years
        datetime.utcnow() + timedelta(days=730)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.DNSName("127.0.0.1"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            x509.IPAddress(ipaddress.IPv6Address("::1")),
        ]),
        critical=False,
    ).add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True,
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=True, 
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False
        ),
        critical=True
    ).add_extension(
        x509.ExtendedKeyUsage([
            x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
            x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH
        ]),
        critical=False
    ).sign(private_key, hashes.SHA256())
    
    # Write the certificate and private key to disk
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
        
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        
    print(f"Self-signed certificate generated successfully!")
    print(f"Certificate: {os.path.abspath(cert_path)}")
    print(f"Private key: {os.path.abspath(key_path)}")
    print("\nNote: This certificate is for development purposes only. ")
    print("      In production, use a proper certificate from a trusted CA.")

if __name__ == "__main__":
    generate_self_signed_cert()

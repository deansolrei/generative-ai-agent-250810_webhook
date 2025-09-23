#!/usr/bin/env python3
"""
Development helper script for the webhook.
Provides common development tasks.
"""
import os
import sys
import subprocess
import argparse

def install_deps():
    """Install project dependencies."""
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def run_server():
    """Run the development server."""
    print("Starting development server...")
    subprocess.run([sys.executable, "webhook.py"])

def run_tests():
    """Run the webhook tests."""
    print("Running tests...")
    subprocess.run([sys.executable, "test_webhook.py"])

def create_env():
    """Create .env file from template."""
    if os.path.exists('.env'):
        print(".env file already exists!")
        return
    
    if os.path.exists('.env.example'):
        import shutil
        shutil.copy('.env.example', '.env')
        print("Created .env file from .env.example")
        print("Please edit .env to configure your settings")
    else:
        print("No .env.example found!")

def main():
    parser = argparse.ArgumentParser(description='Webhook development helper')
    parser.add_argument('command', choices=['install', 'run', 'test', 'setup-env'], 
                       help='Command to execute')
    
    args = parser.parse_args()
    
    if args.command == 'install':
        install_deps()
    elif args.command == 'run':
        run_server()
    elif args.command == 'test':
        run_tests()
    elif args.command == 'setup-env':
        create_env()

if __name__ == "__main__":
    main()
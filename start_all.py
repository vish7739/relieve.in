"""
Master Starter Script for 26AS Parser
Starts both the Flask app and cleanup system
"""

import subprocess
import sys
import os
import time
from threading import Thread

def start_cleanup_system():
    """Start the cleanup system"""
    print("Starting automatic cleanup system...")
    try:
        # Start cleanup script
        cleanup_process = subprocess.Popen(
            [sys.executable, "cleanup_old_files.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return cleanup_process
    except Exception as e:
        print(f"Error starting cleanup system: {e}")
        return None

def start_flask_app():
    """Start the Flask application"""
    print("Starting Flask application...")
    try:
        # Start Flask app
        flask_process = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True
        )
        return flask_process
    except Exception as e:
        print(f"Error starting Flask app: {e}")
        return None

def monitor_processes(cleanup_proc, flask_proc):
    """Monitor both processes"""
    try:
        # Wait for Flask app to finish
        flask_proc.wait()
        
        # Flask app stopped, now stop cleanup
        print("\nFlask application stopped. Stopping cleanup system...")
        cleanup_proc.terminate()
        
        # Wait for cleanup to terminate gracefully
        try:
            cleanup_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cleanup_proc.kill()
        
        print("Cleanup system stopped.")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Stopping all processes...")
        flask_proc.terminate()
        cleanup_proc.terminate()
        
        try:
            flask_proc.wait(timeout=5)
            cleanup_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            flask_proc.kill()
            cleanup_proc.kill()
        
        print("All processes stopped.")

def main():
    print("=" * 60)
    print("26AS Parser - Professional Edition")
    print("With Automatic File Cleanup System")
    print("=" * 60)
    print("\nFeatures:")
    print("✓ Flask Web Application")
    print("✓ Automatic file cleanup (deletes files > 10 hours old)")
    print("✓ Background cleanup process")
    print("✓ Logging to cleanup_log.txt")
    print("=" * 60)
    
    # Start cleanup system
    cleanup_process = start_cleanup_system()
    if cleanup_process is None:
        print("Failed to start cleanup system. Exiting.")
        return
    
    # Give cleanup system time to start
    time.sleep(2)
    
    # Start Flask app
    flask_process = start_flask_app()
    if flask_process is None:
        print("Failed to start Flask app. Stopping cleanup...")
        cleanup_process.terminate()
        return
    
    # Monitor both processes
    monitor_processes(cleanup_process, flask_process)
    
    print("\nApplication session ended.")
    print("Check cleanup_log.txt for cleanup activities.")

if __name__ == "__main__":
    main()
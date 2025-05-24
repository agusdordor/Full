import os
import time
import uiautomator2 as u2
import cv2
import numpy as np
from subprocess import check_output
from colorama import init, Fore, Style

# Initialize colorama
init()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print(Fore.CYAN + """
    ╔══════════════════════════════════════════╗
    ║            GANTI PASSWORD                ║
    ╚══════════════════════════════════════════╝
    """ + Style.RESET_ALL)

def get_connected_devices():
    """Get list of connected Android devices using ADB"""
    try:
        result = check_output(['adb', 'devices']).decode('utf-8')
        devices = []
        for line in result.strip().split('\n')[1:]:
            if line.strip() and 'device' in line:
                device_id = line.split()[0]
                devices.append(device_id)
        return devices
    except Exception as e:
        print(f"{Fore.RED}Error getting devices: {e}{Style.RESET_ALL}")
        return []

def robust_screenshot(device, max_attempts=25):
    """Capture screenshot with validation and retry mechanism"""
    for attempt in range(max_attempts):
        try:
            screenshot = device.screenshot()
            
            # Convert to numpy array if needed
            if not isinstance(screenshot, np.ndarray):
                screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Check if image is empty
            if screenshot is None or screenshot.size == 0:
                continue
                
            # Check if image is all white
            if np.mean(screenshot) > 250:
                continue
                
            return screenshot
            
        except Exception as e:
            print(f"\r{Fore.RED}Attempt {attempt + 1}: Error capturing screenshot: {e}{Style.RESET_ALL}")
        
        time.sleep(0.5)
    
    print(f"\r{Fore.RED}Failed to capture valid screenshot after {max_attempts} attempts{Style.RESET_ALL}")
    return None

def find_image(screenshot, template_path, threshold=0.7):
    """Find image in screenshot and return coordinates with improved validation"""
    try:
        # Validate screenshot
        if screenshot is None or (isinstance(screenshot, np.ndarray) and screenshot.size == 0):
            print(f"\r{Fore.RED}Invalid screenshot{Style.RESET_ALL}")
            return None
            
        # Load and validate template
        template = cv2.imread(template_path)
        if template is None:
            raise ValueError(f"Could not load template image: {template_path}")

        # Convert screenshot to numpy array if needed
        if not isinstance(screenshot, np.ndarray):
            screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
        # Convert both images to grayscale for better matching
        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        # Perform template matching
        result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template_gray.shape[:2]
            x = max_loc[0] + w // 2
            y = max_loc[1] + h // 2
            return (x, y, max_val)
        return None
    except Exception as e:
        print(f"\r{Fore.RED}Error finding image: {e}{Style.RESET_ALL}")
        return None

def wait_for_image(device, template_path, timeout=10, interval=0.5):
    """Wait for image to appear on screen with robust screenshot capture"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        screenshot = robust_screenshot(device)
        if screenshot is not None:
            result = find_image(screenshot, template_path)
            if result:
                return result
        time.sleep(interval)
    return None

def process_id(device, user_id, image_dir, current_index, total_ids):
    """Process a single ID"""
    try:
        def update_status(status, result=None):
            status_str = f"\r[{current_index}/{total_ids}] : {user_id} : {status}"
            if result:
                status_str += f" : {result}"
                print(status_str, flush=True)  # New line only for final result
            else:
                print(status_str, end='', flush=True)  # Stay on same line for progress updates

        update_status("Finding isi button...")
        isi_coords = wait_for_image(device, os.path.join(image_dir, 'isi1.png'))
        if not isi_coords:
            update_status("Finding isi button", f"{Fore.RED}Failed{Style.RESET_ALL}")
            with open('ganti_pass/cobalagi.txt', 'a') as f:
                f.write(f"{user_id}\n")
            return False
        
        device.click(isi_coords[0] - 250, isi_coords[1] + 40)
        
        update_status("Clearing text...")
        current_focused = device(focused=True)
        if current_focused.exists:
            current_focused.clear_text()
        else:
            update_status("Clearing text", f"{Fore.RED}Failed{Style.RESET_ALL}")
            return False
        time.sleep(0.5)

        update_status("Entering ID...")
        device.send_keys(user_id)
        time.sleep(0.5)

        update_status("Clicking lupa button...")
        device.click(850, 350)
        time.sleep(1)

        update_status("Clicking button...")
        button_xpath = '//android.webkit.WebView[@text="domino"]/android.view.View/android.view.View[10]/android.widget.Button'
        try:
            button = device.xpath(button_xpath)
            if button.wait(timeout=5.0):
                button.click()
        except Exception:
            pass
        time.sleep(0.5)

        update_status("Waiting for result...")
        success = False
        found_result = False
        start_time = time.time()
        while time.time() - start_time < 30:
            screenshot = device.screenshot()
            
            if find_image(screenshot, os.path.join(image_dir, 'sukses.png')):
                update_status("Processing", f"{Fore.GREEN}Success{Style.RESET_ALL}")
                success = True
                found_result = True
                with open('ganti_pass/sukses.txt', 'a') as f:
                    f.write(f"{user_id}\n")
                break
                
            if find_image(screenshot, os.path.join(image_dir, 'gagal.png')):
                update_status("Processing", f"{Fore.RED}Failed{Style.RESET_ALL}")
                found_result = True
                with open('ganti_pass/die.txt', 'a') as f:
                    f.write(f"{user_id}\n")
                break
                
            time.sleep(0.5)
            
        if not found_result:
            update_status("Processing", f"{Fore.YELLOW}Not Found{Style.RESET_ALL}")
            with open('ganti_pass/cobalagi.txt', 'a') as f:
                f.write(f"{user_id}\n")

        update_status("Clicking forward...")
        forward_xpath = '//android.widget.Button[@resource-id="com.higgs.domino:id/btnForward"]'
        try:
            forward_button = device.xpath(forward_xpath)
            if forward_button.wait(timeout=5.0):
                forward_button.click()
        except Exception:
            pass
        time.sleep(0.5)

        return success

    except Exception as e:
        update_status("Processing", f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
        return False

def process_device(device_id, device_ids, image_dir):
    """Process IDs for a single device"""
    try:
        print(f"{Fore.CYAN}Connecting to device: {device_id}{Style.RESET_ALL}")
        device = u2.connect(device_id)
        
        total_ids = len(device_ids)
        for idx, user_id in enumerate(device_ids, 1):
            process_id(device, user_id, image_dir, idx, total_ids)
            time.sleep(0.5)

    except Exception as e:
        print(f"{Fore.RED}Error with device {device_id}: {e}{Style.RESET_ALL}")

def chunk_list(lst, n):
    """Split list into n chunks of approximately equal size"""
    k, m = divmod(len(lst), n)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

def main():
    clear_screen()
    print_header()

    devices = get_connected_devices()
    if not devices:
        print(f"{Fore.RED}No devices found{Style.RESET_ALL}")
        return

    print(f"{Fore.GREEN}Found {len(devices)} device(s){Style.RESET_ALL}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(script_dir, '..', 'images')

    try:
        with open(os.path.join(script_dir, '..', 'id.txt'), 'r') as f:
            ids = [line.strip() for line in f if line.strip()]

        # Calculate optimal number of threads based on CPU cores and devices
        import multiprocessing
        optimal_threads = min(len(devices) * 2, multiprocessing.cpu_count())
        
        # Split IDs into chunks for each thread
        id_chunks = chunk_list(ids, optimal_threads)
        
        import threading
        from queue import Queue
        
        # Create a queue for device management
        device_queue = Queue()
        for device_id in devices:
            device_queue.put(device_id)
            
        def worker(chunk, device_queue, image_dir):
            try:
                device_id = device_queue.get()
                process_device(device_id, chunk, image_dir)
            finally:
                device_queue.put(device_id)  # Return device to queue
                
        threads = []
        for chunk in id_chunks:
            if not chunk:
                continue
                
            thread = threading.Thread(
                target=worker,
                args=(chunk, device_queue, image_dir)
            )
            threads.append(thread)
            thread.start()
            print(f"{Fore.CYAN}Started processing thread with {len(chunk)} IDs{Style.RESET_ALL}")

        for thread in threads:
            thread.join()

        print(f"{Fore.GREEN}All threads have completed processing{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()

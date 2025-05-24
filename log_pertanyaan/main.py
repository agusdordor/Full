import os
import time
import uiautomator2 as u2
import cv2
import numpy as np
import pytesseract
import argparse
from colorama import init, Fore, Style
from subprocess import check_output
import threading
from queue import Queue
import multiprocessing

# Initialize colorama
init()

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true', help='Show debug information and matched templates')
args = parser.parse_args()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print(Fore.CYAN + """
    ╔══════════════════════════════════════════╗
    ║           LOGIN PERTANYAAN               ║
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

def robust_screenshot(device, max_attempts=50):
    """Capture screenshot with validation and retry mechanism"""
    for attempt in range(max_attempts):
        try:
            screenshot = device.screenshot()
            if not isinstance(screenshot, np.ndarray):
                screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            if screenshot is None or screenshot.size == 0:
                continue
            if np.mean(screenshot) > 250:
                continue
            return screenshot
        except Exception as e:
            print(f"{Fore.RED}Attempt {attempt + 1}: Error capturing screenshot: {e}{Style.RESET_ALL}")
        time.sleep(0.5)
    print(f"{Fore.RED}Failed to capture valid screenshot after {max_attempts} attempts{Style.RESET_ALL}")
    return False

def find_image(screenshot, template_path, threshold=0.8, debug=False):
    """Find image in screenshot and return coordinates with confidence value"""
    try:
        if screenshot is None or (isinstance(screenshot, np.ndarray) and screenshot.size == 0):
            print(f"{Fore.RED}Invalid screenshot{Style.RESET_ALL}")
            return None
        template = cv2.imread(template_path)
        if template is None:
            print(f"{Fore.RED}Template image not found: {template_path}{Style.RESET_ALL}")
            return None
        if not isinstance(screenshot, np.ndarray):
            screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            h, w = template_gray.shape[:2]
            x = max_loc[0] + w // 2
            y = max_loc[1] + h // 2
            
            if args.debug:
                debug_img = screenshot.copy()
                cv2.rectangle(debug_img, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
                cv2.putText(debug_img, f"Confidence: {max_val:.2f}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow('Debug: Template Match', debug_img)
                cv2.waitKey(1000)
                cv2.destroyAllWindows()
            
            return (x, y, max_val)
        return None
    except Exception as e:
        print(f"{Fore.RED}Error finding image: {e}{Style.RESET_ALL}")
        return None

def ocr_search_text(screenshot, keywords):
    """Search for keywords in screenshot text using pytesseract OCR"""
    try:
        if screenshot is None or screenshot.size == 0:
            return None
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray).lower()
        for keyword in keywords:
            if keyword.lower() in text:
                return keyword
        return None
    except Exception as e:
        print(f"{Fore.RED}OCR error: {e}{Style.RESET_ALL}")
        return None

def update_status(device_id, status, user_id="", current_index=0, total_ids=0, result=None):
    """Update terminal status with consistent formatting - one line per instance"""
    status_str = f"\r[{device_id}][{current_index}/{total_ids}] : {user_id} : {status}"
    if result:
        status_str += f" : {result}"
        print(status_str)  # New line for final results
    else:
        print(status_str, end='', flush=True)  # Stay on same line for progress

def process_id(device, device_id, user_id, image_dir, live_path, die_path, retry_path, jawaban1, jawaban2, current_index=0, total_ids=0, debug=False):
    """Process a single ID according to the specified steps"""
    try:
        # Step 1: Find "isi.png" and click x+150, y+100
        update_status(device_id, "Finding isi button...", user_id, current_index, total_ids)
        screenshot = robust_screenshot(device)
        result = find_image(screenshot, os.path.join(image_dir, "isi.png"), debug=debug)
        if not result:
            update_status(device_id, "Finding isi button", user_id, current_index, total_ids, f"{Fore.YELLOW}Image not found{Style.RESET_ALL}")
            with open(retry_path, 'a') as f:
                f.write(f"{user_id}\n")
            return False
        x, y, conf = result
        device.click(x + 150, y + 100)
        time.sleep(0.5)

        # Step 2: Clear text field
        update_status(device_id, "Clearing text field...", user_id, current_index, total_ids)
        focused = device(focused=True)
        if focused.exists:
            focused.clear_text()
        else:
            update_status(device_id, "Clearing text field", user_id, current_index, total_ids, f"{Fore.RED}Failed{Style.RESET_ALL}")
            with open(die_path, 'a') as f:
                f.write(f"{user_id}\n")
            return False
        time.sleep(0.5)

        # Step 3: Input user_id
        update_status(device_id, "Entering ID...", user_id, current_index, total_ids)
        device.send_keys(user_id)
        time.sleep(0.5)

        # Step 4: Click at x=600, y=450
        update_status(device_id, "Clicking submit...", user_id, current_index, total_ids)
        device.click(600, 450)
        time.sleep(1)

        # Step 5: Check initial response
        update_status(device_id, "Checking initial response...", user_id, current_index, total_ids)
        proceed_to_security = False
        timeout = 30
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            screenshot = robust_screenshot(device)
            if ocr_search_text(screenshot, ["Anda"]):
                device.click(600, 440)
                time.sleep(0.5)
                proceed_to_security = True
                break
            
            result = ocr_search_text(screenshot, ["sandi", "SUKSES"])
            if result == "sandi":
                device.click(600, 440)
                time.sleep(0.5)
                update_status(device_id, "Password Reset Required", user_id, current_index, total_ids, f"{Fore.YELLOW}Failed{Style.RESET_ALL}")
                with open(die_path, 'a') as f:
                    f.write(f"{user_id}\n")
                return False
            elif result == "SUKSES":
                device.click(600, 440)
                update_status(device_id, "Login Success", user_id, current_index, total_ids, f"{Fore.GREEN}Success{Style.RESET_ALL}")
                with open(live_path, 'a') as f:
                    f.write(f"{user_id}\n")
                time.sleep(0.5)
                return True
            
            time.sleep(0.5)
            
        if not proceed_to_security:
            update_status(device_id, "Initial check", user_id, current_index, total_ids, f"{Fore.YELLOW}Timeout or failed{Style.RESET_ALL}")
            with open(die_path, 'a') as f:
                f.write(f"{user_id}\n")
            return False

        # Step 6: Find "security.png"
        update_status(device_id, "Finding security questions...", user_id, current_index, total_ids)
        time.sleep(1)
        screenshot = robust_screenshot(device)
        result = find_image(screenshot, os.path.join(image_dir, "security.png"), debug=debug)
        if not result:
            update_status(device_id, "Finding security", user_id, current_index, total_ids, f"{Fore.YELLOW}Image not found{Style.RESET_ALL}")
            with open(retry_path, 'a') as f:
                f.write(f"{user_id}\n")
            return False

        # Step 7: Click security.png x+100, y+200 and input jawaban1
        x, y, conf = result
        update_status(device_id, "Entering answer 1...", user_id, current_index, total_ids)
        device.click(x + 300, y + 55)
        device.send_keys(jawaban1)
        time.sleep(0.5)

        # Step 8: Delay 0.5s and click security.png x+400, y+200
        time.sleep(1)
        device.click(x + 300, y + 180)
        time.sleep(0.5)

        # Step 9: Input jawaban2 and click x=600, y=500
        device.send_keys(jawaban2)
        time.sleep(0.5)
        device.click(600, 500)
        time.sleep(1)

        # Step 10: OCR check for "SUKSES" or "Salah"
        found_keyword = None
        timeout = 30
        start_time = time.time()
        while time.time() - start_time < timeout:
            screenshot = robust_screenshot(device)
            found_keyword = ocr_search_text(screenshot, ["SUKSES", "Salah"])
            if found_keyword:
                break
            time.sleep(0.5)
        if not found_keyword:
            update_status(device_id, "OCR Detection", user_id, current_index, total_ids, f"{Fore.YELLOW}No keyword found in OCR within timeout{Style.RESET_ALL}")
            with open(die_path, 'a') as f:
                f.write(f"{user_id}\n")
            return False

        # Step 11: Handle success or failure
        if found_keyword.lower() == "salah":
            device.click(600, 440)
            time.sleep(0.5)
            # Click image "silang.png"
            screenshot = robust_screenshot(device)
            update_status(device_id, "Finding close button...", user_id, current_index, total_ids)
            result = find_image(screenshot, os.path.join(image_dir, "silang.png"), debug=debug)
            if result:
                x, y, conf = result
                device.click(x, y)
            update_status(device_id, "Wrong Answer", user_id, current_index, total_ids, f"{Fore.RED}Failed{Style.RESET_ALL}")
            with open(die_path, 'a') as f:
                f.write(f"{user_id}\n")
            return False
        elif found_keyword.lower() == "sukses":
            device.click(600, 440)
            update_status(device_id, "Login Success", user_id, current_index, total_ids, f"{Fore.GREEN}Success{Style.RESET_ALL}")
            with open(live_path, 'a') as f:
                f.write(f"{user_id}\n")
            return True

        return False

    except Exception as e:
        print(f"{Fore.RED}Error processing ID {user_id}: {e}{Style.RESET_ALL}")
        with open(die_path, 'a') as f:
            f.write(f"{user_id}\n")
        return False

def process_device(device_id, device_ids, image_dir, live_path, die_path, retry_path, jawaban1, jawaban2):
    """Process IDs for a single device"""
    try:
        print(f"{Fore.CYAN}Connecting to device: {device_id}{Style.RESET_ALL}")
        device = u2.connect(device_id)
        
        total_ids = len(device_ids)
        for idx, user_id in enumerate(device_ids, 1):
            process_id(device, device_id, user_id, image_dir, live_path, die_path, retry_path, jawaban1, jawaban2, idx, total_ids, args.debug)
            time.sleep(0.5)

    except Exception as e:
        print(f"{Fore.RED}Error with device {device_id}: {e}{Style.RESET_ALL}")

def chunk_list(lst, n):
    """Split list into n chunks of approximately equal size"""
    k, m = divmod(len(lst), n)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

def print_results(live_path, die_path, retry_path):
    """Print summary of successful and failed IDs"""
    print("\n" + "="*50)
    print(f"{Fore.CYAN}RESULTS SUMMARY{Style.RESET_ALL}")
    print("="*50)
    
    try:
        with open(live_path, 'r') as f:
            successful_ids = f.read().strip().split('\n')
        with open(die_path, 'r') as f:
            failed_ids = f.read().strip().split('\n')
            
        if successful_ids and successful_ids[0]:
            print(f"\n{Fore.GREEN}Successful IDs:{Style.RESET_ALL}")
            for id in successful_ids:
                print(f"✓ {id}")
                
        if failed_ids and failed_ids[0]:
            print(f"\n{Fore.RED}Failed IDs:{Style.RESET_ALL}")
            for id in failed_ids:
                print(f"✗ {id}")
                
        with open(retry_path, 'r') as f:
            retry_ids = f.read().strip().split('\n')
            
        if retry_ids and retry_ids[0]:
            print(f"\n{Fore.YELLOW}Retry IDs (Image not found):{Style.RESET_ALL}")
            for id in retry_ids:
                print(f"⟳ {id}")
                
        print("\nSummary:")
        print(f"Total Success: {len(successful_ids) if successful_ids and successful_ids[0] else 0}")
        print(f"Total Failed: {len(failed_ids) if failed_ids and failed_ids[0] else 0}")
        print(f"Total Retry: {len(retry_ids) if retry_ids and retry_ids[0] else 0}")
        
    except Exception as e:
        print(f"{Fore.RED}Error reading results: {e}{Style.RESET_ALL}")

def main():
    # Get answers from user before starting
    clear_screen()
    print_header()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(script_dir, '..', 'images')
    live_path = os.path.join(script_dir, 'live.txt')
    die_path = os.path.join(script_dir, 'die.txt')
    retry_path = os.path.join(script_dir, 'retry.txt')
    id_path = os.path.join(script_dir, '..', 'id.txt')

    # Get connected devices
    devices = get_connected_devices()
    if not devices:
        print(f"{Fore.RED}No devices found{Style.RESET_ALL}")
        return

    print(f"{Fore.GREEN}Found {len(devices)} device(s){Style.RESET_ALL}")

    print(f"{Fore.CYAN}Please enter the answers for security questions:{Style.RESET_ALL}")
    jawaban1 = input("Enter jawaban1: ").strip()
    jawaban2 = input("Enter jawaban2: ").strip()

    if not jawaban1 or not jawaban2:
        print(f"{Fore.RED}Both answers are required to proceed{Style.RESET_ALL}")
        return

    try:
        # Clear result files
        open(live_path, 'w').close()
        open(die_path, 'w').close()
        open(retry_path, 'w').close()

        with open(id_path, 'r') as f:
            ids = [line.strip() for line in f if line.strip()]

        # Calculate optimal number of threads based on CPU cores and devices
        optimal_threads = min(len(devices) * 2, multiprocessing.cpu_count())
        
        # Split IDs into chunks for each thread
        id_chunks = chunk_list(ids, optimal_threads)
        
        # Create a queue for device management
        device_queue = Queue()
        for device_id in devices:
            device_queue.put(device_id)
            
        def worker(chunk, device_queue, image_dir, live_path, die_path, retry_path, jawaban1, jawaban2):
            try:
                device_id = device_queue.get()
                process_device(device_id, chunk, image_dir, live_path, die_path, retry_path, jawaban1, jawaban2)
            finally:
                device_queue.put(device_id)  # Return device to queue
                
        threads = []
        for chunk in id_chunks:
            if not chunk:
                continue
                
            thread = threading.Thread(
                target=worker,
                args=(chunk, device_queue, image_dir, live_path, die_path, retry_path, jawaban1, jawaban2)
            )
            threads.append(thread)
            thread.start()
            print(f"{Fore.CYAN}Started processing thread with {len(chunk)} IDs{Style.RESET_ALL}")

        for thread in threads:
            thread.join()

        print(f"{Fore.GREEN}All threads have completed processing{Style.RESET_ALL}")
        
        # Print final results
        print_results(live_path, die_path, retry_path)

    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

def retry_on_failure(func):
    """Decorator to retry a function on failure"""
    def wrapper(*args, **kwargs):
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise e
                print(f"{Fore.YELLOW}Attempt {attempt + 1} failed, retrying...{Style.RESET_ALL}")
                time.sleep(1)
    return wrapper

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Process interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Fatal error: {e}{Style.RESET_ALL}")

import cv2
import numpy as np
import subprocess
import os
from time import sleep
import pytesseract

def capture_screen():
    """Capture screenshot from emulator using ADB"""
    try:
        # Wait for any previous ADB commands to complete
        sleep(0.5)
        
        # Ensure any existing screenshot is removed
        if os.path.exists('screen.png'):
            os.remove('screen.png')
            
        # Try multiple times if needed
        max_attempts = 20
        for attempt in range(max_attempts):
            try:
                # Capture screenshot using adb
                result = subprocess.run(['adb', 'shell', 'screencap', '-p', '/sdcard/screen.png'], 
                                     capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    print(f"Attempt {attempt + 1}: Error capturing screenshot:", result.stderr)
                    continue
                
                # Pull screenshot to local machine
                result = subprocess.run(['adb', 'pull', '/sdcard/screen.png'],
                                     capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    print(f"Attempt {attempt + 1}: Error pulling screenshot:", result.stderr)
                    continue
                
                # Verify file exists and has content
                if not os.path.exists('screen.png') or os.path.getsize('screen.png') == 0:
                    print(f"Attempt {attempt + 1}: Screenshot file is empty or missing")
                    continue
                
                # Read the screenshot
                screen = cv2.imread('screen.png')
                if screen is None or screen.size == 0:
                    print(f"Attempt {attempt + 1}: Error reading screenshot or image is empty")
                    continue
                
                # Check if image is all white
                if np.mean(screen) > 250:  # If average pixel value is very high (close to white)
                    print(f"Attempt {attempt + 1}: Screenshot appears to be all white, retrying...")
                    continue
                
                # Delete screenshot from device
                subprocess.run(['adb', 'shell', 'rm', '/sdcard/screen.png'])
                
                print(f"Screenshot captured successfully on attempt {attempt + 1}")
                return screen
                
            except subprocess.TimeoutExpired:
                print(f"Attempt {attempt + 1}: ADB command timed out")
            except Exception as e:
                print(f"Attempt {attempt + 1}: Error: {str(e)}")
            
            # Wait before retrying
            sleep(1)
        
        print("Failed to capture screenshot after", max_attempts, "attempts")
        return None
        
    except Exception as e:
        print(f"Error during screen capture: {str(e)}")
        return None

def find_template(screen, template_path, threshold=0.7):
    """
    Find template in screen image using template matching with grayscale images
    Returns: (found, location)
    - found: True if template was found above threshold
    - location: (x,y) center point of found template, or None if not found
    """
    # Read template image and convert to grayscale
    template = cv2.imread(template_path)
    if template is None:
        print(f"Could not read template: {template_path}")
        return False, None
    
    # Convert both images to grayscale
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        
    # Get template dimensions
    h, w = template_gray.shape[:2]
    
    # Perform template matching on grayscale images
    result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    # Check if template was found above threshold
    if max_val >= threshold:
        # Calculate center point
        x = max_loc[0] + w//2
        y = max_loc[1] + h//2
        return True, (x, y)
    
    return False, None

def check_tesseract():
    """Check if tesseract is installed and configured"""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        print("Tesseract is not properly configured.")
        print("To use OCR functionality, please:")
        print("1. Install Tesseract:")
        print("   - Windows: Download installer from https://github.com/UB-Mannheim/tesseract/wiki")
        print("   - Linux: sudo apt-get install tesseract-ocr")
        print("   - Mac: brew install tesseract")
        print("2. Add Tesseract to your PATH")
        print("3. Install pytesseract: pip install pytesseract")
        return False

def find_text(screen, text_to_find, lang='eng'):
    """
    Find text in screen using OCR
    Returns: (found, box)
    - found: True if text was found
    - box: (x,y,w,h) bounding box of found text, or None if not found
    """
    if not check_tesseract():
        return False, None
        
    # Convert to grayscale
    gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    
    # Apply image preprocessing for better OCR
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    # OCR configuration
    custom_config = r'--oem 3 --psm 6'
    
    try:
        # Get OCR data including bounding boxes
        data = pytesseract.image_to_data(gray, lang=lang, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Search for text
        found = False
        box = None
        
        for i, text in enumerate(data['text']):
            if text_to_find.lower() in text.lower():
                found = True
                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]
                box = (x, y, w, h)
                break
                
        return found, box
        
    except Exception as e:
        print(f"OCR error: {str(e)}")
        return False, None

if __name__ == "__main__":
    print("Image Detection Test")
    print("-" * 30)
    
    # Get arguments from command line
    import argparse
    parser = argparse.ArgumentParser(description='Test image detection using template matching or OCR')
    parser.add_argument('--template', help='Path to template image')
    parser.add_argument('--text', help='Text to find using OCR')
    parser.add_argument('--lang', default='eng', help='OCR language (default: eng)')
    parser.add_argument('--debug', action='store_true', help='Save debug images')
    
    args = parser.parse_args()
    
    # Capture screen
    screen = capture_screen()
    if screen is None:
        print("Failed to capture screen")
        exit(1)
        
    # Save debug images if requested
    if args.debug:
        # Save original screenshot
        cv2.imwrite('screen.png', screen)
        # Save grayscale version
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        cv2.imwrite('screen_gray.png', screen_gray)
        # Save thresholded version for OCR
        _, screen_thresh = cv2.threshold(screen_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cv2.imwrite('screen_thresh.png', screen_thresh)
    
    if args.text:
        # Use OCR
        print(f"Searching for text: {args.text}")
        found, box = find_text(screen, args.text, args.lang)
        if found:
            print(f"Text found at box: {box}")
            # Draw rectangle
            x, y, w, h = box
            cv2.rectangle(screen, (x, y), (x+w, y+h), (0,255,0), 2)
            cv2.imwrite('result.png', screen)
            print("Result saved as 'result.png'")
        else:
            print("Text not found")
            
    elif args.template:
        # Use template matching
        template_path = args.template
        print(f"Testing template: {template_path}")
        if os.path.exists(template_path):
            found, location = find_template(screen, template_path)
            print(f"Template found: {found}")
            if found:
                print(f"Location: {location}")
                # Draw rectangle
                template = cv2.imread(template_path)
                h, w = template.shape[:2]
                x, y = location
                cv2.rectangle(screen, (x-w//2, y-h//2), (x+w//2, y+h//2), (0,255,0), 2)
                cv2.imwrite('result.png', screen)
                print("Result saved as 'result.png'")
        else:
            print(f"Template file not found: {template_path}")
    else:
        print("Please provide either --template or --text argument")
        print("\nExample usage:")
        print("  Template matching:")
        print("    python test_image.py --template images/isi.png")
        print("  OCR text search:")
        print("    python test_image.py --text \"Login\"")
        print("    python test_image.py --text \"Masukkan\" --lang ind")
        print("\nOptions:")
        print("  --debug    Save additional debug images")
        print("  --lang     Specify OCR language (default: eng)")

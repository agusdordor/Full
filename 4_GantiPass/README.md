# Memu Automation Script

This script automates tasks in Memu emulator instances using Appium with enhanced image recognition capabilities.

## Prerequisites

1. Node.js 14 or higher
2. Appium Server
3. Android SDK (ADB)
4. Memu Emulator
5. Required images in the `images` folder:
   - isi.png
   - lupa.png
   - sukses.png
   - gagal.png

## Features

- Enhanced image recognition using OpenCV
- Improved device detection with model information
- Robust error handling and logging
- Smart waiting mechanism for UI elements
- Efficient text field operations

## Setup

1. Install the required Node.js packages:
   ```
   npm install
   ```

2. Create an `images` folder and add the required template images:
   - Place "isi.png" in the images folder
   - Place "lupa.png" in the images folder
   - Place "sukses.png" in the images folder
   - Place "gagal.png" in the images folder

3. Create an `id.txt` file with the IDs to process (one ID per line)

4. Start your Memu instance(s)

5. Start Appium server on port 4723

## Usage

Run the script:
```
npm start
```

The script will:
1. Detect connected Memu instances with device information
2. Process IDs sequentially with robust error handling
3. Use image recognition to find and interact with UI elements
4. Log all actions and results

## Technical Details

The script uses:
- webdriverio for Appium control
- opencv4nodejs for advanced image recognition
- Built-in Node.js modules for file and process management

## Image Recognition Process

The script uses template matching to:
1. Find UI elements on screen
2. Verify success/failure conditions
3. Handle dynamic UI states

## Error Handling

The script includes:
- Timeout handling for image recognition
- Device connection error handling
- Process monitoring and logging
- Automatic cleanup of resources

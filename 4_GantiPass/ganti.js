const { remote } = require('webdriverio');
const cv = require('opencv4nodejs');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const util = require('util');
const execPromise = util.promisify(exec);

/**
 * Get available android devices connected via ADB
 * @returns {Promise<Array>} List of device objects with id and name
 */
async function getConnectedDevices() {
    try {
        const { stdout } = await execPromise('adb devices -l');
        const lines = stdout.trim().split('\n').slice(1); // Skip the first line which is "List of devices attached"
        
        const devices = [];
        for (const line of lines) {
            if (line.trim() === '') continue;
            
            const parts = line.trim().split(/\s+/);
            if (parts.length >= 2 && parts[1] === 'device') {
                // Extract device ID
                const deviceId = parts[0];
                
                // Try to get device name
                let deviceName = 'Unknown';
                const modelInfo = line.match(/model:([^\s]+)/);
                if (modelInfo && modelInfo[1]) {
                    deviceName = modelInfo[1];
                }
                
                devices.push({
                    id: deviceId,
                    name: deviceName
                });
            }
        }
        
        return devices;
    } catch (error) {
        console.error('Error getting connected devices:', error);
        return [];
    }
}

/**
 * Takes a screenshot of the device and returns the image as a cv Mat
 * @param {object} driver - WebdriverIO driver
 * @returns {Promise<cv.Mat>} OpenCV Mat object of the screenshot
 */
async function takeScreenshot(driver, retries = 5) {
    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            // Reset UiAutomator2 server before attempting screenshot
            await resetUiAutomator2(driver);
            
            // Wait for UiAutomator2 server to be ready
            await new Promise(resolve => setTimeout(resolve, 3000));
            
            // Try to take screenshot with increased timeout
            const screenshot = await driver.takeScreenshot();
            const screenshotBuffer = Buffer.from(screenshot, 'base64');
            return cv.imdecode(screenshotBuffer);
        } catch (error) {
            console.error(`Screenshot attempt ${attempt} failed:`, error);
            
            if (attempt === retries) {
                // On last retry, try complete session reset
                try {
                    console.log('Attempting complete session reset...');
                    await driver.deleteSession();
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    await driver.createSession();
                    continue;
                } catch (resetError) {
                    console.error('Session reset failed:', resetError);
                    throw error;
                }
            }
            
            // Wait longer between retries
            await new Promise(resolve => setTimeout(resolve, 5000));
        }
    }
    throw new Error('Failed to take screenshot after all retries');
}

async function resetUiAutomator2(driver) {
    try {
        // Stop UiAutomator2 server processes
        await driver.executeScript('mobile: shell', [{
            command: 'am force-stop io.appium.uiautomator2.server'
        }]);
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        await driver.executeScript('mobile: shell', [{
            command: 'am force-stop io.appium.uiautomator2.server.test'
        }]);
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Clear UiAutomator2 app data
        await driver.executeScript('mobile: shell', [{
            command: 'pm clear io.appium.uiautomator2.server'
        }]);
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Start UiAutomator2 server with error checking
        const maxStartAttempts = 3;
        for (let attempt = 1; attempt <= maxStartAttempts; attempt++) {
            try {
                await driver.executeScript('mobile: shell', [{
                    command: 'am start -n io.appium.uiautomator2.server/.MainActivity'
                }]);
                
                // Verify server is running
                await driver.executeScript('mobile: shell', [{
                    command: 'ps | grep io.appium.uiautomator2.server'
                }]);
                
                console.log('UiAutomator2 server started successfully');
                await new Promise(resolve => setTimeout(resolve, 3000));
                return;
            } catch (startError) {
                console.error(`UiAutomator2 server start attempt ${attempt} failed:`, startError);
                if (attempt === maxStartAttempts) {
                    throw new Error('Failed to start UiAutomator2 server after multiple attempts');
                }
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
        }
    } catch (error) {
        console.error('Error resetting UiAutomator2:', error);
        throw error; // Propagate error to allow retry at higher level
    }
}

/**
 * Find an image on the screen and return its location
 * @param {cv.Mat} screenshot - Screenshot as OpenCV Mat
 * @param {string} templatePath - Path to the template image to find
 * @param {number} threshold - Matching threshold (0.0 to 1.0)
 * @returns {object|null} Location object with x, y coordinates or null if not found
 */
function findImageOnScreen(screenshot, templatePath, threshold = 0.8) {
    try {
        const template = cv.imread(templatePath);
        const result = screenshot.matchTemplate(template, cv.TM_CCOEFF_NORMED);
        const { maxVal, maxLoc } = result.minMaxLoc();
        
        if (maxVal >= threshold) {
            const x = maxLoc.x + Math.floor(template.cols / 2);
            const y = maxLoc.y + Math.floor(template.rows / 2);
            return { x, y, confidence: maxVal };
        }
        
        return null;
    } catch (error) {
        console.error('Error finding image on screen:', error);
        return null;
    }
}

/**
 * Wait for an image to appear on screen
 * @param {object} driver - WebdriverIO driver
 * @param {string} imagePath - Path to the image to wait for
 * @param {number} timeout - Maximum time to wait in milliseconds
 * @param {number} interval - Interval between checks in milliseconds
 * @returns {Promise<object|null>} Location object if found, null if timeout
 */
async function waitForImage(driver, imagePath, timeout = 30000, interval = 500) {
    console.log(`Waiting for image: ${path.basename(imagePath)}`);
    
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
        const screenshot = await takeScreenshot(driver);
        const location = findImageOnScreen(screenshot, imagePath);
        
        if (location) {
            console.log(`Image ${path.basename(imagePath)} found after ${(Date.now() - startTime) / 1000} seconds`);
            return location;
        }
        
        await new Promise(resolve => setTimeout(resolve, interval));
    }
    
    console.log(`Timeout waiting for image: ${path.basename(imagePath)}`);
    return null;
}

/**
 * Process a single ID
 * @param {object} driver - WebdriverIO driver
 * @param {string} id - ID to process
 */
async function processId(driver, id) {
    try {
        console.log(`Processing ID: ${id}`);

        // Step 1: Find and click "isi" image with offset
        const isiLocation = await waitForImage(driver, path.join(__dirname, 'images', 'isi.png'));
        if (!isiLocation) {
            console.log('Isi button not found. Skipping this ID.');
            return false;
        }
        await driver.performActions([{
            type: 'pointer',
            id: 'finger1',
            parameters: { pointerType: 'touch' },
            actions: [
                { type: 'pointerMove', duration: 0, x: isiLocation.x + 150, y: isiLocation.y + 100 },
                { type: 'pointerDown', button: 0 },
                { type: 'pause', duration: 100 },
                { type: 'pointerUp', button: 0 }
            ]
        }]);

        // Step 2: Clear text field using key events
        try {
            await driver.pressKeyCode(29, undefined, undefined); // KEYCODE_CTRL_LEFT
            await driver.pressKeyCode(29); // Hold ctrl
            await driver.pressKeyCode(41); // KEYCODE_A
            await driver.pressKeyCode(29, undefined, 1); // Release ctrl
            await driver.pressKeyCode(67); // KEYCODE_DEL
        } catch (error) {
            console.log('Trying alternative clear method...');
            await driver.executeScript('mobile: clearText', [{}]);
        }

        // Step 3: Enter ID
        await driver.sendKeys([id]);
        console.log(`Entered ID: ${id}`);

        // Step 4: Find and click "lupa" image with offset
        const lupaLocation = await waitForImage(driver, path.join(__dirname, 'images', 'lupa.png'));
        if (!lupaLocation) {
            console.log('Lupa button not found. Skipping this ID.');
            return false;
        }
        await driver.performActions([{
            type: 'pointer',
            id: 'finger1',
            parameters: { pointerType: 'touch' },
            actions: [
                { type: 'pointerMove', duration: 0, x: lupaLocation.x + 60, y: lupaLocation.y },
                { type: 'pointerDown', button: 0 },
                { type: 'pause', duration: 100 },
                { type: 'pointerUp', button: 0 }
            ]
        }]);

        // Step 5: Try to click the button instance using UiSelector with timeout
        console.log('Trying to click button using UiSelector');
        try {
            const buttonSelector = 'new UiSelector().className("android.widget.Button").instance(1)';
            const button = await driver.$(`android=${buttonSelector}`);
            await button.waitForExist({ timeout: 5000 }); // 5 second timeout
            await button.click();
        } catch (error) {
            console.log('Button not found within timeout, proceeding to next step');
        }

        // Step 6: Wait for either "sukses" or "gagal" condition
        let conditionFound = false;
        const startTime = Date.now();
        const timeout = 30000;

        while (!conditionFound && Date.now() - startTime < timeout) {
            const screenshot = await takeScreenshot(driver);
            
            // Check for success
            const suksesLocation = findImageOnScreen(screenshot, path.join(__dirname, 'images', 'sukses.png'));
            if (suksesLocation) {
                console.log('Success condition found');
                conditionFound = true;
                // Save successful ID to file
                try {
                    fs.appendFileSync('sukses.txt', id + '\n');
                    console.log(`ID ${id} saved to sukses.txt`);
                } catch (error) {
                    console.error(`Error saving ID to sukses.txt: ${error.message}`);
                }
                break;
            }

            // Check for failure
            const gagalLocation = findImageOnScreen(screenshot, path.join(__dirname, 'images', 'gagal.png'));
            if (gagalLocation) {
                console.log('Failure condition found');
                conditionFound = true;
                break;
            }

            await new Promise(resolve => setTimeout(resolve, 500));
        }

        if (!conditionFound) {
            console.log('Neither success nor failure condition was found within timeout');
            return false;
        }

        // Step 7: Click forward button using UiSelector
        console.log('Clicking forward button using UiSelector');
        const forwardSelector = 'new UiSelector().resourceId("com.higgs.domino:id/btnForward")';
        const forwardButton = await driver.$(`android=${forwardSelector}`);
        await forwardButton.click();

        return true;
    } catch (error) {
        console.error(`Error processing ID ${id}:`, error);
        return false;
    }
}

async function main() {
    try {
        // Get connected devices
        const devices = await getConnectedDevices();
        if (devices.length === 0) {
            console.error('No devices found');
            return;
        }

        // Read IDs from file
        const ids = await fs.promises.readFile('id.txt', 'utf8');
        const idList = ids.split('\n').filter(id => id.trim().length > 0);

        // Split IDs among available devices
        const chunks = [];
        const chunkSize = Math.ceil(idList.length / devices.length);
        
        for (let i = 0; i < idList.length; i += chunkSize) {
            chunks.push(idList.slice(i, i + chunkSize));
        }

        // Process IDs across devices with delay between initializations
        const processPromises = [];
        for (let index = 0; index < devices.length; index++) {
            const device = devices[index];
            // Add delay between device initializations
            if (index > 0) {
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
            // Create WebdriverIO options for this device
            console.log(`Setting up WebdriverIO options for device ${device.id}...`);
            const wdOpts = {
                protocol: 'http',
                hostname: '127.0.0.1',
                port: 4723,
                path: '/',
                logLevel: 'debug', // Changed to debug for more detailed logging
                connectionRetryCount: 15, // Increased retries further
                connectionRetryTimeout: 120000, // Doubled timeout
                capabilities: {
                    platformName: 'Android',
                    'appium:automationName': 'UiAutomator2',
                    'appium:deviceName': device.name,
                    'appium:udid': device.id,
                    'appium:noReset': true,
                    'appium:newCommandTimeout': 600,
                    'appium:uiautomator2ServerInstallTimeout': 120000,
                    'appium:adbExecTimeout': 120000,
                    'appium:skipServerInstallation': true,
                    'appium:skipDeviceInitialization': true,
                    'appium:autoGrantPermissions': true,
                    'appium:disableWindowAnimation': true,
                    'appium:appPackage': 'com.higgs.domino',
                    'appium:appActivity': 'com.higgs.domino.MainActivity'
                }
            };
            console.log('WebdriverIO options:', JSON.stringify(wdOpts, null, 2));


            // Start the app
            console.log(`Starting app on device ${device.id}...`);
            try {
                await execPromise(`adb -s ${device.id} shell am force-stop com.higgs.domino`);
                await new Promise(resolve => setTimeout(resolve, 1000));
                await execPromise(`adb -s ${device.id} shell am start -n com.higgs.domino/com.higgs.domino.MainActivity`);
                await new Promise(resolve => setTimeout(resolve, 5000));
            } catch (e) {
                console.error(`Failed to start app on device ${device.id}:`, e);
            }

            // Create WebdriverIO client for this device
            console.log(`Connecting to Appium server for device ${device.id}...`);
            let driver;
            try {
                driver = await remote(wdOpts);
                console.log(`Connected to device: ${device.id}`);
            } catch (error) {
                console.error(`Failed to initialize device ${device.id}:`, error);
                continue;
            }

            processPromises.push((async () => {
                try {
                    // Process this device's chunk of IDs
                    const deviceIds = chunks[index] || [];
                    let currentIndex = 0;

                    while (currentIndex < deviceIds.length) {
                        const id = deviceIds[currentIndex];
                        try {
                            const success = await processId(driver, id);
                            if (success) {
                                currentIndex++; // Move to next ID only if successful
                            } else {
                                // If process failed but didn't throw error, try to reconnect
                                console.log(`Processing failed for ID ${id}, attempting to reconnect...`);
                                try {
                                    await driver.deleteSession();
                                } catch (e) {
                                    console.log('Session already closed');
                                }

                                let retryCount = 0;
                                const maxRetries = 3;
                                
                                while (retryCount < maxRetries) {
                                    try {
                                        // Brief pause before reconnection
                                        await new Promise(resolve => setTimeout(resolve, 1000));
                                        
                                        // Try to reconnect with timeout
                                        driver = await Promise.race([
                                            remote(wdOpts),
                                            new Promise((_, reject) => setTimeout(() => reject(new Error('Connection timeout')), 10000))
                                        ]);
                                        console.log(`Reconnected to device: ${device.id} (Attempt ${retryCount + 1})`);
                                        break; // Successfully reconnected
                                    } catch (reconnectError) {
                                        retryCount++;
                                        console.error(`Failed to reconnect to device ${device.id} (Attempt ${retryCount}):`, reconnectError);
                                        if (retryCount === maxRetries) {
                                            console.error(`Max retries reached for device ${device.id}, skipping ID ${id}`);
                                            currentIndex++; // Skip this ID after max retries
                                        }
                                        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait before next retry
                                    }
                                }
                            }
                        } catch (error) {
                            console.error(`Error processing ID ${id} on device ${device.id}:`, error);
                            // Try to recover the session
                            try {
                                await driver.executeScript('mobile: shell', [{
                                    command: 'am force-stop io.appium.uiautomator2.server'
                                }]);
                                await new Promise(resolve => setTimeout(resolve, 2000));

                                // If error persists, try to reconnect
                                try {
                                    await driver.deleteSession();
                                } catch (e) {
                                    console.log('Session already closed');
                                }

                                let retryCount = 0;
                                const maxRetries = 3;
                                
                                while (retryCount < maxRetries) {
                                    try {
                                        // Brief pause before reconnection
                                        await new Promise(resolve => setTimeout(resolve, 1000));
                                        
                                        // Try to reconnect with timeout
                                        driver = await Promise.race([
                                            remote(wdOpts),
                                            new Promise((_, reject) => setTimeout(() => reject(new Error('Connection timeout')), 10000))
                                        ]);
                                        console.log(`Reconnected to device: ${device.id} after error (Attempt ${retryCount + 1})`);
                                        break; // Successfully reconnected
                                    } catch (reconnectError) {
                                        retryCount++;
                                        console.error(`Failed to reconnect to device ${device.id} (Attempt ${retryCount}):`, reconnectError);
                                        if (retryCount === maxRetries) {
                                            console.error(`Max retries reached for device ${device.id}, skipping ID ${id}`);
                                            currentIndex++; // Skip this ID after max retries
                                        }
                                        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait before next retry
                                    }
                                }
                            } catch (recoveryError) {
                                console.error('Recovery attempt failed:', recoveryError);
                                await new Promise(resolve => setTimeout(resolve, 5000)); // Wait before retrying
                            }
                        }
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                } finally {
                    try {
                        // Close the session
                        await driver.deleteSession();
                        console.log(`WebdriverIO session closed for device: ${device.id}`);
                    } catch (error) {
                        console.error(`Error closing session for device ${device.id}:`, error);
                    }
                }
            })());
        }

        // Wait for all devices to complete
        await Promise.all(processPromises);
        console.log('All devices completed processing');

    } catch (error) {
        console.error('Main process error:', error);
    }
}

// Run the main function
main().catch(console.error);

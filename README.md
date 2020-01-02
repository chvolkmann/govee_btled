# govee_btled
A Python wrapper for controlling a cheap Bluetooth RGB light bulb.

The LED in question is the Govee H6001 available for about 13€ on [Amazon Germany](https://www.amazon.de/Govee-farbwechsel-mehrfarbige-Leuchtmittel-Dekoration/dp/B07CPP5LCP). I also noticed that it is available under the name Minger H6001.

# Installation
Requires Python 3.  
Tested under Python 3.7 on Linux. Should also work for Windows.
```
pip install -U git+https://github.com/Freemanium/govee_btled
```

# Usage
The wrapper uses [pygatt](https://github.com/peplin/pygatt) to interface with Bluetooth and requires root permissions.


See `__main__.py` for a full example in action.

```python
import time
from govee_btled import BluetoothLED

led = BluetoothLED('<your MAC here>')
led.set_state(True)
led.set_color('blue')
time.sleep(1)
led.set_color('#facd03')
time.sleep(1)
# The bulb seems to have a white-mode which uses cold/warm white LEDs instead of the RGB LEDs.
# Supply a value between -1 (warm) and 1 (cold)
led.set_color_white(-0.4)
```

### Windows compatibility
While the wrapper has not been tested on Windows, you should be able to use it by replacing the backend `pygatt` uses internally.
```python
import pygatt
led = BluetoothLED('<your MAC here>', bt_backend_cls=pygatt.BGAPIBackend)
```

# Credit
- [Henje](https://github.com/henje)  
  Major help in reverse engineering both Govee's app and the Bluetooth protocol.

# Reverse engineering notes
The reverse engineering was done by analyzing the Bluetooth Low Energy communication between [Govee's Android app](https://play.google.com/store/apps/details?id=com.govee.home&hl=gsw) and the LED.

## Getting the traffic
Android has a developer feature that enables you to log and export Bluetooth traffic. Retrieving the dump is a bit different for Samsung phones, see this [StackOverflow post](https://stackoverflow.com/a/50868118). You can then pull the log with the [Android debug bridge](https://developer.android.com/studio/command-line/adb). This script pulls the latest log, in the case of Samsung phones
```bash
#!/bin/bash
# The last entry in the second-to-last row of (ls -l /sdcard/log)
filename=$(adb shell "ls -l /sdcard/log | grep snoop | tail -n 2 | head -n 1 | cut -d ' ' -f 9")
echo "Pulling $filename..."
adb pull "/sdcard/log/$filename"
```

To analyze the traffic, [Wireshark](https://www.wireshark.org/) was used. The following filter was helpful in understanding the protocol:
```
(btatt or btgatt) and (btatt.handle in {0x15 0x11}) and btatt.opcode == 0x52 and not (btatt.value[0] == 0xaa)
```
- I noticed a lot of request-ack messages with handles `0x15 <--> 0x11` respectively. Hexcodes for RGB values recognizable, so I filtered those out.
- Opcode `0x52` filters for write commands as we are only interested in the traffic we send.
- There were two types of prefixes in these packets: `0xaa` and `0x33`, where `0x33` carried the RGB data.

I exported the dump as its own PCAP file and reopened it in Wireshark to export it as JSON. In order to make it easier to analyze the packets' payloads, I put every packet's payload in a row of a text file.

## Analyzing the traffic

For this scenario
1) the LED is turned on, then off, then on again
2) the color is changed
3) the brightness is changed
4) the warm/cold-white slider in the app is used
5) the LED is turned off again

This was mostly done with a delay of approx. 5 seconds in between to recognize the timestamps in Wireshark.

Sample snooped traffic:
```
33 01 01 000000 00 000000 000000000000000000 33
33 09 12 320503 00 000000 000000000000000000 1c
33 09 12 321103 00 000000 000000000000000000 08
33 01 00 000000 00 000000 000000000000000000 32
33 01 01 000000 00 000000 000000000000000000 33
33 09 12 322503 00 000000 000000000000000000 3c
33 05 02 ff0000 00 ff8912 000000000000000000 af
33 05 02 00ff00 00 ff8912 000000000000000000 af
33 05 02 0000ff 00 ff8912 000000000000000000 af
33 05 02 ffff00 00 ff8912 000000000000000000 50
33 05 02 8b00ff 00 ff8912 000000000000000000 24
33 05 02 00ffff 00 ff8912 000000000000000000 50
33 05 02 ffffff 00 ff8912 000000000000000000 af
33 04 7f 000000 00 000000 000000000000000000 48
33 04 2e 000000 00 000000 000000000000000000 19
33 04 14 000000 00 000000 000000000000000000 23
33 04 fe 000000 00 000000 000000000000000000 c9
33 05 02 ffffff 01 d7e2ff 000000000000000000 00
33 05 02 ffffff 01 ff932c 000000000000000000 8a
33 01 00 000000 00 000000 000000000000000000 32
```
Spaces were added according to how I understood the boundaries of the protocol.
- `0x33` seems to be a command indicator (the only alternative value for the first byte is `0xaa`)
- The second byte seems identify the packet type
  - `0x01`: power
  - `0x04`: brightness
  - `0x05`: color
- The third byte differs based on type.
  - For power packets, it's a boolean indicating the power state.
  - For brightness packets, it corresponds to a `uint8` brightness value.
  - For color packets, this indicates an operation mode. The app offers a microphone, a scenes and a manual mode (labeled "color" in the app). We are only interested in manual mode, which is `0x02`.
- Color packets now carry an RGB value, followed by a boolean and a second RGB value. The boolean seems to switch the set of LEDs used within the bulb. There is one set for RGB values and one for warm/cold-white values, where `True` corresponds to the warm/cold-white LEDs. When the flag is set, the first RGB value seems to be ignored and vice-versa. The values for warm/cold-white LEDs cannot be set arbitrarily. The slider within the app UI uses a list of hardcoded color codes. (thanks Henje!)
- Zeropadding follows.
- Finally, a checksum over the payload is calculated by XORing all bytes.
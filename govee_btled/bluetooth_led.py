#!/usr/bin/env python3

from enum import IntEnum

import pygatt
from colour import Color

from .shades_of_white import values as SHADES_OF_WHITE
from .errors import ConnectionTimeout

UUID_CONTROL_CHARACTERISTIC = '00010203-0405-0607-0809-0a0b0c0d2b11'

def color2rgb(color):
    """ Converts a color-convertible into 3-tuple of 0-255 valued ints. """
    col = Color(color)
    rgb = col.red, col.green, col.blue
    rgb = [round(x * 255) for x in rgb]
    return tuple(rgb)

class LedCommand(IntEnum):
    """ A control command packet's type. """
    POWER      = 0x01
    BRIGHTNESS = 0x04
    COLOR      = 0x05

class LedMode(IntEnum):
    """
    The mode in which a color change happens in.
    
    Currently only manual is supported.
    """
    MANUAL     = 0x02
    MICROPHONE = 0x06
    SCENES     = 0x05

class BluetoothLED:
    """ Bluetooth client for Govee's RGB LED H6001. """
    def __init__(self, mac, bt_backend_cls=pygatt.GATTToolBackend):
        self.mac = mac
        self._bt = bt_backend_cls()
        self._bt.start()
        try:
            self._dev = self._bt.connect(self.mac)
        except pygatt.exceptions.NotConnectedError as err:
            self._cleanup()
            raise ConnectionTimeout(self.mac, err)
    
    def __del__(self):
        self._cleanup()

    def _cleanup(self):
        if hasattr(self, '_dev') and self._dev:
            self._dev.disconnect()
            self._dev = None
        if hasattr(self, '_bt') and self._bt:
            self._bt.stop()
            self._bt = None
    
    def _send(self, cmd, payload):
        """ Sends a command and handles paylaod padding. """
        if not isinstance(cmd, int):
           raise ValueError('Invalid command')
        if not isinstance(payload, bytes) and not (isinstance(payload, list) and all(isinstance(x, int) for x in payload)):
            raise ValueError('Invalid payload')
        if len(payload) > 17:
            raise ValueError('Payload too long')

        cmd = cmd & 0xFF
        payload = bytes(payload)

        frame = bytes([0x33, cmd]) + bytes(payload)
        # pad frame data to 19 bytes (plus checksum)
        frame += bytes([0] * (19 - len(frame)))
        
        # The checksum is calculated by XORing all data bytes
        checksum = 0
        for b in frame:
            checksum ^= b
        
        frame += bytes([checksum & 0xFF])
        self._dev.char_write(UUID_CONTROL_CHARACTERISTIC, frame)
    
    def set_state(self, onoff):
        """ Controls the power state of the LED. """
        self._send(LedCommand.POWER, [0x1 if onoff else 0x0])
    
    def set_brightness(self, value):
        """
        Sets the LED's brightness.
        
        `value` must be a value between 0.0 and 1.0
        """
        if not 0 <= float(value) <= 1:
            raise ValueError(f'Brightness out of range: {value}')
        value = round(value * 0xFF)
        self._send(LedCommand.BRIGHTNESS, [value])
        
    def set_color(self, color):
        """
        Sets the LED's color.
        
        `color` must be a color-convertible (see the `colour` library),
        e.g. 'red', '#ff0000', etc.
        """
        self._send(LedCommand.COLOR, [LedMode.MANUAL, *color2rgb(color)])
    
    def set_color_white(self, value):
        """
        Sets the LED's color in white-mode.

        `value` must be a value between -1.0 and 1.0
        White mode seems to enable a different set of LEDs within the bulb.
        This method uses the hardcoded RGB values of whites, directly taken from
        the mechanism used in Govee's app.
        """
        if not -1 <= value <= 1:
            raise ValueError(f'White value out of range: {value}')
        value = (value+1) / 2 # in [0.0, 1.0]
        index = round(value * (len(SHADES_OF_WHITE)-1))
        white = Color(SHADES_OF_WHITE[index])
        
        # Set the color to white (although ignored) and the boolean flag to True
        self._send(LedCommand.COLOR, [LedMode.MANUAL, 0xff, 0xff, 0xff, 0x01, *color2rgb(white)])
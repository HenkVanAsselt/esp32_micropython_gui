try:
  import usocket as socket
except:
  import socket

from machine import Pin
import network
from time import sleep

import esp
esp.osdebug(None)

import gc
gc.collect()

ssid = 'hvahome'
password = 'Groenekanseweg10'

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

print("Connecting ...")
while station.isconnected() == False:
    sleep(0.2)
print("Connected.")

print(station.ifconfig())

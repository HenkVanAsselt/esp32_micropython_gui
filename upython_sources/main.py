print("Running main.py")

from hc_sr04 import HCSR04
from machine import Pin
 
sensor = HCSR04(trigger_pin=4, echo_pin=2,echo_timeout_us=1000000)
 
try:
  while True:
    distance = sensor.distance_cm()
    print('distance (cm): ' + str(distance))
except KeyboardInterrupt:
       pass
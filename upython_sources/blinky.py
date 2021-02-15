from machine import Pin
from time import sleep


def blink():

    led = Pin(2, Pin.OUT)

    while True:
        print("on")
        led.on()
        sleep(0.1)
        print("off")
        led.off()
        sleep(1.5)

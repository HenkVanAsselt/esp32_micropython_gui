import esp32   # noqa
from time import sleep

while True:
   temp_f = esp32.raw_temperature()
   temp_c = (temp_f - 32) / 1.8
   print("Temp is %s Fahrenheit / %s Celcius" % (temp_f, temp_c))

   sleep(2)
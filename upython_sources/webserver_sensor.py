
try:
  import usocket as socket
except:
  import socket

import gc
gc.collect()

import machine
import network

my_ssid = "hvahome"
my_psk = "Groenekanseweg10"

def do_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect(my_ssid, my_psk)
        while not wlan.isconnected():
            pass
    print('network config:', wlan.ifconfig())

def read_ds_sensor():
    # roms = ds_sensor.scan()
    # print('Found DS devices: ', roms)
    # print('Temperatures: ')
    # ds_sensor.convert_temp()
    # for rom in roms:
    #     temp = ds_sensor.read_temp(rom)
    #     if isinstance(temp, float):
    #         msg = round(temp, 2)
    #         print(temp, end=' ')
    #         print('Valid temperature')
    #         return msg
    # return b'0.0'
    return 21.0


def web_page():
    temp = read_ds_sensor()
    html = """<!DOCTYPE HTML><html><head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://use.fontawesome.com/releases/v5.7.2/css/all.css" integrity="sha384-fnmOCqbTlWIlj8LyTjo7mOUStjsKC4pOpQbqyi7RrhN7udi9RwhKkMHpvLbHG9Sr" crossorigin="anonymous">
  <style> html { font-family: Arial; display: inline-block; margin: 0px auto; text-align: center; }
    h2 { font-size: 3.0rem; } p { font-size: 3.0rem; } .units { font-size: 1.2rem; } 
    .ds-labels{ font-size: 1.5rem; vertical-align:middle; padding-bottom: 15px; }
  </style></head><body><h2>ESP32 DS18B20 WebServer</h2>
  <p><i class="fas fa-thermometer-half" style="color:#059e8a;"></i> 
    <span class="ds-labels">Temperature</span>
    <span id="temperature">""" + str(temp) + """</span>
    <sup class="units">&deg;C</sup>
  </p>
    <p><i class="fas fa-thermometer-half" style="color:#059e8a;"></i> 
    <span class="ds-labels">Temperature</span>
    <span id="temperature">""" + str(round(temp * (9 / 5) + 32.0, 2)) + """</span>
    <sup class="units">&deg;F</sup>
  </p></body></html>"""
    return html


do_connect()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)

while True:
    try:
        if gc.mem_free() < 102000:
            gc.collect()
        conn, addr = s.accept()
        conn.settimeout(3.0)
        print('Got a connection from %s' % str(addr))
        request = conn.recv(1024)
        conn.settimeout(None)
        request = str(request)
        print('Content = %s' % request)
        response = web_page()
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)
        conn.close()
    except OSError as e:
        conn.close()
        print('Connection closed')
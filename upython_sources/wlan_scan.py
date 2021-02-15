import machine  # noqa
import network  # noqa


my_ssid = "hvahome"
my_psk = "Groenekanseweg10"


def do_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("connecting to network...")
        wlan.connect(my_ssid, my_psk)
        while not wlan.isconnected():
            pass
    print("network config:", wlan.ifconfig())


do_connect()

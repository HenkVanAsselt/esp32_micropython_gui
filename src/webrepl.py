"""micropython webrepl related functions.

Uses 'selenium' for the connection and 'keyboard' to enter the password.

Example usage:
python webrepl.py --ip 192.168.178.149 --port 8266 --password daan3006

20210322, HenkA
"""

__version__ = 0.1

# Global imports
import webbrowser
import pathlib
import time
import argparse

# 3rd party imports
import keyboard
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

# local imports
from lib.helper import dumpArgs, debug


# -----------------------------------------------------------------------------
def get_webrepl_client_location() -> str:
    """Get the full path to the webrepl client html file."""

    # Check if we can find the esptool executable
    webrepl_client = pathlib.Path("../bin/webrepl-client/webrepl.html").resolve()
    if not webrepl_client.is_file():
        print(f"Error: Could not find {str(webrepl_client)}")
        return str(webrepl_client)
    else:
        return ""


# -----------------------------------------------------------------------------
@dumpArgs
def start_webrepl_html(ip="") -> bool:
    """Start webrepl client

    :param ip: IP address and optional portnumber to connect to
    :returns: True on success, False in case of an error

    The IP address and portnumber can be given like
    '192.168.178.149'   (which will use the default port 8266)
    '192.168.178.149:1111' (which will use portnumber 1111)
    """

    # Check if we can find the esptool executable
    webrepl_client = pathlib.Path("../bin/webrepl-client/webrepl.html").resolve()
    if not webrepl_client.is_file():
        print(f"Error: Could not find {str(webrepl_client)}")
        return False

    if not ip:
        print("Error: Could not obtain WLAN ip address")
        return False

    # If no portnumber was given, use the default port 8266
    if ":" in ip:
        ip, port = ip.split(":", maxsplit=2)
    else:
        port = 8266

    print(f"Modifyting {str(webrepl_client)}")

    with open(str(webrepl_client), "r") as input_file:
        lines = input_file.readlines()

    with open(str(webrepl_client), "w") as output_file:
        for line in lines:
            if line.startswith('<input type="text" name="webrepl_url" id="url" value='):
                output_file.write(
                    f'<input type="text" name="webrepl_url" id="url" value="ws://{ip}:{port}/" />\n'
                )
            else:
                output_file.write(line)

    # Start the webrepl client with the modified IP address
    print(f"Connecting webrepl client to {ip}")
    webbrowser.open(f"{webrepl_client}", new=2)
    return True


# -------------------------------------------------------------------------
@dumpArgs
def start_session(browser, url) -> None:
    """Start the session by entering the url in the webpage.
    :param browser: The selenium browser session
    :param url: URL string. Format is like "ws://192.168.178.149:8266/"
    """

    element = browser.find_element_by_id("url")
    element.clear()
    element.send_keys(url)
    element.send_keys(Keys.RETURN)


# -------------------------------------------------------------------------
@dumpArgs
def enter_password(browser, password: str, interval=0.5, max_retries=10) -> bool:
    """Enter the passsword in the session.
    This will not be done with selenium, but with 3rd party library 'keyboard'
    :param browser: The selenium browser sessin;
    :param password: The password to enter
    :param interval: The time in seconds between each attempt to find the password prompt.
    :param max_retries: Maximum number of retries.
    :returns: True in case of success, False in case of an error.
    """

    element = browser.find_element_by_id("term")

    tries = 0
    while "Password" not in element.text:
        if 'Disconnected' in element.text:
            debug("Session is disconnected")
            return False
        if tries > max_retries:
            debug("Execeeded maximum number of tries to find the password prompt")
            return False
        time.sleep(interval)
        tries += 1

    debug("Found password prompt")
    debug(f"Entering {password}")
    keyboard.write(password)
    keyboard.write('\n')
    debug("Password entered")

    time.sleep(0.5)
    if "Access denied" in element.text:
        debug(f"Access Denied. Was the \"{password}\" correct?")
        return False

    return True


# -------------------------------------------------------------------------
@dumpArgs
def wait_for_repl_prompt(browser, max_retries=10) -> bool:
    """Wait for the repl password prompt '>>>'.
    :returns: True in case of success, False in case of an error.
    """

    element = browser.find_element_by_id("term")

    tries = 0
    while ">>>" not in element.text:
        tries += 1
        debug(f"{element.text=}")
        time.sleep(0.5)
        if tries > max_retries:
            debug("Execedded maximum number of tries to find the >>> prompt")
            return False
    debug("Found >>> prompt")
    return True


# -------------------------------------------------------------------------
@dumpArgs
def start_webrepl_html(url="", password=""):
    """Start webrepl with selenium.
    :returns: selenium webdriver when successfull, None in case of an error
    """

    # Check if we can find the esptool executable
    webrepl_client = pathlib.Path("../bin/webrepl-client/webrepl.html").resolve()
    if not webrepl_client.is_file():
        print(f"Error: Could not find {str(webrepl_client)}")
        return False
    webpage = str(webrepl_client)

    opts = Options()
    opts.headless = False
    browser = Chrome(options=opts)
    browser.get(webpage)

    start_session(browser, url)
    success = enter_password(browser, password)
    if not success:
        return None

    success = wait_for_repl_prompt(browser)
    if not success:
        return None

    # Do something here

    # browser.close()
    return browser


# -------------------------------------------------------------------------
def main(args):
    """main (test function)"""

    debug(f"main arguments = {args=}")

    url = f"ws://{args.ip}:{args.port}/"       # "ws://192.168.178.149:8266/"
    start_webrepl_html(url=url, password=args.password)


# =============================================================================
if __name__ == "__main__":

    import sys
    import lib.helper

    lib.helper.clear_debug_window()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ip",
        help="esp32 wlan ipaddress",
        default="192.168.178.149"
    )

    parser.add_argument(
        "--port",
        help="esp32 wlan portnumber",
        default="8266",
    )

    parser.add_argument(
        "--password",
        help="esp32 webrepl password",
        default="daan3006"
    )

    args = parser.parse_args()
    debug(f"{args=}")

    sys.exit(main(args))

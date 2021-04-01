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

global browser


# -----------------------------------------------------------------------------
def find_webrepl_html_file() -> str:
    """Get the full path to the webrepl client html file.
    """

    webrepl_client = pathlib.Path("../bin/webrepl-client/webrepl.html").resolve()

    if not webrepl_client.is_file():
        print(f"Error: Could not find {str(webrepl_client)}")
        return ""

    return str(webrepl_client)


# -----------------------------------------------------------------------------
@dumpArgs
def start_webrepl_html(ip="") -> bool:
    """Start webrepl client after modifying it's contents to connect to the given ip

    :param ip: IP address and optional portnumber to connect to
    :returns: True on success, False in case of an error

    The IP address and portnumber can be given like
    '192.168.178.149'   (which will use the default port 8266)
    '192.168.178.149:1111' (which will use portnumber 1111)
    """

    # Check if we can find the esptool executable
    webrepl_html_file = find_webrepl_html_file()
    if not webrepl_html_file:
        print(f"Error: Could not find webrepl.html")
        return False

    if not ip:
        print("Error: No WLAN ip address has been given.")
        return False

    url = ip_to_url(ip)

    print(f"Modifying {webrepl_html_file}")

    with open(webrepl_html_file, "r") as input_file:
        lines = input_file.readlines()

    with open(webrepl_html_file, "w") as output_file:
        for line in lines:
            if line.startswith('<input type="text" name="webrepl_url" id="url" value='):
                output_file.write(
                    f'<input type="text" name="webrepl_url" id="url" value="{url}" />\n'
                )
            else:
                output_file.write(line)

    # Start the webrepl client with the modified IP address
    print(f"Connecting webrepl client to {ip}")
    webbrowser.open(f"{webrepl_html_file}", new=2)
    return True


# -------------------------------------------------------------------------
@dumpArgs
def ip_to_url(ip, port="") -> str:
    """Convert an IP address to a full URL like "ws://192.168.178.149:8266/"
    :param ip: ip address with optional port number
    :param port: Optional port number. Could be embedded in the ip address
    :returns: url string.

    If no portnumber was given, use the default port 8266
    """

    # If no portnumber was given, use the default port 8266
    if ":" in ip:
        ip, port = ip.split(":", maxsplit=2)
    else:
        if not port:
            port = 8266

    url = f"ws://{ip}:{port}/"       # "ws://192.168.178.149:8266/"
    debug(f"Returning {url=}")
    return url


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
def wait_for_welcome_message(browser, interval=0.5, max_retries=10) -> bool:
    """Wait for the welcome message.
    :param browser: The selenium browser sessin;
    :param interval: The time in seconds between each attempt to find the password prompt.
    :param max_retries: Maximum number of retries.
    :returns: True in case of success, False in case of an error.
    """

    element = browser.find_element_by_id("term")

    tries = 0
    while "Welcome" not in element.text:
        if tries > max_retries:
            print(f"ERROR: Execeeded maximum number of {max_retries} tries waiting for welcome message.")
            return False
        time.sleep(interval)
        tries += 1
        if "Disconnected" in element.text:
            print("ERROR: webrepl could not succesfully connect to a device.")
            return False
    else:
        print("Welcome message found")

    return True


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
            print("ERROR: webrepl could not succesfully connect to a device.")
            return False
        if tries > max_retries:
            print(f"ERROR: Execeeded maximum number of {max_retries } tries to find the password prompt")
            return False
        time.sleep(interval)
        tries += 1

    keyboard.write(password)
    keyboard.write('\n')
    debug("Password entered")

    time.sleep(0.5)

    if "Access denied" in element.text:
        print(f"Error: Access Denied. Was \"{password}\" the correct password?")
        return False
    else:
        print("password has been accepted.")

    return True


# -------------------------------------------------------------------------
@dumpArgs
def wait_for_repl_prompt(browser, max_retries=10) -> bool:
    """Wait for the repl password prompt '>>>'.
    :returns: True in case of success, False in case of an error.
    """

    element = browser.find_element_by_id("term")

    if "Access denied" in element.text:
        print("Error: Access Denied.")
        return False

    tries = 0
    while ">>>" not in element.text:
        tries += 1
        debug(f"{element.text=}")
        time.sleep(0.5)
        if tries > max_retries:
            print(f"Error: Execeeded maximum number of {max_retries} tries to find the >>> prompt")
            return False
    else:
        print("repl prompt found")

    # Just to be sure, exit raw repl mode
    keyboard.press_and_release('ctrl+b')

    return True


# -------------------------------------------------------------------------
@dumpArgs
def start_webrepl_with_selenium(url="", password=""):
    """Start webrepl with selenium.

    In case of 'Access Denied' or no >>> prompt found, the browser window
    will be closed automatically, else it will stay open for interactive usage.

    :returns: selenium webdriver instance when successfull, None in case of an error
    """

    # Check if we can find the esptool executable
    webrepl_html_file = find_webrepl_html_file()
    if not webrepl_html_file:
        print(f"Error: Could not find webrepl.html")
        return False

    opts = Options()
    opts.headless = False

    # The following should suppress messages like
    # DevTools listening on ws://127.0.0.1:64030/devtools/browser/abba5851-0de1-4f43-9182-df397a0b4eab
    opts.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Make 'browser' global.
    # The side-effect of global is that the browser window will stay open and interactive.
    global browser
    browser = Chrome(options=opts)
    browser.get(webrepl_html_file)

    start_session(browser, url)
    success = wait_for_welcome_message(browser)
    if not success:
        browser.close()
        return None

    success = enter_password(browser, password)
    if not success:
        browser.close()
        return None

    success = wait_for_repl_prompt(browser)
    if not success:
        browser.close()
        return None

    # Do something here

    # browser.close()
    return browser


# -------------------------------------------------------------------------
def main(args):
    """main (test function)"""

    # url = f"ws://{args.ip}:{args.port}/"       # "ws://192.168.178.149:8266/"
    url = ip_to_url(args.ip, args.port)
    browser = start_webrepl_with_selenium(url=url, password=args.password)

    if not browser:
        debug("No browser. Return")
        return

    element = browser.find_element_by_id("term")
    if "Disconnected" in element.text:
        print("ERROR: webrepl could not succesfully connect to a device.")
        browser.close()


# =============================================================================
if __name__ == "__main__":

    import sys
    from lib.helper import clear_debug_window

    clear_debug_window()

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

    arguments = parser.parse_args()
    debug(f"{arguments=}")

    sys.exit(main(arguments))

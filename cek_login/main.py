import os
from colorama import init, Fore, Style
import time
from datetime import datetime

# Initialize colorama
init()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print(Fore.CYAN + """
    ╔══════════════════════════════════════════╗
    ║              CEK LOGIN                   ║
    ╚══════════════════════════════════════════╝
    """ + Style.RESET_ALL)
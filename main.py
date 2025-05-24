import os
import time
from colorama import init, Fore, Back, Style

# Initialize colorama
init()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    print(Fore.CYAN + """
    ╔══════════════════════════════════════════╗
    ║                 DOMINO                   ║
    ╚══════════════════════════════════════════╝
    """ + Style.RESET_ALL)

def print_menu():
    print(Fore.YELLOW + "\n=== MENU UTAMA ===" + Style.RESET_ALL)
    print(Fore.WHITE + """
    [1] Ganti Password
    [2] Login Pertanyaan
    [3] Cek Login
    [4] Keluar
    """ + Style.RESET_ALL)

def main():
    while True:
        clear_screen()
        print_banner()
        print_menu()
        
        try:
            choice = input(Fore.GREEN + "\nPilih menu (1-4): " + Style.RESET_ALL)
            
            if choice == "1":
                clear_screen()
                print(Fore.CYAN + "\nMemuat modul Ganti Password..." + Style.RESET_ALL)
                try:
                    from ganti_pass.main import main as ganti_pass_main
                    ganti_pass_main()
                except ImportError:
                    print(Fore.RED + "\nError: Modul Ganti Password belum tersedia!" + Style.RESET_ALL)
                    time.sleep(2)
                
            elif choice == "2":
                clear_screen()
                print(Fore.CYAN + "\nMemuat modul Login Pertanyaan..." + Style.RESET_ALL)
                try:
                    from log_pertanyaan.main import main as log_pertanyaan_main
                    log_pertanyaan_main()
                except ImportError:
                    print(Fore.RED + "\nError: Modul Login Pertanyaan belum tersedia!" + Style.RESET_ALL)
                    time.sleep(2)
                
            elif choice == "3":
                clear_screen()
                print(Fore.CYAN + "\nMemuat modul Cek Login..." + Style.RESET_ALL)
                try:
                    from cek_login.main import main as cek_login_main
                    cek_login_main()
                except ImportError:
                    print(Fore.RED + "\nError: Modul Cek Login belum tersedia!" + Style.RESET_ALL)
                    time.sleep(2)
                
            elif choice == "4":
                clear_screen()
                print(Fore.YELLOW + "\nTerima kasih telah menggunakan sistem ini!")
                print("Program akan keluar..." + Style.RESET_ALL)
                time.sleep(2)
                break
                
            else:
                print(Fore.RED + "\nError: Pilihan tidak valid!" + Style.RESET_ALL)
                time.sleep(1)
                
        except Exception as e:
            print(Fore.RED + f"\nError: {str(e)}" + Style.RESET_ALL)
            time.sleep(2)

if __name__ == "__main__":
    main()

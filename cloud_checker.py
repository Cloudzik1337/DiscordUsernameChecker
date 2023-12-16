

import itertools
import string
import queue
import threading
from time import sleep
import traceback
import random
import os
import tls_client

lock = threading.Lock()
with open("names.txt", "a") as f: f.close()
with open("proxies.txt", "a") as f: f.close()
with open("unchecked_names.txt", "a") as f: f.close()
with open("errors.txt", "a") as f: f.close()
proxies = open("proxies.txt", "r").read().splitlines()
if len(proxies) == 0:
    proxies = [None]
proxy_cycle = itertools.cycle(proxies)
REQUETS_CLIENT_IDENTIFIER = "chrome_113"

#Globals
RPS = 0
REQUESTS = 0
WORKS = 0
TAKEN = 0







class _Colors:
    """Menu colors"""
    @staticmethod
    def _color_code(code):
        """Static method to format color codes"""
        return f'\033[{code}m'


    ENDC: str = _color_code(0)
    BOLD: str = _color_code(1)
    UNDERLINE: str = _color_code(4)
    BLACK: str = _color_code(30)
    RED: str = _color_code(31)
    GREEN: str = _color_code(32)
    YELLOW: str = _color_code(33)
    BLUE: str = _color_code(34)
    MAGENTA: str = _color_code(35)
    CYAN: str = _color_code(36)
    WHITE: str = _color_code(37)
    REDBG: str = _color_code(41)
    GREENBG: str = _color_code(42)
    YELLOWBG: str = _color_code(43)
    BLUEBG: str = _color_code(44)
    MAGENTABG: str = _color_code(45)
    CYANBG: str = _color_code(46)
    WHITEBG: str = _color_code(47)
    GREY: str = _color_code(90)
    REDGREY: str = _color_code(91)
    GREENGREY: str = _color_code(92)
    YELLOWGREY: str = _color_code(93)
    BLUEGREY: str = _color_code(94)
    MAGENTAGREY: str = _color_code(95)
    CYANGREY: str = _color_code(96)
    WHITEGREY: str = _color_code(97)
    GREYBG: str = _color_code(100)
    REDGREYBG: str = _color_code(101)
    GREENGREYBG: str = _color_code(102)
    YELLOWGREYBG: str = _color_code(103)
    BLUEGREYBG: str = _color_code(104)
    MAGENTAGREYBG: str = _color_code(105)
    CYANGREYBG: str = _color_code(106)
    WHITEGREYBG: str = _color_code(107)

Colors = _Colors()







def clear():
    os.system('cls' if os.name=='nt' else 'clear')
clear()
class Pomelo:
    def __init__(self):
        self.endpoint = "https://discord.com/api/v9"
        self.headers_post = {"Content-Type": "application/json"}
        self.session = tls_client.Session(
            client_identifier=REQUETS_CLIENT_IDENTIFIER,
            random_tls_extension_order=True
        )
        
    def restart_session(self):
        self.session = tls_client.Session(
            client_identifier=REQUETS_CLIENT_IDENTIFIER,
            random_tls_extension_order=True
            
        )


    def check(self, name):
        self.restart_session()
        global RPS, REQUESTS, WORKS, TAKEN
        while True:
            try:
                try:
                    name, proxy = name
                except:
                    proxy = None
                if proxy is not None:
                    proxy = f"http://{str(proxy).strip()}"
                r = self.session.post(
                    url=self.endpoint + "/unique-username/username-attempt-unauthed",
                    headers = self.headers_post,
                    json={"username": name},
                    proxy = proxy
                ) 
                REQUESTS += 1
          
                if r.status_code in [200, 201, 204]:
                    if r.json()["taken"]:
                        TAKEN += 1
                        return False, r.json(), r.status_code
                        
                        
                    else:
                        WORKS += 1
                        if str(r.json()) in ["", None, "{}"]:
                            return False, None, r.status_code
                        return True, r.json(), r.status_code
           
                #rate limited
                elif r.status_code == 429:
                    if proxy is None:
                        try:
                            return "RATELIMITED", r.json()["retry_after"], r.status_code
                        except:
                            with open("errors.txt", "w") as f:
                                f.write(f"{name, r.json(), r.status_code}\n")
                                f.close()
                            return "RATELIMITED", None, r.status_code
                
            except:
            # timeout
                with lock:
                    try:
                        exception = traceback.format_exc()
                        with open("errors.txt", "w") as f:
                            f.write(f"{exception}\n")
                            f.close()
                    except:
                        pass
                
                        
        

        



g = Colors.GREY
r = Colors.RED
x = Colors.ENDC
ASCII = f"""
{g}                      :::!~!!!!!:.
                .xUHWH!! !!?M88WHX:.
                .X*#M@$!!  !X!M$$$$$$WWx:.
            :!!!!!!?H! :!$!$$$$$$$$$$8X:
            !!~  ~:~!! :~!$!#$$$$$$$$$$8X:
            :!~::!H!<   ~.U$X!?R$$$$$$$$MM!
            ~!~!!!!~~ .:XW$$$U!!?$$$$$$RMM!
            !:~~~ .:!M"T#$$$$WX??#MRRMMM!
            ~?WuxiW*`   `"#$$$$8!!!!??!!!
            :X- M$$$$       `"T#$T~!8$WUXU~
            :%`  ~#$$$m:        ~!~ ?$$$$$$
        :!`.-   ~T$$$$8xx.  .xWW- ~""##*"
.....   -~~:<` !    ~?T#$$@@W@*?$$      /`
W$@@M!!! .!~~ !!     .:XUW$W!~ `"~:    :
#"~~`.:x%`!!  !H:   !WM$$$$Ti.: .!WUn+!`
:::~:!!`:X~ .: ?H.!u "$$$B$$$!W:U!T$$M~
.~~   :X@!.-~   ?@WTWo("*$$$W$TH$! `
Wi.~!X$?!-~    : ?$$$B$Wu("**$RM!
$R@i.~~ !     :   ~$$$$$B$$en:``
?MXT@Wx.~    :     ~"##*$$$$M~

                    {r}@{x}  Cloud 2023                  {r}@{x}
                    {r}@{x}  github.com/cloudzik1377     {r}@{x}
                    {r}@{x}  discord.cloudzik.me         {r}@{x}
        """
clear()
print(ASCII)

CLOUDCHECKER = Pomelo()

# username can contain letters, numbers, and underscores
chars = string.ascii_lowercase + string.digits + "_" + '.'

with open("unchecked_names.txt", "r") as f:
    combos = f.read().splitlines()
    f.close()
if len(combos) == 0:
    combos = itertools.product(chars, repeat=int(input("Length of username: ")))
    with open("unchecked_names.txt", "w") as f:
        
        for i in combos:
            f.write("".join(i))
            f.write("\n")
        f.close()
    with open("unchecked_names.txt", "r") as f:
        combos = f.read().splitlines()
        f.close()
queue = queue.Queue()
# actually load only random 50k line (Long list will take too long to load)
# combos = random.sample(combos, 50000)
for name in combos:
    print(f"[{Colors.YELLOW}+{Colors.ENDC}] Adding username = {Colors.CYAN}{name}{Colors.ENDC}", end="\r")
    
    name = [name.strip(), next(proxy_cycle)]
    queue.put(name)

def worker():
    
    while queue.qsize() > 0:
        
        name= queue.get()
        try:
            available, json, status_code = CLOUDCHECKER.check(name)
        except:
            with lock:
                exception = traceback.format_exc()
                with open("errors.txt", "a") as f:
                    f.write(f"{exception}\n")
                    f.close()
            available, json, status_code = "ERROR", None, None
        name, proxy = name
       
        # if proxy cut it down to 10 chars
        proxy_formated = str(proxy[:10]+'*'*10) if proxy else 'Proxyless'
        with lock:
            
            if available is True:
                # Make print aligned so even if under was rate limited it will still be aligned
                print(f"[{Colors.GREEN}+{Colors.ENDC}] Available  : {Colors.CYAN}{name}{Colors.ENDC},    RPS : {Colors.CYAN}{RPS} / s{Colors.ENDC},  resp : {Colors.CYAN}{json}{Colors.ENDC}, proxy : {Colors.CYAN}{proxy_formated}{Colors.ENDC}")
                with open("names.txt", "a") as f:
                    f.write(name)
                    f.write("\n")
                    f.close()
            elif available == "RATELIMITED":
                # add spaces to make = under aligned
                print(f"[{Colors.YELLOW}?{Colors.ENDC}] TIMEOUT    : {Colors.CYAN}{json}{Colors.ENDC},{' '*(8-int(len(str(json))))}RPS : {Colors.CYAN}{RPS} / s{Colors.ENDC},  resp : {Colors.CYAN}{json}{Colors.ENDC},{' '*(18-int(len(str(json)))-1)}proxy : {Colors.CYAN}{proxy_formated}{Colors.ENDC}")
            elif available == "ERROR":
                with open("errors.txt", "a") as f:
                    f.write(f"{name, json, status_code}\n")
            else:
                # Make print aligned so even if under was rate limited it will still be aligned
                print(f"[{Colors.RED}-{Colors.ENDC}]   Taken    : {Colors.CYAN}{name}{Colors.ENDC},    RPS : {Colors.CYAN}{RPS} / s{Colors.ENDC},  resp : {Colors.CYAN}{json}{Colors.ENDC},  proxy : {Colors.CYAN}{proxy_formated}{Colors.ENDC}")
        queue.task_done()                



def RPS_CALCULATOR():
    global RPS, REQUESTS
    while True:
        RPS_BEFORE = REQUESTS
        sleep(1)
        RPS = REQUESTS - RPS_BEFORE
        os.system(f'title "Requests = {REQUESTS} | RPS > {RPS}"') 

clear()
print(ASCII)

print(f"[{Colors.YELLOW}+{Colors.ENDC}] Loaded {Colors.CYAN}{len(combos)}{Colors.ENDC} combos")
ask = input(f"How many threads {Colors.YELLOW}>>>{Colors.ENDC} ")
for _ in range(1):
    print(f"Starting in {5-_}s. with {ask} threads (Ctrl+c Abort)", end="\r")
    sleep(1)
ths = []
threading.Thread(target=RPS_CALCULATOR, daemon=True).start()

for i in range(int(ask)):
    t = threading.Thread(target=worker)
    t.daemon = True   
    t.start()
    ths.append(t)
    
for t in ths:
    t.join()

queue.join()

print(f"[{Colors.GREEN}+{Colors.ENDC}] Done")
print(f"[{Colors.GREEN}+{Colors.ENDC}] Total requests = {Colors.CYAN}{REQUESTS}{Colors.ENDC}")
print(f"[{Colors.GREEN}+{Colors.ENDC}] Total valid names = {Colors.CYAN}{WORKS}{Colors.ENDC}")
print(f"[{Colors.GREEN}+{Colors.ENDC}] Total invalid names = {Colors.CYAN}{TAKEN}{Colors.ENDC}")


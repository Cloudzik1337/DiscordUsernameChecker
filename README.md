
[![Hits](https://hits.sh/github.com/Cloudzik1337/DiscordUsernameChecker.svg)](https://hits.sh/github.com/silentsoft/Cloudzik1337/DiscordUsernameChecker)
[![forthebadge](https://forthebadge.com/images/badges/made-with-python.svg)](https://forthebadge.com)
# CloudChecker !!Tokenless!!

CloudChecker is a Python script for checking the availability of Discord usernames using a list of combinations and proxies. It leverages multi-threading to perform checks concurrently.

## Features
- Username availability check on Discord API
- Multi-threaded for faster execution
- Proxy support for avoiding rate limits
- RPS (Requests Per Second) monitoring
- Error logging for troubleshooting
- Should work on linux

## Showcase


https://github.com/Cloudzik1337/DiscordUsernameChecker/assets/92876777/8066235e-91c8-4580-bc5f-138a619453aa

![image](https://github.com/Cloudzik1337/DiscordUsernameChecker/assets/92876777/97153fdc-0548-4d8d-882b-532fbf9b7a1c)


## Getting Started

### Prerequisites
- Python 3.x
- requests

## Installation

### Video Tutorial 

https://github.com/Cloudzik1337/DiscordUsernameChecker/assets/92876777/757d3d04-603e-449c-83c8-817e1f5c1f3c


### For windows user
1. Run `run.bat`
   
### Text Tutorial
1. Clone the repository:

```bash
git clone https://github.com/Cloudzik1337/DiscordUsernameChecker.git
cd DiscordUsernameChecker
```
2. Install requirements
```bash
pip install -r requirements.txt
```
3. Run cloud_checker.py
```bash
python cloud_checker.py
```

## Usage
1. Configure your proxies by adding them to the proxies.txt file.
2. [CheapProxies](https://www.wtfproxy.com/?ref=o8hX4mfY5hfhFUSZEl146) here 3 usd / gb
3. (Proxyless) works but thread sleeps on ratelimit (ultra slow)
4. Customize the script by adjusting parameters like the length of the usernames, the number of threads, etc.
5. Execute the script, and it will start checking the availability of Discord usernames.
## Usage Dictionary Validator
1. Run file
2. Enter ammount of thread (for smaller than 5k dont use more than 5)
3. Similiar + Hits will be saved to BetterNames.txt
## Additional Information
1. Author: @cloudzik1337
2. Discord: discord.cloudzik.me

import re
from nltk.corpus import words
from itertools import cycle
import time
from threading import Thread, Lock

try:
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

    Colors = _Colors()

    def load_wordlist(file_path):
        with open(file_path, 'r') as file:
            wordlist = [line.strip() for line in file]
        return wordlist

    # Load the words directly from the NLTK words corpus
    english_words = set(words.words())

    def is_dictionary_word(word):
        return word.lower() in english_words

    def is_similar_word(word):
        custom_mappings = {'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '8': 'b', '9': 'g'}
        for number, letter in custom_mappings.items():
            word = word.replace(number, letter)
        return is_dictionary_word(word)

    def similar_to_dictionary_word(word):
        custom_mappings = {'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '8': 'b', '9': 'g'}
        for number, letter in custom_mappings.items():
            word = word.replace(number, letter)
        return word if is_dictionary_word(word) else None

    file_path = 'names.txt'
    words_of_user = load_wordlist(file_path)
    words_iteration = cycle(words_of_user)
    
    DONE = 0
    words_length = len(words_of_user)
    def worker():
        global words_length, DONE
        while DONE < words_length:
            with Lock():
                word = next(words_iteration)

                if is_dictionary_word(word):
                    print(
                        f'{Colors.GREEN}|        {word}        | is     a dictionary word.        |{Colors.ENDC}'
                    )
                    with open('BetterNames.txt', 'a') as file:
                        file.write(f"{word} -> {word}\n")
                elif is_similar_word(word):
                    similar_word = similar_to_dictionary_word(word)
                    print(
                        f'{Colors.YELLOW}|        {word}        | is     a similar word. to {Colors.GREEN}{similar_word}   |{Colors.ENDC}'
                    )
                    with open('BetterNames.txt', 'a') as file:
                        file.write(f"{word} -> {similar_word}\n")
                else:
                    print(
                        f'{Colors.RED}|        {word}        | is not a dictionary word.        |{Colors.ENDC}'
                    )
                
                DONE += 1
    if __name__ == "__main__":
        ask_for_threads = input('How many threads do you want to use >>> ')
        print(
        f'{Colors.BOLD}|        Word        | Status                           |{Colors.ENDC}'
    )
        threads = []
        for _ in range(int(ask_for_threads)):
            thread = Thread(target=worker)
            thread.daemon = True
            thread.start()
            threads.append(thread)
        for th in threads:
            th.join()
        input()

except KeyboardInterrupt:
    print('\n\nExiting...')

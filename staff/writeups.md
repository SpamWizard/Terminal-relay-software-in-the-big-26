# Staff writeups

Solutions for the board. The game does not load this file, and nothing here is copied into a team shell.

Flags are `TR{...}`.

## Steghide

`cover.jpg` has a file hidden with steghide. The passphrase is `rockme` (also in `note.txt`).

```bash
steghide extract -sf cover.jpg -p rockme
cat payload.txt
```

Flag: `TR{hidden_in_the_jpeg}`

## Photo Note

`photo.jpg` stores a note in a JPEG comment and in the EXIF Image Description. The note is base64, not the flag itself.

```bash
exif photo.jpg
```

Image Description is `VFJ7Y29tbWVudF9zZWN0aW9ufQ==`. `strings photo.jpg` and `exiftool photo.jpg` show the same text.

```bash
echo 'VFJ7Y29tbWVudF9zZWN0aW9ufQ==' | base64 -d
```

Flag: `TR{comment_section}`

## Anthem

`anthem.mp3` is a zip with a misleading name. The password is `anthem`.

```bash
file anthem.mp3
unzip -P anthem anthem.mp3
cat flag.txt
```

Flag: `TR{not_an_mp3}`

## Unwrap

`secret.txt` is wrapped three times. Outermost is base64, then hex, then rot13. The rot13 step has to cover lowercase letters (`tr 'A-Za-z'`, not `tr 'A-Za'`).

```bash
base64 -d secret.txt | xxd -r -p | tr 'A-Za-z' 'N-ZA-Mn-za-m'
```

That prints the flag. Intermediate text is `GE{guerr_ynlref}`.

Flag: `TR{three_layers}`

## Wordlist

`hash.txt` is one MD5. `wordlist.txt` is the dictionary.

```bash
john --format=raw-md5 --wordlist=wordlist.txt hash.txt
john --show --format=raw-md5 hash.txt
```

The password is `lantern`.

Flag: `TR{lantern}`

## Hashcat

`hash.txt` is one MD5. `wordlist.txt` has eight words, so hashcat finishes immediately.

```bash
hashcat -m 0 -a 0 hash.txt wordlist.txt
```

The password is `spark`.

Flag: `TR{spark}`

## Regex

`lines.txt` is 400 lines of near misses (two digits, a digit first, a digit in the middle, letters only, uppercase). One line is letters followed by a single digit. Reading the file does not surface it.

```bash
grep -E '^[a-z]+[0-9]$' lines.txt
```

The word is `kite4`.

Flag: `TR{kite4}`

## Crackme

`crackme.py` accepts a password whose reverse is `emkcor`.

```bash
python3 crackme.py rockme
```

It prints `correct`.

Flag: `TR{rockme}`

## Telenet

`telenet.py` approves `TELENET <text> <count>`, where `count` is the number of characters in `text`. The words can be anything.

```bash
python3 telenet.py "TELENET hello 5"
```

That prints the flag. A bad message, including `TELENET hello 4`, prints only `REJECTED`.

Flag: `TR{virtual_circuit}`

## XOR

`cipher.hex` is a single-byte XOR. The key is not in the folder. `xor.py` applies one hex byte and prints the result. The plaintext starts with `TR{`, and the key is `37`.

```bash
python3 xor.py 37
```

Or try every byte:

```bash
python3 -c "import subprocess
for i in range(256):
    out = subprocess.check_output(['python3','xor.py',f'{i:02x}'], text=True)
    if out.startswith('TR{'):
        print(out, end='')"
```

Flag: `TR{just_xor}`

## Hangman

`hangman.py` is a game. Ten wrong letters loses. A loss does not print the phrase, and the phrase is not stored as plain text.

Guess letters. One path that never misses:

```bash
printf '%s\n' a s h l u c m y p v b g z | python3 hangman.py
```

The phrase is `sly pygmy bugs gulp zyzzyva lymph by a chasm`.

The flag is the first letter of each word, in order. Count `by` and `a`.

Flag: `TR{spbgzlbac}`

## Fake Logos

Each question is five logos in a row, labeled A through E. One of them never happened. The answer index in `questions/fake_logos.json` is 0-based.

The real marks are in historical order, and not every historical mark is included. Sources: [1000 Logos](https://1000logos.net/), [Logos World](https://logos-world.net/), [Logopedia](https://logos.fandom.com/wiki/Logopedia).

| Question | Points | Answer |
|----------|--------|--------|
| Google | 100 | D |
| Nintendo | 100 | C |
| Cisco | 200 | C |
| Dropbox | 200 | A |
| IBM | 300 | C |
| Micron | 300 | C |
| Microsoft | 300 | D |
| RadioShack | 400 | C |
| AT&T | 400 | D |
| AOL | 400 | C |
| Dell | 500 | C |
| ICQ | 500 | B |

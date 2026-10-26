# Challenge writeups

Staff solutions for the board. This folder is not loaded by the game, and nothing here is copied into a team shell.

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

## Fake Logos

Each question is five logos in a row, labeled A through E. One of them never happened. The answer index in the question file is 0-based.

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

# Page Source — writeup

**Flag:** `TR{relay_view_source}`

## Solve

1. View `index.html` — `data-token="dG9rZW4udHh0"`.
2. Ignore `TR{look_in_the_markup_not_here}`.
3. `b64 dG9rZW4udHh0` → `token.txt`.
4. `cat token.txt` → `TR{relay_view_source}`.

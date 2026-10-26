# Page Source — writeup

**Flag:** `TR{relay_view_source}`  
**Points:** 200  
**Skills:** rendered vs source, base64

## Intent

Rendered page looks empty. The real payload is base64 in a hidden `data-token`. A decoy `TR{...}` in a script block catches people who submit the first flag-shaped string.

## Solve

1. Glance at the Page pane — useless on purpose.
2. `cat index.html` — find `data-token="cmVsYXlfdmlld19zb3VyY2U="`.
3. Ignore `const decoy = "TR{look_in_the_markup_not_here}"`.
4. `b64 cmVsYXlfdmlld19zb3VyY2U=` → `relay_view_source`.
5. Submit `TR{relay_view_source}`.

## Common traps

- Submitting the decoy from the `<script>` block
- Submitting the raw base64 without wrapping
- Forgetting `TR{` / `}`

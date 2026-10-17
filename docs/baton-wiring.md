# Baton wiring guide

5 GPIO inputs + GND on the RP2040. Each baton bridges **exactly two** pins to GND.

Valid pairs (10 batons): 1+2, 1+3, 1+4, 1+5, 2+3, 2+4, 2+5, 3+4, 3+5, 4+5.

Person → pins mapping lives in `config.toml` under `[[team.people]] baton_pins`.

Internal pull-ups: pin reads low when connected to GND. Partial inserts (1 or 3+ pins) decode as unknown, never as another person.

Default Pico GPIO map and flashing steps: [firmware.md](firmware.md).

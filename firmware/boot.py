"""Enable a second USB CDC so heartbeats don't fight the REPL console."""

import usb_cdc

usb_cdc.enable(console=True, data=True)

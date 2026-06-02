import sys

from quantiphy import Quantity

from smp_common import connect_smp

if __name__ == "__main__":
    try:
        freq = Quantity(sys.argv[1], "Hz")
        power = Quantity(sys.argv[2], "dBm")
        state = sys.argv[3].upper()

        dev = connect_smp()

        if state == "OFF":
            dev.write("*RST;*CLS")
        print(f"Setting {freq} {power} {state.lower()}")
        dev.write(f"SOURCE:FREQUENCY:CW {freq}")
        dev.write(f"POW {power:3.1f}")
        dev.write(f"OUTP:STAT {state}")
    except IndexError:
        raise SystemExit(f"Usage: {sys.argv[0]} frequency dBm on/off")

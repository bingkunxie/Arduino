#!/usr/bin/env python3
"""Drive four LED + passive buzzer pairs in order, then turn everything off."""

import time

from gpiozero import PWMOutputDevice

PAIRS = [
    ("Pair 1", 17),
    ("Pair 2", 27),
    ("Pair 3", 22),
    ("Pair 4", 23),
]
DURATION_SECONDS = 10
BUZZER_FREQUENCY_HZ = 2000
DUTY_CYCLE = 0.5


def main() -> None:
    outputs = [
        (
            name,
            pin,
            PWMOutputDevice(
                pin,
                active_high=True,
                initial_value=0,
                frequency=BUZZER_FREQUENCY_HZ,
            ),
        )
        for name, pin in PAIRS
    ]

    try:
        for name, pin, output in outputs:
            print(
                f"{name} on GPIO {pin}: PWM at {BUZZER_FREQUENCY_HZ} Hz "
                f"for {DURATION_SECONDS} seconds"
            )
            output.value = DUTY_CYCLE
            time.sleep(DURATION_SECONDS)
            output.value = 0
            print(f"{name} on GPIO {pin}: OFF")
    finally:
        for _, pin, output in outputs:
            output.value = 0
            output.close()
            print(f"GPIO {pin} closed")


if __name__ == "__main__":
    main()

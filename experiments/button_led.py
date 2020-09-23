# Package sources: https://github.com/NVIDIA/jetson-gpio

import RPi.GPIO as GPIO
import time

# Pin Definitons:
led_pin = 12  # BOARD pin 12
but_pin = 18  # BOARD pin 18

def main():
    prev_value = None

    # Pin Setup:
    GPIO.setmode(GPIO.BOARD)  # BOARD pin-numbering scheme
    GPIO.setup(led_pin, GPIO.OUT)  # LED pin set as output
    GPIO.setup(but_pin, GPIO.IN)  # Button pin set as input

    # Initial state for LEDs:
    GPIO.output(led_pin, GPIO.LOW)
    print("Starting demo now! Press CTRL+C to exit")
    try:
        while True:
            curr_value = GPIO.input(but_pin)
            if curr_value != prev_value:
                GPIO.output(led_pin, curr_value)
                prev_value = curr_value
                print("Outputting {} to Pin {}".format(curr_value, led_pin))
            time.sleep(0.001)
    finally:
        GPIO.cleanup()  # cleanup all GPIO

if __name__ == '__main__':
    main()


MCU      = attiny85
F_CPU    = 16500000
CC       = avr-gcc
OBJCOPY  = avr-objcopy
SIZE     = avr-size

USBDRV   = v-usb/usbdrv

CFLAGS   = -mmcu=$(MCU) -DF_CPU=$(F_CPU)UL -Os -Wall -Wextra \
           -std=gnu99 -funsigned-char -funsigned-bitfields \
           -ffunction-sections -fdata-sections \
           -I. -I$(USBDRV)

LDFLAGS  = -mmcu=$(MCU) -Wl,--gc-sections

SRC      = main.c $(USBDRV)/usbdrv.c $(USBDRV)/oddebug.c
ASRC     = $(USBDRV)/usbdrvasm.S

OBJ      = $(SRC:.c=.o) $(ASRC:.S=.o)
TARGET   = relay

.PHONY: all flash clean size

all: $(TARGET).hex size

$(TARGET).elf: $(OBJ)
	$(CC) $(LDFLAGS) -o $@ $^

$(TARGET).hex: $(TARGET).elf
	$(OBJCOPY) -O ihex -R .eeprom $< $@

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

%.o: %.S
	$(CC) $(CFLAGS) -x assembler-with-cpp -c -o $@ $<

size: $(TARGET).elf
	@$(SIZE) --mcu=$(MCU) --format=avr $<

flash: $(TARGET).hex
	micronucleus --run $<

clean:
	rm -f $(OBJ) $(TARGET).elf $(TARGET).hex

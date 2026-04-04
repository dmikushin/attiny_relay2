/*
 * ATtiny85 (DigiSpark) CDC ACM Relay Controller
 *
 * USB CDC ACM device that controls an induction relay via PB0:
 *   PB0 HIGH = relay OFF (Normally Open)
 *   PB0 LOW  = relay ON
 *
 * Serial Break on ttyACM -> PB0 HIGH (relay OFF)
 * No break              -> PB0 LOW  (relay ON)
 *
 * Custom device name stored in EEPROM, changeable via command protocol:
 *   Send: 0xAA <len> <name bytes...>
 *   Device writes name to EEPROM and reboots with new USB product name.
 */

#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/eeprom.h>
/* wdt.h not needed — we use USB re-enumeration instead of WDT reset */
#include <avr/pgmspace.h>
#include <string.h>
#include <util/delay.h>
#include "usbdrv.h"

/* ---- Pin definitions ---- */
#define RELAY_DDR    DDRB
#define RELAY_PORT   PORTB
#define RELAY_BIT    PB0

/* ---- EEPROM layout ---- */
#define EE_MAGIC_ADDR    ((uint8_t *)0)
#define EE_NAMELEN_ADDR  ((uint8_t *)1)
#define EE_NAME_ADDR     ((uint8_t *)2)
#define EE_MAGIC_VAL     0xA5
#define NAME_MAX         30

/* ---- CDC ACM class request codes ---- */
#define CDC_SET_LINE_CODING         0x20
#define CDC_GET_LINE_CODING         0x21
#define CDC_SET_CONTROL_LINE_STATE  0x22
#define CDC_SEND_BREAK              0x23

/* ---- Custom command byte ---- */
#define CMD_SET_NAME  0xAA

/* ---- State ---- */
static uchar lineCoding[7] = {
    0x80, 0x25, 0x00, 0x00,  /* 9600 baud (LE) */
    0x00,                     /* 1 stop bit */
    0x00,                     /* no parity */
    0x08                      /* 8 data bits */
};

/* Name-change state machine: 0=idle, 1=wait_len, 2=collecting */
static uchar nameState;
static uchar nameExpected;
static uchar namePos;
static uchar nameBuf[NAME_MAX];

/* Flag: request USB re-enumeration from main loop */
static volatile uchar pendingReenumerate;

/* Product string descriptor in RAM (USB string format) */
static uchar productDesc[2 + 2 * NAME_MAX];
static uchar productDescLen;

/* ================================================================== */
/*                  Load product name from EEPROM                     */
/* ================================================================== */

static void loadProductName(void)
{
    static const char defaultName[] PROGMEM = "ATtiny Relay";
    uchar len;

    if (eeprom_read_byte(EE_MAGIC_ADDR) == EE_MAGIC_VAL) {
        len = eeprom_read_byte(EE_NAMELEN_ADDR);
        if (len > 0 && len <= NAME_MAX) {
            productDesc[0] = 2 + 2 * len;
            productDesc[1] = 3; /* USB string descriptor type */
            for (uchar i = 0; i < len; i++) {
                productDesc[2 + 2 * i]     = eeprom_read_byte(EE_NAME_ADDR + i);
                productDesc[2 + 2 * i + 1] = 0;
            }
            productDescLen = 2 + 2 * len;
            return;
        }
    }

    /* Default name from PROGMEM */
    len = sizeof("ATtiny Relay") - 1;
    productDesc[0] = 2 + 2 * len;
    productDesc[1] = 3;
    for (uchar i = 0; i < len; i++) {
        productDesc[2 + 2 * i]     = pgm_read_byte(&defaultName[i]);
        productDesc[2 + 2 * i + 1] = 0;
    }
    productDescLen = 2 + 2 * len;
}

/* ================================================================== */
/*              Custom USB Configuration Descriptor                   */
/* ================================================================== */

/*
 * 2 interfaces:
 *   IF0 - CDC Control (class 0x02/0x02/0x01) + EP3 IN notification
 *   IF1 - CDC Data    (class 0x0A/0x00/0x00) + EP1 IN/OUT data
 *
 * Total: 9+9+5+5+4+5+7+9+7+7 = 67 bytes
 */
PROGMEM const char usbDescriptorConfiguration[67] = {
    /* --- Configuration Descriptor --- */
    9,                      /* bLength */
    USBDESCR_CONFIG,        /* bDescriptorType */
    67, 0,                  /* wTotalLength */
    2,                      /* bNumInterfaces */
    1,                      /* bConfigurationValue */
    0,                      /* iConfiguration */
    (1 << 7),               /* bmAttributes: bus-powered */
    50,                     /* bMaxPower: 100 mA */

    /* --- Interface 0: CDC Control --- */
    9,                      /* bLength */
    USBDESCR_INTERFACE,     /* bDescriptorType */
    0,                      /* bInterfaceNumber */
    0,                      /* bAlternateSetting */
    1,                      /* bNumEndpoints */
    0x02,                   /* bInterfaceClass: Communications */
    0x02,                   /* bInterfaceSubClass: ACM */
    0x01,                   /* bInterfaceProtocol: AT commands */
    0,                      /* iInterface */

    /* CDC Header Functional Descriptor */
    5, 0x24, 0x00, 0x10, 0x01,

    /* CDC Call Management Functional Descriptor */
    5, 0x24, 0x01, 0x01, 1,

    /* CDC Abstract Control Management Functional Descriptor */
    4, 0x24, 0x02, 0x06,   /* bmCapabilities: line coding + send break */

    /* CDC Union Functional Descriptor */
    5, 0x24, 0x06, 0, 1,   /* master=IF0, slave=IF1 */

    /* Notification Endpoint: EP3 IN, interrupt, 8 bytes, 255ms */
    7, USBDESCR_ENDPOINT, 0x83, 0x03, 8, 0, 255,

    /* --- Interface 1: CDC Data --- */
    9,                      /* bLength */
    USBDESCR_INTERFACE,     /* bDescriptorType */
    1,                      /* bInterfaceNumber */
    0,                      /* bAlternateSetting */
    2,                      /* bNumEndpoints */
    0x0A,                   /* bInterfaceClass: CDC Data */
    0x00,                   /* bInterfaceSubClass */
    0x00,                   /* bInterfaceProtocol */
    0,                      /* iInterface */

    /* Data OUT Endpoint: EP1 OUT, interrupt, 8 bytes, 10ms */
    7, USBDESCR_ENDPOINT, 0x01, 0x03, 8, 0, 10,

    /* Data IN Endpoint: EP1 IN, interrupt, 8 bytes, 10ms */
    7, USBDESCR_ENDPOINT, 0x81, 0x03, 8, 0, 10,
};

/* ================================================================== */
/*                Dynamic USB Descriptor Handler                      */
/* ================================================================== */

USB_PUBLIC usbMsgLen_t usbFunctionDescriptor(struct usbRequest *rq)
{
    if (rq->wValue.bytes[1] == USBDESCR_STRING &&
        rq->wValue.bytes[0] == 2) {
        usbMsgPtr = (usbMsgPtr_t)productDesc;
        return productDescLen;
    }
    return 0;
}

/* ================================================================== */
/*                    USB Setup Request Handler                       */
/* ================================================================== */

usbMsgLen_t usbFunctionSetup(uchar data[8])
{
    usbRequest_t *rq = (usbRequest_t *)data;

    if ((rq->bmRequestType & USBRQ_TYPE_MASK) == USBRQ_TYPE_CLASS) {
        switch (rq->bRequest) {
        case CDC_GET_LINE_CODING:
            usbMsgPtr = (usbMsgPtr_t)lineCoding;
            return 7;

        case CDC_SET_LINE_CODING:
            return USB_NO_MSG; /* -> usbFunctionWrite() */

        case CDC_SET_CONTROL_LINE_STATE:
            return 0;

        case CDC_SEND_BREAK:
            if (rq->wValue.word != 0) {
                RELAY_PORT |= (1 << RELAY_BIT);   /* HIGH -> relay OFF */
            } else {
                RELAY_PORT &= ~(1 << RELAY_BIT);  /* LOW  -> relay ON */
            }
            return 0;
        }
    }

    return 0;
}

/* ================================================================== */
/*          Control-Out Data Handler (SET_LINE_CODING)                */
/* ================================================================== */

uchar usbFunctionWrite(uchar *data, uchar len)
{
    if (len > 7)
        len = 7;
    memcpy(lineCoding, data, len);
    return 1; /* all data received */
}

/* ================================================================== */
/*       Data Endpoint OUT Handler (name-change command)              */
/* ================================================================== */

void usbFunctionWriteOut(uchar *data, uchar len)
{
    for (uchar i = 0; i < len; i++) {
        uchar c = data[i];

        switch (nameState) {
        case 0: /* idle */
            if (c == CMD_SET_NAME)
                nameState = 1;
            break;

        case 1: /* expecting length byte */
            if (c > 0 && c <= NAME_MAX) {
                nameExpected = c;
                namePos = 0;
                nameState = 2;
            } else {
                nameState = 0;
            }
            break;

        case 2: /* collecting name bytes */
            nameBuf[namePos++] = c;
            if (namePos >= nameExpected) {
                /* Write to EEPROM (name, length, magic — magic last as commit) */
                for (uchar j = 0; j < nameExpected; j++)
                    eeprom_write_byte(EE_NAME_ADDR + j, nameBuf[j]);
                eeprom_write_byte(EE_NAMELEN_ADDR, nameExpected);
                eeprom_write_byte(EE_MAGIC_ADDR, EE_MAGIC_VAL);

                /* Reload product name and request re-enumeration */
                loadProductName();
                pendingReenumerate = 1;
                nameState = 0;
            }
            break;
        }
    }
}

/* ================================================================== */
/*                              Main                                  */
/* ================================================================== */

static void usbReenumerate(void)
{
    uchar i;
    cli();
    usbDeviceDisconnect();
    i = 0;
    while (--i)            /* ~255 ms */
        _delay_ms(1);
    usbDeviceConnect();
    sei();
}

int main(void)
{
    /* Configure relay pin: output, LOW (relay ON) */
    RELAY_DDR  |= (1 << RELAY_BIT);
    RELAY_PORT &= ~(1 << RELAY_BIT);

    /* Build product string descriptor from EEPROM */
    loadProductName();

    /* USB init with forced re-enumeration */
    usbInit();
    usbReenumerate();

    /* Main loop */
    for (;;) {
        usbPoll();
        if (pendingReenumerate) {
            pendingReenumerate = 0;
            usbReenumerate();
        }
    }
}

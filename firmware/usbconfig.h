#ifndef __usbconfig_h_included__
#define __usbconfig_h_included__

/* ---- Hardware Config (DigiSpark ATtiny85) ---- */

#define USB_CFG_IOPORTNAME      B
#define USB_CFG_DMINUS_BIT      3
#define USB_CFG_DPLUS_BIT       4
#define USB_CFG_CLOCK_KHZ       (F_CPU/1000)
#define USB_CFG_CHECK_CRC       0

/* ---- Functional Range ---- */

#define USB_CFG_HAVE_INTRIN_ENDPOINT    1   /* EP1 IN: CDC data to host */
#define USB_CFG_HAVE_INTRIN_ENDPOINT3   1   /* EP3 IN: CDC notification */
#define USB_CFG_EP3_NUMBER              3
#define USB_CFG_IMPLEMENT_HALT          0
#define USB_CFG_SUPPRESS_INTR_CODE      0
#define USB_CFG_INTR_POLL_INTERVAL      10
#define USB_CFG_IS_SELF_POWERED         0
#define USB_CFG_MAX_BUS_POWER           100
#define USB_CFG_IMPLEMENT_FN_WRITE      1   /* for SET_LINE_CODING data */
#define USB_CFG_IMPLEMENT_FN_READ       0
#define USB_CFG_IMPLEMENT_FN_WRITEOUT   1   /* EP1 OUT: CDC data from host */
#define USB_CFG_HAVE_FLOWCONTROL        0
#define USB_CFG_DRIVER_FLASH_PAGE       0
#define USB_CFG_LONG_TRANSFERS          0
#define USB_COUNT_SOF                   0
#define USB_CFG_CHECK_DATA_TOGGLING     0
#define USB_CFG_HAVE_MEASURE_FRAME_LENGTH   0
#define USB_USE_FAST_CRC                0

/* ---- Device Description ---- */

#define USB_CFG_VENDOR_ID       0xc0, 0x16  /* 0x16c0 V-USB shared VID */
#define USB_CFG_DEVICE_ID       0xe1, 0x05  /* 0x05e1 CDC ACM shared PID */
#define USB_CFG_DEVICE_VERSION  0x00, 0x01

#define USB_CFG_VENDOR_NAME     'd', 'm', 'i', 'k', 'u', 's', 'h', 'i', 'n'
#define USB_CFG_VENDOR_NAME_LEN 9

/* Product name is dynamic (from EEPROM). Do NOT define USB_CFG_DEVICE_NAME. */

#define USB_CFG_DEVICE_CLASS        0x02    /* CDC */
#define USB_CFG_DEVICE_SUBCLASS     0
#define USB_CFG_INTERFACE_CLASS     0x02    /* CDC (used for auto-PID) */
#define USB_CFG_INTERFACE_SUBCLASS  0x02    /* ACM */
#define USB_CFG_INTERFACE_PROTOCOL  0x01

/* ---- Descriptor Properties ---- */

/* Device descriptor: use V-USB default (generated from defines above) */
#define USB_CFG_DESCR_PROPS_DEVICE                  0

/* Configuration descriptor: custom (CDC ACM with 2 interfaces, 67 bytes) */
#define USB_CFG_DESCR_PROPS_CONFIGURATION           USB_PROP_LENGTH(67)

#define USB_CFG_DESCR_PROPS_STRINGS                 0
#define USB_CFG_DESCR_PROPS_STRING_0                0
#define USB_CFG_DESCR_PROPS_STRING_VENDOR           0

/* Product string: dynamic from EEPROM via usbFunctionDescriptor() */
#define USB_CFG_DESCR_PROPS_STRING_PRODUCT          (USB_PROP_IS_DYNAMIC | USB_PROP_IS_RAM)

#define USB_CFG_DESCR_PROPS_STRING_SERIAL_NUMBER    0
#define USB_CFG_DESCR_PROPS_HID                     0
#define USB_CFG_DESCR_PROPS_HID_REPORT              0
#define USB_CFG_DESCR_PROPS_UNKNOWN                 0

/* ---- MCU: ATtiny85 Pin Change Interrupt on PB4 (D+) ---- */

#define USB_INTR_CFG            PCMSK
#define USB_INTR_CFG_SET        (1 << PCINT4)
#define USB_INTR_CFG_CLR        0
#define USB_INTR_ENABLE         GIMSK
#define USB_INTR_ENABLE_BIT     PCIE
#define USB_INTR_PENDING        GIFR
#define USB_INTR_PENDING_BIT    PCIF
#define USB_INTR_VECTOR         PCINT0_vect

#endif /* __usbconfig_h_included__ */

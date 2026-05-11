# STM32F103 Modbus-RTU master — bare-metal Makefile.
# Tested against gcc-arm-none-eabi 12.2 and FreeRTOS V10.5.

TARGET    = modbus_gateway_stm32
DEBUG     ?= 1
OPT       ?= -O2

BUILD_DIR = build
C_SOURCES = \
  Core/Src/main.c \
  Core/Src/modbus_rtu.c \
  Core/Src/rs485_uart.c \
  Core/Src/bridge_uart.c \
  Core/Src/cbor_encode.c \
  Core/Src/crc16.c \
  Core/Src/stm32f1xx_it.c \
  Core/Src/system_stm32f1xx.c \
  Core/Src/syscalls.c \
  Core/Src/sysmem.c

ASM_SOURCES = startup_stm32f103xb.s

PREFIX     = arm-none-eabi-
CC         = $(PREFIX)gcc
AS         = $(PREFIX)gcc -x assembler-with-cpp
OBJCOPY    = $(PREFIX)objcopy
SZ         = $(PREFIX)size

CPU = -mcpu=cortex-m3
MCU = $(CPU) -mthumb

C_DEFS  = -DUSE_HAL_DRIVER -DSTM32F103xB
C_INCLUDES = -ICore/Inc -IDrivers -IMiddlewares/FreeRTOS/Inc

CFLAGS = $(MCU) $(C_DEFS) $(C_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections
ifeq ($(DEBUG), 1)
CFLAGS += -g -gdwarf-2
endif

LDSCRIPT = STM32F103C8Tx_FLASH.ld
LIBS = -lc -lm -lnosys
LDFLAGS = $(MCU) -specs=nano.specs -T$(LDSCRIPT) $(LIBS) -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections

all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

OBJECTS  = $(addprefix $(BUILD_DIR)/,$(notdir $(C_SOURCES:.c=.o)))
vpath %.c $(sort $(dir $(C_SOURCES)))

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(BUILD_DIR)/$(notdir $(<:.c=.lst)) $< -o $@

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) Makefile
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SZ) $@

$(BUILD_DIR)/%.hex: $(BUILD_DIR)/%.elf
	$(OBJCOPY) -O ihex $< $@

$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf
	$(OBJCOPY) -O binary -S $< $@

$(BUILD_DIR):
	mkdir -p $@

flash: $(BUILD_DIR)/$(TARGET).bin
	st-flash write $< 0x8000000

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all clean flash

#include "bridge_uart.h"
#include "cbor_encode.h"

#include "stm32f1xx.h"

void bridge_uart_init(uint32_t baud)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN;
    RCC->APB1ENR |= RCC_APB1ENR_USART2EN;

    // PA2 = USART2_TX (AF push-pull)
    GPIOA->CRL &= ~(0xF << (4 * 2));
    GPIOA->CRL |=  (0xB << (4 * 2));
    // PA3 = USART2_RX (input floating)
    GPIOA->CRL &= ~(0xF << (4 * 3));
    GPIOA->CRL |=  (0x4 << (4 * 3));

    // USART2 sits on APB1 = 36 MHz
    USART2->BRR = 36000000UL / baud;
    USART2->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
}

static void uart_write_blocking(const uint8_t *data, size_t len)
{
    for (size_t i = 0; i < len; i++) {
        while (!(USART2->SR & USART_SR_TXE)) { }
        USART2->DR = data[i];
    }
    while (!(USART2->SR & USART_SR_TC)) { }
}

void bridge_uart_publish(const modbus_poll_entry_t *entry,
                         const modbus_response_t *resp)
{
    uint8_t buf[300];
    size_t  n = cbor_encode_modbus_reading(buf, sizeof(buf), entry, resp);
    if (n == 0) return;

    // Simple framing: 0x7E start byte, length (LE16), payload, XOR-checksum, 0x7F end.
    uint8_t framed[320];
    size_t  m = 0;
    framed[m++] = 0x7E;
    framed[m++] = (uint8_t)(n & 0xFF);
    framed[m++] = (uint8_t)(n >> 8);
    uint8_t xor_sum = 0;
    for (size_t i = 0; i < n; i++) {
        framed[m++] = buf[i];
        xor_sum   ^= buf[i];
    }
    framed[m++] = xor_sum;
    framed[m++] = 0x7F;
    uart_write_blocking(framed, m);
}

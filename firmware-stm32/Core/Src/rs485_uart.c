#include "rs485_uart.h"

#include "stm32f1xx.h"
#include "FreeRTOS.h"
#include "task.h"

#define UART_TX_PIN_NUM   9
#define UART_RX_PIN_NUM   10
#define DE_PIN_NUM        8

static uint32_t s_baud;

void rs485_uart_init(uint32_t baud)
{
    s_baud = baud;

    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;

    // PA9 = USART1_TX (AF push-pull, 50 MHz)
    GPIOA->CRH &= ~(0xF << (4 * (UART_TX_PIN_NUM - 8)));
    GPIOA->CRH |=  (0xB << (4 * (UART_TX_PIN_NUM - 8)));
    // PA10 = USART1_RX (input floating)
    GPIOA->CRH &= ~(0xF << (4 * (UART_RX_PIN_NUM - 8)));
    GPIOA->CRH |=  (0x4 << (4 * (UART_RX_PIN_NUM - 8)));
    // PA8 = DE/RE control (push-pull, 2 MHz)
    GPIOA->CRH &= ~(0xF << (4 * (DE_PIN_NUM - 8)));
    GPIOA->CRH |=  (0x2 << (4 * (DE_PIN_NUM - 8)));
    GPIOA->BSRR = (1u << (DE_PIN_NUM + 16));  // start in RX

    // Assuming PCLK2 = 72 MHz (default after SystemInit + PLL)
    USART1->BRR = 72000000UL / baud;
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
}

void rs485_uart_set_direction(rs485_direction_t dir)
{
    if (dir == RS485_TX) {
        GPIOA->BSRR = (1u << DE_PIN_NUM);
    } else {
        // ensure TX complete before flipping back
        while (!(USART1->SR & USART_SR_TC)) { }
        GPIOA->BSRR = (1u << (DE_PIN_NUM + 16));
    }
}

void rs485_uart_write(const uint8_t *data, size_t len)
{
    for (size_t i = 0; i < len; i++) {
        while (!(USART1->SR & USART_SR_TXE)) { }
        USART1->DR = data[i];
    }
}

void rs485_uart_wait_tx_complete(void)
{
    while (!(USART1->SR & USART_SR_TC)) { }
}

int rs485_uart_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms)
{
    size_t   n = 0;
    uint32_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);
    // 3.5 character times for inter-frame silence (RTU spec).
    // At 9600 baud, 1 char = ~1.04 ms; 3.5 chars ≈ 4 ms.
    const uint32_t silence_ticks = pdMS_TO_TICKS(4);
    uint32_t last_byte_tick = 0;

    while (xTaskGetTickCount() < deadline) {
        if (USART1->SR & USART_SR_RXNE) {
            if (n >= cap) return (int)n;
            buf[n++] = (uint8_t)USART1->DR;
            last_byte_tick = xTaskGetTickCount();
        } else if (n > 0 && (xTaskGetTickCount() - last_byte_tick) > silence_ticks) {
            return (int)n;
        } else {
            vTaskDelay(1);
        }
    }
    return n == 0 ? -1 : (int)n;
}

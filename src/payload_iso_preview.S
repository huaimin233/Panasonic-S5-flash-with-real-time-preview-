    .syntax unified
    .thumb
    .cpu cortex-a7
    .global _start
    .text

/* Select ambient preview in the settings message for forced flash and
 * forced flash with red-eye reduction, with no shutter pulse pending.
 */
_start:
    ldrb.w  r0, [r5, #0xa84]
    push.w  {r2, r3, ip, lr}
    mrs     ip, APSR

    /* 1 means the sender ran, 2 means the packet mode was overridden. */
    ldr     r2, =0x86373900
    ldrh    r3, [r2]
    cbnz    r3, check_preview
    movs    r3, #1
    strh    r3, [r2]

check_preview:
    cmp     r0, #6
    beq     check_packet
    cmp     r0, #0x0f
    bne     restore_registers
check_packet:
    ldr     r2, =0x08AC7FA8
    bic     r3, r4, #0x80000000
    cmp     r3, r2
    bne     restore_registers

#ifdef ISO_INPUT_PREVIEW
    ldr     r2, =0x08AA819C
    ldrh    r3, [r2]
    cmp     r3, #0
    bne     restore_registers
#endif

    ldr     r2, =0x8F301018
    ldrb    r3, [r2]
    cmp     r3, #1
#ifdef ISO_INPUT_PREVIEW
    beq     read_dials
    cmp     r3, #2
    bne     restore_registers

read_dials:
    mov     lr, r3
    ldr     r2, =0x08AA81A2     /* aperture and shutter dial selections */
    ldrh    r3, [r2]
    ldrh    r2, [r2, #2]
    orr.w   r2, r3, r2, lsl #16
    ldr     r3, =0x8637390C
    cmp     lr, #1
    beq     sample_initial_dials
    ldr     lr, [r3]
    cmp     r2, lr
    beq     check_iso_selector
    str     r2, [r3]
    b       remember_adjustment

sample_initial_dials:
    str     r2, [r3]
    b       override_packet

check_iso_selector:
    /* The original publisher copies this ISO selector to packet +0x19.
     * Compare the new input with the preceding packet before it is replaced.
     */
    ldr.w   r2, [sl, #0x484]
    ldrb.w  r2, [r2, #0x18a]
    ldrb    r3, [r4, #0x19]
    cmp     r2, r3
    beq     check_iso_window
    ldr     r3, =0x86373904
    strh    r2, [r3]            /* last ISO selector seen before serialization */
remember_adjustment:
    ldr     r2, =0x8F301020
    ldr     r2, [r2]
    ldr     r3, =0x86373908
    str     r2, [r3]
    b       override_packet

check_iso_window:
    /* One adjustment can publish the same settings several times. */
    ldr     r3, =0x86373908
    ldr     r3, [r3]
    cbz     r3, restore_registers
    ldr     r2, =0x8F301020
    ldr     r2, [r2]
    subs    r2, r2, r3
    cmp     r2, #12
    bhs     restore_registers
#else
    bne     restore_registers
    ldr     r2, =0x08AA819C
    ldrh    r3, [r2]
    cbnz    r3, restore_registers
#endif

override_packet:
    ldr     r2, =0x86373900
    ldrh    r3, [r2, #2]
    cmp     r3, r0
    it      ne
    strhne  r0, [r2, #2]
    movs    r0, #5
    ldrh    r3, [r2]
    cmp     r3, #2
    beq     restore_registers
    movs    r3, #2
    strh    r3, [r2]

restore_registers:
    msr     APSR_nzcvq, ip
    pop.w   {r2, r3, ip, lr}
    b.w     0x86805A50
    .ltorg

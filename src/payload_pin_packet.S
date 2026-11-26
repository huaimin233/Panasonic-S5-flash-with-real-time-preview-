    .syntax unified
    .thumb
    .cpu cortex-a7
    .global _start
    .text

/* Preview phases at 0x8F301018: 0 normal, 1 awaiting ambient settings,
 * 2 ambient applied. Phase 1 allows the settings hook to apply ambient
 * preview. Phase 2 limits further overrides to exposure adjustments and
 * lets the camera arm the flash for capture. The flash commands stay intact.
 */
_start:
    push.w  {r0-r3, ip, lr}
    ldr     r3, =0x8F301014      /* previous Fn2 pressed flag */
    ldr     r1, [r3, #12]       /* tick count, at 0x8F301020 */
    adds    r1, #1
    str     r1, [r3, #12]

#ifdef PIN_ISO_TRACE
    bl      .Ltrace_iso
    ldr     r3, =0x8F301014
#endif

    ldr     r0, =0x08AA82C2
    ldrh    r0, [r0]
    ldrb    r2, [r3]
    cbz     r0, .Lfn2_released
    cmp     r2, #0
    bne     .Lcheck_shutter

    movs    r2, #1
    strb    r2, [r3]
    ldr     r1, [r3, #16]       /* Fn2 edge count */
    adds    r1, #1
    str     r1, [r3, #16]
    ldrb    r2, [r3, #4]
    cbnz    r2, .Lend_preview
    ldr     r0, =0x08B4436C    /* applied ISO */
    ldrh    r0, [r0]
.Lstart_preview:
    strh    r0, [r3, #6]        /* last applied ISO */
    movs    r2, #1
    strh    r2, [r3, #4]        /* phase and consecutive enabled ticks */
    b       .Lpublish

.Lfn2_released:
    movs    r2, #0
    strb    r2, [r3]
.Lcheck_shutter:
    ldrb    r2, [r3, #4]
    cmp     r2, #0
    beq     .Ldone
    ldr     r0, =0x08AA819C
    ldrh    r0, [r0]
    tst.w   r0, #0x1
    beq     .Lfull
    ldr     r1, [r3, #20]
    adds    r1, #1
    str     r1, [r3, #20]
.Lfull:
    tst.w   r0, #0x100
    beq     .Lcheck_pressed
    ldr     r1, [r3, #24]
    adds    r1, #1
    str     r1, [r3, #24]
.Lcheck_pressed:
    movw    r1, #0x0101
    tst     r0, r1
    beq     .Lcheck_applied
.Lend_preview:
    movs    r2, #0
    strh    r2, [r3, #4]
    b       .Lpublish

.Lcheck_applied:
    ldr     r0, =0x08B44356    /* settings application flash enable */
    ldrb    r0, [r0]
    cmp     r2, #2
    beq     .Larmed
    cbnz    r0, .Ldone
    ldrb    r1, [r3]            /* let the firmware handle Fn2 release first */
    cbnz    r1, .Ldone
    ldr     r1, =0x08AC7FAC
    ldrb    r1, [r1]
    cmp     r1, #5
    bne     .Ldone
    ldr     r1, =0x08AC8F34    /* settings mailbox pending bits */
    ldrb    r1, [r1]
    tst     r1, #1
    bne     .Ldone
    ldrb    r1, [r3, #5]
    adds    r1, #1
    strb    r1, [r3, #5]
    cmp     r1, #15            /* collect the settings updates on release */
    blo     .Ldone
    movs    r2, #2
    strh    r2, [r3, #4]
    b       .Ldone

.Larmed:
    ldr     r1, =0x08B4436C
    ldrh    r1, [r1]
    ldrh    r2, [r3, #6]
    cmp     r1, r2
    beq     .Lcheck_timeout
    strh    r1, [r3, #6]
    movw    r2, #0x0E01        /* ISO refresh needs only one applied tick */
    strh    r2, [r3, #4]
    b       .Lpublish
.Lcheck_timeout:
    cbnz    r0, .Lcount_enabled
    strb    r0, [r3, #5]
    b       .Ldone
.Lcount_enabled:
    ldrb    r1, [r3, #5]
    adds    r1, #1
    strb    r1, [r3, #5]
    cmp     r1, #12            /* allow the ISO echo to follow the settings */
    blo     .Ldone
    movs    r2, #0
    strh    r2, [r3, #4]        /* capture can finish before a pulse is observed */
    b       .Ldone

.Lpublish:
    ldr     r1, [r3, #32]       /* settings publication count */
    adds    r1, #1
    str     r1, [r3, #32]
    bl      0x866B16B8          /* mark settings dirty and publish */

.Ldone:
    pop.w   {r0-r3, ip, lr}
    .inst.w 0xE92D41FC          /* original: push.w {r2-r8, lr} */
    b.w     0x866B1248
    .ltorg

#ifdef PIN_ISO_TRACE
/* Sample into the reserved RAM cave when armed by the host. */
    .macro trace_half address, offset
    ldr     r2, =\address
    ldrh    r3, [r2]
    strh    r3, [r5, #\offset]
    .endm

.Ltrace_iso:
    ldr     r2, =0x86370c00
    ldrh    r3, [r2]
    cmp     r3, #1
    bne.w   .Ltrace_return
    push    {r4, r5, r6, r7}
    mov     r4, r2
    ldr     r6, [r4, #4]
    and     r5, r6, #127
    ldr     r2, =0x86371000
    add.w   r5, r2, r5, lsl #6
    str     r1, [r5]

    trace_half 0x08CC1824, 4
    trace_half 0x08B4441A, 6
    trace_half 0x08B4441E, 8
    trace_half 0x08B44356, 10
    trace_half 0x08B4436C, 12
    trace_half 0x08B23B54, 14
    trace_half 0x090CA022, 16
    trace_half 0x090CA038, 18
    trace_half 0x08AC8BC2, 20
    trace_half 0x08AC8BD8, 22
    trace_half 0x08CA8182, 24
    trace_half 0x08CA8198, 26
    trace_half 0x090C7A98, 28
    trace_half 0x090C66E0, 30
    trace_half 0x08CC1DA4, 32
    trace_half 0x08CC1944, 34
    trace_half 0x08AA819C, 36
    trace_half 0x8F301018, 38
    trace_half 0x08AC8F38, 40

    adds    r6, #1
    str     r6, [r4, #4]
    ldrh    r7, [r5, #6]
    lsrs    r7, r7, #8
    ldrh    r2, [r4, #8]
    strh    r7, [r4, #8]
    ldrh    r3, [r4, #12]
    cbnz    r3, .Ltrace_countdown
    cmp     r6, #1
    beq     .Ltrace_done
    cmp     r7, r2
    beq     .Ltrace_done
    movs    r3, #60
.Ltrace_countdown:
    subs    r3, #1
    strh    r3, [r4, #12]
    bne     .Ltrace_done
    movs    r3, #2
    strh    r3, [r4]
.Ltrace_done:
    pop     {r4, r5, r6, r7}
.Ltrace_return:
    bx      lr
    .ltorg
#endif

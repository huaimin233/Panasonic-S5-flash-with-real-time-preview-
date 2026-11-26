    .syntax unified
    .thumb
    .cpu cortex-a7
    .global _start
    .text

#ifndef SETTINGS_CAVE
#define SETTINGS_CAVE 0x86373800
#endif

    /* Install or remove the dispatcher hook with a single aligned store.
     * Run from the settings hook so the main CPU can refresh its I-cache.
     * Request/result: 0 idle, 1 install, 2 remove, 3 done, 4 unexpected code.
     */
_start:
    push.w  {r0-r5, ip, lr}
    mrs     r5, APSR
    ldr     r4, =0x86373b00
    ldrh    r0, [r4]
    cmp     r0, #1
    beq     install
    cmp     r0, #2
    bne     resume
    ldr     r1, =0xbedcf4be
    ldr     r2, =0x41fce92d
    b       replace
install:
    ldr     r1, =0x41fce92d
    ldr     r2, =0xbedcf4be
replace:
    ldr     r3, =0x866b1244
    ldr     r0, [r3]
    cmp     r0, r2
    beq     refresh
    cmp     r0, r1
    bne     unexpected
    str     r2, [r3]
refresh:
    bl      0x86410026          /* firmware instruction cache invalidation */
    movs    r0, #3
    b       report
unexpected:
    movs    r0, #4
report:
    strh    r0, [r4]
resume:
    msr     APSR_nzcvq, r5
    pop.w   {r0-r5, ip, lr}
    b.w     SETTINGS_CAVE      /* settings packet override */
    .ltorg

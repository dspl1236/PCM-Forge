! Minimal SH4 crt for QNX: entry _start, read argc/argv off the stack,
! call main, then _exit(main's return). SH4 SysV: at entry r15 -> argc.
    .text
    .global _start
_start:
    mov.l   @r15, r4          ! r4 = argc
    mov     r15, r5
    add     #4, r5            ! r5 = &argv[0]
    mov.l   .Lmain, r0
    jsr     @r0               ! main(argc, argv)
    nop
    mov     r0, r4            ! exit code = main() return
    mov.l   .Lexit, r0
    jsr     @r0               ! _exit(code)
    nop
1:  bra     1b
    nop
    .align  2
.Lmain: .long main
.Lexit: .long _exit

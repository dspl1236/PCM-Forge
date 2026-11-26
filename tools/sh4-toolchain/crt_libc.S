! SH4 crt for QNX 6.3 programs that use libc's stdio, heap or environment.
! The same steps as a real PCM binary's _start (showScreen, decoded from its
! disassembly): set the FPU mode, find envp and the aux vector, call
! _init_libc(argc, argv, envp, auxv, exit hook), then exit(main(argc, argv,
! envp)) so stdio is flushed and atexit handlers run.
! At entry r15 -> argc and r0 holds the loader's exit hook, which becomes
! _init_libc's 5th argument (on the stack). Programs without stdio/malloc can
! keep the bare crt.S; build.sh picks this one when the source needs libc.
    .text
    .global _start
_start:
    mov.l   .Lfpscr, r1
    mov.l   .Lfpval, r4
    jsr     @r1               ! __set_fpscr(0xC0000)
    mov.l   r0, @-r15         ! (delay slot) push the exit hook: 5th argument
    mov     r15, r5
    mov.l   @(4,r15), r4      ! r4 = argc
    add     #8, r5            ! r5 = argv
    mov     r4, r1
    shll2   r1
    mov     #4, r6
    add     r1, r6
    add     r5, r6            ! r6 = envp = argv + argc*4 + 4
    mov     r4, r10           ! keep argc/argv/envp in callee-saved registers
    mov     r5, r11
    mov     r6, r7
1:  mov.l   @r7, r1           ! r7 = auxv: the word after envp's NULL
    tst     r1, r1
    bf.s    1b
    add     #4, r7
    mov.l   .Linit, r0
    jsr     @r0               ! _init_libc(argc, argv, envp, auxv, exit hook)
    mov     r6, r12
    mov     r10, r4
    mov     r11, r5
    mov.l   .Lmain, r1
    jsr     @r1               ! main(argc, argv, envp)
    mov     r12, r6
    mov.l   .Lexit, r1
    jmp     @r1               ! exit(main's return): flushes stdio, runs atexit
    mov     r0, r4
    .align  2
.Lfpscr: .long __set_fpscr
.Lfpval: .long 0x000C0000
.Linit:  .long _init_libc
.Lmain:  .long main
.Lexit:  .long exit

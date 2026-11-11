/* Turing Machine engine for the TM wave of LFO 2, 3, 4 (tools/machines/lfo_tm/DRAFT.md, tm_model.py).
 *
 * Pure routines, no OS address inside: the wrapper that plugs them into lfo_plus supplies the random byte (from the
 * OS generator 0x40091a96) and the settings. Same algorithm, bit for bit, as tm_model.py (tools/emu/
 * test_lfo_tm_engine.py proves it against the model).
 *
 * State (8 bytes per machine): +0 long = the 32-bit shift register, +4 long = the clock counter for DIV.
 *
 * tm_chance : d0 = PROB knob 0..127  ->  d0 = flip chance in 1/256 (0..256). Clobbers nothing else.
 * tm_clock  : a0 = state, d1 = LENGTH 1..32, d2 = flip chance (from tm_chance), d3 = DIV 1..8,
 *             d4 = random byte 0..255 (upper bits clear)  ->  d0 = 1 if the register moved, else 0.
 *             Clobbers d5, d6, d7.
 */
	.globl	tm_chance, tm_clock

	.section .text.tm, "ax"
	.balign	2
tm_chance:
	tst.l	%d0
	bgt.s	1f
	moveq	#0, %d0				/* 0 (or below): locked loop */
	rts
1:	cmpi.l	#127, %d0
	blt.s	2f
	move.l	#256, %d0			/* last notch: every bit flips (Moebius) */
	rts
2:	cmpi.l	#95, %d0
	bgt.s	3f
	lsl.l	#5, %d0				/* 1..95: knob * 32 / 95 */
	divu.l	#95, %d0
	rts
3:	subi.l	#95, %d0			/* 96..126: 32 + (knob - 95) * 96 / 31 */
	mulu.l	#96, %d0
	divu.l	#31, %d0
	addi.l	#32, %d0
	rts

	.balign	2
tm_clock:
	move.l	4(%a0), %d0			/* counter + 1 < DIV : not this time */
	addq.l	#1, %d0
	cmp.l	%d3, %d0
	bcc.s	1f
	move.l	%d0, 4(%a0)
	moveq	#0, %d0
	rts
1:	clr.l	4(%a0)
	move.l	(%a0), %d5			/* register */
	move.l	%d1, %d6
	subq.l	#1, %d6				/* the bit LENGTH - 1 ... */
	move.l	%d5, %d7
	lsr.l	%d6, %d7
	moveq	#1, %d6
	and.l	%d6, %d7			/* ... is the bit that comes back */
	cmp.l	%d2, %d4			/* random byte < chance : flip it */
	bcc.s	2f
	eori.l	#1, %d7
2:	lsl.l	#1, %d5
	or.l	%d7, %d5
	move.l	%d5, (%a0)
	moveq	#1, %d0
	rts

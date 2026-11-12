/* Turing Machine engine for the TM wave of LFO 2, 3, 4 (tools/machines/lfo_tm/DRAFT.md, tm_model.py).
 *
 * Pure routines, no OS address inside: the wrapper that plugs them into lfo_plus supplies the random byte (from the
 * OS generator 0x40091a96) and the settings. Same algorithm, bit for bit, as tm_model.py (tools/emu/
 * test_lfo_tm_engine.py proves it against the model).
 *
 * State (8 bytes per machine): +0 long = the 32-bit shift register, +4 long = the clock counter for DIV.
 *
 * tm_chance : d0 = PROB knob 0..127  ->  d0 = flip chance in 1/256 (0..256). Clobbers a1. A table (chance_tab, generated from
 *             tm_model.flip_chance) replaces the divides: no divide instruction at all.
 * tm_clock  : a0 = state, d1 = LENGTH 1..32, d2 = flip chance (from tm_chance), d3 = DIV 1..8,
 *             d4 = random byte 0..255 (upper bits clear)  ->  d0 = 1 if the register moved, else 0.
 *             Clobbers d5, d6, d7.
 */
	.globl	tm_chance, tm_clock

	.section .text.tm, "ax"
	.balign	2
tm_chance:
	cmpi.l	#127, %d0
	blt.s	1f
	move.l	#256, %d0			/* last notch (127 or more): every bit flips (Moebius) */
	rts
1:	tst.l	%d0
	bgt.s	2f
	moveq	#0, %d0				/* 0 (or below): locked loop */
	rts
2:	lea	chance_tab, %a1			/* 1..126 : table made from tm_model.flip_chance (no divide) */
	move.b	(%a1,%d0.l), %d0
	andi.l	#255, %d0
	rts
	.balign	2
chance_tab:
	.byte	0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5
	.byte	5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10, 10
	.byte	10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14, 14, 14, 15, 15, 15
	.byte	16, 16, 16, 17, 17, 17, 18, 18, 18, 19, 19, 19, 20, 20, 20, 21
	.byte	21, 21, 22, 22, 22, 23, 23, 23, 24, 24, 24, 25, 25, 25, 26, 26
	.byte	26, 27, 27, 27, 28, 28, 28, 29, 29, 29, 30, 30, 30, 31, 31, 32
	.byte	35, 38, 41, 44, 47, 50, 53, 56, 59, 62, 66, 69, 72, 75, 78, 81
	.byte	84, 87, 90, 93, 97, 100, 103, 106, 109, 112, 115, 118, 121, 124, 128
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

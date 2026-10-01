V23.129 Entrance Terminal Pause Screen
======================================

This release replaces the plain white authentication error shown when the
Entrance Verification Terminal logs out while its paired Voting Terminal is
still open.

New behavior
------------
1. The Voting Terminal authentication is preserved when only the Entrance
   Verification Terminal goes offline.
2. Voting is paused on a branded page with this instruction:
   "The Entrance Verification Terminal for this station is logged out. Please
   log it back in to allow voting to continue."
3. The pause page checks the paired terminal every eight seconds.
4. After the Entrance Verification Terminal logs back in, the Voting Terminal
   automatically returns to the voter-entry screen.
5. A Check Again button is available for a manual retry.
6. Genuine expired, released or replaced Voting Terminal sessions now show a
   styled login-required page instead of plain text on a white screen.

No vote is created or removed by the pause/recovery process.

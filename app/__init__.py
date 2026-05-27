"""Apex Resident — always-on background companion.

Owns the state machine, tray icon, global hotkey, and audit log.
Boots: agent + wake listener + dashboard + (optional) tray + hotkey.
Logs everything to ~/.apex/resident.log so closing a terminal doesn't matter.
"""

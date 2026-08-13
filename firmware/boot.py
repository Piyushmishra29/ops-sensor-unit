# boot.py — runs before main.py on every reset.
#
# Deliberately almost empty. Anything that can fail belongs in main.py, where
# a failure leaves you at a REPL prompt with a traceback; a failure in boot.py
# on some ports leaves you with a board that is hard to talk to.
import gc

gc.collect()

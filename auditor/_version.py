"""The one place the version is written.

It used to live only in pyproject, and everything at run time read it back out
of the installed distribution metadata. That metadata goes stale in an editable
install, and a receipt stamped with the wrong instrument version is a receipt
that lies about what produced it. pyproject now reads this attribute, so the
packaged metadata and the running code cannot disagree.
"""
__version__ = "0.6.10"

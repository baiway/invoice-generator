#!/usr/bin/env python
"""
Wrapper for running the CLI from a checkout.

Equivalent to the `generate-invoices` command that `uv sync` (or
`pip install -e .`) puts on your PATH.
"""

from invoice_generator.cli import main

if __name__ == "__main__":
    main()

"""Entry point for `python -m jw_cli`.

This mirrors what the installed `jw` console script does, but is useful
for tests that invoke the CLI via subprocess without depending on the
script being on PATH.
"""

from jw_cli.main import main

if __name__ == "__main__":
    main()

"""Standards shipped inside the wheel.

`specs/kya_constitution_v1.yaml` in the repository is the authoring copy and the
one the experiment reads. It is excluded from the wheel by design, because the
spec box is externalised data rather than code. A published package still has to
be able to run the check, so the same file is carried here as package data, and
`tests/test_mcp_server.py` fails if the two ever differ.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def path(name: str = "kya_constitution_v1.yaml") -> Path:
    return HERE / name

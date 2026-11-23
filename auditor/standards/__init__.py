"""Standards shipped inside the wheel.

`specs/` in the repository holds the authoring copies and the ones the
experiment reads. They are excluded from the wheel by design, because the spec
box is externalised data rather than code. A published package still has to be
able to run the check, so the same files are carried here as package data, and
a test fails if any pair ever differs by a byte.

Two standards are shipped, and they declare the same five elements with the
same `basis`, so they produce identical readings:

  kya_constitution_v1.yaml            the identity the published study ran
                                      against. Frozen. CLAUDE.md forbids
                                      editing a spec mid-experiment.
  agent_constitution_v1.yaml          the normative identity from here on, and
                                      the one a committee submission names. It
                                      declares `supersedes: {kya, 1}` and adds
                                      `established_by`, which is what lets
                                      behavioural evidence finish the three
                                      elements a static read never can.

`DEFAULT` is still `kya/1`. Flipping it renames the standard inside every new
receipt, which changes every content digest, and the digest is the billable
unit: a customer would be charged a second time for one unchanged codebase.
The default moves in the same release as the version-two envelope, so the two
breaking changes land together and once. See docs/NAMING.md.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULT = "kya_constitution_v1.yaml"
NORMATIVE = "agent_constitution_v1.yaml"

SHIPPED = (DEFAULT, NORMATIVE)


def path(name: str = DEFAULT) -> Path:
    return HERE / name

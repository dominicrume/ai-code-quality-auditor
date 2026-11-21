"""What a pip-install user gets, asserted without building anything.

The wheel excludes `specs/` on purpose: the spec box is externalised data, not
code. That decision has a cost — the KYA standard the check reads has to travel
as package data instead — and this file is the guard on that cost. It asserts
the packaged copies exist, parse, and still agree with the authoring copies,
using only the import machinery a published package has.

These tests build no artefact and reach no network. They are a statement about
the installed tree, which in a checkout is the source tree, so a file that
stopped being shipped fails here before anyone runs `twine upload`.
"""
from __future__ import annotations

import importlib.resources as resources
from pathlib import Path

import pytest
import yaml

import auditor.standards as standards
from auditor.receipts import bundle

REPO = Path(__file__).resolve().parent.parent

#: Every non-Python file the package reads at run time, by the path it is
#: served at inside the installed package. Adding a data file without adding it
#: here, and to [tool.setuptools.package-data], is how data stops shipping.
PACKAGE_DATA = [
    "standards/kya_constitution_v1.yaml",
    "standards/open_defects.yaml",
    "assets/theme.css",
    "dashboard/templates/index.html",
    "dashboard/templates/report.html",
    "live/templates/live.html",
]


@pytest.mark.parametrize("relative", PACKAGE_DATA)
def test_package_data_is_reachable_as_package_data(relative: str) -> None:
    """Reachable through importlib.resources, not through the checkout.

    A file that only exists because the test ran from the repository root is a
    file that is missing from the wheel.
    """
    package, _, name = relative.rpartition("/")
    anchor = "auditor." + package.replace("/", ".")
    assert resources.files(anchor).joinpath(name).is_file(), (
        f"{relative} is not reachable as package data; it will be absent from "
        f"the wheel. Declare it in [tool.setuptools.package-data]."
    )


def test_standards_is_a_package_not_a_bare_data_directory() -> None:
    """`auditor.standards` must be importable, or its data is never found.

    A directory with no `__init__.py` is not discovered by
    `[tool.setuptools.packages.find]`, so its `package-data` entry matches
    nothing and the build succeeds silently with the data missing.
    """
    assert (Path(standards.__file__).name == "__init__.py")
    assert standards.path().name == "kya_constitution_v1.yaml"


def test_packaged_standard_matches_the_authoring_copy() -> None:
    """The wheel's KYA standard is byte-identical to `specs/`.

    Two copies of a standard is a hazard accepted deliberately. This is the
    only thing that stops them drifting, so it compares bytes rather than
    parsed content: a reordered key changes the standard's digest, and the
    digest is what a receipt attests to.
    """
    authoring = REPO / "specs" / "kya_constitution_v1.yaml"
    if not authoring.exists():
        pytest.skip("not a checkout: specs/ is excluded from the wheel")
    assert standards.path().read_bytes() == authoring.read_bytes(), (
        "auditor/standards/kya_constitution_v1.yaml has drifted from "
        "specs/kya_constitution_v1.yaml; copy the authoring file over it"
    )


def test_open_defects_file_parses_and_declares_the_open_key() -> None:
    """The shape is load-bearing: `open_defects()` reads `data['open']`."""
    data = yaml.safe_load(standards.path("open_defects.yaml").read_text())
    assert isinstance(data, dict)
    assert "open" in data, "open_defects.yaml must declare an 'open' key"
    assert isinstance(data["open"], list)


def test_open_defects_returns_a_list_from_shipped_data() -> None:
    """A list, and from the file rather than from the `return []` fallback.

    `bundle.open_defects()` returns `[]` both when nothing is open and when the
    file failed to ship. Those are opposite facts about a receipt's disclosure,
    so this asserts the file is there as well as asserting the return type.
    """
    assert standards.path("open_defects.yaml").is_file()
    defects = bundle.open_defects()
    assert isinstance(defects, list)
    for entry in defects:
        assert isinstance(entry, dict)
        assert entry.get("id"), "every open defect needs an id"
        assert entry.get("summary"), "every open defect needs a one-line summary"


def test_a_receipt_carries_the_open_defect_list_field() -> None:
    """Whatever is open, the field is present, so a reader can rely on it."""
    from auditor.governance import constitution

    codebase = {"files": {"a.py": "x = 1\n"}}
    standard = constitution.load_standard(standards.path())
    verdict = constitution.evaluate(codebase, standard)
    finding = bundle.build(codebase, standard, verdict)
    assert "instrument_open_defects" in finding
    assert isinstance(finding["instrument_open_defects"], list)


def test_console_script_is_declared() -> None:
    """`auditor` on the PATH is the whole interface for an installed user."""
    from importlib.metadata import entry_points
    scripts = {e.name: e.value
               for e in entry_points(group="console_scripts")}
    assert scripts.get("auditor") == "auditor.core.cli:main"


def test_only_auditor_is_installed_as_a_top_level_package() -> None:
    """Nothing but `auditor` may claim a top-level name in site-packages.

    `service/` is a separately deployed app that depends on this package by
    name, and `install/` holds client config templates. Either one promoted to
    a package would install a top-level `service`/`install` into site-packages:
    wrong, and a collision with whatever else owns that name.
    """
    from importlib.metadata import distribution
    top_level = distribution("ai-code-quality-auditor").read_text("top_level.txt")
    if top_level is None:
        pytest.skip("no top_level.txt in this install")
    assert top_level.split() == ["auditor"]


@pytest.mark.parametrize("name", ["service", "install"])
def test_sibling_directories_are_not_importable_packages(name: str) -> None:
    """They must stay plain directories, with no `__init__.py` to find.

    This fails in a checkout the moment somebody adds one, which is the moment
    `packages.find` would start shipping it.
    """
    directory = REPO / name
    if not directory.exists():
        pytest.skip(f"not a checkout: {name}/ is excluded from both artefacts")
    offenders = [str(p.relative_to(REPO)) for p in directory.rglob("__init__.py")
                 if ".venv" not in p.parts]
    assert not offenders, (
        f"{offenders} would make {name}/ a discoverable package; it is excluded "
        f"from the distribution on purpose"
    )


def test_seal_extra_is_declared_so_the_crypto_dependency_is_optional() -> None:
    """`pip install 'ai-code-quality-auditor[seal]'` has to resolve.

    The error message in `auditor.receipts.seal` tells the user to type exactly
    that, so the extra existing is part of the contract.
    """
    from importlib.metadata import metadata
    meta = metadata("ai-code-quality-auditor")
    assert "seal" in meta.get_all("Provides-Extra", [])
    requires = meta.get_all("Requires-Dist", [])
    assert any("cryptography" in r and 'extra == "seal"' in r for r in requires)
    assert not any("cryptography" in r and "extra ==" not in r for r in requires), \
        "cryptography must stay optional; a base dependency defeats the extra"


def test_mcp_client_templates_are_valid_and_name_the_console_script() -> None:
    """The templates are what a user copies, so a typo is a broken install.

    They ship in the sdist and not the wheel — a wheel unpacks into
    site-packages, where a top-level `install/` has no business being — so
    documentation has to point at the repository rather than a local path.
    """
    directory = REPO / "install"
    if not directory.exists():
        pytest.skip("not a checkout: install/ is excluded from the wheel")
    import json
    import tomllib

    templates = sorted(p for p in directory.iterdir()
                       if p.suffix in (".json", ".toml"))
    assert templates, "install/ is empty"
    for template in templates:
        text = template.read_text(encoding="utf-8")
        if template.suffix == ".json":
            # The templates are JSONC: they lead with `//` comments explaining
            # where the file goes. Several clients accept that and some do not,
            # which is a question about those clients rather than about
            # packaging, so this strips the comments and checks the body is
            # well formed. A stray comma or brace fails here.
            body = "\n".join(line for line in text.splitlines()
                             if not line.lstrip().startswith("//"))
            assert json.loads(body), f"{template.name} has no content"
        else:
            assert tomllib.loads(text), f"{template.name} has no content"
        assert "auditor" in text, f"{template.name} does not invoke the auditor"


def test_typing_classifier_is_backed_by_a_py_typed_marker() -> None:
    """`Typing :: Typed` is a promise type checkers read literally.

    Without `auditor/py.typed`, a downstream mypy run silently ignores every
    annotation in the package while the classifier says otherwise.
    """
    assert resources.files("auditor").joinpath("py.typed").is_file(), (
        "pyproject declares the 'Typing :: Typed' classifier but the package "
        "ships no py.typed marker; add auditor/py.typed and declare it in "
        "[tool.setuptools.package-data] under \"auditor\""
    )

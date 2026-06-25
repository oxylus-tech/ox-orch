from __future__ import annotations

import importlib
from collections import defaultdict
from typing import Dict, List


def _resolve_module(module_name: str, symbol_name: str) -> str:
    module = importlib.import_module(module_name)
    obj = getattr(module, symbol_name, None)

    if obj is None:
        return module_name

    return getattr(obj, "__module__", module_name)


def _group(module_name: str, names: List[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = defaultdict(list)

    for name in names:
        mod = _resolve_module(module_name, name)
        groups[mod].append(name)

    return dict(sorted(groups.items()))


def _build_rst(module_name: str, groups: Dict[str, List[str]]) -> str:
    lines: List[str] = []

    for submodule, symbols in groups.items():
        # ✅ SAFE TABLE (no width issues)
        lines.append(".. list-table::")
        lines.append("   :widths: 30 70")
        lines.append("   :header-rows: 1")
        lines.append("")
        lines.append(f"   * - :py:mod:`{submodule}`")
        lines.append("     - ")

        for sym in symbols:
            full = f"{module_name}.{sym}"
            link = f":obj:`{full}`"

            lines.append(f"   * - {sym}")
            lines.append(f"     - {link}")

        lines.append("")

    return "\n".join(lines)


def setup(app):
    from docutils.parsers.rst import Directive
    from docutils.statemachine import ViewList
    from docutils import nodes

    class PublicApiDirective(Directive):
        required_arguments = 1
        has_content = False

        def run(self):
            module_name = self.arguments[0]

            module = importlib.import_module(module_name)
            names = getattr(module, "__all__", None)

            if names is None:
                raise self.error(f"{module_name} has no __all__")

            groups = _group(module_name, names)
            rst = _build_rst(module_name, groups)

            container = nodes.container()

            vl = ViewList()
            for i, line in enumerate(rst.splitlines()):
                vl.append(line, f"{module_name}-public-api.rst", i)

            self.state.nested_parse(vl, self.content_offset, container)

            return [container]

    app.add_directive("public-api", PublicApiDirective)

    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }

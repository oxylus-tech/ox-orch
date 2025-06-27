from pathlib import Path
from typing import Type, Sequence

from pydantic import BaseModel
from rich import print
from rich.align import Align
from rich.table import Table

from ox_orch.core import files


__all__ = ("get_file_backend", "load_file", "save_file", "create_table", "print_registry_info")


def get_file_backend(self, path: Path, model_class: Type[BaseModel], as_list: bool = False):
    """Return file backend using provided path extension and arguments."""
    backend_cls = files.backends.get(path.suffix[1:])
    if not backend_cls:
        raise NotImplementedError(
            f"No backend found for {path.suffix[1:]}. Available: " + ", ".join(files.backends.keys())
        )

    return backend_cls(model_class, as_list)


def load_file(
    self, path: Path, model_class: Type[BaseModel], as_list: bool = False, exc: bool = False
) -> BaseModel | None:
    """
    Read file and return the deserialized object if file exists.

    It read path suffix to detect which file backend to use.

    :yields ValueError: when file does not exists and `exc`.
    :yields NotImplementedError: when no file backend matches file extension.
    :yields pydantic.ValidationError: invalid file content.
    """
    if not path.exists():
        if exc:
            raise ValueError(f"File {path} does not exists.")
        return None

    backend = get_file_backend(path, model_class, as_list)
    return backend.load(path)


def save_file(
    self, path: Path, model_class: Type[BaseModel], data: BaseModel, as_list: bool = False
) -> BaseModel | None:
    """
    Read file and return the deserialized object if file exists.

    It read path suffix to detect which file backend to use.

    :yields ValueError: when file does not exists and `exc`.
    :yields NotImplementedError: when no file backend matches file extension.
    :yields pydantic.ValidationError: invalid file content.
    """
    backend = get_file_backend(path, model_class, as_list)
    return backend.save(path, data)


def create_table(title, columns: Sequence[str | tuple[str, str]], title_style="b yellow", expand=True, **kwargs):
    """Create a rich table using provided column list and other arguments."""
    t = Table(title=title, title_style=title_style, expand=expand, **kwargs)
    for col in columns:
        if isinstance(col, str):
            t.add_column(col)
        else:
            t.add_column(col[0], style=col[1])
    return t


def print_registry_info(title, registry):
    table = create_table(title, columns=["Name", "Label / Default", "Description"])
    infos = registry.get_infos(skip_no_doc=True)
    infos.sort(key=lambda o: o.type_id)

    for info in infos:
        table.add_row(f"[b]{info.type_id}[/b]", f"[b]{info.label}[/b]", f"[b]{info.description}[/b]")

        if info.fields:
            table.add_section()
            for field in info.fields:
                table.add_row(
                    Align(f"[i]{field.name}[/i]", "right"),
                    Align(f"[i cyan]{field.default}[/i cyan]", "right"),
                    f"[i]{field.description}[/i]",
                )
        table.add_section()
    print(table)

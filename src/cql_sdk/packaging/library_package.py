"""A :class:`LibraryPackage` bundles ELM + metadata + optional resources."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cql_sdk.packaging.manifest import PackageManifest


@dataclass(slots=True)
class LibraryPackage:
    manifest: PackageManifest
    source_dir: Path
    elm_files: list[Path] = field(default_factory=list)
    resource_files: list[Path] = field(default_factory=list)

    @classmethod
    def discover(cls, source_dir: Path, *, name: str | None = None) -> LibraryPackage:
        source_dir = source_dir.resolve()
        elm = sorted(source_dir.glob("**/*.elm.json"))
        resources = sorted(p for p in source_dir.glob("**/*.json") if p not in elm)
        manifest = PackageManifest(
            name=name or source_dir.name,
            libraries=[str(p.relative_to(source_dir)) for p in elm],
            resources=[str(p.relative_to(source_dir)) for p in resources],
        )
        return cls(manifest=manifest, source_dir=source_dir, elm_files=elm, resource_files=resources)

    def write(self, output_dir: Path) -> Path:
        output_dir = output_dir.resolve()
        target = output_dir / self.manifest.name
        target.mkdir(parents=True, exist_ok=True)

        for src in self.elm_files + self.resource_files:
            rel = src.relative_to(self.source_dir)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)

        (target / "manifest.json").write_text(
            json.dumps(self.manifest.to_dict(), indent=2), encoding="utf-8"
        )
        return target

    def describe(self) -> dict[str, Any]:
        return {
            "source": str(self.source_dir),
            "manifest": self.manifest.to_dict(),
        }

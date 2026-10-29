"""Complete notice texts with shared storage for identical content."""

import hashlib
import json

from dataclasses import dataclass, field

from pathlib import Path


@dataclass
class LicenseTextArchive:
    """Readable TXT content with provenance and byte boundaries in JSON."""

    metadata: dict = field(default_factory = dict)
    entries: list[dict] = field(default_factory = list)
    texts: dict[str, bytes] = field(default_factory = dict, repr = False)

    def add(self, name: str, content: bytes, details: dict | None = None) -> None:
        if not content.strip() or b"\x00" in content or not name or "\n" in name:
            raise ValueError('Missing license text or invalid notice name')

        if any(entry["name"] == name for entry in self.entries):
            raise ValueError(f"Duplicate notice: {name}")

        digest = hashlib.sha256(content).hexdigest()
        self.entries.append({"name": name, "sha256": digest, "details": details or {}})
        self.texts[digest] = content

    def write(self, text_path: Path, manifest_path: Path) -> dict:
        content = bytearray("Complete original license and copyright notices.\n"
                            "Identical content appears once; sources are recorded in the manifest.\n".encode())
        positions = {}

        for entry in sorted(self.entries, key = lambda item: item["name"]):
            digest = entry["sha256"]

            if digest in positions:
                continue

            names = [item["name"] for item in self.entries if item["sha256"] == digest]
            content.extend(("\n\n" + "=" * 72 + "\n" + "\n".join(sorted(names)) + "\n" + "=" * 72 + "\n").encode())
            original = self.texts[digest]
            positions[digest] = {"offset": len(content), "bytes": len(original)}
            content.extend(original)

        result = {"version": "1", "metadata": self.metadata,
                  "entries": sorted(self.entries, key = lambda item: item["name"]),
                  "texts": positions, "text_sha256": hashlib.sha256(content).hexdigest()}
        text_path.write_bytes(content)
        manifest_path.write_text(json.dumps(result, ensure_ascii = False, indent = 2) + "\n", encoding = "utf-8")

        return result

    @staticmethod
    def read(text_path: Path, manifest_path: Path) -> "LicenseTextArchive":
        document = json.loads(manifest_path.read_text(encoding = "utf-8"))
        content = text_path.read_bytes()

        if document["version"] != "1" or hashlib.sha256(content).hexdigest() != document["text_sha256"]:
            raise ValueError('License bundle version or hash mismatch')

        result = LicenseTextArchive(metadata = document["metadata"])
        texts = {}
        ranges = []

        for digest, position in document["texts"].items():
            start, size = position["offset"], position["bytes"]

            if type(start) is not int or type(size) is not int or start < 0 or size <= 0 or start + size > len(content):
                raise ValueError('Invalid license text boundaries')

            original = content[start:start + size]

            if hashlib.sha256(original).hexdigest() != digest:
                raise ValueError('Original license text hash mismatch')

            ranges.append((start, start + size))
            texts[digest] = original

        ordered = sorted(ranges)

        if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
            raise ValueError('License text ranges overlap')

        for entry in document["entries"]:
            if entry["sha256"] not in texts:
                raise ValueError('A notice has no license text')

            result.add(entry["name"], texts[entry["sha256"]], entry["details"])

        if set(result.texts) != set(texts):
            raise ValueError('The bundle contains texts without provenance')

        return result

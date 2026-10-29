# Windows Microsoft runtime provenance and conditions

This record describes the two Microsoft Visual C runtime DLLs verified on
2026-10-29 in the private v0.1.4 Windows x64 package, built from commit
`e58fad5ca46bb58e726b72dfde13a7be6e4c07f6`. It records technical provenance and
governing notices; it does not establish that every redistribution condition
has been satisfied.

## Verified files and upstream binary package

Both DLLs identify Microsoft Corporation as their producer. Their PE file and
product versions are `14.42.34438.0`. Each shipped file byte-matches the same
file in the official
[CPython 3.14.4 Windows x64 embeddable package](https://www.python.org/ftp/python/3.14.4/python-3.14.4-embed-amd64.zip).

| File | File/product version | SHA-256 |
| --- | --- | --- |
| `vcruntime140.dll` | `14.42.34438.0` | `052ad6a20d375957e82aa6a3c441ea548d89be0981516ca7eb306e063d5027f4` |
| `vcruntime140_1.dll` | `14.42.34438.0` | `6a99bc0128e0c7d6cbbf615fcc26909565e17d4ca3451b97f8987f9c6acbc6c8` |

The SHA-256 of that upstream ZIP is
`cda80a9b1e75c0f1b4f9872ca1b417f0d19bce32facc811aea9180e70fad5fb9`.
The release is listed on the official
[Python 3.14.4 download page](https://www.python.org/downloads/release/python-3144/).

The CPython v3.14.4 build sources describe the upstream collection process:
[FindVCRedistDir and FindVCRuntime](https://github.com/python/cpython/blob/v3.14.4/PCbuild/pyproject.props)
resolve `vcruntime*.dll` from `VCRedistDir` under `Microsoft.VC*.CRT`, and
[_CopyVCRuntime](https://github.com/python/cpython/blob/v3.14.4/PCbuild/pythoncore.vcxproj)
copies those files into the Python build output.

The independently verified binary source is the CPython distribution above.
No particular complete Visual Studio or Microsoft redistributable installer
archive is claimed as its source without a matching installer record. The DLL
version alone does not identify such an archive. The CPython installer SBOM
does not separately enumerate these runtime DLLs; their identity is established
by the PE metadata and byte comparison described here.

## Preserved notices and downstream distribution

The official CPython Windows `LICENSE.txt` is preserved in full in the portable
license bundle's `THIRD_PARTY_LICENSES.txt`, under the `Python/LICENSE.txt`
entry. `sources.json` records its original byte boundaries and SHA-256. The
verified original is 35,407 bytes with SHA-256
`935cf13e19f8c31b497d20b05d73623431a226b230c3599bc30fa3348979bc68`.
It includes the complete original Microsoft additional conditions for the
Windows binary build.

The Windows native-library catalogue maps these DLLs to the same full original
notice under `native/windows/CPython/LICENSE.txt`; shared notice content is
stored once without changing its bytes.

Those conditions require downstream distributors of programs containing
Microsoft Distributable Code to comply with Microsoft's distribution
restrictions and require protective terms for distributors and external end
users. They address preservation of notices, Microsoft trademarks and
endorsement, supported Microsoft platforms, and malicious, deceptive, or
unlawful programs. Their stated scope is Microsoft Distributable Code; the
project's MIT license does not relicense these DLLs.

Microsoft's [redistribution documentation](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
and [Visual Studio 2022 distributable-code list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution)
describe the applicable licensing requirements for runtime packages and
individual binaries. The separate
[Microsoft Visual C++ Runtime 2015–2022 license](https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/)
is an additional primary reference; it should not be treated as a standalone
redistribution grant.

Maintainers and downstream distributors must comply with the terms applicable
to their distribution. Preserving original notices, matching DLL hashes, and
documenting this chain do not by themselves prove licensing entitlement,
end-user agreement, or compliance with every condition.

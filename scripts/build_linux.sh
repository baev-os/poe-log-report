#!/usr/bin/env bash
# Build and verify a tagged Linux release using the pinned container toolchain.
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$project_root"

release_tag=""
output=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --release-tag|--output)
            if [[ $# -lt 2 || -z "$2" ]]; then
                printf 'Missing value for %s\n' "$1" >&2
                exit 2
            fi

            if [[ "$1" == --release-tag ]]; then
                release_tag="$2"
            else
                output="$2"
            fi

            shift 2
            ;;
        --help|-h)
            printf '%s\n' 'Usage: scripts/build_linux.sh --release-tag vVERSION [--output build/FRESH-DIRECTORY]'
            printf '%s\n' 'Requires Docker, a clean checkout, and the matching local version tag.'
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            exit 2
            ;;
    esac
done

if [[ ! "$release_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?$ ]]; then
    printf '%s\n' 'Use --release-tag with the exact application version, for example v0.1.0.' >&2
    exit 2
fi

if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    printf '%s\n' 'This helper requires a Linux x86_64 host.' >&2
    exit 1
fi

release_sha="$(git --no-optional-locks rev-parse --verify "refs/tags/$release_tag^{commit}")"

if [[ "$(git --no-optional-locks rev-parse HEAD)" != "$release_sha" || -n "$(git --no-optional-locks status --porcelain --untracked-files=all)" ]]; then
    printf '%s\n' 'Check out the matching release tag with a clean worktree before building.' >&2
    exit 1
fi

if [[ -z "$output" ]]; then
    output="build/linux-release-$release_tag-$(date +%Y%m%d-%H%M%S)-$$"
fi

output_root="$(realpath -m -- "$output")"

if [[ "$(realpath -m -- "$project_root/build")" != "$project_root/build" || "$output_root" != "$project_root/build/"* ]]; then
    printf '%s\n' 'The output directory must remain inside the project build/ directory.' >&2
    exit 2
fi

if [[ -e "$output_root" || -L "$output_root" ]]; then
    printf 'The output directory already exists: %s\n' "$output_root" >&2
    exit 1
fi

mkdir -p -- "$project_root/build/tmp"
export TMPDIR="$project_root/build/tmp" TEMP="$project_root/build/tmp" TMP="$project_root/build/tmp"

if ! docker buildx version > /dev/null 2>&1; then
    export DOCKER_BUILDKIT=0
fi

docker build -f scripts/linux/Dockerfile -t poe-log-report-builder:3.14.4 .

export POE_BUILD_IMAGE="$(docker image inspect poe-log-report-builder:3.14.4 --format '{{.Id}}')"
export RELEASE_TAG="$release_tag" RELEASE_SHA="$release_sha"
export BUILD_OUTPUT="${output_root#"$project_root/"}"

docker run --rm --init --memory=7g --memory-swap=7g --cpus=2 --network=none \
    --user "$(id -u):$(id -g)" -v "$project_root:/workspace:ro" -v "$project_root/build:/workspace/build" \
    -e RELEASE_TAG -e RELEASE_SHA -e POE_BUILD_IMAGE -e BUILD_OUTPUT \
    -e TMPDIR=/workspace/build/tmp -e TEMP=/workspace/build/tmp -e TMP=/workspace/build/tmp \
    "$POE_BUILD_IMAGE" sh -eu -c '
        python -B scripts/build_desktop.py --output "$BUILD_OUTPUT/native" --jobs 2 \
            --release-tag "$RELEASE_TAG" --collect-native-licenses
        xvfb-run -a python -B scripts/package_release.py \
            --distribution "$BUILD_OUTPUT/native/poe_desktop.dist" --output "$BUILD_OUTPUT/release" \
            --tag "$RELEASE_TAG" --commit "$RELEASE_SHA" --verify
        cp "$BUILD_OUTPUT/release/verification/verification.json" "$BUILD_OUTPUT/release/verification-Linux.json"
    '

printf 'Release files and verification evidence: %s/release\n' "$output_root"

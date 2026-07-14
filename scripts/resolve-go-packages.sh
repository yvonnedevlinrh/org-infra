#!/usr/bin/env bash
# Resolve Go packages for analysis, with auto-discovery for multi-module repos
#
# Requirements:
#   - bash 4.0+
#   - go (any version with module support)
#   - Standard POSIX utilities (find, sed, xargs)
#
# Usage: resolve-go-packages.sh [INPUT_PACKAGES]
#   INPUT_PACKAGES: Package pattern from workflow input (default: ./...)
#
# Outputs:
#   stdout: Space-separated package patterns (consumed by callers)
#   stderr: Diagnostic messages and GitHub Actions annotations (::notice::, ::error::)
# Exits: 0 on success, 1 if no packages found
#
# Exit on error, undefined variables, and pipe failures
set -euo pipefail

INPUT_PKGS="${1:-./...}"

# If using default ./..., check if it actually works
if [[ "$INPUT_PKGS" = "./..." ]]; then
	# Test if ./... resolves to any packages
	if ! go list ./... >/dev/null 2>&1; then
		echo "::notice::Default './...' pattern did not resolve packages. Auto-discovering Go modules..." >&2
		echo "Searching for go.mod files..." >&2

		# Find all go.mod files and construct package patterns.
		# Count lines before paste collapses them — wc -w is inaccurate for paths with spaces.
		# Note: find does not follow symlinks by default for -type predicates
		DISCOVERED=$(find . -name go.mod -type f -not -path '*/vendor/*' -not -path '*/.*/*' -print0 |
			xargs -0 -I{} dirname {} |
			sed 's|^\./||' |
			sed 's|^$|.|' |
			sed 's|$|/...|' |
			sort)

		if [[ -z "$DISCOVERED" ]]; then
			echo "::error::No Go modules found in repository. Cannot analyze." >&2
			# shellcheck disable=SC2312 # pwd is a shell builtin used for diagnostic output only
			echo "Searched in: $(pwd)" >&2
			exit 1
		fi

		# Count newline-separated entries before collapsing to a single line
		MODULE_COUNT=$(echo "$DISCOVERED" | grep -c .)
		echo "Found $MODULE_COUNT module(s)" >&2

		DISCOVERED=$(echo "$DISCOVERED" | tr '\n' ' ' | sed 's/ $//')
		echo "$DISCOVERED"
		echo "Auto-discovered packages: $DISCOVERED" >&2
		echo "::notice::Analyzing all discovered modules. To analyze specific modules, set the 'packages' workflow input." >&2
	else
		# ./... works, use it
		echo "$INPUT_PKGS"
		echo "Using default packages: $INPUT_PKGS" >&2
	fi
else
	# Use explicitly configured packages as-is
	echo "$INPUT_PKGS"
	echo "Using configured packages: $INPUT_PKGS" >&2
fi
